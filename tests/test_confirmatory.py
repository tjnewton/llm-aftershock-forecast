import numpy as np
import pandas as pd
import pytest

from laf import confirmatory as C


def test_holm_step_down():
    assert C.holm({"a": 0.01, "b": 0.04}) == {"a": True, "b": True}
    assert C.holm({"a": 0.03, "b": 0.04}) == {"a": False, "b": False}  # 0.03 > 0.025 stops
    assert C.holm({"a": 0.02, "b": 0.06}) == {"a": True, "b": False}


def test_noninferiority_decisions_and_p_value():
    rng = np.random.default_rng(0)
    good = rng.normal(0.0, 0.05, 80)
    r = C.noninferiority(good, 0.10)
    assert r["noninferior"] and r["p"] < 0.001
    bad = rng.normal(0.2, 0.05, 80)
    assert not C.noninferiority(bad, 0.10)["noninferior"]
    better = rng.normal(-0.1, 0.05, 80)
    assert C.noninferiority(better, 0.10)["superior"]
    # the p-value and the percentile bound agree on the decision, also for skewed effects
    for x in (good, bad, better, rng.normal(0.09, 0.1, 30), np.r_[np.zeros(17), 1.0]):
        r = C.noninferiority(x, 0.10)
        assert (r["p"] <= 0.05) == r["noninferior"]


def test_the_decision_rule_has_three_outcomes():
    rng = np.random.default_rng(0)
    good, bad, wide = rng.normal(0.0, 0.05, 80), rng.normal(0.3, 0.05, 80), rng.normal(0.1, 0.5, 20)
    assert C.decide(good)["status"] == "supported"
    r = C.decide(bad)  # the lower bound above delta
    assert r["status"] == "inferior" and r["lower"] > C.DELTA and r["lower"] < r["upper"]
    assert C.decide(wide)["status"] == "inconclusive"
    assert C.decide(np.array([0.5]))["status"] == "inconclusive"  # one sequence: no claim


def test_heavy_tail_moves_the_mean_not_the_median():
    x = np.r_[np.zeros(17), 1.0]
    r = C.robust(x)
    assert r["median"] == 0.0 and r["trimmed_mean"] == 0.0
    assert x.mean() == pytest.approx(1 / 18)


def test_report_corrects_only_the_co_primary_models():
    rng = np.random.default_rng(1)
    cells = pd.DataFrame({
        "model": ["A"] * 400 + ["B"] * 400 + ["C"] * 400,
        "sequence_id": [f"s{i % 80}" for i in range(1200)],
        "d": np.r_[
            rng.normal(0, 0.05, 400), rng.normal(0.02, 0.05, 400), rng.normal(0.3, 0.05, 400)
        ],
    })  # fmt: skip
    t = C.report(cells, ("A", "B")).set_index("model")
    assert t.loc["A", "holm_noninferior"] and t.loc["B", "holm_noninferior"]
    assert t.loc["C", "holm_noninferior"] is None and not t.loc["C", "noninferior"]
    assert t.loc["A", "status"] == "supported" and t.loc["C", "status"] == "inferior"
    d = C.report(cells, ("A",), descriptive=("C",)).set_index("model")
    assert pd.isna(d.loc["C", "status"]) and pd.isna(d.loc["C", "lower"])  # no test row


def test_s2_is_prospective_only():
    assert "gpt-6.1-sol" not in C.SECONDARY and C.S2_MODEL == "gpt-6.1-sol"


def test_report_refuses_an_incomplete_co_primary_family():
    cells = pd.DataFrame({"model": ["A"] * 10, "sequence_id": [f"s{i}" for i in range(10)],
                          "d": np.zeros(10)})  # fmt: skip
    with pytest.raises(ValueError, match="primary results missing"):
        C.report(cells, ("A", "B"))


