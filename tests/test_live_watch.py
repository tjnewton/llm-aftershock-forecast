import json
from pathlib import Path

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


def test_step_logs_detections_once_and_keeps_polling_after_errors(tmp_path, monkeypatch):
    feed = json.dumps({"features": [{"id": "nc75458907"}]}).encode()
    pages = {"poll": feed, "event": json.dumps(DOC).encode()}
    get = lambda url: pages["poll"] if "updatedafter" in url else pages["event"]  # noqa: E731
    newest = W.new_versions(DOC, set())[-1]["update_ms"]
    built = {
        "items_sha256": "x", "matched_update_ms": newest,
        "matched_window_start_ms": 0, "strict_window_start_ms": 10**13,
    }  # fmt: skip
    monkeypatch.setattr(W, "build_live_items", lambda *a, **k: built)
    state = W.step(tmp_path, tmp_path, {}, get)
    n = sum(r["kind"] == "detection" for r in _log(tmp_path))
    assert n == len(W.new_versions(DOC, set())) and "last_poll_ms" in state
    dets = [r for r in _log(tmp_path) if r["kind"] == "detection"]
    assert all(r["backlog"] for r in dets)  # versions published before the watch began
    assert [r["matched_margin_s"] is not None for r in dets].count(True) == 1  # newest only
    assert all(r["superseded"] for r in dets if r["update_ms"] != newest)
    W.step(tmp_path, tmp_path, state, get)  # nothing new on the second poll
    assert sum(r["kind"] == "detection" for r in _log(tmp_path)) == n

    def broken(url):
        raise TimeoutError("ComCat slow")

    W.step(tmp_path, tmp_path, state, broken)
    assert "error" in _log(tmp_path)[-1]


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
