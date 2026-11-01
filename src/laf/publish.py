"""Publishing sealed live records (prereg v2 section 5; ADR 0017 decision 7).

A seal file (`answers.seal.json`, `baselines.seal.json`: hashes and the seal time, no forecast)
is committed to a branch's worktree and pushed at once. GitHub's record of that push (the
repository activity API) is the registered on-time time. OpenTimestamps proofs of the same file,
one per public calendar, follow in a second commit, so a slow calendar never delays the push;
they are an independent witness, completed once Bitcoin confirms (`ots upgrade`). The full
records are released after their windows close. The study publishes to `live`; the dry run to
`live-test`, so the study branch holds study records only.
"""

import contextlib
import hashlib
import json
import re
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from laf.usgs import USER_AGENT, download

# the official client's default aggregators (opentimestamps-client)
CALENDARS = (
    "https://a.pool.opentimestamps.org",
    "https://b.pool.opentimestamps.org",
    "https://a.pool.eternitywall.com",
)
# detached timestamp file, format version 1: magic, version, file hash op (SHA-256), digest,
# then the calendar's serialized timestamp for that digest
OTS_HEADER = b"\x00OpenTimestamps\x00\x00Proof\x00\xbf\x89\xe2\xe8\x84\xe8\x92\x94\x01\x08"
OTS_PENDING = bytes.fromhex("83dfe30d2ef90c8e")  # pending-attestation tag
PUSH_ATTEMPTS = 3


def _post(url: str, body: bytes) -> bytes:
    req = urllib.request.Request(
        url, data=body,
        headers={"Accept": "application/vnd.opentimestamps.v1", "User-Agent": USER_AGENT},
    )  # fmt: skip
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def ots_proof(data: bytes, calendar: str, post=_post) -> bytes:
    """A detached OpenTimestamps proof of `data` from one calendar (pending until Bitcoin
    confirms). Only the SHA-256 leaves this machine."""
    digest = hashlib.sha256(data).digest()
    stamp = post(f"{calendar}/digest", digest)
    if OTS_PENDING not in stamp:
        raise ValueError(f"{calendar}: no pending attestation in the reply")
    return OTS_HEADER + digest + stamp