def test_hierarchical_model_recovers_the_mean():
    rng = np.random.default_rng(3)
    rows = []
    for i in range(60):
        u = rng.normal(0, 0.1)
        for j in range(4):
            v = rng.normal(0, 0.05)
            for w in ("day", "week", "month"):
                rows.append({"sequence_id": f"s{i}", "issue_id": f"s{i}@{j}", "window": w,
                             "stratum": C.stratum([0.1, 2.0, 10.0, 30.0][j]),
                             "d": 0.03 + u + v + rng.normal(0, 0.1)})  # fmt: skip
    r = C.hierarchical(pd.DataFrame(rows))
    assert abs(r["hier_mu"] - 0.03) < 3 * r["hier_se"]
    assert r["hier_noninferior"] and r["hier_converged"]
    assert 0.05 < r["hier_sd_sequence"] < 0.2 and r["hier_error"] is None
    assert C.stratum(0.5) == "under 1 day" and C.stratum(7.0) == "7 days or more"


def test_a_failed_hierarchical_fit_is_reported_not_raised():
    # two sequences with one issue each: a singular design (the run must still write its tables)
    cells = pd.DataFrame({"sequence_id": ["s0", "s1"], "issue_id": ["s0@first", "s1@first"],
                          "window": "day", "stratum": "under 1 day", "d": [0.0, 0.1]})  # fmt: skip
    r = C.hierarchical(cells)
    assert r["hier_error"] and np.isnan(r["hier_mu"]) and not r["hier_noninferior"]


def test_eligibility_follows_clean_periods_and_magnitude(monkeypatch):
    from laf import splits

    monkeypatch.setattr(splits, "development_ids", lambda: frozenset())
    ms = lambda d: pd.Timestamp(d, tz="UTC").value // 1_000_000  # noqa: E731
    seqs = pd.DataFrame({
        "sequence_id": ["old", "mid", "new", "small"],
        "origin_ms": [ms("2024-12-15"), ms("2026-01-15"), ms("2026-10-15"), ms("2026-10-20")],
        "mag": [6.0, 5.5, 5.1, 4.6],
    })  # fmt: skip
    assert C.eligible(seqs, "gpt-5.1-2025-11-13") == {"mid", "new"}
    assert C.eligible(seqs, "claude-opus-4-6") == {"mid", "new"}
    assert C.eligible(seqs, "claude-opus-5-5") == {"new"}
    assert C.eligible(seqs, "claude-opus-5-5", min_mag=0) == {"new", "small"}


def test_confirmatory_cells_keep_eligible_primary_prompt_samples(monkeypatch):
    from laf import splits

    monkeypatch.setattr(splits, "development_ids", lambda: frozenset({"dev"}))
    ms = lambda d: pd.Timestamp(d, tz="UTC").value // 1_000_000  # noqa: E731
    origins = [ms("2026-10-10"), ms("2025-06-01"), ms("2026-10-12")]
    seqs = pd.DataFrame(
        {"sequence_id": ["a", "b", "dev"], "origin_ms": origins, "mag": [5.5, 5.5, 6.0]}
    )
    rows = [  # model, effort, variant, status, sequence, d5
        ("claude-opus-5-5", "high", "v3A", "ok", "a", 0.1),
        ("claude-opus-5-5", "high", "v3A", "ok", "a", 0.3),
        ("claude-opus-5-5", "high", "v3A", "max_tokens", "a", None),  # counts log 2
        ("claude-opus-5-5", "high", "v3A", "transport_error", "a", None),  # left out
        ("claude-opus-5-5", "high", "v3B", "ok", "a", 9.0),  # robustness prompt: not here
        ("claude-opus-5-5", "medium", "v3A", "ok", "a", 7.0),  # other effort: not here
        ("gpt-5.1-2025-11-13", "medium", "v3A", "ok", "b", 0.2),
        ("gpt-5.1-2025-11-13", "medium", "v3A", "ok", "dev", 0.4),  # development: never
    ]
    names = ("model", "effort", "variant", "status", "sequence_id", "d5")
    samples = pd.DataFrame([dict(zip(names, r, strict=True)) for r in rows])
    samples = samples.assign(item_id=samples["sequence_id"] + "@1", window="day", worst_base_d5=0.5)
    elapsed = {"a@1": 0.5, "b@1": 3.0, "dev@1": 0.2}

    def got(**kw):
        cells = C.confirmatory_cells(samples, seqs, elapsed, **kw)
        return {
            (r.model, r.sequence_id): (round(float(r.d), 3), r.stratum)  # type: ignore[arg-type]
            for r in cells.itertuples()
        }

    # cell a: the invalid sample counts log 2, and the v3B answer's 9.0 is not here
    log2 = float(np.log(2))
    assert got() == {("claude-opus-5-5", "a"): (round((0.1 + 0.3 + log2) / 3, 3), "under 1 day"),
                     ("gpt-5.1-2025-11-13", "b"): (0.2, "1 to 7 days")}  # fmt: skip
    # the count score's rule: the worst baseline in the cell (0.5)
    worst = got(invalid="worst_baseline")
    assert worst[("claude-opus-5-5", "a")] == (round((0.1 + 0.3 + 0.5) / 3, 3), "under 1 day")
    assert C.study_effort("gpt-5.1-2025-11-13") == "medium"
    assert C.study_effort("claude-opus-4-6") == "medium"
    assert C.study_effort("gpt-6.1-sol") == "high"


