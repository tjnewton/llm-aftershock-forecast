"""Expand the registered design into Claude requests; submit and track Message Batches.

Blocks follow docs/PLAN.md 4.2 (prereg sections 3 and 9). Batch results are collected only
after the scoring code is tagged `scoring-v1` (prereg section 12).
"""

import hashlib
import json
import statistics
import subprocess
from pathlib import Path

from laf.items import Item
from laf.prompts import PROMPT_DIR, render, schema
from laf.providers import API_BASE_URL, anthropic_params, cost_usd

RUNS = Path("runs")
MAX_TOKENS_BATCH = 32_000
SPEND_CAP_USD = 140.0  # harness guard below the $150 workspace limit (PLAN section 9)
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
}


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def request_id(params: dict, sample: int) -> str:
    """Batch custom_id: SHA-256 of the canonical request plus the sample index."""
    blob = json.dumps({"params": params, "sample": sample}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def expand(items: list[Item], block: str, model: str) -> list[dict]:
    spec = BLOCKS[block]
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
                        schema(arm),
                        effort=spec["effort"],
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
                            "effort": spec["effort"],
                        }
                        reqs.append(
                            {"custom_id": request_id(params, s), "meta": meta, "params": params}
                        )
    return reqs


def estimate_usd(reqs: list[dict], pilot: Path = RUNS / "pilot") -> float:
    """Batch cost from the pilot's count_tokens inputs and mean outputs x 1.25 (prereg sec. 9)."""
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
    total = 0.0
    for r in reqs:
        m = r["meta"]
        n_in = tokens.get((m["item_id"], m["arm"], m["info"]))
        if n_in is None:  # params x I0 was not counted; the direct prompt is the same size
            n_in = tokens[(m["item_id"], "direct", m["info"])]
        usage = {"input_tokens": n_in, "output_tokens": mean_out[m["model"]]}
        total += cost_usd(m["model"], usage, batch=True)
    return total


def spent_usd(runs: Path = RUNS) -> float:
    """Recorded spend: synchronous calls, collected batch results (half price) and the
    estimates of submitted batches not yet collected."""
    total = 0.0
    for path in runs.glob("*/batch.json"):
        if not (path.parent / "results.jsonl").exists():
            total += json.loads(path.read_text(encoding="utf-8")).get("estimate_usd", 0.0)
    for path in runs.glob("*/calls.jsonl"):
        total += sum(
            cost_usd(r["model_requested"], r["usage"]) for r in _jsonl(path) if r.get("usage")
        )
    for path in runs.glob("*/results.jsonl"):
        total += sum(
            cost_usd(r["model"], r["usage"], batch=True) for r in _jsonl(path) if r.get("usage")
        )
    return total


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def submit(client, name: str, reqs: list[dict], snapshot: str, *, estimate: float) -> str:
    """Write the request ledger, submit one batch, record its id. Never resubmits a run."""
    out = RUNS / name
    if (out / "batch.json").exists():
        raise SystemExit(f"{out}/batch.json exists: run already submitted")
    spent = spent_usd()
    if spent + estimate > SPEND_CAP_USD:
        raise SystemExit(f"spend guard: ${spent:.2f} spent + ${estimate:.2f} > ${SPEND_CAP_USD}")
    out.mkdir(parents=True, exist_ok=True)
    ledger = []
    for r in reqs:
        canonical = json.dumps(r["params"], sort_keys=True, ensure_ascii=False).encode("utf-8")
        row = {"custom_id": r["custom_id"], **r["meta"]}
        row["params_sha256"] = hashlib.sha256(canonical).hexdigest()
        ledger.append(json.dumps(row, sort_keys=True) + "\n")
    (out / "requests.jsonl").write_text("".join(ledger), encoding="utf-8", newline="\n")
    batch = client.messages.batches.create(
        requests=[{"custom_id": r["custom_id"], "params": r["params"]} for r in reqs]
    )
    record = {
        "batch_id": batch.id,
        "created_at": str(batch.created_at),
        "n_requests": len(reqs),
        "estimate_usd": round(estimate, 2),
        "spent_before_usd": round(spent, 2),
        "snapshot": snapshot,
        "git_sha": _git("rev-parse", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain", "--untracked-files=no")),
        "prompt_hashes_sha256": _sha256(PROMPT_DIR / "HASHES.json"),
        "items_sha256": _sha256(Path("data/processed") / snapshot / "items.jsonl"),
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
