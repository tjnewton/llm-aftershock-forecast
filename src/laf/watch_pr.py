"""`laf watch-pr N [N ...]`: wait for Codex on each pull request's current head and squash-merge
it once approved, the routine merge Tyler allowed: a Codex thumbs-up, or its "didn't find any
major issues" receipt naming the head, after GitHub recorded the push of that head (the
repository activity API; a commit's own date can predate its push); no Codex review comment on
the head; no failing or pending check. Only the Codex connector's account counts, and the merge
is pinned to the approved head (`--match-head-commit`). A pull request with findings or failing
checks is reported and left alone. Prints one line per pull request when it settles."""

import json
import subprocess
import time


def _gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def _api(path: str):
    return json.loads(_gh("api", f"repos/:owner/:repo/{path}"))


CODEX_ID = 199175422  # chatgpt-codex-connector[bot]: the only trusted reviewer


def _is_codex(item: dict) -> bool:
    return (item.get("user") or {}).get("id") == CODEX_ID


def verdict(head: str, pushed: str, reactions: list, comments: list, reviews: list,
            checks: list) -> str:  # fmt: skip
    """ "findings", "failing", "approved" or "waiting" for a head pushed at `pushed` (ISO time)."""
    if any(_is_codex(c) and c.get("original_commit_id") == head for c in reviews):
        return "findings"
    if any(c.get("bucket") == "fail" for c in checks):
        return "failing"
    up = any(_is_codex(r) and r["content"] == "+1" and r["created_at"] > pushed for r in reactions)
    receipt = any(
        _is_codex(c) and c["created_at"] > pushed and "find any major issues" in c["body"]
        and head[:10] in c["body"] for c in comments
    )  # fmt: skip
    pending = any(c.get("bucket") == "pending" for c in checks)
    return "approved" if (up or receipt) and not pending else "waiting"


def _checks(pr: int) -> list:
    # `gh pr checks` exits non-zero while checks fail or wait, and with no checks at all
    r = subprocess.run(["gh", "pr", "checks", str(pr), "--json", "bucket"],
                       capture_output=True, text=True)  # fmt: skip
    return json.loads(r.stdout) if r.stdout.strip().startswith("[") else []


def _pushed(branch: str, head: str) -> str | None:
    """When `head` became the tip of `branch` (its push or the branch's creation), or None."""
    acts = _api(f"activity?ref={branch}&per_page=100")
    times = [a["timestamp"] for a in acts if a.get("after") == head]
    return max(times) if times else None


def step(pr: int) -> str | None:
    """One look at `pr`: a final line, or None while it waits."""
    p = _api(f"pulls/{pr}?per_page=100")
    if p["state"] != "open":
        return f"PR {pr}: {'MERGED' if p.get('merged') else p['state']}"
    head = p["head"]["sha"]
    pushed = _pushed(p["head"]["ref"], head)
    if pushed is None:  # no record of the push yet: approval cannot be dated
        return None
    v = verdict(head, pushed, _api(f"issues/{pr}/reactions?per_page=100"),
                _api(f"issues/{pr}/comments?per_page=100"),
                _api(f"pulls/{pr}/comments?per_page=100"), _checks(pr))  # fmt: skip
    if v == "findings":
        return f"PR {pr}: Codex findings on {head[:10]}"
    if v == "failing":
        return f"PR {pr}: failing checks"
    if v == "approved":
        subprocess.run(["gh", "pr", "merge", str(pr), "--squash", "--match-head-commit", head],
                       capture_output=True)  # fmt: skip
        merged = _api(f"pulls/{pr}").get("merged")
        return f"PR {pr}: {'MERGED' if merged else 'approved, merge refused'} ({head[:10]})"
    return None


def watch(prs: list[int], minutes: int = 45, every_s: int = 60) -> None:
    left = list(prs)
    for _ in range(minutes):
        for pr in list(left):
            line = step(pr)
            if line:
                print(line, flush=True)
                left.remove(pr)
        if not left:
            return
        time.sleep(every_s)
    print(f"timed out waiting on: {' '.join(map(str, left))}", flush=True)
