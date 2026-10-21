import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from laf.oaf import Forecast, oaf_versions, parse_forecast

GOLDEN = Path(__file__).parent / "golden"
PANAMA_V1 = GOLDEN / "oaf_us6000u18k_1791593712688.json"  # ETAS, 399 fractiles
KAMCHATKA_REPOST = GOLDEN / "oaf_us6000qw60_1759165484245.json"  # posted a week after creation
REDWOOD_RJ = GOLDEN / "oaf_nc75382936_1791991293434.json"  # Reasenberg-Jones, 197 fractiles


def load(path: Path) -> Forecast:
    return parse_forecast(path.read_bytes())


def test_panama_v1_matches_published_numbers():
    f = load(PANAMA_V1)
    assert f.creationTime == 1791593462216
    assert f.model.name.startswith("Epidemic-Type")
    assert f.mc == 4.95
    assert len(f.fractileProbabilities) == 399
    week = f.window("1 Week")
    m5 = week.bin(5.0)
    assert (m5.median, m5.p95minimum, m5.p95maximum) == (12, 3, 38)
    assert week.bin(6.0).probability == pytest.approx(0.6736)
    region = f.region
    assert (region.lat, region.lon, region.radius_km) == (7.5735, -80.8225, 381.6)


def _two_sig_figs(x: int) -> int:
    return int(float(f"{x:.2g}"))


@pytest.mark.parametrize("path", [PANAMA_V1, KAMCHATKA_REPOST, REDWOOD_RJ])
def test_golden_files_validate_and_median_is_the_rounded_half_fractile(path: Path):
    # In 2025 products the `median` field is display-rounded to 2 significant figures
    # (Kamchatka M3: fractile 534, median 530); 2026 products report it exactly. Scoring must
    # therefore use fractileValues, never median/p95*.
    f = load(path)
    assert [w.label for w in f.forecast] == ["1 Day", "1 Week", "1 Month", "1 Year"]
    i = f.fractileProbabilities.index(0.5)
    for w in f.forecast:
        for b in w.bins:
            v = b.fractileValues[i]
            assert b.median in (v, _two_sig_figs(v))


def test_rj_forecast_uses_mcat_and_197_fractiles():
    f = load(REDWOOD_RJ)
    assert f.model.name.startswith("Reasenberg-Jones")
    assert len(f.fractileProbabilities) == 197
    assert f.mc == 1.5


def test_kamchatka_repost_keeps_its_own_creation_time():
    f = load(KAMCHATKA_REPOST)
    # Posted 2025-09-29 (product updateTime 1759165484245) but created 2025-09-22.
    assert f.creationTime == 1758561938035
    assert f.window("1 Day").timeStart > f.creationTime


def _mutated(path: Path, mutate) -> bytes:
    doc = json.loads(path.read_bytes())
    mutate(doc)
    return json.dumps(doc).encode()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["forecast"][0]["bins"][2]["fractileValues"].reverse(),
        lambda d: d["forecast"][0]["bins"][2]["fractileValues"].pop(),
        lambda d: d["fractileProbabilities"].reverse(),
        lambda d: d["forecast"][0].update(timeEnd=d["forecast"][0]["timeStart"]),
        lambda d: d["forecast"][1]["bins"][3].update(probability=1.5),
        lambda d: d["forecast"][1]["bins"][3]["fractileValues"].__setitem__(-1, 10**9),
        lambda d: d["model"]["parameters"].update(regionType="rectangle"),
    ],
    ids=[
        "non-monotone fractiles",
        "fractile length mismatch",
        "probabilities not increasing",
        "empty window",
        "probability out of range",
        "M6 count above M5 count",
        "non-circle region",
    ],
)
def test_invalid_forecasts_are_rejected(mutate):
    with pytest.raises(ValidationError):
        parse_forecast(_mutated(PANAMA_V1, mutate))


def test_oaf_versions_lists_every_version_oldest_first():
    doc = json.loads((GOLDEN / "event_us6000u18k_trimmed.geojson").read_bytes())
    versions = oaf_versions(doc)
    assert len(versions) == 11
    times = [v.update_time_ms for v in versions]
    assert times == sorted(times)
    assert versions[0].update_time_ms == 1791593712688
    assert versions[0].url == (
        "https://earthquake.usgs.gov/product/oaf/us6000u18k/us/1791593712688/forecast.json"
    )


PANAMA_EPICENTRE = (7.5868, -80.769, 7.7, 1791568566036)  # lat, lon, mag, origin ms
KAMCHATKA_EPICENTRE = (52.4948, 160.2395, 8.8, 1753831492483)


def test_event_mismatch_accepts_the_right_event():
    assert load(PANAMA_V1).event_mismatch(*PANAMA_EPICENTRE) is None
    assert load(KAMCHATKA_REPOST).event_mismatch(*KAMCHATKA_EPICENTRE) is None


def test_event_mismatch_flags_a_forecast_filed_under_the_wrong_event():
    # Kamchatka's first ComCat oaf product (posted 2025-07-30) holds a Myanmar forecast
    # (centre 21.86N 95.94E, magMain 7.7) created before the Kamchatka mainshock.
    f = load(GOLDEN / "oaf_us6000qw60_1753897487444_wrong_event.json")
    assert f.event_mismatch(*KAMCHATKA_EPICENTRE) == "created before the mainshock"
    lat, lon, mag, _ = KAMCHATKA_EPICENTRE
    assert "magMain" in (f.event_mismatch(lat, lon, mag, 0) or "")
    assert "km from the epicentre" in (f.event_mismatch(lat, lon, 7.7, 0) or "")


def test_info_cutoff_is_the_earlier_of_creation_and_window_start():
    f = load(PANAMA_V1)
    assert f.info_cutoff_ms == min(f.creationTime, f.time_start) == f.creationTime


def test_event_mismatch_rejects_a_forecast_for_a_doublet_partner():
    # Venezuela v1-v6 publish magMain 7.2 (the foreshock 33 s earlier), not the M7.5 mainshock.
    f = load(PANAMA_V1)
    lat, lon, _, origin = PANAMA_EPICENTRE
    assert "magMain" in (f.event_mismatch(lat, lon, 7.7 + 0.3, origin) or "")
    assert f.event_mismatch(lat, lon, 7.7 + 0.1, origin) is None  # ordinary revision


def test_simulated_min_mag_is_read_from_the_fractile_lattice():
    # Kamchatka 2025 (Feb-2025 legacy build): M3-M5 fractiles are 10^(b (5.8 - M)) x integers.
    assert load(KAMCHATKA_REPOST).simulated_min_mag == 5.8
    assert load(PANAMA_V1).simulated_min_mag is None  # 2026 build: simulated from M3.0
    assert load(REDWOOD_RJ).simulated_min_mag is None  # not the legacy ETAS