def test_confirmatory_command_refuses_while_outcomes_are_sealed(tmp_path):
    from laf.cli import main
    from laf.splits import unsealed

    if unsealed():
        pytest.skip("prereg-v2 exists")
    (tmp_path / "r").mkdir()
    (tmp_path / "r/results.jsonl").write_text("")
    (tmp_path / "r/requests.jsonl").write_text("")
    with pytest.raises(SystemExit, match="sealed"):
        main(["confirmatory", "--snapshot", "20261029T2000Z", "--runs", str(tmp_path)])


def test_sensitivity_threshold_widens_only_the_named_model(monkeypatch):
    from laf import splits

    monkeypatch.setattr(splits, "development_ids", lambda: frozenset())
    ms = pd.Timestamp("2026-10-15", tz="UTC").value // 1_000_000
    seqs = pd.DataFrame({"sequence_id": ["big", "small"], "origin_ms": [ms, ms], "mag": [5.5, 4.5]})
    rows = [(m, e, sid) for m, e in (("gpt-5.1-2025-11-13", "medium"), ("claude-opus-5-5", "high"))
            for sid in ("big", "small")]  # fmt: skip
    samples = pd.DataFrame(rows, columns=["model", "effort", "sequence_id"])
    samples = samples.assign(variant="v3A", status="ok", d5=0.0, worst_base_d5=0.0, window="day",
                             item_id=samples["sequence_id"] + "@1")  # fmt: skip
    elapsed = {"big@1": 1.0, "small@1": 1.0}
    cells = C.confirmatory_cells(samples, seqs, elapsed, {"gpt-5.1-2025-11-13": 0.0})
    got = sorted(zip(cells["model"], cells["sequence_id"], strict=True))
    assert got == [("claude-opus-5-5", "big"), ("gpt-5.1-2025-11-13", "big"),
                   ("gpt-5.1-2025-11-13", "small")]  # fmt: skip


