"""OpenAI models (ADR 0014) through the official `openai` SDK: the request shape, a synchronous
the Batch API (submit, status, collect). Spend is tracked separately from Claude,
with its own monthly cap (LAF_OPENAI_MONTHLY_CAP_USD).

Scored-call settings mirror the Claude ones: explicit reasoning effort (gpt-5.1 defaults to
none) and a strict JSON schema; no sampling parameters, no tools, no prefill, no user or
safety identifiers; `store` off. The client pins https://api.openai.com/v1, whatever
OPENAI_BASE_URL says, and the SDK's own retries are disabled.
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from laf.items import Item
from laf.prompts import PROMPT_DIR, render, schema_for
from laf.providers import env_value
from laf.runner import (
    CHARS_PER_TOKEN,
    RUNS,
    _git,
    _jsonl,
    _sha256,
    check_budget,
    request_id,
    scoring_frozen,
)

API_BASE_URL = "https://api.openai.com/v1"
CAP_VAR = "LAF_OPENAI_MONTHLY_CAP_USD"
# USD per MTok, input and output (developers.openai.com model page, checked 2026-10-30); the
# Batch API halves both. Cached input is billed here at the full input price (an overestimate).
PRICES = {"gpt-5.1-2025-11-13": (1.25, 10.00)}
MAX_OUTPUT_TOKENS = 32_000
ENDPOINT = "/v1/responses"


def client():
    import openai

    key = env_value("OPENAI_API_KEY")
    if not key:
        raise SystemExit("OPENAI_API_KEY not set (environment or .env)")
    return openai.OpenAI(api_key=key, base_url=API_BASE_URL, max_retries=0)


def openai_params(
    model: str, system: str, user: str, schema: dict, *, effort: str, max_output_tokens: int
) -> dict:
    return {
        "model": model,
        "instructions": system,
        "input": [{"role": "user", "content": user}],
        "reasoning": {"effort": effort},
        "text": {
            "format": {"type": "json_schema", "name": "forecast", "schema": schema, "strict": True}
        },
        "max_output_tokens": max_output_tokens,
        "store": False,
    }


def cost_usd(model: str, usage: dict, *, batch: bool = False) -> float:
    pin, pout = PRICES[model]
    total = (usage.get("input_tokens", 0) * pin + usage.get("output_tokens", 0) * pout) / 1e6
    return total / 2 if batch else total


def stop_reason(body: dict) -> str | None:
    """A Responses API body mapped to the stop reasons `laf.schemas.validate` knows."""
    reason = (body.get("incomplete_details") or {}).get("reason")
    if reason == "max_output_tokens":
        return "max_tokens"
    if reason == "content_filter" or any(
        c.get("type") == "refusal"
        for o in body.get("output", [])
        if o.get("type") == "message"
        for c in o.get("content", [])
    ):
        return "refusal"
    return body.get("status")


def output_text(body: dict) -> str | None:
    texts = [
        c["text"]
        for o in body.get("output", [])
        if o.get("type") == "message"
        for c in o.get("content", [])
        if c.get("type") == "output_text"
    ]
    return "".join(texts) if texts else None


def pilot_items(items: list[Item], n: int = 3) -> list[Item]:
    """The earliest test-post item of the `n` sequences with the largest mainshocks."""
    first: dict[str, Item] = {}
    for i in sorted(items, key=lambda i: i.issue_ms):
        if i.role == "test-post":
            first.setdefault(i.sequence_id, i)
    return sorted(first.values(), key=lambda i: -i.mainshock.mag)[:n]


def expand(
    items: list[Item], model: str, effort: str, *, paraphrase: str = "v2A", k: int = 3,
    roles: tuple[str, ...] = ("test-post",), block: str = "d2",
    max_output_tokens: int = MAX_OUTPUT_TOKENS,
) -> list[dict]:  # fmt: skip
    """Direct-arm requests with the catalog (I1), as the Claude D2 blocks."""
    reqs = []
    for item in items:
        if item.role not in roles:
            continue
        system, user = render(item, "direct", "I1", paraphrase)  # type: ignore[arg-type]
        params = openai_params(
            model, system, user, schema_for("direct", paraphrase),  # type: ignore[arg-type]
            effort=effort, max_output_tokens=max_output_tokens,
        )  # fmt: skip
        for s in range(k):
            meta = {"item_id": item.item_id, "arm": "direct", "info": "I1",
                    "paraphrase": paraphrase, "sample": s, "block": block, "model": model,
                    "effort": effort}  # fmt: skip
            reqs.append({"custom_id": request_id(params, s), "meta": meta, "params": params})
    return reqs


def spend_records(runs: Path = RUNS) -> list[tuple[str, float]]:
    """(UTC month, USD) of OpenAI spend: collected batch results (half price) and the
    estimates of submitted, uncollected batches."""
    out = []
    for path in runs.glob("**/batch.json"):
        rec = json.loads(path.read_text(encoding="utf-8"))
        if rec.get("provider") != "openai":
            continue
        month = rec["created_at"][:7]
        res = path.parent / "results.jsonl"
        if not res.exists():
            out.append((month, rec.get("estimate_usd", 0.0)))
            continue
        out += [
            (month, cost_usd(r["model"], r["usage"], batch=True))
            for r in _jsonl(res)
            if r.get("usage")
        ]
    return out


def month_spend_usd(month: str, runs: Path = RUNS) -> float:
    return sum(usd for m, usd in spend_records(runs) if m == month)


def check_openai_budget(estimate_usd: float, runs: Path = RUNS) -> float:
    return check_budget(estimate_usd, runs, cap_var=CAP_VAR, month_spend=month_spend_usd)


def bound_usd(reqs: list[dict]) -> float:
    """Batch cost if every request used its whole output budget."""
    return sum(
        cost_usd(
            r["meta"]["model"],
            {
                "input_tokens": len(json.dumps(r["params"], ensure_ascii=False)) / CHARS_PER_TOKEN,
                "output_tokens": r["params"]["max_output_tokens"],
            },
            batch=True,
        )
        for r in reqs
    )


def estimate_usd(reqs: list[dict], pilot_run: Path) -> float:
    """Batch cost: input from the request length, output 1.25 times the mean of the collected
    pilot batch for the same model and effort."""
    meta = {r["custom_id"]: r for r in _jsonl(pilot_run / "requests.jsonl")}
    outs: dict[tuple[str, str], list[int]] = {}
    for r in _jsonl(pilot_run / "results.jsonl"):
        m = meta[r["custom_id"]]
        if r.get("usage"):
            outs.setdefault((m["model"], m["effort"]), []).append(r["usage"]["output_tokens"])
    total = 0.0
    for r in reqs:
        m = r["meta"]
        out = outs[(m["model"], m["effort"])]
        usage = {
            "input_tokens": len(json.dumps(r["params"], ensure_ascii=False)) / CHARS_PER_TOKEN,
            "output_tokens": 1.25 * sum(out) / len(out),
        }
        total += cost_usd(m["model"], usage, batch=True)
    return total


def _record(body: dict) -> dict:
    return {
        "id": body.get("id"),
        "model_reported": body.get("model"),
        "status": body.get("status"),
        "stop_reason": stop_reason(body),
        "usage": body.get("usage"),
        "text": output_text(body),
    }


def submit(
    c, name: str, reqs: list[dict], snapshot: str, *, estimate: float,
    items_file: str = "items_m3.jsonl", prompt_set: str = "v2",
) -> str:  # fmt: skip
    """Write the request ledger, upload the input file, create one batch, record its id."""
    out = RUNS / name
    if (out / "batch.json").exists():
        raise SystemExit(f"{out}/batch.json exists: run already submitted")
    spent = check_openai_budget(estimate)
    # provenance first: nothing is sent unless every file it records exists
    provenance = {
        "prompt_hashes_sha256": _sha256(PROMPT_DIR / prompt_set / "HASHES.json"),
        "items_file": items_file,
        "items_sha256": _sha256(Path("data/processed") / snapshot / items_file),
    }
    out.mkdir(parents=True, exist_ok=True)
    ledger, lines = [], []
    for r in reqs:
        canonical = json.dumps(r["params"], sort_keys=True, ensure_ascii=False).encode("utf-8")
        row = {"custom_id": r["custom_id"], **r["meta"]}
        row["params_sha256"] = hashlib.sha256(canonical).hexdigest()
        ledger.append(json.dumps(row, sort_keys=True) + "\n")
        line = {"custom_id": r["custom_id"], "method": "POST", "url": ENDPOINT, "body": r["params"]}
        lines.append(json.dumps(line, ensure_ascii=False) + "\n")
    (out / "requests.jsonl").write_text("".join(ledger), encoding="utf-8", newline="\n")
    upload = out / "batch_input.jsonl"  # sent to OpenAI; gitignored by name below
    upload.write_text("".join(lines), encoding="utf-8", newline="\n")
    with upload.open("rb") as f:
        file = c.files.create(file=f, purpose="batch")
    batch = c.batches.create(input_file_id=file.id, endpoint=ENDPOINT, completion_window="24h")
    upload.unlink()  # the ledger and the code rebuild it; it repeats every prompt in full
    record = {
        "provider": "openai",
        "batch_id": batch.id,
        "input_file_id": file.id,
        "created_at": datetime.fromtimestamp(batch.created_at, UTC).isoformat(),
        "n_requests": len(reqs),
        "estimate_usd": round(estimate, 2),
        "spent_month_before_usd": round(spent, 2),
        "snapshot": snapshot,
        "git_sha": _git("rev-parse", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain", "--untracked-files=no")),
        **provenance,
        "base_url": API_BASE_URL,
    }
    (out / "batch.json").write_text(
        json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    return batch.id


def status(c, name: str) -> dict:
    """Status and request counts only: no result content (prereg section 12)."""
    rec = json.loads((RUNS / name / "batch.json").read_text(encoding="utf-8"))
    b = c.batches.retrieve(rec["batch_id"])
    return {"batch_id": b.id, "status": b.status, "request_counts": b.request_counts.model_dump()}


def collect(c, name: str) -> int:
    """Write runs/<name>/results.jsonl in the Claude runner's format (result, model, text,
    stop_reason, usage), only once `scoring-v1` exists and the batch has ended (completed,
    expired or cancelled: an ended batch keeps its finished, billed responses; the rest are
    errors or missing)."""
    if not scoring_frozen():
        raise SystemExit("refusing to collect: tag scoring-v1 does not exist (prereg section 12)")
    out = RUNS / name
    if (out / "results.jsonl").exists():
        raise SystemExit(f"{out}/results.jsonl exists")
    rec = json.loads((out / "batch.json").read_text(encoding="utf-8"))
    b = c.batches.retrieve(rec["batch_id"])
    if b.status not in ("completed", "expired", "cancelled"):  # terminal; partial results kept
        raise SystemExit(f"batch status {b.status}: not collecting yet")
    model = {r["custom_id"]: r["model"] for r in _jsonl(out / "requests.jsonl")}
    lines = []
    for fid in (b.output_file_id, b.error_file_id):
        if fid:
            lines += [json.loads(x) for x in c.files.content(fid).text.split("\n") if x.strip()]
    rows = []
    for x in lines:
        row: dict = {"custom_id": x["custom_id"], "model": model[x["custom_id"]]}
        resp = x.get("response") or {}
        if resp.get("status_code") == 200 and not x.get("error"):
            row |= {"result": "succeeded", **_record(resp["body"])}
        else:
            row |= {"result": "errored", "error": x.get("error") or resp.get("body")}
        rows.append(row)
    missing = set(model) - {r["custom_id"] for r in rows}
    rows += [
        {"custom_id": cid, "model": model[cid], "result": "missing"} for cid in sorted(missing)
    ]
    (out / "results.jsonl").write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8", newline="\n"
    )
    return len(rows)
