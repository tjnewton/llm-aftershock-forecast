import json

from laf import live_status as T

DAY = 86_400_000
L = 1_800_000_000_000


def _include(live, folder, origin, detected, **kw):
    (live / folder).mkdir(parents=True)
    rec = {"key": folder, "tier": "primary", "reason": "included", "mag": 5.2, "lat": 0.0,
           "lon": 0.0, "time_ms": origin, "detected_ms": detected} | kw  # fmt: skip
    (live / folder / "inclusion.json").write_text(json.dumps(rec))


def test_s_is_the_latest_origin_of_the_first_26_eligible_sequences(tmp_path):
    live = tmp_path / "live"
    for i in range(27):  # one a day; the 25th detected late, after the 26th
        detected = L + i * DAY + (2 * DAY if i == 24 else 3_600_000)
        _include(live, f"us{i:03d}", L + i * DAY, detected)
    _include(live, "us900", L - 1, L + 1)  # origin before L: retrospective
    _include(live, "us901", L + 2, L + 3, tier="secondary")
    _include(live, "us902", L + 2, L + 3, reason="aftershock", tier=None)
    _include(live, "us903", L, L + 3_600_000, key="us000")  # us000 under a new preferred ID
    seqs = T.eligible(live, L)
    assert len(seqs) == 27 and seqs[0]["key"] == "us000"  # counted once
    assert [r["folder"] for r in seqs[23:26]] == ["us023", "us025", "us024"]  # detection order
    s, why = T.stop_ms(L, seqs)
    assert s == L + 25 * DAY and "26" in why  # us025's origin: every one of the 26 in [L, S]
    assert T.stop_ms(L, seqs[:25]) == (L + 182 * DAY, "L + 182 days")


def test_the_status_flags_a_stale_detector_and_seals_without_receipts(tmp_path):
    live, out = tmp_path / "live", tmp_path / "out"
    (live / "us1/5").mkdir(parents=True)
    out.mkdir()
    (live / "start.json").write_text(json.dumps({"start_ms": L, "commit": "c" * 40}))
    (live / "us1/5/answers.seal.json").write_text(json.dumps({"sealed_ms": L + DAY}))
    spend = {"started_utc": "2027-01-15T00:00:00+00:00", "provider": "claude", "usd": 1.25}
    (live / "us1/5/spend.jsonl").write_text(json.dumps(spend) + "\n")
    polls = [{"kind": "poll", "poll_ms": L + 10 * DAY}, {"kind": "detection", "error": "x"}]
    (out / "log.jsonl").write_text("".join(json.dumps(r) + "\n" for r in polls))
    now = L + 10 * DAY + 3_600_000
    lines, attention = T.status(live, out, now_ms=now)
    assert any("Claude $1.25" in x for x in lines) and any(x.startswith("S: ") for x in lines)
    assert any("not polled" in x for x in attention)
    assert any("1 error records" in x for x in attention)
    assert any("1 waiting" in x for x in attention)
    (live / "us1/5/receipt.json").write_text("{}")
    (out / "log.jsonl").write_text(json.dumps({"kind": "poll", "poll_ms": now - 60_000}) + "\n")
    assert T.status(live, out, now_ms=now)[1] == []
