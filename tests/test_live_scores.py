import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from laf import confirmatory as C
from laf import live_scores as L
from laf import prospective as P
from laf.analysis import load_tables
from laf.cli import snapshot_ms
from laf.d2 import BASELINES
from laf.registry import load_sequences
from laf.schemas import QKEYS, WINDOWS

PANAMA = next(s for s in load_sequences(Path("config/sequences.toml")) if s.id == "us6000u18k")
SNAP = "20261021T1027Z"  # Panama is development: its outcomes may be scored
NOW = snapshot_ms(SNAP) - 3_600_000


def _answer(m5: int) -> str:
    q = {k: m5 + (i >= 6) for i, k in enumerate(QKEYS)}  # non-decreasing integer quantiles
    win = {"m5_count_quantiles": q, "m4_count_quantiles": q, "m3_count_quantiles": q,
           "p_m6_at_least_one": 0.01}  # fmt: skip
    return json.dumps({**{w: win for w in WINDOWS}, "notes": "Synthetic."})


@pytest.fixture(scope="module")
def live(tmp_path_factory):
    """One released Panama issue on a synthetic `live` worktree: seal, receipt, answers from
    both live models (one answer reports another model), baselines, notice."""
    _, items, update_ms = P.issue(Path("data"), SNAP, PANAMA, NOW)
    root = tmp_path_factory.mktemp("live")
    d = root / PANAMA.id / str(update_ms)
    d.mkdir(parents=True)
    (d / "items.jsonl").write_text("".join(i.model_dump_json() + "\n" for i in items))
    first = {i.item_id: min(w.start_ms for w in i.windows) for i in items}
    seal = {"sealed_ms": 1, "items": {k: {"first_window_ms": v, "on_time": True}
                                      for k, v in first.items()}}  # fmt: skip
    (d / "answers.seal.json").write_text(json.dumps(seal))
    matched = next(k for k in first if k.endswith("@live-matched"))
    (d / "receipt.json").write_text(json.dumps({"receipt_ms": first[matched] - 1000}))
    calls = []
    for it in items:
        for m in ("claude-opus-5-5", "gpt-6.1-sol"):
            calls.append({"item_id": it.item_id, "model_requested": m, "model_reported": m,
                          "sample": 0, "effort": "high", "paraphrase": "v2A",
                          "text": _answer(0), "stop_reason": "end_turn"})  # fmt: skip
        calls.append({**calls[-1], "sample": 1, "model_reported": "gpt-other"})  # invalid
        calls.append({"item_id": it.item_id, "model_requested": "gpt-6.1-sol", "sample": 2,
                      "missed": "budget"})  # fmt: skip
    (d / "calls.jsonl").write_text("".join(json.dumps(c) + "\n" for c in calls))
    base = [{"forecaster": b, "item_id": it.item_id, "window": w.label,
             "m5": [0, 0, 0, 0, 0, 1, 1, 2, 2]}
            for b in BASELINES for it in items for w in it.windows]  # fmt: skip
    (d / "baselines.jsonl").write_text("".join(json.dumps(b) + "\n" for b in base))
    (d / "NOTICE.txt").write_text("not official forecasts\n")
    (root / PANAMA.id / "inclusion.json").write_text(json.dumps({"tier": "primary"}))
    return root, items


def _mature(tables):
    """The outcome snapshot as if fetched long after every window closed."""
    return {**tables, "sequences": tables["sequences"].assign(catalog_end_ms=10**14)}


def test_live_answers_are_scored_like_batch_answers(live):
    root, _ = live
    tables = load_tables(Path("data/processed") / SNAP)
    assert L.live_samples(root, tables).empty  # windows not settled in this snapshot
    s = L.live_samples(root, _mature(tables))
    assert set(s["tier"]) == {"primary"}  # the first-detection decision
    assert set(s["kind"]) == {"matched", "strict"} and set(s["window"]) == set(WINDOWS)
    assert (s.loc[s["model"] == "gpt-6.1-sol", "status"] == "model_mismatch").any()
    assert not s["sample"].eq(2).any()  # a budget miss is listed, never scored
    ok = s[s["status"] == "ok"]
    assert ok["d5"].notna().all() and bool(ok["on_time"].all())
    strict = ok[ok["kind"] == "strict"]  # no official forecast: scores relative to 0
    assert (strict["worst_base_d5"] >= strict["base_d5_naive"]).all()
    assert L.live_start_ms(root) == 1
    assert all("#" in i for i in s["item_id"])  # one scoring ID per issue
    issue = next(root.glob("*/*/baselines.jsonl"))
    kept = issue.read_text()
    issue.unlink()  # released without its baselines record (the baselines push failed)
    try:
        bare = L.live_samples(root, _mature(tables))
    finally:
        issue.write_text(kept)
    assert set(bare["kind"]) == {"matched"}  # strict cells need a baseline; matched still score


