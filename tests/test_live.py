from pathlib import Path

from laf.live import HOUR_MS, live_items, next_full_hour
from laf.registry import load_sequences

PANAMA = next(s for s in load_sequences(Path("config/sequences.toml")) if s.id == "us6000u18k")
NOW = 1792593000000  # 2026-10-21 14:30 UTC


def test_next_full_hour():
    assert next_full_hour(NOW) == 1792594800000
    assert next_full_hour(1792594800000) == 1792594800000


def test_live_items_see_only_events_before_their_cutoff():
    strict = next_full_hour(NOW + 50 * 60_000)
    items, _ = live_items(Path("data"), "20261021T1027Z", PANAMA, NOW, strict)
    matched, strict_item = items
    assert [i.item_id for i in items] == ["us6000u18k@live-matched", "us6000u18k@live-strict"]
    assert all(w.start_ms == strict for w in strict_item.windows)
    assert strict_item.issue_ms == NOW and strict - NOW >= HOUR_MS / 2
    assert matched.issue_ms <= min(w.start_ms for w in matched.windows) + 60_000
    for i in items:
        elapsed = (i.issue_ms - i.mainshock.origin_ms) / 86_400_000
        assert all(r.t_days < elapsed for r in i.catalog)
        assert [w.key for w in i.windows] == ["day", "week", "month"]
