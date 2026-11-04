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
    monkeypatch.setattr(W, "live_issue", lambda *a, **k: calls.append(a) or built)
    state = W.step(tmp_path, tmp_path, {}, _get())
    n = len(W.new_versions(DOC, set()))
    dets = [r for r in _log(tmp_path) if r["kind"] == "detection"]
    assert len(dets) == n and len(calls) == 1 and "last_poll_ms" in state
    assert all(r["tier"] == "secondary" and r["inclusion"] == "included" for r in dets)  # M4.01 nc
    assert state["inclusion"]["nc75458907"]["tier"] == "secondary"
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

    monkeypatch.setattr(W, "live_issue", fail)
    state = W.step(tmp_path, tmp_path, {}, _get())
    errs = [r for r in _log(tmp_path) if r["kind"] == "detection"]
    assert all("RuntimeError" in r["error"] for r in errs)
    assert sorted(r["update_ms"] for r in errs) == [
        v["update_ms"] for v in W.new_versions(DOC, set())
    ]  # every version tried keeps its record
    monkeypatch.setattr(W, "live_issue", lambda *a, **k: pytest.fail("retried"))
    W.step(tmp_path, tmp_path, state, _get())


def test_aftershocks_and_small_events_are_not_run(tmp_path, monkeypatch):
    monkeypatch.setattr(W, "live_issue", lambda *a, **k: pytest.fail("excluded event was run"))
    lon, lat, _ = DOC["geometry"]["coordinates"]
    bigger = {"properties": {"mag": 6.5, "time": DOC["properties"]["time"] - 86_400_000,
                             "types": ",origin,"},
              "geometry": {"coordinates": [lon + 0.01, lat, 8.0]}}  # fmt: skip
    state = W.step(tmp_path, tmp_path, {}, _get([bigger]))
    assert {r["inclusion"] for r in _log(tmp_path) if r["kind"] == "detection"} == {"aftershock"}
    assert state["inclusion"]["nc75458907"]["reason"] == "aftershock"
    small = json.loads(json.dumps(DOC))
    small["properties"]["mag"] = 3.9
    (tmp_path / "s").mkdir()
    vs = [v["update_ms"] for v in W.new_versions(DOC, set())]
    small_state: dict = {"seen": {"nc75458907": vs[:-1]}}  # the newest version arrives later
    W.step(tmp_path / "s", tmp_path, small_state, _get(doc=small))
    assert {r["inclusion"] for r in _log(tmp_path / "s") if "inclusion" in r} == {"magnitude"}
    # the magnitude at first detection decides: a later upgrade to M4.1 changes nothing
    small_state["seen"]["nc75458907"] = vs[:-2]
    small["properties"]["mag"] = 4.1
    W.step(tmp_path / "s", tmp_path, small_state, _get(doc=small))
    assert small_state["inclusion"]["nc75458907"]["reason"] == "magnitude"


