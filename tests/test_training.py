import json

import pandas as pd

from laf import training as T
from laf.schemas import validate


def test_fore_and_aftershocks_of_larger_listed_events_are_dropped():
    day = 86_400_000
    ev = pd.DataFrame(
        {
            "id": ["main", "after", "far", "late"],
            "time_ms": [0, 30 * day, 30 * day, 400 * day],
            "latitude": [0.0, 0.5, 30.0, 0.2],
            "longitude": [0.0, 0.5, 30.0, 0.2],
            "mag": [8.0, 6.8, 6.9, 6.7],
        }
    )
    assert list(T.exclude_fore_aftershocks(ev)["id"]) == ["main", "far", "late"]


def test_completion_is_a_valid_direct_answer_with_coherent_magnitudes():
    rows = [
        {
            "window": w,
            "b": 1.0,
            "p_m6": 0.123456,
            **dict(zip(T.QKEYS, (0, 0, 1, 1, 2, 3, 5, 6, 8), strict=True)),
        }
        for w in ("1 Day", "1 Week", "1 Month")
    ]
    c = T.completion(rows)
    status, _, warn = validate("direct", json.dumps(c), "end_turn")
    assert status == "ok" and "incoherent_magnitudes" not in warn
    assert c["day"]["m4_count_quantiles"]["q975"] == 80 and c["day"]["p_m6_at_least_one"] == 0.1235
