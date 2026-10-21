from pathlib import Path

import pytest

from laf.items import CatalogRow, Item, Mainshock, Region, WindowSpec
from laf.prompts import render, schema, template_hashes

ORIGIN = 1791568566036


def _item(n_rows: int = 2) -> Item:
    return Item(
        item_id="us6000u18k@first",
        sequence_id="us6000u18k",
        role="test-post",
        issue_ms=ORIGIN + 25_000_000,
        elapsed_days=0.29,
        mainshock=Mainshock(
            origin_ms=ORIGIN,
            origin_utc="2026-10-09 17:56:06",
            place="Panama",
            lat=7.5868,
            lon=-80.769,
            depth_km=12.6,
            mag=7.7,
            mag_type="mww",
        ),
        region=Region(lat=7.5735, lon=-80.8225, radius_km=381.6),
        windows=[
            WindowSpec(
                key="day",
                label="1 Day",
                start_ms=ORIGIN + 26_000_000,
                end_ms=ORIGIN + 26_000_000 + 86_400_000,
            )
        ],
        catalog=[
            CatalogRow(
                t_days=0.01 * i,
                utc_time="2026-10-09 18:00:00",
                mag=5.0,
                mag_type="mb",
                depth_km=10.0,
                dist_km=20.0,
            )
            for i in range(n_rows)
        ],
        truncated=False,
        daily_counts=None,
    )


@pytest.mark.parametrize("arm", ["direct", "params"])
@pytest.mark.parametrize("para", ["p1", "p2"])
def test_render_is_deterministic_and_complete(arm, para):
    a = render(_item(), arm, "I1", para)
    assert a == render(_item(), arm, "I1", para)
    _, user = a
    assert "$" not in user.replace("$ ", "")  # no unrendered ${field}
    assert "381.6 km" in user and "0.0100,2026-10-09 18:00:00,5.0,mb" in user


def test_mainshock_only_prompt_has_no_catalog_rows():
    _, user = render(_item(), "direct", "I0", "p1")
    assert "t_days,utc_time" not in user and "No list of earthquakes" in user


def test_prompts_never_mention_official_forecast_numbers():
    text = " ".join(p.read_text() for p in Path("prompts").glob("*.txt"))
    for leak in ("USGS forecast", "ETAS", "Mc ", "fractile"):
        assert leak not in text


def test_schemas_load_and_hashes_cover_every_template():
    assert schema("direct")["required"] == ["day", "week", "month", "notes"]
    hashes = template_hashes()
    assert {"system_p1.txt", "schema_params.json", "probe_recall.txt"} <= set(hashes)
