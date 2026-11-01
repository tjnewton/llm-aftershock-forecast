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


@pytest.fixture
def worktree(tmp_path, monkeypatch):
    """A clone of a local bare repository: the live branch's worktree with its origin."""
    import os

    for var in [v for v in os.environ if v.startswith("GIT_")]:  # e.g. set by pre-commit hooks
        monkeypatch.delenv(var)
    origin, wt = tmp_path / "origin.git", tmp_path / "wt"

    def git(*a, cwd=wt):
        return subprocess.run(["git", "-C", str(cwd), *a], check=True, capture_output=True,
                              text=True).stdout.strip()  # fmt: skip

    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    subprocess.run(["git", "clone", "-q", str(origin), str(wt)], check=True, capture_output=True)
    for k, v in (
        ("user.email", "t@example.invalid"),
        ("user.name", "t"),
        ("core.hooksPath", "/dev/null"),
    ):
        git("config", k, v)
    git("checkout", "-q", "-b", "live-test")
    (wt / "README.md").write_text("live-test\n")
    git("add", "README.md")
    git("commit", "-qm", "start")
    git("push", "-q", "-u", "origin", "live-test")
    return wt, origin, git


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


def test_the_receipt_is_githubs_time_for_the_push_of_that_commit():
    acts = [{"after": "b" * 40, "timestamp": "2026-11-01T15:00:00Z"},
            {"after": "a" * 40, "timestamp": "2026-11-01T14:51:11Z"}]  # fmt: skip
    urls = []
    get = lambda url: urls.append(url) or json.dumps(acts).encode()  # noqa: E731
    assert U.push_receipt("o/r", "live", "a" * 40, get) == 1793544671000
    assert "ref=refs/heads/live" in urls[0] and "activity_type=push" in urls[0]
    assert U.push_receipt("o/r", "live", "c" * 40, get) is None