def _git(worktree: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(worktree), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit_push(worktree: Path, paths: list[str], message: str) -> str:
    _git(worktree, "add", "--", *paths)
    _git(worktree, "commit", "-q", "-m", message)
    for i in range(PUSH_ATTEMPTS):
        try:
            _git(worktree, "push", "-q", "origin", "HEAD")
            break
        except subprocess.CalledProcessError:
            if i == PUSH_ATTEMPTS - 1:
                raise
            time.sleep(5 * (i + 1))
            with contextlib.suppress(subprocess.CalledProcessError):  # another host pushed first
                _git(worktree, "pull", "-q", "--rebase", "origin", branch(worktree))
    return _git(worktree, "rev-parse", "HEAD")


def publish(
    worktree: Path, rel: str, seal: Path, *, extra: tuple[Path, ...] = (), ots=ots_proof,
    calendars=CALENDARS,
) -> dict:  # fmt: skip
    """Push `seal` (and `extra` files, such as the issue's spend file) to `<worktree>/<rel>/`,
    then the seal's calendar proofs. Returns the commit, the local time the push returned and
    the calendars that answered; a calendar failure is recorded, a push failure raises."""
    dest = worktree / rel
    if (dest / seal.name).exists():
        raise FileExistsError(f"{rel}/{seal.name} is already published: never overwritten")
    dest.mkdir(parents=True, exist_ok=True)
    data = seal.read_bytes()
    for f in (seal, *extra):
        (dest / f.name).write_bytes(f.read_bytes())
    paths = [f"{rel}/{f.name}" for f in (seal, *extra)]
    commit = _commit_push(worktree, paths, f"Seal {rel}/{seal.name}")
    rec: dict = {
        "commit": commit, "pushed_ms": int(time.time() * 1000), "ots": {},
        "repo": repo_slug(worktree), "branch": branch(worktree),
    }  # fmt: skip
    proofs = []
    for cal in calendars:
        name = f"{seal.name}.{re.sub(r'^https://', '', cal)}.ots"
        try:
            (dest / name).write_bytes(ots(data, cal))
            proofs.append(f"{rel}/{name}")
            rec["ots"][cal] = "pending"
        except Exception as e:  # an outage must not lose the record or the push
            rec["ots"][cal] = f"{type(e).__name__}: {e}"[:200]
    if proofs:
        rec["ots_commit"] = _commit_push(worktree, proofs, f"Timestamps {rel}/{seal.name}")
    return rec


NOTICE = (
    "Research forecasts from the llm-aftershock-forecast study (docs/preregistration-v2.md on\n"
    "post-submission), released after every forecast window of this issue closed. They are not\n"
    "official forecasts and must not be used as such; official aftershock forecasts come from\n"
    "the USGS.\n"
)
SEALS = ("answers.seal.json", "baselines.seal.json")


def release(worktree: Path, rel: str, record_dir: Path) -> str | None:
    """Publish an issue's full records once its windows have closed: every file named in the
    manifests of its seals on the branch, each checked against the published hash first, and a
    notice that these are not official forecasts. Returns the commit, or None if already
    released; a file that differs from its seal is never released."""
    dest = worktree / rel
    if released(worktree, rel):
        return None
    files: dict[str, bytes] = {}
    for seal in SEALS:
        if not (dest / seal).exists():  # e.g. the baselines push failed: nothing to check against
            continue
        for name, sha in json.loads((dest / seal).read_text(encoding="utf-8"))["manifest"].items():
            data = (record_dir / name).read_bytes()
            if hashlib.sha256(data).hexdigest() != sha:
                raise ValueError(f"{rel}/{name} differs from its published seal: not released")
            files[name] = data
    if not files:
        raise FileNotFoundError(f"{rel}: no seal on the branch")
    for name, data in files.items():
        (dest / name).write_bytes(data)
    (dest / "NOTICE.txt").write_text(NOTICE, encoding="utf-8", newline="\n")
    paths = [f"{rel}/{n}" for n in (*files, "NOTICE.txt")]
    return _commit_push(worktree, paths, f"Release {rel} (windows closed; not official forecasts)")


def _committed(worktree: Path, path: str) -> bool:
    shown = subprocess.run(["git", "-C", str(worktree), "cat-file", "-e", f"HEAD:{path}"],
                           capture_output=True)  # fmt: skip
    return shown.returncode == 0


def released(worktree: Path, rel: str) -> bool:
    """The release is committed (its notice is in HEAD); `push_pending` gets it to the remote."""
    return _committed(worktree, f"{rel}/NOTICE.txt")


def push_pending(worktree: Path) -> int:
    """Push local commits the remote does not have yet (a seal or a release whose push failed
    earlier); returns how many there were."""
    ahead = int(_git(worktree, "rev-list", "--count", f"origin/{branch(worktree)}..HEAD"))
    if ahead:
        _git(worktree, "push", "-q", "origin", "HEAD")
    return ahead


def add_record(worktree: Path, rel: str, name: str, rec: dict) -> str:
    """Commit and push one small JSON record (such as an issue's push receipt) beside its
    seal; returns the commit. Never overwrites."""
    path = worktree / rel / name
    if path.exists():
        raise FileExistsError(f"{rel}/{name} is already published: never overwritten")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(rec, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    return _commit_push(worktree, [f"{rel}/{name}"], f"Receipt {rel}/{name}")


def branch(worktree: Path) -> str:
    return _git(worktree, "branch", "--show-current")


def repo_slug(worktree: Path) -> str | None:
    """owner/name of the worktree's GitHub origin (None for another remote: no receipt)."""
    url = _git(worktree, "remote", "get-url", "origin")
    m = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
    return m.group(1) if m else None


def push_receipt(repo: str, branch: str, commit: str, get=download) -> int | None:
    """GitHub's time (epoch ms) of the push that moved `branch` to `commit`, or None while the
    activity list does not show it yet."""
    url = (f"https://api.github.com/repos/{repo}/activity?ref=refs/heads/{branch}"
           "&activity_type=push&per_page=100")  # fmt: skip
    for a in json.loads(get(url)):
        if a.get("after") == commit:
            return int(
                datetime.fromisoformat(a["timestamp"].replace("Z", "+00:00")).timestamp() * 1000
            )
    return None