def test_co_primary_bounds_are_at_their_holm_level_and_superiority_is_its_own_family():
    rng = np.random.default_rng(5)
    cells = pd.DataFrame({
        "model": ["A"] * 400 + ["B"] * 400,
        "sequence_id": [f"s{i % 80}" for i in range(800)],
        "d": np.r_[rng.normal(-0.05, 0.05, 400), rng.normal(0.0, 0.08, 400)],
    })  # fmt: skip
    t = C.report(cells, ("A", "B")).set_index("model")
    assert sorted(t["holm_level"]) == [0.025, 0.05]
    for m in ("A", "B"):
        e = C.sequence_effects(cells[cells["model"] == m]).to_numpy()
        expect = C.noninferiority(e, alpha=float(t.loc[m, "holm_level"]))["upper"]  # type: ignore[arg-type]
        assert t.loc[m, "upper"] == pytest.approx(expect)
    assert t.loc["A", "superior"]  # clearly better, and non-inferior first
    assert C.holm_levels({"x": 0.3, "y": 0.01}) == {"y": 0.025, "x": 0.05}


def test_bootstrap_t_controls_size_better_on_heavy_tails():
    # one sequence in 18 at +1 nat (like gpt-5.1's development effects), true mean at delta
    e = np.r_[np.random.default_rng(4).normal(0, 0.055, 17), 1.0]
    pct = C.size(e, 89, alpha=0.025, sims=300, b=500, method="percentile")
    stu = C.size(e, 89, alpha=0.025, sims=300, b=500, method="student")
    assert stu < pct and stu < 0.05


def test_size_at_another_truth_is_power():
    e = np.random.default_rng(5).normal(0, 0.05, 30)
    assert C.size(e, 60, alpha=0.05, sims=100, b=300) < 0.15  # the truth at delta: the size
    assert C.size(e, 60, alpha=0.05, sims=100, b=300, truth=0.0) > 0.9  # far inside the margin


def test_descriptive_models_get_no_test():
    rng = np.random.default_rng(2)
    cells = pd.DataFrame({
        "model": ["A"] * 300 + ["B"] * 300 + ["S"] * 300,
        "sequence_id": [f"s{i % 60}" for i in range(900)],
        "d": rng.normal(0, 0.05, 900),
    })  # fmt: skip
    t = C.report(cells, ("A", "B"), descriptive=("S",)).set_index("model")
    assert pd.isna(t.loc["S", "noninferior"]) and pd.isna(t.loc["S", "upper"])
    assert t.loc["S", "median"] == t.loc["S", "median"]  # summaries kept


def test_bootstrap_t_keeps_the_tail_of_zero_variance_resamples():
    # 17 tied effects and one outlier: about a third of resamples hold only the ties, whose mean
    # lies below the observed mean; their T* must count as -inf, not 0 (Codex review)
    e = np.r_[np.zeros(17), 1.0]
    r = C.noninferiority(e, 0.10, alpha=0.025)
    assert not r["noninferior"] and r["upper"] == float("inf")
    flat = C.noninferiority(np.zeros(30), 0.10)
    assert not flat["noninferior"] and flat["p"] == 1.0


def test_fewer_than_two_sequences_make_no_claim():
    for e in (np.array([0.2]), np.array([-0.5]), np.array([])):
        for method in ("student", "percentile"):
            r = C.noninferiority(e, 0.10, method=method)
            assert not r["noninferior"] and not r["superior"] and r["p"] == 1.0
    cells = pd.DataFrame({"model": ["A", "B", "B"], "sequence_id": ["s1", "s1", "s2"],
                          "d": [0.2, 0.0, 0.01]})  # fmt: skip
    t = C.report(cells, ("A",)).set_index("model")
    assert not t.loc["A", "noninferior"] and not t.loc["A", "superior"]


def _contrast_samples(n_seq: int = 12, d5: float = -0.3, naive: float = 0.2, rj: float = 0.5):
    """Synthetic per-sample rows: every sequence one cell, two valid samples and one invalid.
    The model is `d5` below official; the rule of thumb `naive` and generic RJ `rj` above."""
    rng = np.random.default_rng(0)
    rows = []
    for i in range(n_seq):
        jitter = float(rng.normal(0, 0.05))
        for st in ("ok", "ok", "max_tokens"):
            rows.append({"model": "gpt-5.1-2025-11-13", "effort": "medium", "variant": "v3A",
                         "status": st, "sequence_id": f"s{i}", "item_id": f"s{i}@1",
                         "window": "day", "d5": d5 + jitter if st == "ok" else None,
                         "worst_base_d5": 1.0, "base_d5_naive": naive, "base_d5_generic_rj": rj,
                         "base_d5_rj_mle": 0.1, "base_d5_etas": d5 + jitter})  # fmt: skip
    return pd.DataFrame(rows)


