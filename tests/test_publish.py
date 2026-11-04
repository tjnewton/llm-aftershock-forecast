import hashlib
import json
import subprocess

import pytest

from laf import publish as U

STAMP = b"\xf0\x10" + b"n" * 16 + b"\x08\x00" + U.OTS_PENDING + b"\x1ahttps://a.example/calendar"


def test_a_proof_is_the_v1_header_the_digest_and_the_calendar_stamp():
    sent = []
    proof = U.ots_proof(
        b"seal", "https://cal.example", post=lambda u, b: sent.append((u, b)) or STAMP
    )
    digest = hashlib.sha256(b"seal").digest()
    assert sent == [("https://cal.example/digest", digest)]  # only the hash leaves
    assert proof == U.OTS_HEADER + digest + STAMP
    with pytest.raises(ValueError, match="no pending attestation"):
        U.ots_proof(b"seal", "https://cal.example", post=lambda u, b: b"garbage")


def test_publish_pushes_the_seal_then_its_proofs(worktree, tmp_path):
    wt, origin, git = worktree
    seal = tmp_path / "answers.seal.json"
    seal.write_text('{"record_sha256": "abc"}\n')

    def ots(data, cal):
        if "down" in cal:
            raise TimeoutError("calendar down")
        return U.OTS_HEADER + hashlib.sha256(data).digest() + STAMP

    rec = U.publish(
        wt, "us1/123", seal, ots=ots, calendars=("https://up.example", "https://down.example")
    )
    log = git("log", "--format=%H %s", "live-test", cwd=origin).splitlines()
    assert [x.split(" ", 1)[1] for x in log[:2]] == [
        "Timestamps us1/123/answers.seal.json", "Seal us1/123/answers.seal.json"]  # fmt: skip
    assert log[1].split()[0] == rec["commit"] and log[0].split()[0] == rec["ots_commit"]
    assert (
        rec["ots"]["https://up.example"] == "pending"
        and "TimeoutError" in rec["ots"]["https://down.example"]
    )
    assert rec["branch"] == "live-test" and rec["repo"] is None  # a local origin: no receipt
    shown = git("show", f"{rec['commit']}:us1/123/answers.seal.json", cwd=origin)
    assert shown == seal.read_text().strip()
    with pytest.raises(FileExistsError, match="never overwritten"):
        U.publish(wt, "us1/123", seal, ots=ots, calendars=())
    tree = git("ls-tree", "-r", "--name-only", "live-test", cwd=origin).splitlines()
    pub = "us1/123/answers.seal.json"
    assert tree == ["README.md", pub, f"{pub}.up.example.ots"]


def test_the_push_time_excludes_calendar_waits(worktree, tmp_path, monkeypatch):
    wt, _, _ = worktree
    seal = tmp_path / "answers.seal.json"
    seal.write_text("{}\n")
    clock = [1_000.0]
    monkeypatch.setattr(U.time, "time", lambda: clock[0])

    def slow(data, cal):
        clock[0] += 30.0  # a calendar timing out
        raise TimeoutError("slow calendar")

    rec = U.publish(
        wt, "us1/9", seal, ots=slow, calendars=("https://a.example", "https://b.example")
    )
    assert rec["pushed_ms"] == 1_000_000 and clock[0] == 1_060.0


def test_the_receipt_is_githubs_time_of_the_push_that_first_held_the_commit():
    a, b, c, d = ("a" * 40, "b" * 40, "c" * 40, "d" * 40)
    page1 = [{"before": c, "after": d, "timestamp": "2026-11-01T15:00:00Z"},
             {"before": b, "after": c, "timestamp": "2026-11-01T14:55:00Z"}]  # fmt: skip
    page2 = [{"before": "0" * 40, "after": a, "timestamp": "2026-11-01T14:51:11Z"}]
    urls = []

    def page(url):
        urls.append(url)
        return (json.dumps(page1).encode(), "next") if len(urls) == 1 else (
            json.dumps(page2).encode(), None)  # fmt: skip

    t = 1793544000000  # the commits' time, before every push
    assert U.push_times("o/r", "live", {a: t}, page) == {a: 1793544671000}  # on page 2
    assert "ref=refs/heads/live" in urls[0] and "activity_type=push" in urls[0]
    urls.clear()
    # pushed together with c (an earlier push failed): found through the commits c's push added
    added = {(b, c): {"e" * 40, c}}
    got = U.push_times("o/r", "live", {"e" * 40: t}, page,
                       introduced=lambda x, y: added.get((x, y), {y}))  # fmt: skip
    assert got == {"e" * 40: 1793544900000} and len(urls) == 1  # no exact match, still page 1
    urls.clear()
    late = 1793552100000  # made 2 h after page 1's oldest push: page 2 cannot hold it
    assert U.push_times("o/r", "live", {"f" * 40: late}, page) == {} and len(urls) == 1


