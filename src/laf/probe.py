"""Recall probe (prereg section 8): one closed-book question per scored sequence except Panama,
k = 3 per Claude model; scored deterministically against today's catalog."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from string import Template

import pandas as pd

from laf.catalog import haversine_km
from laf.prompts import PROMPT_DIR, schema
from laf.providers import MODELS, anthropic_params, call_anthropic
from laf.runner import check_budget

DAY_MS = 86_400_000
K = 3
EXCLUDED = ("us6000u18k",)  # Panama: too recent for a 30-day answer
SYSTEM = "Return only the JSON object that the response schema describes."
MAG_TOL = 0.2
BATH_DELTA = 1.2


def render_probe(seq: dict) -> str:
    return Template((PROMPT_DIR / "probe_recall.txt").read_text(encoding="utf-8")).substitute(
        mag=f"{seq['mag']:.1f}",
        origin_date=datetime.fromtimestamp(seq["origin_ms"] / 1000, UTC).strftime("%Y-%m-%d"),
        place=seq["place"],
        radius_km=f"{seq['region_radius_km']:.0f}",
    )


def truth(seq: dict, catalog: pd.DataFrame) -> dict:
    """Largest aftershock and N(M>=5) within the stated radius of the epicentre, first 30 days."""
    c = catalog[catalog["sequence_id"] == seq["sequence_id"]]
    d = haversine_km(seq["lat"], seq["lon"], c["latitude"], c["longitude"])
    t0 = seq["origin_ms"]
    a = c[(c["time_ms"] > t0) & (c["time_ms"] < t0 + 30 * DAY_MS) & (d <= seq["region_radius_km"])]
    a = a[a["id"] != seq["sequence_id"]]
    return {
        "largest": float(a["mag"].max()) if len(a) else None,
        "n_m5": int((a["mag"] >= 5.0 - 1e-6).sum()),
    }


def correct_largest(answer: float | None, true: float | None) -> bool:
    return answer is not None and true is not None and abs(answer - true) <= MAG_TOL + 1e-9


def correct_count(answer: int | None, true: int) -> bool:
    """Within a factor of 2: true/2 <= answer <= 2 * true (so only 0 matches a true 0)."""
    return answer is not None and true / 2 <= answer <= 2 * true


def baseline(seq: dict, generic_median_30d: int) -> dict:
    """Bath's law for the largest aftershock; the generic-RJ median 30-day M>=5 count."""
    return {"largest": seq["mag"] - BATH_DELTA, "n_m5": generic_median_30d}


def run_probe(client, sequences: pd.DataFrame, out: Path, estimate_usd: float = 1.0) -> int:
    check_budget(estimate_usd)
    out.mkdir(parents=True, exist_ok=False)  # before any paid call
    seqs = [
        s
        for s in sequences.to_dict("records")
        if s["role"] != "dev" and s["sequence_id"] not in EXCLUDED
    ]
    jobs = []
    for s in seqs:
        user = render_probe(s)
        for model in MODELS:
            params = anthropic_params(
                model, SYSTEM, user, schema("probe"), effort="high", max_tokens=16_000
            )
            jobs += [(s["sequence_id"], k, params) for k in range(K)]

    def call(job):
        sid, k, params = job
        return {"kind": "probe", "sequence_id": sid, "sample": k, **call_anthropic(client, params)}

    with ThreadPoolExecutor(6) as pool:
        recs = sorted(
            pool.map(call, jobs),
            key=lambda r: (r["sequence_id"], r["model_requested"], r["sample"]),
        )
    (out / "calls.jsonl").write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in recs), encoding="utf-8", newline="\n"
    )
    return len(recs)


def score_probe(
    calls: list[dict],
    sequences: pd.DataFrame,
    catalog: pd.DataFrame,
    generic_median_30d: dict[str, int],
) -> pd.DataFrame:
    """One row per answer: knows_event, correctness of both answers and of the baselines."""
    seqs = {s["sequence_id"]: s for s in sequences.to_dict("records")}
    rows = []
    for r in calls:
        s = seqs[r["sequence_id"]]
        t = truth(s, catalog)
        base = baseline(s, generic_median_30d[r["sequence_id"]])
        try:
            a = json.loads(r.get("text") or "")
        except ValueError:
            a = None
        valid = isinstance(a, dict) and r.get("stop_reason") not in ("refusal", "max_tokens")
        rows.append(
            {
                "sequence_id": r["sequence_id"],
                "name": s["name"],
                "role": s["role"],
                "model": r["model_requested"],
                "sample": r["sample"],
                "valid": valid,
                "knows_event": bool(a.get("knows_event")) if valid and a else False,
                "largest_correct": valid
                and a is not None
                and correct_largest(a.get("largest_aftershock_magnitude"), t["largest"]),
                "count_correct": valid
                and a is not None
                and correct_count(a.get("n_m5_aftershocks_30d"), t["n_m5"]),
                "bath_correct": correct_largest(base["largest"], t["largest"]),
                "generic_count_correct": correct_count(base["n_m5"], t["n_m5"]),
                "true_largest": t["largest"],
                "true_n_m5": t["n_m5"],
            }
        )
    return pd.DataFrame(rows)
