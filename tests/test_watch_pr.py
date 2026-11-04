from laf.watch_pr import verdict

HEAD, PUSHED = "abcdef1234567890", "2026-11-03T10:00:00Z"
CODEX = {"login": "chatgpt-codex-connector[bot]"}


def test_a_thumbs_up_after_the_head_approves():
    up = [{"user": CODEX, "content": "+1", "created_at": "2026-11-03T10:05:00Z"}]
    assert verdict(HEAD, PUSHED, up, [], [], []) == "approved"
    old = [{"user": CODEX, "content": "+1", "created_at": "2026-11-03T09:00:00Z"}]
    assert verdict(HEAD, PUSHED, old, [], [], []) == "waiting"  # on an earlier head
    someone = [
        {"user": {"login": "tjnewton"}, "content": "+1", "created_at": "2026-11-03T10:05:00Z"}
    ]
    assert verdict(HEAD, PUSHED, someone, [], [], []) == "waiting"


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
