import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from laf import d1
from laf.analysis import load_tables
from laf.items import DAY_MS, build_items
from laf.prompts import render

E3 = Path("data/processed/20261021T2300Z")


@pytest.fixture(scope="module")
def probe():
    tables = load_tables(E3)
    items = d1.probe_items(build_items(tables, d1.FLOOR), tables["sequences"])
    seqs = tables["sequences"].set_index("sequence_id").to_dict("index")
    return {i.item_id: i for i in items}, seqs


def test_probe_items_cover_the_design_once(probe):
    items, _ = probe
    seqs = {i.sequence_id for i in items.values()}
    assert len(seqs) == 18
    per_seq = len(d1.DELTAS) + len(d1.ELAPSED_DAYS) + len(d1.COUNTS) + 1
    assert len(items) == 18 * per_seq
    reqs = d1.expand(list(items.values()), "claude-opus-4-6")
    assert len(reqs) == len(items) * d1.K == len({r["custom_id"] for r in reqs})
    assert all(r["params"]["thinking"] == {"type": "adaptive"} for r in reqs)
    assert {r["params"]["output_config"]["effort"] for r in reqs} == {"medium"}
    assert {r["meta"]["effort"] for r in reqs} == {"medium"}
    assert d1.study_setting("claude-opus-4-6") == "adaptive-medium"
    assert d1.study_setting("claude-opus-5-5") == "registered"
    for i in items.values():
        assert [(w.start_ms, (w.end_ms - w.start_ms) // DAY_MS) for w in i.windows] == [
            (i.issue_ms, 1), (i.issue_ms, 7), (i.issue_ms, 30)
        ]  # fmt: skip


def test_committed_probe_items_match_a_rebuild(probe):
    items, _ = probe
    assert (E3 / "items_d1.jsonl").read_text(encoding="utf-8") == d1.items_jsonl(
        list(items.values())
    )


def test_i0_probes_show_no_catalog_and_i1_probes_show_the_synthetic_one(probe):
    items, _ = probe
    seq = "us7000ti1p"
    p1 = items[f"{seq}@d1-p1+1.0"]
    assert d1.info(p1) == "I0" and p1.mainshock.mag == pytest.approx(7.5)
    assert "No list of earthquakes is provided" in render(p1, "direct", "I0", "v2A")[1]
    p3 = items[f"{seq}@d1-p3-n30"]
    user = render(p3, "direct", d1.info(p3), "v2A")[1]
    assert d1.info(p3) == "I1" and user.count(",ml,") == 30


def test_synthetic_catalogs(probe):
    items, _ = probe
    for i in items.values():
        tag = i.item_id.split("@d1-")[1]
        if not tag.startswith(("p3", "p4")):
            assert i.catalog == []
            continue
        main, rest = i.catalog[0], i.catalog[1:]
        assert (main.t_days, main.mag) == (0.0, i.mainshock.mag)
        assert len(rest) == (d1.P4_N if tag == "p4-even" else int(tag[4:]))
        assert all(0 < r.t_days < d1.P3_DAYS for r in rest)
        assert all(d1.FLOOR <= r.mag < i.mainshock.mag for r in rest)
        assert all(r.dist_km <= i.region.radius_km for r in rest)
    a, b = items["us7000ti1p@d1-p3-n10"], items["us7000ti1p@d1-p4-even"]
    assert sorted(r.mag for r in a.catalog) == sorted(r.mag for r in b.catalog)
    assert [r.t_days for r in a.catalog] != [r.t_days for r in b.catalog]


def test_references_follow_the_inputs(probe):
    items, seqs = probe
    s = "us7000ti1p"
    tags = ("p2-1d", "p1+1.0", "p2-3d", "p2-30d", "p3-n0", "p3-n100", "p3-n10", "p4-even")
    ref = {t: d1.reference(items[f"{s}@d1-{t}"], seqs[s]) for t in tags}
    med = lambda t, w="month": ref[t][w]["m3_count_quantiles"][4]  # noqa: E731
    assert med("p1+1.0") > 5 * med("p2-1d")  # about 10 per magnitude unit
    assert med("p2-30d") < med("p2-3d") < med("p2-1d")  # Omori decay
    assert med("p3-n0") < med("p3-n10") < med("p3-n100")  # the observed count updates a
    assert med("p4-even") > med("p3-n10")  # an undecayed pattern updates p
    for r in ref.values():
        for w in r.values():
            m5, m4, m3 = (w[f"m{m}_count_quantiles"] for m in (5, 4, 3))
            assert all(x <= y <= z for x, y, z in zip(m5, m4, m3, strict=True))
            assert 0 <= w["p_m6"] <= 1


def _fake_client(out_tokens):
    outs = iter(out_tokens)

    def create(**params):
        n = next(outs)
        usage = SimpleNamespace(model_dump=lambda: {"input_tokens": 2000, "output_tokens": n})
        return SimpleNamespace(
            id="msg", model=params["model"], stop_reason="end_turn", stop_details=None,
            usage=usage, content=[SimpleNamespace(type="text", text="{}")],
        )  # fmt: skip

    return SimpleNamespace(
        messages=SimpleNamespace(create=create), base_url="https://api.anthropic.com"
    )


def test_pilot_alternates_models_and_never_exceeds_its_budget(probe, tmp_path, monkeypatch):
    items, _ = probe
    monkeypatch.chdir(tmp_path)  # an empty runs/ for the monthly guard
    monkeypatch.setenv("LAF_CLAUDE_MONTHLY_CAP_USD", "10")
    d1.pilot(_fake_client([1000] * 8), list(items.values()), tmp_path / "p", budget_usd=10)
    rows = [json.loads(x) for x in (tmp_path / "p" / "calls.jsonl").read_text().splitlines()]
    assert len(rows) == 8 and {r["status"] for r in rows} == {"schema_invalid"}
    assert [r["model_requested"] for r in rows[:2]] == ["claude-opus-4-6", "claude-sonnet-4-6"]
    # outputs that grow after the first calls (Codex review): the guard uses each call's worst
    # case, not the previous cost
    for budget in (0.5, 0.8):
        out = tmp_path / f"b{budget}"
        spent = d1.pilot(
            _fake_client([1000, 1000] + [16000] * 6), list(items.values()), out, budget
        )
        assert spent <= budget


def test_settings_pilot_requests_and_their_worst_case(probe):
    items, _ = probe
    reqs = d1.settings_requests(list(items.values()))
    assert len(reqs) == len(d1.SETTINGS_TAGS) * len(d1.SETTINGS) * 2
    assert len({r["custom_id"] for r in reqs}) == len(reqs)
    for r in reqs:
        thinking, effort = r["params"].get("thinking"), r["params"]["output_config"]["effort"]
        name = r["meta"]["setting"]
        assert (thinking is not None) == name.startswith("adaptive")
        assert effort == name.split("-")[1]
    assert sum(d1.bound_usd(r["params"], batch=True) for r in reqs) <= 2.5
