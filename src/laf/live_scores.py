"""Scores of the released live records (prereg v2 sections 5 and 6): the prospective inputs to
test B, S2 and S5.

The `live` branch (its worktree) holds every issue as `<sequence>/<OAF update ms>/`: the seals,
the push receipt and, once its windows closed, the items, answers and baselines with a NOTICE.
Each released issue is scored on the outcome snapshot: counts of M>=5 events in the item's own
circle and windows. Matched items are scored against the official version they were built from;
strict items have no official forecast, so their scores are taken relative to 0 and only the
contrasts with the pipeline's baselines (S5) use them. A matched item counts for test B and S2
only if GitHub's receipt for its answers seal precedes its first window. Rows match
`laf.d2.analyze`'s per-sample table, so `laf.confirmatory` builds cells from them unchanged.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from laf.catalog import count_in_window
from laf.d2 import BASELINES, _ls
from laf.forecast import official_forecast
from laf.items import Item
from laf.oaf import Circle
from laf.schemas import QKEYS, TARGETS_V2, validate
from laf.splits import require_outcomes


def _jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def released(live: Path) -> list[Path]:
    """Issue folders whose records are released (a NOTICE beside the seals)."""
    return sorted(p.parent for p in live.glob("*/*/NOTICE.txt"))


def live_start_ms(live: Path) -> int | None:
    """L: the seal time of the first answers record on the branch (prereg v2 section 5)."""
    seals = [json.loads(p.read_text(encoding="utf-8"))["sealed_ms"]
             for p in live.glob("*/*/answers.seal.json")]  # fmt: skip
    return min(seals) if seals else None


def _status(call: dict, window: str) -> tuple[str, list[float] | None]:
    """A live answer's status and its M>=5 quantiles for one window, as the batch answers are
    read (`laf.d2.samples`); a reported model other than the requested one is invalid."""
    if call.get("text") is None:
        return "transport_error", None  # a pipeline or transport failure: listed, left out
    status, parsed, _ = validate("direct", call["text"], call.get("stop_reason"), TARGETS_V2)
    if status == "ok" and call.get("model_reported") != call["model_requested"]:
        return "model_mismatch", None
    if status != "ok" or not parsed:
        return status, None
    return status, [parsed[window]["m5_count_quantiles"][k] for k in QKEYS]


COLUMNS = ("item_id", "window", "sequence_id", "kind", "on_time", "part", "origin_ms", "mag",
           "tier", "elapsed_days", "worst_base_d5", *(f"base_d5_{b}" for b in BASELINES), "model",
           "effort", "variant", "sample", "status", "d5")  # fmt: skip


def live_samples(live: Path, tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """One row per released live answer and window, on the outcome snapshot `tables` (the
    columns are kept when nothing is released yet). Item IDs repeat across a sequence's issues
    (`<sequence>@live-matched`), so each row's `item_id` adds the issue's OAF update time.
    `tier` is the sequence's first-detection decision (`<sequence>/inclusion.json`, prereg v2
    section 4). A window counts only once it closed at least 21 days before its sequence's
    catalog end in the snapshot, the batch rule (`analysis.PRIMARY_SETTLING_DAYS`)."""
    from laf.analysis import PRIMARY_SETTLING_DAYS

    cat, fr, bins = tables["catalog"], tables["forecast_fractiles"], tables["forecast_bins"]
    catalog_end = tables["sequences"].set_index("sequence_id")["catalog_end_ms"]
    settle_ms = PRIMARY_SETTLING_DAYS * 86_400_000
    rows = []
    for d in released(live):
        lines = (d / "items.jsonl").read_text(encoding="utf-8").splitlines()
        items = [Item.model_validate_json(x) for x in lines if x.strip()]
        require_outcomes({i.sequence_id for i in items})  # the second gate (laf.splits)
        seal = json.loads((d / "answers.seal.json").read_text(encoding="utf-8"))
        receipt = d / "receipt.json"
        receipt_ms = json.loads(receipt.read_text(encoding="utf-8"))["receipt_ms"] if (
            receipt.exists()) else None  # fmt: skip
        base = {(b["forecaster"], b["item_id"], b["window"]): b["m5"]
                for b in _jsonl(d / "baselines.jsonl")}  # fmt: skip
        calls = [c for c in _jsonl(d / "calls.jsonl") if not c.get("missed")]
        inclusion = d.parent / "inclusion.json"
        tier = json.loads(inclusion.read_text(encoding="utf-8"))["tier"] if (
            inclusion.exists()) else None  # fmt: skip
        for it in items:
            if it.sequence_id not in catalog_end.index:
                raise SystemExit(f"outcome snapshot lacks live sequence {it.sequence_id}")
            kind = "matched" if it.item_id.endswith("@live-matched") else "strict"
            first = seal["items"][it.item_id]["first_window_ms"]
            on_time = receipt_ms is not None and receipt_ms < first
            circle = Circle(it.region.lat, it.region.lon, it.region.radius_km)
            own = cat[cat["sequence_id"] == it.sequence_id]  # overlapping catalogs share events
            for w in it.windows:
                if w.end_ms + settle_ms > catalog_end[it.sequence_id]:
                    continue  # not settled in this snapshot
                y = count_in_window(own, circle, w.start_ms, w.end_ms, 5.0)
                ls = {b: _ls(base.get((b, it.item_id, w.label)), y) for b in BASELINES}
                if kind == "matched":
                    fc = official_forecast(fr, bins, it.sequence_id, it.issue_ms, w.label)
                    ls["official"] = off = _ls(list(fc.m5), y)
                else:  # strict windows: no official forecast, scores relative to 0
                    off = 0.0
                scored = [v for v in ls.values() if not np.isnan(v)]
                if not scored:  # strict, and its baselines record is missing: nothing to score
                    continue
                worst = max(scored)
                cell = {
                    "item_id": f"{it.item_id}#{d.name}", "window": w.key,
                    "sequence_id": it.sequence_id,
                    "kind": kind, "on_time": on_time, "part": "prospective",
                    "origin_ms": it.mainshock.origin_ms, "mag": it.mainshock.mag, "tier": tier,
                    "elapsed_days": it.elapsed_days, "worst_base_d5": worst - off,
                    **{f"base_d5_{b}": ls[b] - off for b in BASELINES},
                }  # fmt: skip
                for c in calls:
                    if c["item_id"] != it.item_id:
                        continue
                    status, q = _status(c, w.key)
                    rows.append({
                        **cell, "model": c["model_requested"], "effort": c.get("effort"),
                        "variant": c.get("paraphrase"), "sample": c["sample"], "status": status,
                        "d5": _ls(q, y) - off if q else np.nan,
                    })  # fmt: skip
    return pd.DataFrame(rows, columns=list(COLUMNS))


def live_items(live: Path) -> pd.DataFrame:
    """Every published live item with its on-time status and its answers: valid, invalid,
    failed and missed (budget), as the prereg lists late, missed and failed items."""
    rows = []
    for seal_path in sorted(live.glob("*/*/answers.seal.json")):
        d = seal_path.parent
        seal = json.loads(seal_path.read_text(encoding="utf-8"))
        receipt = d / "receipt.json"
        receipt_ms = json.loads(receipt.read_text(encoding="utf-8"))["receipt_ms"] if (
            receipt.exists()) else None  # fmt: skip
        calls = _jsonl(d / "calls.jsonl")  # empty until released
        for item_id, v in seal["items"].items():
            mine = [c for c in calls if c["item_id"] == item_id]
            rows.append({
                "issue": d.relative_to(live).as_posix(), "item_id": item_id,
                "first_window_ms": v["first_window_ms"], "receipt_ms": receipt_ms,
                "on_time": receipt_ms is not None and receipt_ms < v["first_window_ms"],
                "released": (d / "NOTICE.txt").exists(),
                "missed_budget": sum(bool(c.get("missed")) for c in mine),
                "failed": sum(c.get("text") is None and not c.get("missed") for c in mine),
                "answers": sum(c.get("text") is not None for c in mine),
            })  # fmt: skip
    return pd.DataFrame(rows)