def test_contrasts_take_ds_against_each_baseline_and_test_superiority():
    s = _contrast_samples()
    seqs = pd.DataFrame({"sequence_id": s["sequence_id"].unique()})
    elapsed = {i: 2.0 for i in s["item_id"]}
    sets = {"gpt-5.1-2025-11-13": set(seqs["sequence_id"])}
    cells = C.confirmatory_cells(s, seqs, elapsed, reference="naive", sets=sets)
    # per cell: valid answers d5 - naive, the invalid one log 2 - naive (prereg v2 section 7)
    first = s[s["sequence_id"] == "s0"]
    want = (first["d5"].iloc[0] * 2 + np.log(2)) / 3 - 0.2
    assert float(cells.loc[cells["sequence_id"] == "s0", "d"].iloc[0]) == pytest.approx(want)
    t = C.contrasts(s, seqs, elapsed, ("gpt-5.1-2025-11-13",), sets).set_index("reference")
    assert bool(t.loc["generic_rj", "superior"])  # well below generic RJ
    lo, mid, up = (float(t.loc["etas", c]) for c in ("lower95", "mean", "upper95"))  # type: ignore[arg-type]
    assert lo < mid < up  # an interval, no test, against ETAS
    assert pd.isna(t.loc["etas", "superior"])


def test_assay_flags_a_test_that_cannot_separate_from_generic_rj():
    s = _contrast_samples(rj=0.0)  # generic RJ as good as the official forecast
    ids = {"sequence_id": s["sequence_id"].unique(), "issue_id": s["item_id"].unique()}
    cells = pd.DataFrame({"model": C.PRIMARY[0], **ids, "window": "day", "d": 0.0})
    noisy = s.assign(base_d5_generic_rj=np.random.default_rng(1).normal(0, 0.02, len(s)))
    assert C.assay(noisy, cells).iloc[0]["generic_rj_status"] == "noninferior"
    worse = s.assign(base_d5_generic_rj=0.5 + np.random.default_rng(2).normal(0, 0.02, len(s)))
    assert C.assay(worse, cells).iloc[0]["generic_rj_status"] == "inferior"
    near = s.assign(base_d5_generic_rj=0.1 + np.random.default_rng(4).normal(0, 0.3, len(s)))
    assert C.assay(near, cells).iloc[0]["generic_rj_status"] == "inconclusive"  # no claim
    one = cells.head(1)  # one sequence: no spread, so no claim either way
    assert C.assay(s, one).iloc[0]["generic_rj_status"] == "inconclusive"
    # on a secondary model's cells: the estimate and bounds, no label
    other = C.assay(worse, cells.assign(model="claude-opus-5-5")).iloc[0]
    assert other["generic_rj_status"] is None and other["generic_rj_lower"] > C.DELTA


def test_informative_sequences_use_generic_rj_at_the_first_issue_with_a_month_window(monkeypatch):
    from pathlib import Path

    from laf import analysis as A

    proc = Path("data/processed/20261021T2300Z")  # development data
    tables, items = A.load_tables(proc), A.load_items(proc)
    keep = C.informative(tables, items)
    mag = tables["sequences"].set_index("sequence_id")["mag"]
    assert keep and keep < set(mag.index)  # some sequences qualify, not all
    # a larger mainshock means more expected aftershocks: every M>=6 sequence qualifies
    assert set(mag.index[mag >= 6.0]) <= keep and mag[sorted(keep)].mean() > mag.mean()
    # the rule reads forecasts only: the same set with every count hidden
    blind = tables | {"observed_counts": tables["observed_counts"].assign(count=-1)}
    assert C.informative(blind, items) == keep
    monkeypatch.setattr(C, "INFORMATIVE_P", 0.0)
    assert C.informative(tables, items) == set(mag.index)  # every sequence has a month window


