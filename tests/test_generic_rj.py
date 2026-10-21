import csv
import json
from pathlib import Path

import pytest

from laf.generic_rj import (
    REFERENCE_REL,
    STREC_TO_GARCIA,
    garcia_regime,
    generic_rj,
    mag_comp,
)

REF = Path(__file__).parents[1] / "data" / REFERENCE_REL
GOLDEN = Path(__file__).parent / "golden"


def test_operational_parameters_equal_the_page_et_al_table():
    doc = json.loads((REF / "GenericRJ_ParametersFetch.json").read_text())
    ops = {r["regime"]: r["params"] for r in doc["regimes"]}
    with (REF / "PageEtAlGenericParams_032116.csv").open() as f:
        rows = list(csv.DictReader(f))
    assert {r["regionName"].strip() for r in rows} == set(STREC_TO_GARCIA.values())
    for r in rows:
        p = ops[r["regionName"].strip()]
        assert p["aValue_mean"] == float(r["aValue_Mean"])
        assert p["aValue_sigma0"] == float(r["aValue_Sigma0"])
        assert p["aValue_sigma1"] == float(r["aValue_Sigma1"])
        assert (p["pValue"], p["bValue"], p["cValue"]) == (
            float(r["pValue_MaxLike"]),
            float(r["bValue"]),
            float(r["cValue"]),
        )


@pytest.mark.parametrize(
    ("lat", "lon", "regime"),
    [
        (34.05, -118.25, "CAL-SCSN"),  # special California region wins over the Garcia table
        (-25.0, 134.0, "SCR-GENERIC"),  # central Australia: stable continental
        (0.0, -150.0, "SOR-GENERIC"),  # mid-Pacific plate: stable oceanic
    ],
)
def test_lookup_of_unambiguous_locations(lat, lon, regime):
    assert generic_rj(REF, lat, lon, 10.0).regime == regime


def test_alaska_completeness_region_crosses_the_date_line():
    assert mag_comp(REF, 52.9, 173.2, 10.0).region == "ALASKA"  # Attu, west of 180
    assert mag_comp(REF, 61.2, -149.9, 10.0).region == "ALASKA"  # Anchorage
    assert mag_comp(REF, -25.0, 134.0, 10.0).region == "WORLD"


@pytest.mark.parametrize(
    ("golden", "lat", "lon", "depth", "mag", "regime"),
    [
        # First USGS products (pure generic forecasts: pSigma = 0) for the two RJ sequences.
        ("oaf_us7000qd1y_1752699471265_generic_rj.json", 54.565, -160.469, 38.0, 7.3, "SZ-ONSHORE"),
        (
            "oaf_us6000rsy1_1765058285666_generic_rj.json",
            60.313,
            -139.541,
            10.3,
            7.0,
            "ANSR-SHALCON",
        ),
    ],
)
def test_lookup_reproduces_usgs_generic_forecasts(golden, lat, lon, depth, mag, regime):
    p = json.loads((GOLDEN / golden).read_text())["model"]["parameters"]
    assert p["pSigma"] == 0.0
    g = generic_rj(REF, lat, lon, depth)
    assert g.regime == regime
    assert (g.a_mean, g.p, g.b, g.c) == (p["a"], p["p"], p["b"], p["c"])
    assert g.sigma_a(mag) == pytest.approx(p["aSigma"], abs=0.002)
    m = mag_comp(REF, lat, lon, depth)
    assert (p["F"], p["G"], p["H"]) == (m.F, m.G, m.H)


def test_sigma_and_completeness_formulas():
    g = generic_rj(REF, 7.587, -80.769, 13.0)  # Panama
    assert g.sigma_a(7.7) == pytest.approx((0.49**2 + 570**2 / 10**7.7) ** 0.5)
    assert g.sigma_a(5.0) == g.sigma_a(6.0)  # magnitude floor of 6 in the USGS formula
    m = mag_comp(REF, 7.587, -80.769, 13.0)
    assert m.mc(7.7, m.complete_after_days(7.7, 4.95)) == pytest.approx(4.95)
    assert garcia_regime(REF, 7.587, -80.769 + 360.0) == garcia_regime(REF, 7.587, -80.769)
