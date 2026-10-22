"""Live Panama forecasts (prereg section 10): matched to the newest official version, and
strictly prospective with windows that open after the outputs are hashed."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from laf.catalog import haversine_km
from laf.items import Item, build_items
from laf.oaf import parse_forecast_lenient
from laf.prompts import render, schema
from laf.providers import MODELS, anthropic_params, call_anthropic, cost_usd
from laf.registry import Sequence
from laf.tables import (
    DAY_MS,
    FORESHOCK_LOOKBACK_MS,
    SCORED_WINDOWS,
    build_tables,
    schedule_windows,
)
from laf.usgs import read_raw

HOUR_MS = 3_600_000
K = 5
MAX_TOKENS_SYNC = 16_000
BUDGET_USD = 5.0


def next_full_hour(ms: int) -> int:
    return -(-ms // HOUR_MS) * HOUR_MS


def live_items(data_dir: Path, snapshot: str, seq: Sequence, now_ms: int, strict_ms: int):
    """The matched and strict items, with today's catalog up to each information cutoff."""
    t = build_tables(data_dir, snapshot, [seq])
    s = t["sequences"].iloc[0]
    ov = t["oaf_versions"]
    newest = ov[ov["valid"] & ~ov["duplicate"].astype(bool)].sort_values("info_cutoff_ms").iloc[-1]
    raw = read_raw(data_dir, f"raw/oaf/{seq.id}/{int(newest['update_ms'])}.json")
    f = parse_forecast_lenient(raw)[0]
    issues = {
        f"{seq.id}@live-matched": (
            f.info_cutoff_ms,
            {w.label: (w.timeStart, w.timeEnd) for w in f.forecast if w.label in SCORED_WINDOWS},
        ),
        f"{seq.id}@live-strict": (now_ms, schedule_windows(strict_ms)),
    }
    cat = t["catalog"]
    rows: dict[str, list[dict]] = {"issue_times": [], "observed_counts": [], "issue_catalogs": []}
    for issue_id, (issue_ms, windows) in issues.items():
        rows["issue_times"].append(
            {
                "issue_id": issue_id,
                "sequence_id": seq.id,
                "issue_ms": issue_ms,
                "elapsed_days": (issue_ms - int(s["origin_ms"])) / DAY_MS,
                "mag_main": float(f.model.parameters.get("magMain") or s["mag"]),
                "region_lat": f.region.lat,
                "region_lon": f.region.lon,
                "region_radius_km": f.region.radius_km,
            }
        )
        rows["observed_counts"] += [
            {"issue_id": issue_id, "window": w, "time_start_ms": a, "time_end_ms": b}
            for w, (a, b) in windows.items()
        ]
        inside = haversine_km(f.region.lat, f.region.lon, cat["latitude"], cat["longitude"])
        seen = cat[
            (cat["time_ms"] < issue_ms)
            & (cat["time_ms"] >= int(s["origin_ms"]) - FORESHOCK_LOOKBACK_MS)
            & (inside <= f.region.radius_km)
        ]
        rows["issue_catalogs"] += [{"issue_id": issue_id, **r} for r in seen.to_dict("records")]
    tables = {"sequences": t["sequences"], **{k: pd.DataFrame(v) for k, v in rows.items()}}
    return build_items(tables), int(newest["update_ms"])


def run_live(client, items: list[Item], out: Path) -> tuple[str, float]:
    """60 synchronous calls; writes canonical items.jsonl and calls.jsonl; returns the SHA-256."""
    jobs = []
    for item in items:
        for model in MODELS:
            for arm in ("direct", "params"):
                system, user = render(item, arm, "I1", "p1")
                params = anthropic_params(
                    model, system, user, schema(arm), effort="high", max_tokens=MAX_TOKENS_SYNC
                )
                jobs += [(item.item_id, arm, s, params) for s in range(K)]

    def call(job):
        item_id, arm, s, params = job
        rec = call_anthropic(client, params)
        return {"kind": "live", "item_id": item_id, "arm": arm, "sample": s, **rec}

    with ThreadPoolExecutor(6) as pool:
        recs = list(pool.map(call, jobs))
    recs.sort(key=lambda r: (r["item_id"], r["model_requested"], r["arm"], r["sample"]))
    spent = sum(cost_usd(r["model_requested"], r["usage"]) for r in recs if r.get("usage"))
    out.mkdir(parents=True, exist_ok=False)
    (out / "items.jsonl").write_text(
        "".join(i.model_dump_json() + "\n" for i in items), encoding="utf-8", newline="\n"
    )
    body = "".join(json.dumps(r, sort_keys=True) + "\n" for r in recs)
    (out / "calls.jsonl").write_text(body, encoding="utf-8", newline="\n")
    if spent > BUDGET_USD:
        print(f"WARNING: live spend ${spent:.2f} above ${BUDGET_USD}")
    return hashlib.sha256(body.encode("utf-8")).hexdigest(), spent


def provisional_scores(
    data_dir: Path, snapshot: str, seq: Sequence, run: Path, version_ms: int
) -> pd.DataFrame:
    """Provisional scores for the live windows that closed before `snapshot`: N(M>=5) counted in
    the item's circle from the fresh catalog, the mean log-QS of each model's valid direct
    answers, and, for the matched item, the official version's log-QS on the same window."""
    from laf.catalog import count_in_window
    from laf.cli import snapshot_ms
    from laf.forecast import official_forecast
    from laf.oaf import Circle
    from laf.schemas import validate
    from laf.scoring import quantile_score

    t = build_tables(data_dir, snapshot, [seq])
    end_ms = snapshot_ms(snapshot)
    ov = t["oaf_versions"]
    cutoff = int(ov.loc[ov["update_ms"] == version_ms, "info_cutoff_ms"].iloc[0])
    items = [json.loads(x) for x in (run / "items.jsonl").read_text(encoding="utf-8").splitlines()]
    calls = [json.loads(x) for x in (run / "calls.jsonl").read_text(encoding="utf-8").splitlines()]
    rows = []
    for it in items:
        circle = Circle(it["region"]["lat"], it["region"]["lon"], it["region"]["radius_km"])
        for w in it["windows"]:
            if w["end_ms"] > end_ms:
                continue  # window still open
            y = count_in_window(t["catalog"], circle, w["start_ms"], w["end_ms"], 5.0)
            scores: dict[str, list[float]] = {}
            for c in calls:
                if c["item_id"] != it["item_id"] or c["arm"] != "direct":
                    continue
                status, parsed, _ = validate("direct", c["text"], c["stop_reason"])
                if status == "ok" and parsed:
                    q = parsed[w["key"]]["m5_count_quantiles"]
                    scores.setdefault(c["model_requested"], []).append(
                        quantile_score([q[k] for k in sorted(q)], y)
                    )
            off = None
            if it["item_id"].endswith("matched"):
                fc = official_forecast(
                    t["forecast_fractiles"], t["forecast_bins"], seq.id, cutoff, w["label"]
                )
                off = quantile_score(list(fc.m5), y)
            for model, s in sorted(scores.items()):
                rows.append(
                    {
                        "item_id": it["item_id"],
                        "window": w["label"],
                        "window_end_utc": pd.Timestamp(w["end_ms"], unit="ms", tz="UTC"),
                        "y5": y,
                        "model": model,
                        "n_valid": len(s),
                        "log_qs": sum(s) / len(s),
                        "official_log_qs": off,
                    }
                )
    return pd.DataFrame(rows)