def test_a_failed_proof_push_keeps_the_seals_record(worktree, tmp_path, monkeypatch):
    wt, origin, git = worktree
    seal = tmp_path / "answers.seal.json"
    seal.write_text("{}\n")
    real, n = U._commit_push, []

    def flaky(*a, **k):
        n.append(1)
        if len(n) == 2:  # the proofs' push, after the seal's
            raise subprocess.CalledProcessError(128, "git push")
        return real(*a, **k)

    monkeypatch.setattr(U, "_commit_push", flaky)
    proof = lambda data, cal: U.OTS_HEADER + hashlib.sha256(data).digest() + STAMP  # noqa: E731
    rec = U.publish(wt, "us1/7", seal, ots=proof, calendars=("https://up.example",))
    assert rec["commit"] == git("rev-parse", "live-test", cwd=origin)  # the seal is out
    assert "CalledProcessError" in rec["ots_error"] and "ots_commit" not in rec
    assert U.seal_commit(wt, "us1/7") == (
        rec["commit"],
        int(git("log", "-1", "--format=%ct")) * 1000,
    )
    assert U.seal_commit(wt, "us1/8") is None


def test_release_checks_every_file_against_its_published_seal(worktree, tmp_path):
    wt, origin, git = worktree
    rec = tmp_path / "rec"
    rec.mkdir()
    bodies = {"items.jsonl": '{"a": 1}\n', "calls.jsonl": '{"text": "forecast"}\n'}
    for name, body in bodies.items():
        (rec / name).write_bytes(body.encode())  # no newline translation (Windows)
    manifest = {n: hashlib.sha256(b.encode()).hexdigest() for n, b in bodies.items()}
    (rec / "answers.seal.json").write_text(json.dumps({"manifest": manifest}) + "\n")
    U.publish(wt, "us1/1", rec / "answers.seal.json", calendars=())
    assert not (wt / "us1/1/calls.jsonl").exists()  # forecasts stay unpublished until release
    commit = U.release(wt, "us1/1", rec)
    tree = git("ls-tree", "-r", "--name-only", commit, cwd=origin).splitlines()
    assert {"us1/1/items.jsonl", "us1/1/calls.jsonl", "us1/1/NOTICE.txt"} <= set(tree)
    assert "not official forecasts" in " ".join((wt / "us1/1/NOTICE.txt").read_text().split())
    assert U.release(wt, "us1/1", rec) is None  # once
    U.publish(wt, "us1/2", rec / "answers.seal.json", calendars=())
    (rec / "calls.jsonl").write_text('{"text": "edited after the seal"}\n')
    with pytest.raises(ValueError, match="differs from its published seal"):
        U.release(wt, "us1/2", rec)
    assert not (wt / "us1/2/NOTICE.txt").exists()


def test_a_release_whose_push_failed_is_pushed_on_a_later_poll(worktree, tmp_path):
    wt, origin, git = worktree
    rec = tmp_path / "rec"
    rec.mkdir()
    (rec / "items.jsonl").write_bytes(b"{}\n")  # no newline translation (Windows)
    sha = hashlib.sha256(b"{}\n").hexdigest()
    (rec / "answers.seal.json").write_text(json.dumps({"manifest": {"items.jsonl": sha}}) + "\n")
    U.publish(wt, "us1/1", rec / "answers.seal.json", calendars=())
    hook = origin / "hooks/pre-receive"
    hook.write_text("#!/bin/sh\nexit 1\n")  # the remote refuses every push for now
    hook.chmod(0o755)
    U.PUSH_ATTEMPTS, attempts = 1, U.PUSH_ATTEMPTS
    try:
        with pytest.raises(subprocess.CalledProcessError):
            U.release(wt, "us1/1", rec)
    finally:
        U.PUSH_ATTEMPTS = attempts
    assert U.released(wt, "us1/1")  # committed here, not yet on the remote
    assert "us1/1/NOTICE.txt" not in git("ls-tree", "-r", "--name-only", "live-test", cwd=origin)
    hook.unlink()
    assert U.push_pending(wt) == 1 and U.push_pending(wt) == 0
    assert "us1/1/NOTICE.txt" in git("ls-tree", "-r", "--name-only", "live-test", cwd=origin)


def test_stamp_writes_a_proof_per_answering_calendar(tmp_path):
    f = tmp_path / "freeze_manifest.json"
    f.write_bytes(b"{}")

    def ots(data, cal):
        if "down" in cal:
            raise TimeoutError("calendar down")
        return b"proof:" + data

    names, status = U.stamp(f, ots=ots, calendars=("https://up.example", "https://down.example"))
    assert names == ["freeze_manifest.json.up.example.ots"]
    assert (tmp_path / names[0]).read_bytes() == b"proof:{}"
    assert (
        status["https://up.example"] == "pending"
        and "TimeoutError" in status["https://down.example"]
    )
