import pandas as pd

from laf.asof import VERSION_COLUMNS, as_of, origin_versions


def _v(event, source, update, index, weight, mag, status="UPDATE", t=1_000):
    return {
        "event_id": event, "source": source, "code": f"{source}{event}", "status": status,
        "update_ms": update, "index_ms": index, "weight": weight, "time_ms": t, "latitude": 0.0,
        "longitude": 0.0, "depth": 10.0, "mag": mag, "magType": "mb", "review": "automatic",
    }  # fmt: skip


VERSIONS = pd.DataFrame(
    [
        _v("e1", "at", 100, 105, 50, 4.4, t=100),  # first seen at 105
        _v("e1", "us", 200, 210, 150, 4.7),  # preferred source from 210
        _v("e1", "us", 300, 305, 150, 4.6),  # its revision from 305
        _v("e2", "us", 150, 160, 150, 5.0),
        _v("e2", "us", 400, 410, 150, 5.0, status="DELETE"),  # deleted at 410
    ],
    columns=VERSION_COLUMNS,
)


def mags(t):
    return dict(zip(*as_of(VERSIONS, t)[["id", "mag"]].T.values, strict=True))


def test_as_of_follows_availability_preference_revision_and_deletion():
    assert mags(104) == {}
    assert mags(105) == {"e1": 4.4}
    assert mags(209) == {"e1": 4.4, "e2": 5.0}
    assert mags(210) == {"e1": 4.7, "e2": 5.0}  # higher preferredWeight wins
    assert mags(305) == {"e1": 4.6, "e2": 5.0}  # latest version of that product
    assert mags(410) == {"e1": 4.6}  # deletion removes the event
    by_update = as_of(VERSIONS, 200, clock="update_ms")
    assert dict(zip(by_update["id"], by_update["mag"], strict=True)) == {"e1": 4.7, "e2": 5.0}


def test_origin_versions_reads_superseded_products():
    doc = {
        "id": "us1",
        "properties": {
            "products": {
                "origin": [
                    {"source": "us", "code": "us1", "status": "UPDATE", "updateTime": 2,
                     "indexTime": 3, "preferredWeight": 156,
                     "properties": {"eventtime": "2026-01-01T00:00:00.500Z", "latitude": "1.5",
                                    "longitude": "2", "depth": "10", "magnitude": "4.8",
                                    "magnitude-type": "mb", "review-status": "reviewed"}},
                ],
                "phase-data": [{"source": "us"}],
            }
        },
    }  # fmt: skip
    (row,) = origin_versions(doc)
    assert (row["time_ms"], row["mag"], row["index_ms"], row["weight"]) == (
        1767225600500,
        4.8,
        3,
        156.0,
    )


def test_events_without_history_keep_their_hindsight_row():
    from laf.asof import as_of_or_hindsight

    hind = pd.DataFrame(
        {"id": ["e1", "e2", "e3"], "time_ms": [100, 100, 200], "latitude": 0.0,
         "longitude": 0.0, "depth": 10.0, "mag": [4.6, 5.0, 4.2], "magType": "mb"}
    )  # fmt: skip
    cat, fallback = as_of_or_hindsight(VERSIONS, hind, 305)
    assert dict(zip(cat["id"], cat["mag"], strict=True)) == {"e1": 4.6, "e2": 5.0, "e3": 4.2}
    assert dict(zip(cat["id"], fallback, strict=True)) == {"e1": False, "e2": False, "e3": True}
    cat, _ = as_of_or_hindsight(VERSIONS, hind, 150)  # e3 occurs at t=200: not yet visible
    assert "e3" not in set(cat["id"])
