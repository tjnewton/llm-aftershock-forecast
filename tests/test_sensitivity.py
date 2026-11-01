import numpy as np
import pandas as pd
import pytest

from laf import confirmatory as C
from laf import sensitivity as S


def test_clean_rules():
    assert C.clean_from("gpt-5.1-2025-11-13") == pd.Timestamp("2025-01-01", tz="UTC")
    assert C.clean_from("gpt-5.1-2025-11-13", "unbuffered") == pd.Timestamp("2024-10-01", tz="UTC")
    assert C.clean_from("gpt-5.1-2025-11-13", "release") == pd.Timestamp("2025-11-10", tz="UTC")
    with pytest.raises(ValueError):
        C.clean_from("gpt-5.1-2025-11-13", "other")


def test_non_overlapping_keeps_one_window_per_issue_time():
    cells = pd.DataFrame({
        "issue_id": ["s@first", "s@first", "s@first", "s@1d", "s@1d", "s@7d", "s@first+1d"],
        "window": ["day", "week", "month", "day", "week", "week", "month"],
    })  # fmt: skip
    assert S.non_overlapping(cells).tolist() == [True, True, True, True, False, True, True]


def test_exact_match_subset():
    it = pd.DataFrame({"issue_id": ["a", "b"], "oaf_obs_m5": [3, 2], "comcat_m5_at_cutoff": [3, 1]})
    assert S.exact_match({"issue_times": it}) == {"a"}


def _samples():
    rng = np.random.default_rng(0)
    rows = []
    for i in range(8):
        for target, win in (("first", "day"), ("1d", "week")):
            for st, v in (("ok", "v2A"), ("ok", "v2A"), ("max_tokens", "v2A"), ("ok", "v2B")):
                rows.append({"model": "claude-opus-5-5", "effort": "high", "variant": v,
                             "status": st, "sequence_id": f"s{i}", "item_id": f"s{i}@{target}",
                             "window": win, "sample": len(rows),
                             "d5": float(rng.normal(-0.05, 0.05)) if st == "ok" else None,
                             "worst_base_d5": 0.4})  # fmt: skip
    return pd.DataFrame(rows)


def test_one_table_with_every_variant():
    s = _samples()
    tables = {"sequences": pd.DataFrame({"sequence_id": s["sequence_id"].unique()}),
              "issue_times": pd.DataFrame({"issue_id": s["item_id"].unique(), "oaf_obs_m5": 1,
                                           "comcat_m5_at_cutoff": 1})}  # fmt: skip
    elapsed = {i: (0.5 if i.endswith("first") else 3.0) for i in s["item_id"]}
    sets = {"claude-opus-5-5": set(s["sequence_id"])}
    t = S.sensitivity(s, tables, elapsed, ("claude-opus-5-5",), samples_2d=s, sets=sets)
    got = dict(zip(t["analysis"], t["mean"], strict=True))
    assert {"main", "non-overlapping subset", "v2B", "valid answers only", "2-day settling rule",
            "as-of catalog matches the official count", "stratum: under 1 day",
            "stratum: 1 to 7 days"} <= set(got)  # fmt: skip
    assert got["valid answers only"] < got["main"]  # the penalty raised the main mean
    rates = S.invalid_rates(s).set_index("variant")
    assert rates.loc["v2A", "invalid_rate"] == pytest.approx(1 / 3)


def test_the_release_rule_skips_models_without_a_release_date(monkeypatch):
    from laf import splits

    monkeypatch.setattr(splits, "development_ids", lambda: frozenset())
    s = _samples()
    other = s.assign(model="claude-haiku-5-5")  # clean period known, release date not recorded
    both = pd.concat([s, other], ignore_index=True)
    origin = pd.Timestamp("2026-10-15", tz="UTC").value // 1_000_000
    seqs = pd.DataFrame({"sequence_id": s["sequence_id"].unique(), "origin_ms": origin,
                         "mag": 5.5})  # fmt: skip
    elapsed = {i: 0.5 for i in s["item_id"]}
    cells = C.confirmatory_cells(both, seqs, elapsed, rule="release")
    assert set(cells["model"]) == {"claude-opus-5-5"}


