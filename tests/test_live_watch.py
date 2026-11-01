import json
from pathlib import Path

import pytest

from laf import live_watch as W
from laf.usgs import read_raw

DOC = json.loads(read_raw(Path("data"), "raw/snapshots/20261029T2000Z/event/nc75458907.geojson.gz"))


def test_new_versions_are_the_unseen_ones_oldest_first():
    allv = W.new_versions(DOC, set())
    assert allv and allv == sorted(allv, key=lambda v: v["update_ms"])
    seen = {v["update_ms"] for v in allv[:-1]}
    assert [v["update_ms"] for v in W.new_versions(DOC, seen)] == [allv[-1]["update_ms"]]
    assert all(v["index_ms"] >= v["update_ms"] for v in allv)


def _log(out):
    return [json.loads(x) for x in (out / "log.jsonl").read_text().splitlines()]


def _get(context=(), doc=DOC):
    """A ComCat stub: the poll feed, the aftershock-context query, and the event document."""
    feed = json.dumps({"features": [{"id": doc["id"]}]}).encode()

    def get(url):
        if "updatedafter" in url:
            return feed
        if "minmagnitude" in url:
            return json.dumps({"features": list(context)}).encode()
        return json.dumps(doc).encode()

    return get


def test_step_runs_each_new_version_once_and_keeps_polling_after_errors(tmp_path, monkeypatch):
    newest = W.new_versions(DOC, set())[-1]["update_ms"]
    built = {"matched_update_ms": newest, "slot": "first", "matched_margin_s": -5.0,
             "strict_margin_s": 900.0}  # fmt: skip
    calls = []
    monkeypatch.setattr(W, "dry_issue", lambda *a, **k: calls.append(a) or built)
    state = W.step(tmp_path, tmp_path, {}, _get())
    n = len(W.new_versions(DOC, set()))
    dets = [r for r in _log(tmp_path) if r["kind"] == "detection"]
    assert len(dets) == n and len(calls) == 1 and "last_poll_ms" in state
    assert all(r["tier"] == "secondary" and r["inclusion"] == "included" for r in dets)  # M4.01 nc
    assert state["included"] == {"nc75458907": "secondary"}
    assert all(r["backlog"] for r in dets)  # versions published before the watch began
    own = [r for r in dets if r["update_ms"] == newest]
    assert len(own) == 1 and own[0]["slot"] == "first" and not own[0]["superseded"]
    assert all(r["superseded"] and "slot" not in r for r in dets if r["update_ms"] != newest)
    W.step(tmp_path, tmp_path, state, _get())  # nothing new on the second poll
    assert sum(r["kind"] == "detection" for r in _log(tmp_path)) == n and len(calls) == 1

    def broken(url):
        raise TimeoutError("ComCat slow")

    W.step(tmp_path, tmp_path, state, broken)
    assert "error" in _log(tmp_path)[-1]


def test_a_failed_issue_is_logged_and_never_retried(tmp_path, monkeypatch):
    def fail(*a, **k):
        raise RuntimeError("fetch failed")

    monkeypatch.setattr(W, "dry_issue", fail)
    state = W.step(tmp_path, tmp_path, {}, _get())
    assert "RuntimeError" in _log(tmp_path)[-1]["error"]
    monkeypatch.setattr(W, "dry_issue", lambda *a, **k: pytest.fail("retried"))
    W.step(tmp_path, tmp_path, state, _get())


def test_aftershocks_and_small_events_are_not_run(tmp_path, monkeypatch):
    monkeypatch.setattr(W, "dry_issue", lambda *a, **k: pytest.fail("excluded event was run"))
    lon, lat, _ = DOC["geometry"]["coordinates"]
    bigger = {"properties": {"mag": 6.5, "time": DOC["properties"]["time"] - 86_400_000,
                             "types": ",origin,"},
              "geometry": {"coordinates": [lon + 0.01, lat, 8.0]}}  # fmt: skip
    state = W.step(tmp_path, tmp_path, {}, _get([bigger]))
    assert {r["inclusion"] for r in _log(tmp_path) if r["kind"] == "detection"} == {"aftershock"}
    assert state["included"] == {}
    small = json.loads(json.dumps(DOC))
    small["properties"]["mag"] = 3.9
    (tmp_path / "s").mkdir()
    W.step(tmp_path / "s", tmp_path, {}, _get(doc=small))
    assert {r["inclusion"] for r in _log(tmp_path / "s") if "inclusion" in r} == {"magnitude"}


def test_a_sequence_is_tracked_through_its_associated_ids(tmp_path, monkeypatch):
    vs = [v["update_ms"] for v in W.new_versions(DOC, set())]
    state = {"seen": {"us7000ttnj": vs[:-1]}, "included": {"us7000ttnj": "secondary"}}
    built = {"matched_update_ms": vs[-1], "slot": "1d"}
    monkeypatch.setattr(W, "dry_issue", lambda *a, **k: built)

    def no_context(url):
        assert "minmagnitude" not in url, "an included sequence is never checked again"
        return _get()(url)

    W.step(tmp_path, tmp_path, state, no_context)
    dets = [r for r in _log(tmp_path) if r["kind"] == "detection"]
    assert [r["update_ms"] for r in dets] == [vs[-1]] and dets[0]["key"] == "us7000ttnj"
    assert set(state["seen"]) == {"us7000ttnj"}


def test_late_share_bounds_and_monotonicity():
    import numpy as np

    from laf.live_watch import late_share

    lags = [5.0]
    assert late_share(np.array([-60.0]), lags, 600, 30) == 1.0  # window opened before publication
    assert late_share(np.array([7200.0]), lags, 600, 30) == 0.0
    slack = np.linspace(-300, 3000, 50)
    shares = [late_share(slack, lags, p, 60) for p in (120, 300, 600)]
    assert shares == sorted(shares)


def test_index_lags_skip_failed_detections(tmp_path):
    from laf.live_watch import index_lags_s

    log = tmp_path / "log.jsonl"
    log.write_text(
        '{"kind": "poll"}\n'
        '{"kind": "detection", "index_ms": 7000, "update_ms": 2000}\n'
        '{"kind": "detection", "event_id": "x", "error": "HTTPError: 503"}\n'
    )
    assert index_lags_s(log) == [5.0]
