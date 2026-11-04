from laf.watch_pr import verdict

HEAD, PUSHED = "abcdef1234567890", "2026-11-03T10:00:00Z"
CODEX = {"login": "chatgpt-codex-connector[bot]", "id": 199175422}


def test_a_thumbs_up_after_the_head_approves():
    up = [{"user": CODEX, "content": "+1", "created_at": "2026-11-03T10:05:00Z"}]
    assert verdict(HEAD, PUSHED, up, [], [], []) == "approved"
    old = [{"user": CODEX, "content": "+1", "created_at": "2026-11-03T09:00:00Z"}]
    assert verdict(HEAD, PUSHED, old, [], [], []) == "waiting"  # on an earlier head
    someone = [{**up[0], "user": {"login": "tjnewton", "id": 1}}]
    assert verdict(HEAD, PUSHED, someone, [], [], []) == "waiting"
    lookalike = [{**up[0], "user": {"login": "codex-fan", "id": 2}}]  # a name is not trust
    assert verdict(HEAD, PUSHED, lookalike, [], [], []) == "waiting"


def test_a_receipt_must_name_the_head():
    body = f"Codex Review: Didn't find any major issues. Reviewed commit: `{HEAD[:10]}`"
    ok = [{"user": CODEX, "created_at": "2026-11-03T10:05:00Z", "body": body}]
    assert verdict(HEAD, PUSHED, [], ok, [], []) == "approved"
    other = [{**ok[0], "body": body.replace(HEAD[:10], "0000000000")}]
    assert verdict(HEAD, PUSHED, [], other, [], []) == "waiting"


def test_findings_failing_and_pending_checks_stop_or_wait():
    up = [{"user": CODEX, "content": "+1", "created_at": "2026-11-03T10:05:00Z"}]
    finding = [{"user": CODEX, "original_commit_id": HEAD}]
    assert verdict(HEAD, PUSHED, up, [], finding, []) == "findings"
    assert verdict(HEAD, PUSHED, up, [], [], [{"bucket": "fail"}]) == "failing"
    assert verdict(HEAD, PUSHED, up, [], [], [{"bucket": "pending"}]) == "waiting"
    stale = [{"user": CODEX, "original_commit_id": "1111111111"}]  # on an earlier head
    assert verdict(HEAD, PUSHED, up, [], stale, [{"bucket": "pass"}]) == "approved"


def test_approval_is_dated_by_the_push_and_the_merge_pinned_to_the_head(monkeypatch):
    from laf import watch_pr as W

    acts = [{"after": "old", "timestamp": "2026-11-03T08:00:00Z"},
            {"after": HEAD, "timestamp": PUSHED}]  # fmt: skip
    pr = {"state": "open", "head": {"sha": HEAD, "ref": "feat/x"}}
    # the thumbs-up came after the commit's own date but before its push: not for this head
    early = [{"user": CODEX, "content": "+1", "created_at": "2026-11-03T09:30:00Z"}]
    late = [{"user": CODEX, "content": "+1", "created_at": "2026-11-03T10:30:00Z"}]
    calls = []
    for reactions, merges in ((early, False), (late, True)):
        api = {"pulls/7?per_page=100": pr, "activity?ref=feat/x&per_page=100": acts,
               "issues/7/reactions?per_page=100": reactions,
               "issues/7/comments?per_page=100": [], "pulls/7/comments?per_page=100": [],
               "pulls/7": {"merged": True}}  # fmt: skip
        monkeypatch.setattr(W, "_api", lambda path, api=api: api[path])
        monkeypatch.setattr(W, "_checks", lambda n: [])
        monkeypatch.setattr(W.subprocess, "run", lambda args, **k: calls.append(args))
        line = W.step(7)
        assert (line or "").startswith("PR 7: MERGED") if merges else line is None
    assert calls == [["gh", "pr", "merge", "7", "--squash", "--match-head-commit", HEAD]]
    # no activity record of the head yet: wait, whatever the reactions say
    monkeypatch.setattr(W, "_api", lambda path: [] if path.startswith("activity") else (
        pr if path.startswith("pulls/7?") else late))  # fmt: skip
    assert W.step(7) is None
