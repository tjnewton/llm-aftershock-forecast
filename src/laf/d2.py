"""D2 prompt-robustness results (docs/proposals/d2-prompt-robustness.md), development data
only. Unlike `analysis.llm_samples`, which serves the registered requests, this loader
validates v2 answers with their M3 quantiles (`schemas.TARGETS_V2`)."""

import json
from pathlib import Path

from laf.prompts import V2
from laf.schemas import QKEYS, TARGETS, TARGETS_V2, WINDOWS, validate


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").split("\n") if x.strip()]


def samples(run_dirs: list[Path]) -> list[dict]:
    """One record per sample and window: request metadata, status, warnings and, for valid
    answers, the quantile lists of every target the prompt asked for."""
    out = []
    for d in run_dirs:
        meta = {r["custom_id"]: r for r in _jsonl(d / "requests.jsonl")}
        for res in _jsonl(d / "results.jsonl"):
            m = meta[res["custom_id"]]
            targets = TARGETS_V2 if m["paraphrase"] in V2 else TARGETS
            if res["result"] != "succeeded":
                status, parsed, warn = "transport_error", None, []
            else:
                status, parsed, warn = validate(
                    m["arm"], res.get("text"), res.get("stop_reason"), targets
                )
            for w in WINDOWS:
                rec = {**m, "window": w, "status": status, "warnings": ",".join(warn)}
                for t in targets:
                    rec[t] = [parsed[w][t][k] for k in QKEYS] if parsed and status == "ok" else None
                out.append(rec)
    return out
