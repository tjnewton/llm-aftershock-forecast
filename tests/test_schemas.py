import json
from pathlib import Path

from laf.schemas import QKEYS, validate

SCHEMA = json.loads(Path("prompts/schema_direct.json").read_text("utf-8"))


def direct(**over):
    w = {
        "m5_count_quantiles": dict(zip(QKEYS, range(9), strict=True)),
        "m4_count_quantiles": dict(zip(QKEYS, range(10, 19), strict=True)),
        "p_m6_at_least_one": 0.1,
    }
    d = {
        "day": w,
        "week": json.loads(json.dumps(w)),
        "month": json.loads(json.dumps(w)),
        "notes": "One sentence.",
    }
    d.update(over)
    return json.dumps(d)


PARAMS = {
    "b": 1.0,
    "p": 1.1,
    "c_days": 0.05,
    "a_p05": -2.8,
    "a_p50": -2.4,
    "a_p95": -2.0,
    "notes": "Generic.",
}


def test_validator_keys_match_the_schema_file():
    assert set(SCHEMA["properties"]) == {"day", "week", "month", "notes"}
    win = SCHEMA["$defs"]["window"]["properties"]
    assert set(win) == {"m5_count_quantiles", "m4_count_quantiles", "p_m6_at_least_one"}
    assert set(SCHEMA["$defs"]["quantiles"]["properties"]) == set(QKEYS)


def test_each_status():
    assert validate("direct", direct(), "end_turn")[0] == "ok"
    assert validate("direct", None, "refusal")[0] == "refusal"
    assert validate("direct", direct(), "max_tokens")[0] == "max_tokens"
    assert validate("direct", "{not json", "end_turn")[0] == "schema_invalid"
    bad = json.loads(direct())
    bad["day"]["m5_count_quantiles"]["q500"] = 0
    assert validate("direct", json.dumps(bad), "end_turn")[0] == "non_monotone"
    bad = json.loads(direct())
    bad["week"]["p_m6_at_least_one"] = 1.5
    assert validate("direct", json.dumps(bad), "end_turn")[0] == "out_of_range"
    assert validate("params", json.dumps(PARAMS), "end_turn")[0] == "ok"
    assert validate("params", json.dumps(PARAMS | {"c_days": 20.0}), None)[0] == "out_of_range"
    flipped = PARAMS | {"a_p05": -2.0, "a_p95": -2.8}
    assert validate("params", json.dumps(flipped), None)[0] == "out_of_range"


def test_warnings():
    bad = json.loads(direct())
    bad["day"]["m5_count_quantiles"] = dict(zip(QKEYS, range(20, 29), strict=True))
    status, _, warn = validate("direct", json.dumps(bad | {"notes": "A. B. C."}), "end_turn")
    assert status == "ok"
    assert {"incoherent_windows", "incoherent_magnitudes", "notes_too_long"} <= set(warn)