def test_contrasts_follow_test_as_widened_eligibility(monkeypatch):
    from laf import splits

    monkeypatch.setattr(splits, "development_ids", lambda: frozenset())
    s = _contrast_samples(n_seq=6)
    origin = pd.Timestamp("2026-06-01", tz="UTC").value // 1_000_000
    seqs = pd.DataFrame({"sequence_id": [f"s{i}" for i in range(6)], "origin_ms": origin,
                         "mag": [5.5, 5.5, 5.5, 4.5, 4.5, 4.5]})  # fmt: skip
    elapsed = {i: 2.0 for i in s["item_id"]}
    m = ("gpt-5.1-2025-11-13",)
    m5 = C.contrasts(s, seqs, elapsed, m)
    wide = C.contrasts(s, seqs, elapsed, m, min_mag={m[0]: 0.0})
    assert set(m5["sequences"]) == {3} and set(wide["sequences"]) == {6}


def test_test_b_resamples_its_two_parts_separately():
    rng = np.random.default_rng(3)
    retro, pro = rng.normal(0.0, 0.05, 20), rng.normal(0.3, 0.05, 10)
    x = np.concatenate([retro, pro])
    parts = np.array(["retrospective"] * 20 + ["prospective"] * 10)
    pooled, strat = C.noninferiority(x), C.noninferiority(x, strata=parts)
    assert strat["mean"] == pytest.approx(pooled["mean"]) and strat["strata"] == 2
    # the gap between the parts is fixed by design, not sampling noise: a tighter bound
    assert strat["upper"] < pooled["upper"]
    one = np.array(["prospective"] + ["retrospective"] * 29)  # a part of one: no spread
    assert C.noninferiority(x, strata=one) == pooled
    assert C.noninferiority(x, strata=np.array(["retrospective"] * 30)) == pooled
    with pytest.raises(ValueError, match="bootstrap-t"):  # never a silent change of method
        C.noninferiority(x, strata=parts, method="percentile")


def test_confirmatory_batches_send_each_models_own_set_in_parts(monkeypatch):
    from types import SimpleNamespace

    from laf import splits

    monkeypatch.setattr(splits, "development_ids", lambda: frozenset())
    ms = lambda d: pd.Timestamp(d, tz="UTC").value // 1_000_000  # noqa: E731
    seqs = pd.DataFrame({"sequence_id": [f"s{i}" for i in range(7)] + ["us7000s2bn"],
                         "origin_ms": [ms(f"2025-0{i + 2}-01") for i in range(7)]
                                      + [ms("2026-03-05")],
                         "mag": [5.5, 5.5, 5.5, 4.5, 4.5, 5.2, 5.0, 5.5]})  # fmt: skip
    items = [SimpleNamespace(sequence_id=s, item_id=f"{s}@first") for s in seqs["sequence_id"]]

    def got(*a, **k):
        return {i.sequence_id for i in C.batch_items(items, seqs, *a, **k)}

    gpt = "gpt-5.1-2025-11-13"
    assert got(gpt, "confirmatory") == {"s0", "s1", "s2", "s5", "s6"}  # M>=5, forward out
    assert got(gpt, "confirmatory-sens") == {"s3", "s4"}  # test A's sensitivity set
    parts = [got(gpt, "confirmatory", chunk=f"{k}/2") for k in (1, 2)]
    assert parts[0] | parts[1] == got(gpt, "confirmatory") and not parts[0] & parts[1]
    assert got(gpt, "confirmatory", include_forward=True) == {"us7000s2bn"}
    with pytest.raises(SystemExit, match="v3B"):
        got("claude-opus-4-6", "confirmatory-v3b")
    with pytest.raises(SystemExit, match="test A"):
        got("claude-opus-4-6", "confirmatory-sens")
    # the unbuffered rule's extras: clean only without the buffer, M>=5
    monkeypatch.setattr(C, "clean_from", lambda m, rule="buffered": pd.Timestamp(
        "2025-04-15" if rule == "buffered" else "2025-01-15", tz="UTC"))  # fmt: skip
    assert got(gpt, "confirmatory") == {"s5", "s6"}
    assert got(gpt, "confirmatory-unbuffered") == {"s0", "s1", "s2"}
    with pytest.raises(SystemExit, match="test A"):
        got("claude-opus-5-5", "confirmatory-unbuffered")


