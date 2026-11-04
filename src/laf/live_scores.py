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
    return [json.loads(x) for x in path.read_text(encoding="utf-8").split("\n") if x.strip()]


def released(live: Path) -> list[Path]:
    """Issue folders whose records are released (a NOTICE beside the seals)."""
    return sorted(p.parent for p in live.glob("*/*/NOTICE.txt"))


def live_start_ms(live: Path) -> int | None:
    """L: the paid detector's start, which it records in `start.json` at the root of the branch
    before its first poll (prereg v2 section 5), or None before that."""
    p = live / "start.json"
    return int(json.loads(p.read_text(encoding="utf-8"))["start_ms"]) if p.exists() else None


def _delivered(call: dict) -> bool:
    """The provider returned an answer, valid or not; a call with an error or without a reported
    model is a pipeline or transport failure."""
    return not call.get("error") and call.get("model_reported") is not None


def model_changes(live: Path) -> dict[str, int]:
    """Per live model, the answers seal time of the first issue where it answered as another
    model (prereg v2 section 3): its accrual stops at that issue; earlier answers stand."""
    out: dict[str, int] = {}
    for seal_path in live.glob("*/*/answers.seal.json"):
        sealed = json.loads(seal_path.read_text(encoding="utf-8"))["sealed_ms"]
        for c in _jsonl(seal_path.parent / "calls.jsonl"):
            m = c["model_requested"]
            if _delivered(c) and c["model_reported"] != m:
                out[m] = min(out.get(m, sealed), sealed)
    return out


def _after_change(call: dict, sealed_ms: int, changes: dict[str, int]) -> bool:
    stop = changes.get(call.get("model_requested", ""))
    return stop is not None and sealed_ms >= stop


def _status(call: dict, window: str) -> tuple[str, list[float] | None]:
    """A live answer's status and its M>=5 quantiles for one window, as the batch answers are
    read (`laf.d2.samples`): a delivered answer cut off at the cap or refused, even without
    text, is invalid and penalized; only an undelivered call is a transport error. Answers from
    a model change on never get here (`model_changes`)."""
    if not _delivered(call):
        return "transport_error", None  # a pipeline or transport failure: listed, left out
    status, parsed, _ = validate("direct", call.get("text"), call.get("stop_reason"), TARGETS_V2)
    if status != "ok" or not parsed:
        return status, None
    return status, [parsed[window]["m5_count_quantiles"][k] for k in QKEYS]


COLUMNS = ("item_id", "window", "sequence_id", "table_sequence_id", "kind", "on_time", "part",
           "origin_ms", "mag", "tier", "elapsed_days", "worst_base_d5",
           *(f"base_d5_{b}" for b in BASELINES), "model", "effort", "variant", "sample", "status",
           "d5")  # fmt: skip


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
    changes = model_changes(live)
    for d in released(live):
        lines = (d / "items.jsonl").read_text(encoding="utf-8").split("\n")
        items = [Item.model_validate_json(x) for x in lines if x.strip()]
        require_outcomes({i.sequence_id for i in items})  # the second gate (laf.splits)
        if not (d / "baselines.jsonl").exists():
            continue  # a pipeline failure: no registered penalty pool; listed by `live_items`
        seal = json.loads((d / "answers.seal.json").read_text(encoding="utf-8"))
        receipt = d / "receipt.json"
        receipt_ms = json.loads(receipt.read_text(encoding="utf-8"))["receipt_ms"] if (
            receipt.exists()) else None  # fmt: skip
        base = {(b["forecaster"], b["item_id"], b["window"]): b["m5"]
                for b in _jsonl(d / "baselines.jsonl")}  # fmt: skip
        # a model's answers from its first model change on are left out and listed
        sealed = seal["sealed_ms"]
        calls = [c for c in _jsonl(d / "calls.jsonl")
                 if not c.get("missed") and not _after_change(c, sealed, changes)]  # fmt: skip
        inclusion = d.parent / "inclusion.json"
        inc = json.loads(inclusion.read_text(encoding="utf-8")) if inclusion.exists() else {}
        tier = inc.get("tier")
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
                    # grouped under the frozen key: a changed preferred ID is one sequence
                    "item_id": f"{it.item_id}#{d.name}", "window": w.key,
                    "sequence_id": inc.get("key") or it.sequence_id,
                    "table_sequence_id": it.sequence_id,  # the ID in the outcome tables
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
    """Every published live item with its on-time status and its answers: delivered (valid or
    invalid), failed (transport), missed (budget) and, of the delivered, those left out after a
    model change, as the prereg lists late, missed and failed items."""
    rows = []
    changes = model_changes(live)
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
                "baselines": (d / "baselines.jsonl").exists() or not (d / "NOTICE.txt").exists(),
                "missed_budget": sum(bool(c.get("missed")) for c in mine),
                "failed": sum(not c.get("missed") and not _delivered(c) for c in mine),
                "answers": sum(_delivered(c) for c in mine),
                "after_model_change": sum(
                    _delivered(c) and _after_change(c, seal["sealed_ms"], changes) for c in mine
                ),
            })  # fmt: skip
    return pd.DataFrame(rows)


