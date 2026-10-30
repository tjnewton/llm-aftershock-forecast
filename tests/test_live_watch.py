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
    built = {"items": 3, "items_sha256": "x", "newest_window_start_ms": 0}
    monkeypatch.setattr(W, "build_live_items", lambda *a, **k: built)
    state = W.step(tmp_path, tmp_path, {}, get)
    n = sum(r["kind"] == "detection" for r in _log(tmp_path))
    assert n == len(W.new_versions(DOC, set())) and "last_poll_ms" in state
    assert all(r["backlog"] for r in _log(tmp_path) if r["kind"] == "detection")  # old versions
    W.step(tmp_path, tmp_path, state, get)  # nothing new on the second poll
    assert sum(r["kind"] == "detection" for r in _log(tmp_path)) == n

    def broken(url):
        raise TimeoutError("ComCat slow")

    W.step(tmp_path, tmp_path, state, broken)
    assert "error" in _log(tmp_path)[-1]