def _snapshot(tmp_path, monkeypatch):
    """A synthetic snapshot with no items: the run commands never touch a real one."""
    from laf import openai_runner, pilot, runner

    (tmp_path / "processed/S").mkdir(parents=True)
    pd.DataFrame({"sequence_id": ["s"], "origin_ms": [0], "mag": [5.0]}).to_parquet(
        tmp_path / "processed/S/sequences.parquet"
    )
    monkeypatch.setattr(pilot, "load_items", lambda *a: [])
    monkeypatch.setattr(runner, "RUNS", tmp_path / "runs")

    def refuse(*a, **k):
        raise AssertionError("submitted")

    monkeypatch.setattr(openai_runner, "submit", refuse)
    monkeypatch.setattr(runner, "submit", refuse)
    return ["--data-dir", str(tmp_path)]


def test_the_openai_run_name_option_is_kept(tmp_path, monkeypatch, capsys):
    from laf import cli

    seen = {}
    monkeypatch.setattr(cli, "_batch_name", lambda a: seen.setdefault("default", "x") and "x")
    args = [*_snapshot(tmp_path, monkeypatch), "openai", "run", "--block", "confirmatory",
            "--snapshot", "S", "--name", "confirmatory/custom-test", "--dry-run"]  # fmt: skip
    cli.main(args)
    assert "confirmatory/custom-test:" in capsys.readouterr().out and "default" not in seen
    assert (tmp_path / "processed/S/items_m3.jsonl").read_text() == ""  # written once, if absent


def test_confirmatory_batches_are_paid_only_after_the_tag(tmp_path, monkeypatch):
    from laf import cli, splits

    monkeypatch.setattr(splits, "_tagged", lambda tag: False)
    data = _snapshot(tmp_path, monkeypatch)
    for cmd in (["openai", "run"], ["run", "--model", "claude-opus-4-6"]):
        with pytest.raises(SystemExit, match="only after the tag prereg-v2"):
            cli.main([*data, *cmd, "--block", "confirmatory", "--snapshot", "S"])
        cli.main([*data, *cmd, "--block", "confirmatory", "--snapshot", "S", "--dry-run"])


def test_the_runners_never_rewrite_the_frozen_items(tmp_path, monkeypatch):
    from laf import cli

    data = _snapshot(tmp_path, monkeypatch)
    (tmp_path / "processed/S/items_m3.jsonl").write_text('{"item_id": "a"}\n')
    with pytest.raises(SystemExit, match="differs from a fresh rebuild"):
        cli.main([*data, "openai", "run", "--block", "confirmatory", "--snapshot", "S",
                  "--dry-run"])  # fmt: skip
    assert (tmp_path / "processed/S/items_m3.jsonl").read_text() == '{"item_id": "a"}\n'


