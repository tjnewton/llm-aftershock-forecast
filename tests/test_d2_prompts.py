import json
from pathlib import Path

from laf import runner
from laf.analysis import load_tables
from laf.items import build_items
from laf.prompts import render, schema_for
from laf.schemas import QKEYS, TARGETS_V2, validate

E3 = Path("data/processed/20261021T2300Z")


def _items(floor):
    return {i.item_id: i for i in build_items(load_tables(E3), floor)}


def test_registered_items_are_unchanged_by_the_floor_parameter():
    for snap in ("20261021T1027Z", "20261021T2300Z"):
        p = Path("data/processed") / snap
        body = "".join(i.model_dump_json() + "\n" for i in build_items(load_tables(p)))
        assert body == (p / "items.jsonl").read_text(encoding="utf-8")


def test_v2_prompts_ask_for_m3_and_show_the_catalog_from_m3():
    items = _items(3.0)
    item = next(i for i in items.values() if i.role == "test-post" and len(i.catalog) > 25)
    assert any(r.mag < 4.0 for r in item.catalog)
    for para in ("v2A", "v2B"):
        _, user = render(item, "direct", "I1", para)
        assert "M>=3.0" in user or "magnitude 3.0 or larger" in user
        assert "magnitude 3.0 and above" in user
    _, c = render(item, "direct", "I1", "v2C")
    assert "Counts per day" in c and "largest" in c
    csv_rows = c.split("```csv")[1].split("```")[0].strip().splitlines()
    assert 1 < len(csv_rows) <= 21  # header + at most 20 events, not the full list
    _, p1 = render(_items(4.0)[item.item_id], "direct", "I1", "p1")
    assert "magnitude 3.0 or larger" not in p1  # registered prompt untouched
    assert "m3_count_quantiles" in json.dumps(schema_for("direct", "v2C"))
    assert "m3_count_quantiles" not in json.dumps(schema_for("direct", "p1"))


def test_d2_blocks_expand_to_the_planned_requests():
    items = list(_items(3.0).values())
    reqs = runner.expand(items, "d2", "claude-opus-5-5")
    n_post = sum(i.role == "test-post" for i in items)
    assert len(reqs) == n_post * 3 * 3
    assert all(r["params"]["output_config"]["effort"] == "high" for r in reqs)
    med = runner.expand(items, "d2-medium", "claude-sonnet-5-5")
    assert len(med) == n_post * 3 and med[0]["params"]["output_config"]["effort"] == "medium"


def test_v2_answers_validate_with_m3_and_flag_incoherent_magnitudes():
    def w(m5, m4, m3):
        q = lambda v: dict(zip(QKEYS, v, strict=True))  # noqa: E731
        return {
            "m5_count_quantiles": q(m5),
            "m4_count_quantiles": q(m4),
            "m3_count_quantiles": q(m3),
            "p_m6_at_least_one": 0.1,
        }

    a, b, c = [0] * 9, [0, 0, 0, 1, 1, 2, 3, 4, 5], [1, 1, 2, 3, 5, 8, 12, 15, 20]
    good = json.dumps({"day": w(a, b, c), "week": w(a, b, c), "month": w(a, b, c), "notes": "x"})
    assert validate("direct", good, "end_turn", TARGETS_V2)[0] == "ok"
    bad = json.dumps({"day": w(a, c, b), "week": w(a, c, b), "month": w(a, c, b), "notes": "x"})
    status, _, warn = validate("direct", bad, "end_turn", TARGETS_V2)
    assert status == "ok" and "incoherent_magnitudes" in warn
