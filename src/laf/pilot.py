"""Pre-freeze smoke test and dev-item pilot (participant-approved: <= $1 and <= $3).

Only dev items (Aomori, Hubbard Glacier) are sent to models. Test items are only token-counted
(count_tokens returns no model output). Records go to runs/<name>/calls.jsonl.
"""

import json
import statistics
from collections import Counter
from pathlib import Path

import pandas as pd

from laf.items import Item, build_items
from laf.prompts import Arm, Info, render, schema
from laf.providers import MODELS, anthropic_params, call_anthropic, client, cost_usd
from laf.runner import check_budget

PILOT_ITEMS = ("us6000rtdt@28d", "us6000sri7@28d")  # largest dev catalogs (90, 95 rows)
SMOKE_SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}, "word": {"type": "string"}},
    "required": ["ok", "word"],
    "additionalProperties": False,
}


def _append(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")


def load_items(data_dir: Path, snapshot: str, floor: float = 4.0) -> list[Item]:
    tables = {
        p.stem: pd.read_parquet(p) for p in (data_dir / "processed" / snapshot).glob("*.parquet")
    }
    return build_items(tables, floor)


def smoke(out: Path, budget_usd: float = 1.0) -> float:
    """One tiny structured-output call per model at effort high, plus a count_tokens check."""
    check_budget(budget_usd)
    c, spent = client(), 0.0
    for model in MODELS:
        params = anthropic_params(
            model,
            "Reply with the requested JSON only.",
            "Set ok to true and word to 'seismology'.",
            SMOKE_SCHEMA,
            effort="high",
            max_tokens=2000,
        )
        rec = call_anthropic(c, params)
        spent += cost_usd(model, rec.get("usage") or {})
        n = c.messages.count_tokens(
            model=model, system=params["system"], messages=params["messages"]
        ).input_tokens
        _append(out / "calls.jsonl", {"kind": "smoke", "count_tokens": n, **rec})
        print(
            f"{model}: reported={rec.get('model_reported')} stop={rec.get('stop_reason')} "
            f"text={rec.get('text')!r} error={rec.get('error')} spent=${spent:.4f}"
        )
        if spent > budget_usd:
            raise SystemExit(f"smoke budget ${budget_usd} exceeded")
    return spent


def pilot(out: Path, items: list[Item], budget_usd: float = 3.0, k: int = 2) -> float:
    """Dev items x arms x models x k at effort high (p1, I1); stops at the budget."""
    by_id = {i.item_id: i for i in items}
    check_budget(budget_usd)
    c, spent = client(), 0.0
    for model in MODELS:
        for item_id in PILOT_ITEMS:
            item = by_id[item_id]
            assert item.role == "dev", item_id
            for arm in ("direct", "params"):
                system, user = render(item, arm, "I1", "p1")
                params = anthropic_params(
                    model, system, user, schema(arm), effort="high", max_tokens=16000
                )
                for s in range(k):
                    rec = call_anthropic(c, params)
                    usd = cost_usd(model, rec.get("usage") or {})
                    spent += usd
                    _append(
                        out / "calls.jsonl",
                        {
                            "kind": "pilot",
                            "item_id": item_id,
                            "arm": arm,
                            "sample": s,
                            "cost_usd": usd,
                            **rec,
                        },
                    )
                    print(
                        f"{model} {item_id} {arm} #{s}: stop={rec.get('stop_reason')} "
                        f"out={(rec.get('usage') or {}).get('output_tokens')} ${spent:.3f}"
                    )
                    if spent > budget_usd:
                        raise SystemExit(f"pilot budget ${budget_usd} reached; stopping")
    return spent


def count_inputs(out: Path, items: list[Item]) -> None:
    """count_tokens for every item's rendered prompt (no generation, free)."""
    c = client()
    for item in items:
        combos: tuple[tuple[Arm, Info], ...] = (
            ("direct", "I1"),
            ("params", "I1"),
            ("direct", "I0"),
        )
        for arm, info in combos:
            system, user = render(item, arm, info, "p1")
            n = c.messages.count_tokens(
                model="claude-opus-5-5",
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={"format": {"type": "json_schema", "schema": schema(arm)}},
            ).input_tokens
            _append(
                out / "input_tokens.jsonl",
                {"item_id": item.item_id, "arm": arm, "info": info, "input_tokens": n},
            )
    rows = [
        json.loads(line)
        for line in (out / "input_tokens.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    xs = [r["input_tokens"] for r in rows if r["info"] == "I1"]
    print(f"I1 input tokens: median {statistics.median(xs)}, max {max(xs)}, n {len(xs)}")


# Calls per Claude model in the full T2 design (docs/PLAN.md 4.2): batched blocks, unbatched blocks.
BATCHED = {"core": 980, "i0": 220}
UNBATCHED = {"probe": 24, "live": 20}
SONNET_LOW = 110


def summarize(out: Path, items: list[Item]) -> dict:
    """Pilot statuses and output tokens per model, and the projected T2 cost (prereg sec. 9)."""
    from laf.providers import PRICES

    calls = [
        json.loads(line) for line in (out / "calls.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    inputs = [
        json.loads(line)
        for line in (out / "input_tokens.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    scored = {i.item_id for i in items if i.role != "dev"}
    i1 = [r["input_tokens"] for r in inputs if r["info"] == "I1" and r["item_id"] in scored]
    i0 = [r["input_tokens"] for r in inputs if r["info"] == "I0" and r["item_id"] in scored]
    mean_in = {"core": statistics.mean(i1), "i0": statistics.mean(i0), "probe": 300, "live": 3000}
    report: dict = {"mean_input_tokens_I1": round(mean_in["core"]), "max_input_tokens_I1": max(i1)}
    total = 0.0
    for model in MODELS:
        recs = [r for r in calls if r.get("model_requested") == model and r.get("kind") == "pilot"]
        outs = [r["usage"]["output_tokens"] for r in recs if r.get("usage")]
        parsed = 0
        for r in recs:
            try:
                json.loads(r.get("text") or "")
                parsed += 1
            except ValueError:
                pass
        mean_out = statistics.mean(outs) * 1.25 if outs else 0.0  # prereg: pilot mean x 1.25
        pin, pout = PRICES[model][:2]
        cost = sum(n * (mean_in[b] * pin + mean_out * pout) / 2e6 for b, n in BATCHED.items())
        cost += sum(n * (mean_in[b] * pin + mean_out * pout) / 1e6 for b, n in UNBATCHED.items())
        if model == "claude-sonnet-5-5":
            cost += (
                SONNET_LOW * (mean_in["core"] * pin + mean_out * pout) / 2e6
            )  # low effort: upper bound
        total += cost
        report[model] = {
            "calls": len(recs),
            "json_parsed": parsed,
            "stop_reasons": dict(Counter(r.get("stop_reason") for r in recs)),
            "mean_output_tokens": round(statistics.mean(outs)) if outs else None,
            "max_output_tokens": max(outs) if outs else None,
            "projected_t2_usd": round(cost, 2),
        }
    report["projected_t2_total_usd"] = round(total, 2)
    return report
