"""Expand the registered design into Claude requests; submit and track Message Batches.

Blocks follow docs/PLAN.md 4.2 (prereg sections 3 and 9). Batch results are collected only
after the scoring code is tagged `scoring-v1` (prereg section 12).
"""

import contextlib
import hashlib
import json
import math
import statistics
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from laf.items import Item
from laf.prompts import PROMPT_DIR, render, schema_for
from laf.providers import API_BASE_URL, PRICES, anthropic_params, cost_usd, env_value, study_effort

RUNS = Path("runs")
MAX_TOKENS_BATCH = 32_000
CAP_VAR = "LAF_CLAUDE_MONTHLY_CAP_USD"  # per calendar month (UTC); value kept out of the repo
SCORED_ROLES = ("test-post", "test-pre", "ambiguous")
BLOCKS: dict[str, dict] = {
    "core": {
        "roles": SCORED_ROLES,
        "arms": ("direct", "params"),
        "infos": ("I1",),
        "paras": ("p1", "p2"),
        "k": 5,
        "effort": "high",
    },
    "i0": {
        "roles": ("test-post",),
        "arms": ("direct", "params"),
        "infos": ("I0",),
        "paras": ("p1",),
        "k": 5,
        "effort": "high",
    },
    "sonnet-low": {
        "roles": ("test-post",),
        "arms": ("direct",),
        "infos": ("I1",),
        "paras": ("p1",),
        "k": 5,
        "effort": "low",
    },
    # E3 extended exploratory set (ADR 0012), run on the E3 snapshot into runs/e3/
    "e3": {
        "roles": ("test-post",),
        "arms": ("direct",),
        "infos": ("I1",),
        "paras": ("p1",),
        "k": 5,
        "effort": "high",
    },
    "e3pre": {
        "roles": ("test-pre",),
        "arms": ("direct",),
        "infos": ("I1",),
        "paras": ("p1",),
        "k": 3,
        "effort": "high",
    },
    "e3i0": {
        "roles": ("test-post",),
        "arms": ("direct",),
        "infos": ("I0",),
        "paras": ("p1",),
        "k": 3,
        "effort": "high",
    },
    # D2 prompt robustness (docs/proposals/d2-prompt-robustness.md), development items only:
    # v2 prompts ask for M3 quantiles and show the catalog from M3.0 (items built at floor 3)
    "d2": {
        "roles": ("test-post",),
        "arms": ("direct",),
        "infos": ("I1",),
        "paras": ("v2A", "v2B", "v2C"),
        "k": 3,
        "effort": "high",
        "floor": 3.0,
    },
    "d2-medium": {
        "roles": ("test-post",),
        "arms": ("direct",),
        "infos": ("I1",),
        "paras": ("v2A",),
        "k": 3,
        "effort": "medium",
        "floor": 3.0,
    },
    # D2 for the confirmatory 4.6 models at their study settings (ADR 0014 decision 5)
    "d2-46": {
        "roles": ("test-post",),
        "arms": ("direct",),
        "infos": ("I1",),
        "paras": ("v2A",),
        "k": 3,
        "effort": "study",
        "floor": 3.0,
    },
}
CHARS_PER_TOKEN = 1.25  # below the pilot prompts' minimum (1.28; median 1.36): overestimates


def _jsonl(path: Path) -> list[dict]:
    # "\n" only: str.splitlines also breaks on U+0085/U+2028/U+2029, which json.dumps with
    # ensure_ascii=False leaves raw inside strings (model text)
    return [json.loads(x) for x in path.read_text(encoding="utf-8").split("\n") if x.strip()]


