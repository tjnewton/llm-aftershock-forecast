from pathlib import Path

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from laf.catalog import (
    count_in_window,
    haversine_km,
    read_comcat_csv,
    wells_coppersmith_radius_km,
)
from laf.oaf import Circle

GOLDEN = Path(__file__).parent / "golden"
# ComCat CSV, Panama OAF circle, M>=4.5, 2026-10-09T17:00 to 2026-10-11T18:00.
PANAMA_CSV = GOLDEN / "comcat_us6000u18k_2d_m4.5.csv"
PANAMA_CIRCLE = Circle(7.5735, -80.8225, 381.6)
MAINSHOCK_MS = 1791568566036  # 2026-10-09T17:56:06.036Z
DAY_MS = 86_400_000


def test_read_comcat_csv_parses_types_and_quoted_places():
    cat = read_comcat_csv(PANAMA_CSV.read_bytes())
    assert len(cat) == 50
    assert cat["id"].is_unique
    first = cat.iloc[0]
    assert first["id"] == "us6000u18k"
    assert first["time_ms"] == MAINSHOCK_MS
    assert first["mag"] == 7.7
    assert first["magType"] == "mww"
    assert cat["time_ms"].is_monotonic_increasing


@pytest.mark.parametrize(
    ("t0", "t1", "mag", "expected"),
    [
        # Oracles: the ComCat count endpoint for the same circle, minus one.
        # FDSN truncates starttime to whole seconds, so starttime=17:56:06.037 still returned
        # the mainshock (47/16/3); filter windows locally in milliseconds instead.
        (MAINSHOCK_MS + 1, MAINSHOCK_MS + DAY_MS, 4.5, 46),
        (MAINSHOCK_MS + 1, MAINSHOCK_MS + DAY_MS, 5.0, 15),
        (MAINSHOCK_MS + 1, MAINSHOCK_MS + DAY_MS, 6.0, 2),
        # First OAF version's "1 Day" window [timeStart, timeEnd).
        (1791594028116, 1791594028116 + DAY_MS, 5.0, 2),
    ],
)
def test_count_in_window_matches_comcat_count_endpoint(t0, t1, mag, expected):
    cat = read_comcat_csv(PANAMA_CSV.read_bytes())
    assert count_in_window(cat, PANAMA_CIRCLE, t0, t1, mag) == expected


def test_count_window_is_half_open():
    cat = read_comcat_csv(PANAMA_CSV.read_bytes())
    assert count_in_window(cat, PANAMA_CIRCLE, MAINSHOCK_MS, MAINSHOCK_MS + 1, 7.0) == 1
    assert count_in_window(cat, PANAMA_CIRCLE, MAINSHOCK_MS + 1, MAINSHOCK_MS + 2, 7.0) == 0


def test_wells_coppersmith_radius_reproduces_research_notes():
    # Research notes used 110.4 km for Chiapas (M7.3) and 56 km for Kumamoto (M6.8).
    assert wells_coppersmith_radius_km(7.3) == pytest.approx(110.4, abs=0.1)
    assert wells_coppersmith_radius_km(6.8) == pytest.approx(56.0, abs=0.1)
    assert wells_coppersmith_radius_km(3.0) == 10.0


def test_haversine_known_distance():
    # One degree of latitude on a 6371 km sphere.
    assert haversine_km(0.0, 0.0, 1.0, 0.0) == pytest.approx(111.195, abs=1e-3)


@given(
    st.floats(-89, 89),
    st.floats(-180, 180),
    st.floats(-89, 89),
    st.floats(-180, 180),
)
def test_haversine_symmetric_and_bounded(lat1, lon1, lat2, lon2):
    d1 = haversine_km(lat1, lon1, lat2, lon2)
    d2 = haversine_km(lat2, lon2, lat1, lon1)
    assert np.isclose(d1, d2)
    assert 0.0 <= d1 <= np.pi * 6371.0 + 1e-6