def test_scoring_variants_change_only_what_they_name():
    import math
    from types import SimpleNamespace

    from laf.countdist import from_quantiles, log_score
    from laf.d2 import _ls, scorer
    from laf.scoring import quantile_score

    q, y = [0, 0, 0, 1, 1, 2, 3, 4, 5], 40  # a count far beyond the 97.5% quantile
    assert scorer()(q, y) == _ls(q, y)
    assert scorer(floor=1e-4)(q, y) == pytest.approx(-math.log(1e-4))  # the floor binds
    assert scorer(floor=1e-8)(q, y) >= scorer()(q, y)
    assert scorer("nb_tail")(q, 8) != scorer()(q, 8)  # another tail beyond the last knot
    assert scorer("log_qs")(q, y) == quantile_score(q, y)
    grid = ([0.01 * i for i in range(1, 100)], [min(i // 10, 9) for i in range(1, 100)])
    official = SimpleNamespace(fractiles_m5=grid, cdf_m5=None)
    want = log_score(from_quantiles(grid[1], grid[0]).cdf, 3)[0]
    assert scorer("full")(q, 3, official, "official") == pytest.approx(want)  # the whole grid
    etas = SimpleNamespace(fractiles_m5=None, cdf_m5=np.array([0.5, 0.75, 1.0]))
    assert scorer("full")(q, 1, etas, "etas") == pytest.approx(-math.log(0.25))  # its histogram
    # generic RJ and the rule of thumb carry full distributions too, but stay as registered
    assert scorer("full")(q, 1, etas, "generic_rj") == scorer()(q, 1)
    assert scorer("full")(q, 3) == scorer()(q, 3)  # model answers: as registered
    with pytest.raises(ValueError):
        scorer("other")


def test_diagnostics_per_forecaster_on_development_answers():
    from pathlib import Path

    run, proc = [Path("runs/d2/d2-claude-opus-5-5")], Path("data/processed/20261021T2300Z")
    dev = set(pd.read_parquet(proc / "sequences.parquet")["sequence_id"])
    t = S.diagnostics(proc, run, ("claude-opus-5-5",), {"claude-opus-5-5": dev})
    rows = {r["forecaster"]: r for r in t.to_dict("records")}
    few = S.diagnostics(proc, run, ("claude-opus-5-5",), {"claude-opus-5-5": set(sorted(dev)[:3])})
    assert few["answers"].sum() < t["answers"].sum()  # only the model's own sequences count
    assert {"official", "generic_rj", "naive", "rj_mle", "etas", "claude-opus-5-5"} <= set(rows)
    assert rows["official"]["ig_per_quake"] == 0.0  # against itself
    assert all(0 <= r["n_test_fail"] <= 1 and 0 <= r["pit_ks"] <= 1 for r in rows.values())


def test_recounted_outcomes_match_at_x1_and_grow_with_the_radius():
    from pathlib import Path

    from laf import analysis as A
    from laf.d2 import recount_m5

    tables = A.load_tables(Path("data/processed/20261021T2300Z"))
    cells = A.cells(tables)
    cells = cells[cells["primary"] & cells["oaf_cell"]]
    same = recount_m5(tables, cells, 1.0)
    assert same == {(c["issue_id"], c["window"]): int(c["y5"]) for c in cells.to_dict("records")}
    half, wide = recount_m5(tables, cells, 0.5), recount_m5(tables, cells, 1.5)
    for k, n in same.items():
        h, w = half[k], wide[k]
        assert h is not None and n is not None and h <= n and (w is None or n <= w)
    uncovered = {**tables, "issue_times": tables["issue_times"].assign(query_covers_x1_5=False)}
    assert set(recount_m5(uncovered, cells, 1.5).values()) == {None}  # no wider catalog: out


def test_the_recount_refuses_sealed_sequences(monkeypatch):
    from laf import splits
    from laf.d2 import recount_m5

    monkeypatch.setattr(splits, "unsealed", lambda: False)
    sid = "us7000zzzz"  # in no development source: confirmatory
    cells = pd.DataFrame({"sequence_id": [sid], "issue_id": [f"{sid}@first"], "window": ["1 Day"],
                          "time_start_ms": [0], "time_end_ms": [1]})  # fmt: skip
    with pytest.raises(SystemExit, match="sealed"):
        recount_m5({}, cells, 0.5)


def test_a_radius_variant_with_no_covered_cell_reports_zero_sequences(monkeypatch):
    from pathlib import Path

    from laf import analysis as A
    from laf import d2

    proc = Path("data/processed/20261021T2300Z")
    load = A.load_tables

    def uncovered(p):
        t = load(p)
        return {**t, "issue_times": t["issue_times"].assign(query_covers_x1_5=False)}

    monkeypatch.setattr(A, "load_tables", uncovered)
    s, summary = d2.analyze(proc, [Path("runs/d2/d2-claude-opus-5-5")], radius=1.5)
    assert s.empty and summary.empty
    monkeypatch.setattr(S, "SCORE_VARIANTS", (("region radius x1.5", {"radius": 1.5}),))
    t = S.scoring_variants(proc, [Path("runs/d2/d2-claude-opus-5-5")], uncovered(proc), {},
                           ("claude-opus-5-5",))  # fmt: skip
    assert t.to_dict("records") == [
        {"analysis": "region radius x1.5", "model": "claude-opus-5-5", "sequences": 0}]  # fmt: skip