def test_nothing_released_yet_keeps_the_report_running(tmp_path, monkeypatch):
    from laf import splits

    monkeypatch.setattr(splits, "development_ids", lambda: frozenset())
    empty = L.live_samples(tmp_path, load_tables(Path("data/processed") / SNAP))
    assert empty.empty and "elapsed_days" in empty.columns
    retro = pd.DataFrame([_rows("claude-opus-5-5", f"r{i}", "batch") for i in range(3)])
    clean = pd.Timestamp("2026-10-15", tz="UTC").value // 1_000_000  # Opus 5.5's clean period
    seqs = pd.DataFrame({"sequence_id": [f"r{i}" for i in range(3)], "origin_ms": clean,
                         "mag": 5.5})  # fmt: skip
    recs = C.live_report(retro, empty, seqs, {i: 2.0 for i in retro["item_id"]}, 10**13, None)
    t = {r["hypothesis"]: r for r in recs.to_dict("records")}
    assert t["B retrospective part"]["sequences"] == 3 and t["B prospective part"]["sequences"] == 0


def test_every_live_item_is_listed_with_its_status(live):
    root, _ = live
    rows = {r["item_id"]: r for r in L.live_items(root).to_dict("records")}
    m = next(r for i, r in rows.items() if i.endswith("@live-matched"))
    assert m["on_time"] and m["released"] and m["missed_budget"] == 1 and m["answers"] == 3


def _rows(model, sid, kind="matched", on_time=True, origin=10, d=-0.1, mag=5.5):
    return {"model": model, "effort": "high", "variant": "v2A", "status": "ok", "sample": 0,
            "sequence_id": sid, "item_id": f"{sid}@{kind}", "window": "day", "kind": kind,
            "on_time": on_time, "origin_ms": origin, "mag": mag, "elapsed_days": 2.0, "d5": d,
            "tier": "primary" if mag >= 5 else "secondary",
            "worst_base_d5": 1.0, **{f"base_d5_{b}": 0.5 for b in BASELINES}}  # fmt: skip


def test_test_b_joins_its_two_parts_and_s2_s5_use_the_live_items(monkeypatch):
    from laf import splits

    monkeypatch.setattr(splits, "development_ids", lambda: frozenset())
    rng = np.random.default_rng(0)
    effects = rng.normal(-0.1, 0.05, 6)
    retro = pd.DataFrame([_rows("claude-opus-5-5", f"r{i}", "batch", d=float(e))
                          for i, e in enumerate(effects)])  # fmt: skip
    start = pd.Timestamp("2026-11-15", tz="UTC").value // 1_000_000
    seqs = pd.DataFrame({"sequence_id": [f"r{i}" for i in range(6)] + [f"p{i}" for i in range(8)],
                         "origin_ms": [start - 10**9] * 6 + [start + 10**6] * 8,
                         "mag": 5.5})  # fmt: skip
    live = pd.DataFrame(
        [_rows(m, f"p{i}", origin=start + 10**6, d=float(rng.normal(-0.2, 0.05)))
         for m in ("claude-opus-5-5", "gpt-6.1-sol") for i in range(6)]
        + [_rows("claude-opus-5-5", "p6", on_time=False, origin=start + 10**6)]  # late: out
        + [_rows("claude-opus-5-5", "p7", origin=start + 10**6, mag=4.6)]  # secondary: out
        + [_rows(m, f"p{i}", "strict", origin=start + 10**6, d=float(rng.normal(-0.2, 0.05)))
           for m in ("claude-opus-5-5", "gpt-6.1-sol") for i in range(6)]
    )  # fmt: skip
    elapsed = {i: 2.0 for i in retro["item_id"]}
    keep = {"r0", "r1", "p0", "p1", "p2"}
    recs = C.live_report(retro, live, seqs, elapsed, start, None, keep).to_dict("records")
    t = {r["hypothesis"]: r for r in recs if r["hypothesis"] not in ("S5", "assay", "informative")}
    assay = {r["model"]: r for r in recs if r["hypothesis"] == "assay"}
    assert set(assay) == {"claude-opus-5-5", "gpt-6.1-sol"}  # on the full B and S2 cells
    info = {r["model"]: r["sequences"] for r in recs if r["hypothesis"] == "informative"}
    assert info == {"claude-opus-5-5": 5, "gpt-6.1-sol": 3}
    assert t["B"]["sequences"] == 12  # 6 retrospective + 6 prospective; late and M4.6 out
    assert t["B retrospective part"]["sequences"] == t["B prospective part"]["sequences"] == 6
    assert t["S2"]["sequences"] == 6 and t["S2"]["noninferior"]
    s34 = {(r["hypothesis"], r["model"], r["reference"]): r for r in recs
           if r["hypothesis"] in ("S3", "S4")}  # fmt: skip
    assert s34[("S3", "claude-opus-5-5", "naive")]["sequences"] == 12  # B's full set
    assert s34[("S4", "gpt-6.1-sol", "generic_rj")]["sequences"] == 6  # S2's set
    assert "lower95" in s34[("S4", "claude-opus-5-5", "etas")]
    s5 = [r for r in recs if r["hypothesis"] == "S5"]
    assert {r["model"] for r in s5} == {"claude-opus-5-5", "gpt-6.1-sol"} and len(s5) == 6
    assert {r["sequences"] for r in s5} == {6}
    late = live.assign(on_time=live["kind"] == "matched")  # every strict answer sealed late
    recs = C.live_report(retro, late, seqs, elapsed, start, None).to_dict("records")
    assert not [r for r in recs if r["hypothesis"] == "S5"]
    failed = live.assign(status="transport_error")  # every live call failed
    recs = C.live_report(retro, failed, seqs, elapsed, start, None).to_dict("records")
    t = {r["hypothesis"]: r for r in recs}
    assert t["B prospective part"]["sequences"] == 0 and t["B"]["sequences"] == 6