def unissued(live: Path, tables: dict[str, pd.DataFrame], start_ms: int | None) -> pd.DataFrame:
    """Missed issues (prereg v2 section 5: missed items are listed, never backfilled): for each
    sequence included at first detection (`<sequence>/inclusion.json` with a tier) with origin
    at L or later, the versions the ADR 0004 schedule picks among the outcome snapshot's valid
    versions (the rule of `prospective.scheduled_slot`) that have no issue on the branch under
    any of its IDs (a changed preferred ID adds a folder with the same inclusion key)."""
    from laf.tables import select_issue_times

    cols = ["sequence_id", "table_sequence_id", "slot", "info_cutoff_ms", "update_ms", "reason"]
    ov = tables["oaf_versions"]
    valid = ov[ov["valid"] & ~ov["duplicate"].fillna(False).astype(bool)]
    origin = tables["sequences"].set_index("sequence_id")["origin_ms"]
    groups: dict[str, tuple[list[str], dict]] = {}
    for p in sorted(live.glob("*/inclusion.json")):
        inc = json.loads(p.read_text(encoding="utf-8"))
        if inc.get("tier"):
            groups.setdefault(inc.get("key") or p.parent.name, ([], inc))[0].append(p.parent.name)
    rows = []
    for key, (folders, inc) in groups.items():
        sid = next((f for f in (key, *folders) if f in origin.index), None)
        o = int(origin[sid]) if sid else inc.get("time_ms")
        if start_ms is None or o is None or o < start_ms:
            continue  # not prospective
        if sid is None:  # fetch every included sequence (`laf outcome-config`)
            lost = {"sequence_id": key, "reason": "not in the outcome snapshot"}
            rows.append(dict.fromkeys(cols) | lost)
            continue
        issued = {int(d.name) for f in folders for d in (live / f).iterdir() if d.name.isdigit()}
        v = valid[valid["sequence_id"] == sid]
        for pick in select_issue_times(o, [int(c) for c in v["info_cutoff_ms"]]):
            ups = {int(u) for u in v.loc[v["info_cutoff_ms"] == pick.issue_ms, "update_ms"]}
            if not ups & issued:  # any version with the picked cutoff fills the slot
                rows.append({"sequence_id": key, "table_sequence_id": sid, "slot": pick.target,
                             "info_cutoff_ms": pick.issue_ms, "update_ms": min(ups),
                             "reason": "not issued"})  # fmt: skip
    return pd.DataFrame(rows, columns=cols)


def timeliness(live: Path, tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """On-time against late matched items on outcome-blind covariates (prereg v2 section 5):
    magnitude, network (the event ID's prefix), time since the mainshock and the official
    model type of the matched version (`oaf_versions.model` at the issue's update time)."""
    import re

    ov = tables["oaf_versions"].drop_duplicates(["sequence_id", "update_ms"])
    model = ov.set_index(["sequence_id", "update_ms"])["model"]
    rows = []
    for d in released(live):
        receipt = d / "receipt.json"
        receipt_ms = json.loads(receipt.read_text(encoding="utf-8"))["receipt_ms"] if (
            receipt.exists()) else None  # fmt: skip
        seal = json.loads((d / "answers.seal.json").read_text(encoding="utf-8"))
        for x in (d / "items.jsonl").read_text(encoding="utf-8").split("\n"):
            it = Item.model_validate_json(x) if x.strip() else None
            if it is None or not it.item_id.endswith("@live-matched"):
                continue
            first = seal["items"][it.item_id]["first_window_ms"]
            net = re.match(r"[a-z]+", it.sequence_id)
            rows.append({"on_time": receipt_ms is not None and receipt_ms < first,
                         "mag": it.mainshock.mag, "network": net.group(0) if net else "",
                         "elapsed_days": it.elapsed_days,
                         "model": model.get((it.sequence_id, int(d.name)))})  # fmt: skip
    df = pd.DataFrame(rows, columns=["on_time", "mag", "network", "elapsed_days", "model"])

    def counts(x: pd.Series) -> str:
        return ", ".join(f"{k} {v}" for k, v in x.fillna("unknown").value_counts().items())

    return df.groupby("on_time").agg(
        items=("mag", "size"), mag_median=("mag", "median"),
        elapsed_days_median=("elapsed_days", "median"),
        networks=("network", counts), official_models=("model", counts),
    ).reset_index()  # fmt: skip