def request_id(params: dict, sample: int) -> str:
    """Batch custom_id: SHA-256 of the canonical request plus the sample index."""
    blob = json.dumps({"params": params, "sample": sample}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def expand(items: list[Item], block: str, model: str) -> list[dict]:
    spec = BLOCKS[block]
    effort = study_effort(model) if spec["effort"] == "study" else spec["effort"]
    reqs = []
    for item in items:
        if item.role not in spec["roles"]:
            continue
        for arm in spec["arms"]:
            for info in spec["infos"]:
                for para in spec["paras"]:
                    system, user = render(item, arm, info, para)
                    params = anthropic_params(
                        model,
                        system,
                        user,
                        schema_for(arm, para),
                        effort=effort,
                        max_tokens=MAX_TOKENS_BATCH,
                    )
                    for s in range(spec["k"]):
                        meta = {
                            "item_id": item.item_id,
                            "arm": arm,
                            "info": info,
                            "paraphrase": para,
                            "sample": s,
                            "block": block,
                            "model": model,
                            "effort": effort,
                        }
                        reqs.append(
                            {"custom_id": request_id(params, s), "meta": meta, "params": params}
                        )
    return reqs


def estimate_usd(reqs: list[dict], pilot: Path = RUNS / "pilot") -> float:
    """Batch cost from the pilot's count_tokens inputs and mean outputs x 1.25 (prereg sec. 9).
    Models the registered pilot never called (the 4.6 models) take their mean output from
    their D1 batch at the same study settings."""
    tokens = {
        (r["item_id"], r["arm"], r["info"]): r["input_tokens"]
        for r in _jsonl(pilot / "input_tokens.jsonl")
    }
    calls = [r for r in _jsonl(pilot / "calls.jsonl") if r.get("usage")]
    mean_out = {
        m: 1.25 * statistics.mean(r["usage"]["output_tokens"] for r in rs)
        for m in {r["model_requested"] for r in calls}
        if (rs := [r for r in calls if r["model_requested"] == m])
    }
    for m in {r["meta"]["model"] for r in reqs} - set(mean_out):
        d1 = [
            x["usage"]["output_tokens"] for x in _jsonl(RUNS / "d1" / f"d1-{m}" / "results.jsonl")
        ]
        mean_out[m] = 1.25 * statistics.mean(d1)
    total = 0.0
    for r in reqs:
        m = r["meta"]
        n_in = tokens.get((m["item_id"], m["arm"], m["info"]))
        if n_in is None:  # params x I0 was not counted; the direct prompt is the same size
            n_in = tokens.get((m["item_id"], "direct", m["info"]))
        if n_in is None:  # items the pilot never counted (E3): from the request's length
            n_in = len(json.dumps(r["params"], ensure_ascii=False)) / CHARS_PER_TOKEN
        usage = {"input_tokens": n_in, "output_tokens": mean_out[m["model"]]}
        total += cost_usd(m["model"], usage, batch=True)
    return total


def spend_records(runs: Path = RUNS) -> list[tuple[str, float]]:
    """(UTC month "YYYY-MM", USD) for every recorded spend in every run folder (nested too):
    synchronous calls by `started_utc`; collected batch results (half price) and estimates of
    submitted, uncollected batches by the batch's `created_at`."""
    out = []
    for path in runs.glob("**/batch.json"):
        rec = json.loads(path.read_text(encoding="utf-8"))
        if rec.get("provider") == "openai":  # tracked by laf.openai_runner, not this cap
            continue
        if not (path.parent / "results.jsonl").exists():
            out.append((rec["created_at"][:7], rec.get("estimate_usd", 0.0)))
    for path in runs.glob("**/calls.jsonl"):
        out += [
            (r["started_utc"][:7], cost_usd(r["model_requested"], r["usage"]))
            for r in _jsonl(path)
            if r.get("usage") and r.get("model_requested") in PRICES
        ]
    for path in runs.glob("**/results.jsonl"):
        rows = [r for r in _jsonl(path) if r.get("usage") and r.get("model") in PRICES]
        if not rows:  # local models are free
            continue
        batch = path.parent / "batch.json"
        if not batch.exists():
            raise SystemExit(f"{path}: priced results without batch.json, cannot date the spend")
        month = json.loads(batch.read_text(encoding="utf-8"))["created_at"][:7]
        out += [(month, cost_usd(r["model"], r["usage"], batch=True)) for r in rows]
    return out


def spent_usd(runs: Path = RUNS) -> float:
    return sum(usd for _, usd in spend_records(runs))


def month_spend_usd(month: str, runs: Path = RUNS) -> float:
    return sum(usd for m, usd in spend_records(runs) if m == month)


def check_budget(
    estimate_usd: float, runs: Path = RUNS, cap_var: str = CAP_VAR, month_spend=None
) -> float:
    """Refuse a paid run unless this UTC month's spend plus `estimate_usd` stays within the cap
    in `cap_var` (environment or .env; LAF_CLAUDE_MONTHLY_CAP_USD for Claude). Returns the
    month's spend so far.
    A check, not a reservation: two paid runs started at once could both pass. Runs start one
    at a time by hand; a lock file is needed once the live workflow runs beside them."""
    raw = env_value(cap_var)
    if not raw:
        raise SystemExit(f"{cap_var} not set (environment or .env): refusing to spend")
    try:
        cap = float(raw)
    except ValueError:
        raise SystemExit(f"{cap_var} is not a number: refusing to spend") from None
    if not (math.isfinite(cap) and cap >= 0 and math.isfinite(estimate_usd) and estimate_usd >= 0):
        raise SystemExit(
            f"spend guard: cap {raw!r} and estimate {estimate_usd} must be finite, >= 0"
        )
    month = datetime.now(UTC).strftime("%Y-%m")
    spent = (month_spend or month_spend_usd)(month, runs)
    if spent + estimate_usd > cap:
        raise SystemExit(
            f"spend guard: ${spent:.2f} spent in {month} + ${estimate_usd:.2f} > monthly cap"
        )
    return spent


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def submit(
    client,
    name: str,
    reqs: list[dict],
    snapshot: str,
    *,
    estimate: float,
    items_file: str = "items.jsonl",
    prompt_set: str = "",
) -> str:
    """Write the request ledger, submit one batch, record its id. Never resubmits a run."""
    out = RUNS / name
    if (out / "batch.json").exists():
        raise SystemExit(f"{out}/batch.json exists: run already submitted")
    spent = check_budget(estimate)
    # provenance first: nothing is sent unless every file it records exists
    provenance = {
        "prompt_hashes_sha256": _sha256(PROMPT_DIR / prompt_set / "HASHES.json"),
        "items_file": items_file,
        "items_sha256": _sha256(Path("data/processed") / snapshot / items_file),
    }
    ledger = []
    for r in reqs:
        canonical = json.dumps(r["params"], sort_keys=True, ensure_ascii=False).encode("utf-8")
        row = {"custom_id": r["custom_id"], **r["meta"]}
        row["params_sha256"] = hashlib.sha256(canonical).hexdigest()
        ledger.append(json.dumps(row, sort_keys=True) + "\n")
    # staged before anything is sent, so a local error cannot follow a paid batch
    out.mkdir(parents=True, exist_ok=True)
    ledger_path = out / "requests.jsonl"
    ledger_path.write_text("".join(ledger), encoding="utf-8", newline="\n")
    try:
        batch = client.messages.batches.create(
            requests=[{"custom_id": r["custom_id"], "params": r["params"]} for r in reqs]
        )
    except Exception:  # refused: no batch exists, so remove what was staged for it
        ledger_path.unlink(missing_ok=True)
        with contextlib.suppress(OSError):
            out.rmdir()  # only if empty
        raise
    record = {
        "batch_id": batch.id,
        "created_at": str(batch.created_at),
        "n_requests": len(reqs),
        "estimate_usd": round(estimate, 2),
        "spent_before_usd": round(spent_usd(), 2),
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


def status(client, name: str) -> dict:
    """Processing status and request counts only: no result content (prereg section 12)."""
    rec = json.loads((RUNS / name / "batch.json").read_text(encoding="utf-8"))
    b = client.messages.batches.retrieve(rec["batch_id"])
    return {
        "batch_id": b.id,
        "processing_status": b.processing_status,
        "request_counts": b.request_counts.model_dump(),
        "ended_at": str(b.ended_at),
    }


def scoring_frozen() -> bool:
    return bool(_git("tag", "--list", "scoring-v1"))


def collect(client, name: str) -> int:
    """Write runs/<name>/results.jsonl, only once `scoring-v1` exists."""
    if not scoring_frozen():
        raise SystemExit("refusing to collect: tag scoring-v1 does not exist (prereg section 12)")
    out = RUNS / name
    if (out / "results.jsonl").exists():
        raise SystemExit(f"{out}/results.jsonl exists")
    rec = json.loads((out / "batch.json").read_text(encoding="utf-8"))
    model = {r["custom_id"]: r["model"] for r in _jsonl(out / "requests.jsonl")}
    rows = []
    for r in client.messages.batches.results(rec["batch_id"]):
        row: dict = {"custom_id": r.custom_id, "result": r.result.type, "model": model[r.custom_id]}
        if r.result.type == "succeeded":
            m = r.result.message
            row |= {
                "id": m.id,
                "model_reported": m.model,
                "stop_reason": m.stop_reason,
                "stop_details": m.stop_details.model_dump() if m.stop_details else None,
                "usage": m.usage.model_dump(),
                "text": next((b.text for b in m.content if b.type == "text"), None),
            }
        elif r.result.type == "errored":
            row["error"] = r.result.error.model_dump()
        rows.append(row)
    (out / "results.jsonl").write_text(
        "".join(json.dumps(x, sort_keys=True) + "\n" for x in rows),
        encoding="utf-8",
        newline="\n",
    )
    return len(rows)