def test_a_failed_aftershock_query_is_retried_on_the_first_detection_values(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(W, "live_issue", lambda *a, **k: calls.append(a) or {})
    vs = [v["update_ms"] for v in W.new_versions(DOC, set())]
    state: dict = {"seen": {"nc75458907": vs[:-2]}}

    def down(url):
        if "minmagnitude" in url:
            raise TimeoutError("ComCat slow")
        return _get()(url)

    W.step(tmp_path, tmp_path, state, down)
    assert state["inclusion"]["nc75458907"]["reason"] == "pending" and not calls
    state["seen"]["nc75458907"] = vs[:-1]  # the next version arrives, magnitude revised down
    revised = json.loads(json.dumps(DOC))
    revised["properties"]["mag"] = 3.9
    W.step(tmp_path, tmp_path, state, _get(doc=revised))
    d = state["inclusion"]["nc75458907"]
    assert (d["tier"], d["reason"], d["mag"]) == ("secondary", "included", 4.01) and calls


def test_a_sequence_is_tracked_through_its_associated_ids(tmp_path, monkeypatch):
    vs = [v["update_ms"] for v in W.new_versions(DOC, set())]
    state = {
        "seen": {"us7000ttnj": vs[:-1]},
        "inclusion": {"us7000ttnj": {"tier": "secondary", "reason": "included"}},
    }
    built = {"matched_update_ms": vs[-1], "slot": "1d"}
    monkeypatch.setattr(W, "live_issue", lambda *a, **k: built)

    def no_context(url):
        assert "minmagnitude" not in url, "an included sequence is never checked again"
        return _get()(url)

    W.step(tmp_path, tmp_path, state, no_context)
    dets = [r for r in _log(tmp_path) if r["kind"] == "detection"]
    assert [r["update_ms"] for r in dets] == [vs[-1]] and dets[0]["key"] == "us7000ttnj"
    assert set(state["seen"]) == {"us7000ttnj"}


def test_receipts_come_from_the_branch_not_this_hosts_memory(worktree, tmp_path, monkeypatch):
    from laf import publish as U

    wt, origin, git = worktree
    monkeypatch.setattr(W, "repo_slug", lambda w: "o/r")
    out = tmp_path / "out"
    out.mkdir()
    seal = tmp_path / "answers.seal.json"
    items = {"nc1@live-matched": {"first_window_ms": 1_600_000},
             "nc1@live-strict": {"first_window_ms": 9_000_000}}  # fmt: skip
    seal.write_text(json.dumps({"items": items}) + "\n")
    rec = U.publish(wt, "nc1/5", seal, calendars=())
    acts = [{"before": "0" * 40, "after": rec["commit"], "timestamp": "1970-01-01T00:16:41Z"}]
    pages = []

    def page(url):
        pages.append(url)
        return json.dumps(acts).encode(), None

    state: dict = {}  # a restart lost what this host knew about the push
    W.check_receipts(out, state, wt, page)
    got = json.loads((wt / "nc1/5/receipt.json").read_text())
    assert got["receipt_ms"] == 1_001_000 and got["commit"] == rec["commit"]
    assert "nc1/5/receipt.json" in git("ls-tree", "-r", "--name-only", "live-test", cwd=origin)
    assert [r["matched_receipt_margin_s"] for r in _log(out) if r["kind"] == "receipt"] == [599.0]
    W.check_receipts(out, state, wt, page)
    assert len(pages) == 1  # nothing pending: GitHub is not asked again
    U.publish(wt, "nc1/6", seal, calendars=())  # GitHub never lists this push
    clock = [10**13]  # long after its commit: a push that failed for days still gets a day
    monkeypatch.setattr(W, "_now_ms", lambda: clock[0])
    W.check_receipts(out, state, wt, lambda url: (b"[]", None))
    assert state["receipts_missing"] == [] and state["receipts_since"] == {"nc1/6": 10**13}
    clock[0] += 86_400_001  # a day after it was first seen pushed
    W.check_receipts(out, state, wt, lambda url: (b"[]", None))
    assert state["receipts_missing"] == ["nc1/6"]
    assert _log(out)[-1]["receipt_ms"] is None  # listed as missing, once
    W.check_receipts(out, state, wt, lambda url: pytest.fail("asked again"))


def test_each_poll_looks_back_an_hour_and_forty_days_of_origins(tmp_path):
    from urllib.parse import parse_qs, urlparse

    from laf.usgs import iso

    urls = []
    since = 1_793_000_000_000

    def get(url):
        urls.append(url)
        return b'{"features": []}'

    state = W.step(tmp_path, tmp_path, {"last_poll_ms": since}, get)
    q = parse_qs(urlparse(urls[0]).query)
    assert q["updatedafter"] == [iso(since - 3_600_000)]  # a late-indexed version is seen again
    assert q["starttime"] == [iso(since - 3_600_000 - 40 * 86_400_000)]  # not ComCat's 30 days
    assert state["last_poll_ms"] > since


def test_sequences_older_than_the_start_are_not_admitted(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(W, "live_issue", lambda *a, **k: calls.append(a) or {})
    monkeypatch.setattr(W, "add_record", lambda *a, **k: None)
    origin = int(DOC["properties"]["time"])
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / "start.json").write_text(json.dumps({"start_ms": origin + 1}))  # L after its origin
    state = W.step(tmp_path, tmp_path, {}, _get(), publish_to=wt)
    assert state["inclusion"]["nc75458907"]["reason"] == "before the start" and not calls
    (wt / "start.json").write_text(json.dumps({"start_ms": origin}))  # L at its origin
    (tmp_path / "s").mkdir()
    state = W.step(tmp_path / "s", tmp_path, {}, _get(), publish_to=wt)
    d = state["inclusion"]["nc75458907"]
    assert d["reason"] == "included" and calls and d["detected_ms"] == state["last_poll_ms"]


def test_a_published_decision_survives_a_lost_local_state(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(W, "live_issue", lambda *a, **k: calls.append(a) or {})
    monkeypatch.setattr(W, "add_record", lambda *a, **k: None)  # no git outside a clone
    wt = tmp_path / "wt"
    (wt / "nc75458907").mkdir(parents=True)
    rec = {"key": "nc75458907", "tier": "primary", "reason": "included", "mag": 5.0, "lat": 0.0,
           "lon": 0.0, "time_ms": 1, "detected_ms": 2}  # fmt: skip
    (wt / "nc75458907/inclusion.json").write_text(json.dumps(rec))
    state = W.step(tmp_path, tmp_path, {}, _get(), publish_to=wt)  # ComCat now says M4.01
    assert state["inclusion"]["nc75458907"]["tier"] == "primary" and calls[0][-1] == "primary"
    # published under an ID that is no longer the preferred one: found through the event's
    # associated IDs, and tracked under its original key
    other = tmp_path / "other"
    (other / "us7000ttnj").mkdir(parents=True)
    (other / "us7000ttnj/inclusion.json").write_text(json.dumps(rec | {"key": "us7000ttnj"}))
    (tmp_path / "o").mkdir()
    state = W.step(tmp_path / "o", tmp_path, {}, _get(), publish_to=other)
    assert set(state["inclusion"]) == {"us7000ttnj"} and set(state["seen"]) == {"us7000ttnj"}
    assert state["inclusion"]["us7000ttnj"]["tier"] == "primary" and calls[1][-1] == "primary"


def test_the_paid_detector_publishes_its_start_once(worktree, tmp_path, monkeypatch):
    from laf import openai_runner, providers

    wt, origin, git = worktree
    monkeypatch.setattr(W, "branch", lambda w: "live")
    monkeypatch.setattr(W, "live_budget", lambda w: {})
    monkeypatch.setattr(openai_runner, "client", lambda: None)
    monkeypatch.setattr(providers, "client", lambda: None)
    args = (tmp_path / "out", tmp_path / "data", Path("data"))
    W.run(*args, polls=0, publish_to=wt, paid=True)
    start = json.loads((wt / "start.json").read_text())
    assert W.start_ms(wt) == start["start_ms"] and len(start["commit"]) == 40
    assert "start.json" in git("ls-tree", "--name-only", "live-test", cwd=origin)
    W.run(*args, polls=0, publish_to=wt, paid=True)  # a restart
    assert W.start_ms(wt) == start["start_ms"]  # L is never rewritten


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


def test_paid_runs_publish_to_live_and_the_dry_run_never_does(tmp_path, monkeypatch):
    on = ["live-test"]
    monkeypatch.setattr(W, "branch", lambda wt: on[0])
    with pytest.raises(SystemExit, match="--paid publishes"):
        W.run(tmp_path, tmp_path, Path("data"), polls=0, publish_to=tmp_path, paid=True)
    with pytest.raises(SystemExit, match="--paid publishes"):
        W.run(tmp_path, tmp_path, Path("data"), polls=0, paid=True)  # no worktree at all
    on[0] = "live"
    with pytest.raises(SystemExit, match="never publishes to live"):
        W.run(tmp_path, tmp_path, Path("data"), polls=0, publish_to=tmp_path)
    from laf import runner

    monkeypatch.setattr(runner, "env_value", lambda var: "")
    with pytest.raises(SystemExit, match="not set"):  # caps and reserves, before any poll
        W.run(tmp_path, tmp_path, Path("data"), polls=0, publish_to=tmp_path, paid=True)


def test_issues_are_released_only_after_every_window_closed(tmp_path, monkeypatch):
    released = []
    monkeypatch.setattr(W, "release", lambda wt, rel, d: released.append(rel) or "c")
    wt, data = tmp_path / "wt", tmp_path / "data"
    for rel, end in (("us1/1", 1_000), ("us1/2", 5_000), ("us2/1", 1_000), ("us3/1", 1_000)):
        (data / "issues" / rel).mkdir(parents=True)
        item = {"windows": [{"end_ms": end - 500}, {"end_ms": end}]}
        (data / "issues" / rel / "items.jsonl").write_text(json.dumps(item) + "\n")
        if rel != "us3/1":  # never published: nothing to release against
            (wt / rel).mkdir(parents=True)
            (wt / rel / "answers.seal.json").write_text("{}")
    monkeypatch.setattr(W, "released", lambda wt, rel: rel == "us2/1")  # committed before
    (data / "issues/us4/1").mkdir(parents=True)
    (data / "issues/us4/1/items.jsonl").write_text('{"windows": [{"end_ms": 1')  # truncated
    (wt / "us4/1").mkdir(parents=True)
    (wt / "us4/1/answers.seal.json").write_text("{}")
    W.release_closed(tmp_path, data, wt, now_ms=2_000)
    assert released == ["us1/1"]  # us1/2's month window is still open
    logged = {r["rel"]: r for r in _log(tmp_path) if r["kind"] == "release"}
    assert set(logged) == {"us1/1", "us4/1"} and "JSONDecodeError" in logged["us4/1"]["error"]


def test_the_inclusion_record_is_written_before_the_issue_runs(tmp_path, monkeypatch):
    added = []
    monkeypatch.setattr(W, "add_record", lambda wt, rel, name, r: added.append(name))

    def boom(*a, **k):
        raise RuntimeError("baselines failed after the answers were published")

    monkeypatch.setattr(W, "live_issue", boom)
    W.step(tmp_path, tmp_path, {}, _get(), publish_to=tmp_path)
    assert added == ["inclusion.json"]


def test_after_the_stop_no_new_sequence_is_admitted(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(W, "live_issue", lambda *a, **k: calls.append(a) or {})
    origin = int(DOC["properties"]["time"])
    monkeypatch.setattr(W, "admission_stop_ms", lambda path=None: origin - 1)  # S just before it
    state = W.step(tmp_path, tmp_path, {}, _get())
    assert state["inclusion"]["nc75458907"]["reason"] == "after the stop" and not calls
    monkeypatch.setattr(W, "admission_stop_ms", lambda path=None: origin)  # S at its origin
    (tmp_path / "s").mkdir()
    state = W.step(tmp_path / "s", tmp_path, {}, _get())
    assert state["inclusion"]["nc75458907"]["reason"] != "after the stop"  # [L, S] holds it
    kept = {"inclusion": {"nc75458907": {"tier": "secondary", "reason": "included"}}}
    (tmp_path / "b").mkdir()
    W.step(tmp_path / "b", tmp_path, kept, _get())
    assert calls  # admitted before the stop: its scheduled issues continue


def test_the_stop_is_read_from_the_checkout(tmp_path):
    assert W.admission_stop_ms(tmp_path / "missing.toml") is None
    stop = tmp_path / "live_stop.toml"
    stop.write_text("s_ms = 1793000000000\n")
    assert W.admission_stop_ms(stop) == 1793000000000


def test_the_paid_detector_never_reuses_the_dry_runs_folders(tmp_path, monkeypatch):
    import os
    import subprocess

    for k in [k for k in os.environ if k.startswith("GIT_")]:  # a commit hook's GIT_DIR etc.
        monkeypatch.delenv(k)
    live = tmp_path / "laf-live"
    subprocess.run(["git", "init", "-q", "-b", "live", str(live)], check=True)
    dry_out, dry_data = tmp_path / "dry", tmp_path / "dry-data"
    dry_out.mkdir()
    (dry_out / "state.json").write_text('{"last_poll_ms": 1}')  # a dry run's state, no marker
    with pytest.raises(SystemExit, match="holds the dry run"):
        W.run(dry_out, tmp_path / "new-data", Path("data"), polls=0, publish_to=live, paid=True)
    (dry_data / "issues").mkdir(parents=True)  # the dry run's issue folders
    with pytest.raises(SystemExit, match="holds the dry run"):
        W.run(tmp_path / "new", dry_data, Path("data"), polls=0, publish_to=live, paid=True)
    paid_data = tmp_path / "paid-data"
    paid_data.mkdir()
    (paid_data / "mode.txt").write_text("paid\n")
    with pytest.raises(SystemExit, match="holds the paid run"):
        W.run(tmp_path / "other", paid_data, Path("data"), polls=0)