def test_leave_one_sequence_out_influence():
    cells = pd.DataFrame({"sequence_id": [f"s{i}" for i in range(20)],
                          "d": np.r_[np.zeros(19), 2.0]})  # fmt: skip
    t = C.influence(cells).set_index("sequence_id")
    assert len(t) == 20 and t["mean"].iloc[0] == pytest.approx(0.1)
    assert t.loc["s19", "mean_without"] == 0.0 and t.loc["s0", "mean_without"] == pytest.approx(
        2 / 19
    )
    parts = pd.Series(["r"] * 10 + ["p"] * 10, index=[f"s{i}" for i in range(20)])
    assert len(C.influence(cells, parts)) == 20  # test B: its strata kept


def test_a_supported_row_that_is_measurably_worse_says_so_and_estimates_get_no_verdict():
    rng = np.random.default_rng(1)
    cells = pd.DataFrame({
        "model": ["A"] * 400 + ["B"] * 400 + ["C"] * 400,
        "sequence_id": [f"s{i % 80}" for i in range(1200)],
        "d": np.r_[
            rng.normal(0, 0.05, 400), rng.normal(0.02, 0.05, 400), rng.normal(0.3, 0.05, 400)
        ],
    })  # fmt: skip
    t = C.report(cells, ("A",), unlabeled=("C",)).set_index("model").to_dict("index")
    assert t["A"]["status"] == "supported"
    # B: upper bound below the margin, lower bound above 0
    assert t["B"]["status"] == C.WORSE_INSIDE and 0 < t["B"]["lower"] < t["B"]["upper"]
    assert t["B"]["noninferior"]
    # C keeps its estimate and bounds, without a label
    assert pd.isna(t["C"]["status"]) and pd.isna(t["C"]["noninferior"])
    assert t["C"]["lower"] > C.DELTA and abs(t["C"]["mean"] - 0.3) < 0.02


def test_the_rule_of_thumb_control_is_labelled_as_test_a_is():
    s = _contrast_samples()
    ids = {"sequence_id": s["sequence_id"].unique(), "issue_id": s["item_id"].unique()}
    cells = pd.DataFrame({"model": C.PRIMARY[0], **ids, "window": "day", "d": 0.0})
    bad = s.assign(base_d5_naive=0.4 + np.random.default_rng(2).normal(0, 0.02, len(s)))
    control = C.assay(bad, cells, baseline="naive").iloc[0]
    assert control["naive_status"] == "inferior" and abs(control["naive_mean"] - 0.4) < 0.02
    assert "generic_rj_status" not in control.index  # columns carry the baseline's name
    slightly = s.assign(base_d5_naive=0.02 + np.random.default_rng(3).normal(0, 0.005, len(s)))
    assert C.assay(slightly, cells, baseline="naive").iloc[0]["naive_status"] == C.WORSE_INSIDE


def test_identical_effects_never_support_and_a_constant_deficit_is_inferior():
    ties = C.decide(np.zeros(30))
    assert ties["status"] == "inconclusive" and not ties["noninferior"]  # ties prove nothing
    never_answers = C.decide(np.full(89, np.log(2)))  # every answer invalid
    assert never_answers["status"] == "inferior" and never_answers["lower"] > C.DELTA
    cells = pd.DataFrame({"model": "A", "sequence_id": [f"s{i}" for i in range(89)],
                          "d": np.log(2)})  # fmt: skip
    assert C.report(cells, ("A",)).iloc[0]["status"] == "inferior"


def test_a_measurably_worse_row_says_so_on_either_side_of_the_margin():
    rng = np.random.default_rng(5)
    z = rng.normal(0, 1, 100)
    z = (z - z.mean()) / z.std(ddof=1)  # mean exactly 0, SD exactly 1
    wide = C.decide(0.045 + 0.06 * z)  # lower bound above 0, upper bound above delta
    assert 0 < wide["lower"] < C.DELTA < wide["upper"] and wide["status"] == C.WORSE_UNBOUNDED
    tight = C.decide(0.02 + rng.normal(0, 0.02, 200))  # the deficit is bounded inside the margin
    assert 0 < tight["lower"] < tight["upper"] < C.DELTA and tight["status"] == C.WORSE_INSIDE
