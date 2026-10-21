import json
import shutil
from pathlib import Path

import pandas as pd

from laf.generic_rj import REFERENCE_REL
from laf.registry import Sequence
from laf.tables import DAY_MS, add_months, build_tables, select_issue_times
from laf.usgs import store

GOLDEN = Path(__file__).parent / "golden"
ORIGIN = 1791568566036  # Panama mainshock, ms
V1_UPDATE = 1791593712688


def test_select_issue_times_picks_first_version_at_or_after_each_target():
    creations = [ORIGIN + int(h * 3_600_000) for h in (6.9, 22.0, 30.0, 75.0, 170.0, 200.0)]
    picks = select_issue_times(ORIGIN, creations, targets_days=(1, 3, 7, 14))
    assert [(p.target, p.issue_ms) for p in picks] == [
        ("first", creations[0]),
        ("1d", creations[2]),  # 22 h is before the 1-day target
        ("3d", creations[3]),
        ("7d", creations[4]),
    ]  # no version within the 14-day tolerance window, so no 14d issue time


def test_select_issue_times_merges_targets_that_hit_the_same_version():
    creations = [ORIGIN + DAY_MS + 60_000]
    picks = select_issue_times(ORIGIN, creations, targets_days=(1,))
    assert [(p.target, p.issue_ms) for p in picks] == [("first+1d", creations[0])]


def test_select_issue_times_without_oaf_uses_the_schedule():
    picks = select_issue_times(ORIGIN, None, targets_days=(1, 3))
    assert [(p.target, p.issue_ms) for p in picks] == [
        ("first", ORIGIN + int(0.3 * DAY_MS)),
        ("1d", ORIGIN + DAY_MS),
        ("3d", ORIGIN + 3 * DAY_MS),
    ]


def test_add_months_is_calendar_month_like_oaf():
    # Panama v1 "1 Month" window starts 2026-10-10 and is 31 days long.
    assert add_months(1791594028116, 1) - 1791594028116 == 31 * DAY_MS


def _mini_snapshot(tmp_path: Path) -> Path:
    data = tmp_path / "data"
    repo_ref = Path(__file__).parents[1] / "data" / REFERENCE_REL
    shutil.copytree(repo_ref, data / REFERENCE_REL)
    event = json.loads((GOLDEN / "event_us6000u18k_trimmed.geojson").read_bytes())
    event["properties"]["products"]["oaf"] = [
        p for p in event["properties"]["products"]["oaf"] if p["updateTime"] == V1_UPDATE
    ]
    snap = "raw/snapshots/20261019T0000Z"
    store(
        data, f"{snap}/event/us6000u18k.geojson.gz", json.dumps(event).encode(), "x", compress=True
    )
    store(
        data,
        f"raw/oaf/us6000u18k/{V1_UPDATE}.json",
        (GOLDEN / f"oaf_us6000u18k_{V1_UPDATE}.json").read_bytes(),
        "x",
    )
    store(
        data,
        f"{snap}/catalog/us6000u18k.csv",
        (GOLDEN / "comcat_us6000u18k_2d_m4.5.csv").read_bytes(),
        "x",
    )
    meta = {
        "catalog_end_ms": ORIGIN + 2 * DAY_MS,
        "center_lat": 7.5868,
        "center_lon": -80.769,
        "radius_km": 600.0,
    }
    store(data, f"{snap}/catalog/us6000u18k.meta.json", json.dumps(meta).encode(), "x")
    return data


def test_build_tables_from_golden_snapshot(tmp_path: Path):
    data = _mini_snapshot(tmp_path)
    seq = Sequence(id="us6000u18k", name="Panama", role="test-post", catalog_min_mag=3.0)
    t = build_tables(data, "20261019T0000Z", [seq])

    s = t["sequences"].iloc[0]
    assert (s["origin_ms"], s["mag"], s["n_oaf_versions"]) == (ORIGIN, 7.7, 1)
    assert (s["generic_regime"], s["generic_a_mean"], s["magcomp_region"]) == (
        "SZ-GENERIC",
        -2.47,
        "WORLD",
    )

    v = t["oaf_versions"].iloc[0]
    assert v["creation_ms"] == 1791593462216
    assert v["obs_m5"] == 11 and pd.isna(v["obs_m4"])  # Panama v1 reports no M4 observation

    bins = t["forecast_bins"]
    assert len(bins) == 4 * 6  # 4 windows x M3..M8
    fr = t["forecast_fractiles"]
    assert len(fr) == 4 * 6 * 399

    issues = t["issue_times"]
    assert issues["target"].tolist() == ["first"]

    obs = t["observed_counts"]
    day_m5 = obs[(obs["window"] == "1 Day") & (obs["magnitude"] == 5.0)].iloc[0]
    week_m5 = obs[(obs["window"] == "1 Week") & (obs["magnitude"] == 5.0)].iloc[0]
    assert day_m5["count"] == 2
    assert bool(day_m5["closed"]) is True
    assert bool(week_m5["closed"]) is False  # catalog ends at day 2

    cat = t["catalog"]
    assert cat["t_days"].min() == 0.0 and (cat["sequence_id"] == "us6000u18k").all()


def test_issue_times_carry_their_scoring_circle(tmp_path: Path):
    data = _mini_snapshot(tmp_path)
    seq = Sequence(id="us6000u18k", name="Panama", role="test-post", catalog_min_mag=3.0)
    it = build_tables(data, "20261019T0000Z", [seq])["issue_times"].iloc[0]
    assert (it["region_lat"], it["region_lon"], it["region_radius_km"]) == (7.5735, -80.8225, 381.6)
    assert it["mag_main"] == 7.7 and it["oaf_obs_m5"] == 11
    assert it["comcat_m5_at_cutoff"] >= 0 and bool(it["query_covers_x1_5"]) is True
    assert (it["oaf_mc"], it["oaf_b"], it["oaf_ams"], it["oaf_a"]) == (4.95, 1.0, -2.07, -2.31)


def test_items_never_show_events_at_or_after_the_issue_time(tmp_path: Path):
    from laf.items import build_items

    data = _mini_snapshot(tmp_path)
    seq = Sequence(id="us6000u18k", name="Panama", role="test-post", catalog_min_mag=3.0)
    (item,) = build_items(build_tables(data, "20261019T0000Z", [seq]))
    assert item.catalog and all(r.t_days < item.elapsed_days for r in item.catalog)
    assert all(w.start_ms >= item.issue_ms for w in item.windows)
    mainshock_row = item.catalog[0]
    assert mainshock_row.t_days == 0.0 and mainshock_row.dist_km == 0.0  # distance from epicentre
    assert "Earthquake" not in item.mainshock.place  # uniform origin title, not an event name


def test_snapshot_id_fixes_the_catalog_end_time():
    from laf.cli import snapshot_ms

    assert snapshot_ms("20261009T1756Z") == ORIGIN - 6036  # 2026-10-09T17:56:00Z
