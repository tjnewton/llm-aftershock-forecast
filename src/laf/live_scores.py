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
from laf.d2 import BASELINES, CONTROL_P
from laf.items import Item
from laf.oaf import Circle
from laf.schemas import fields, stated_p5, validate
from laf.scoring import P_CLIP, log_score_binary
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
    before its first poll (prereg v2 section 5; `live_watch.run`), or None before that."""
    from laf.live_watch import start_ms

    return start_ms(live)


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


def _status(call: dict, window: str) -> tuple[str, float | None]:
    """A live answer's status and its stated probability of at least one M>=5 earthquake for
    one window, as the batch answers are read (`laf.d2.samples`). The probability is usable
    whatever else is wrong with the answer (prereg v2 section 7); a delivered answer cut off
    at the cap or refused, even without text, has none and is penalized; only an undelivered
    call is a transport error. Answers from a model change on never get here
    (`model_changes`)."""
    if not _delivered(call):
        return "transport_error", None  # a pipeline or transport failure: listed, left out
    text, stop = call.get("text"), call.get("stop_reason")
    status, _, _ = validate("direct", text, stop, *fields(call.get("paraphrase")))
    return status, stated_p5(text, stop)[window]


def _sp(p: float | None, event: bool) -> float:
    """The primary score of a probability (clipped log score); NaN without one."""
    return float("nan") if p is None or p != p else log_score_binary(float(p), event)


def _p_official(bins: pd.DataFrame, sequence_id: str, cutoff_ms: int, window: str):
    """The matched official version's published probability of at least one M>=5 earthquake."""
    b = bins[(bins["sequence_id"] == sequence_id) & (bins["info_cutoff_ms"] == cutoff_ms)
             & (bins["window"] == window) & (bins["magnitude"] == 5.0)]  # fmt: skip
    return float(b["probability"].iloc[0]) if len(b) else None


COLUMNS = ("item_id", "window", "sequence_id", "table_sequence_id", "kind", "on_time", "part",
           "origin_ms", "mag", "tier", "elapsed_days", "worst_base_d5", "worst_case_d5",
           "m5_event", *(f"base_d5_{b}" for b in (*BASELINES, "constant")), "model", "effort",
           "variant", "sample", "status", "valid5", "d5")  # fmt: skip


def live_samples(live: Path, tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """One row per released live answer and window, on the outcome snapshot `tables` (the
    columns are kept when nothing is released yet). Item IDs repeat across a sequence's issues
    (`<sequence>@live-matched`), so each row's `item_id` adds the issue's OAF update time.
    `tier` is the sequence's first-detection decision (`<sequence>/inclusion.json`, prereg v2
    section 4). A window counts only once it closed at least 21 days before its sequence's
    catalog end in the snapshot, the batch rule (`analysis.PRIMARY_SETTLING_DAYS`)."""
    from laf.analysis import PRIMARY_SETTLING_DAYS

    cat, bins = tables["catalog"], tables["forecast_bins"]
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
        # each baseline's sealed probability (records sealed before prompt v3 have none)
        base = {(b["forecaster"], b["item_id"], b["window"]): b.get("p_m5")
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
                event = count_in_window(own, circle, w.start_ms, w.end_ms, 5.0) >= 1
                ls = {b: _sp(base.get((b, it.item_id, w.label)), event) for b in BASELINES}
                if kind == "matched":
                    p_off = _p_official(bins, it.sequence_id, it.issue_ms, w.label)
                    if p_off is None:
                        continue  # no published probability to score against
                    ls["official"] = off = _sp(p_off, event)
                else:  # strict windows: no official forecast, scores relative to 0, so an
                    off = 0.0  # invalid answer scores log 2 itself, a probability of one half
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
                    "worst_case_d5": -np.log(P_CLIP) - off, "m5_event": event,
                    **{f"base_d5_{b}": ls[b] - off for b in BASELINES},
                    "base_d5_constant": _sp(CONTROL_P, event) - off,
                }  # fmt: skip
                for c in calls:
                    if c["item_id"] != it.item_id:
                        continue
                    status, p5 = _status(c, w.key)
                    rows.append({
                        **cell, "model": c["model_requested"], "effort": c.get("effort"),
                        "variant": c.get("paraphrase"), "sample": c["sample"], "status": status,
                        "valid5": p5 is not None, "d5": _sp(p5, event) - off,
                    })  # fmt: skip
    return pd.DataFrame(rows, columns=list(COLUMNS))


def live_informative(live: Path, threshold: float) -> set[str]:
    """The prospective sequences of the informative-sequence estimand (prereg v2 section 2):
    generic RJ's sealed probability of at least one M>=5 earthquake is at least `threshold`
    in the month window of the sequence's first released issue that has one (its matched
    item). Read from the sealed baselines records alone: no outcome is read. Sequences are
    named as `live_samples` names them (the frozen inclusion key, else the item's ID)."""
    first: dict[str, tuple[int, float]] = {}
    for d in released(live):
        if not (d / "baselines.jsonl").exists():
            continue
        inclusion = d.parent / "inclusion.json"
        inc = json.loads(inclusion.read_text(encoding="utf-8")) if inclusion.exists() else {}
        for b in _jsonl(d / "baselines.jsonl"):
            month = b["forecaster"] == "generic_rj" and b["window"] == "1 Month"
            if month and b["item_id"].endswith("@live-matched") and b.get("p_m5") is not None:
                key, at = inc.get("key") or b["item_id"].split("@")[0], int(d.name)
                if key not in first or at < first[key][0]:
                    first[key] = (at, float(b["p_m5"]))
    return {k for k, (_, p) in first.items() if p >= threshold}


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
