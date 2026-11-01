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
    assert 0.05 < r["hier_sd_sequence"] < 0.2
    assert C.stratum(0.5) == "under 1 day" and C.stratum(7.0) == "7 days or more"


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
        ("claude-opus-5-5", "high", "v2A", "ok", "a", 0.1),
        ("claude-opus-5-5", "high", "v2A", "ok", "a", 0.3),
        ("claude-opus-5-5", "high", "v2A", "max_tokens", "a", None),  # gets the cell's worst
        ("claude-opus-5-5", "high", "v2A", "transport_error", "a", None),  # left out
        ("claude-opus-5-5", "high", "v2B", "ok", "a", 9.0),  # robustness prompt: not here
        ("claude-opus-5-5", "medium", "v2A", "ok", "a", 7.0),  # other effort: not here
        ("gpt-5.1-2025-11-13", "medium", "v2A", "ok", "b", 0.2),
        ("gpt-5.1-2025-11-13", "medium", "v2A", "ok", "dev", 0.4),  # development: never
    ]
    names = ("model", "effort", "variant", "status", "sequence_id", "d5")
    samples = pd.DataFrame([dict(zip(names, r, strict=True)) for r in rows])
    samples = samples.assign(item_id=samples["sequence_id"] + "@1", window="day", worst_base_d5=0.5)
    cells = C.confirmatory_cells(samples, seqs, {"a@1": 0.5, "b@1": 3.0, "dev@1": 0.2})
    got = {
        (r.model, r.sequence_id): (round(float(r.d), 3), r.stratum)  # type: ignore[arg-type]
        for r in cells.itertuples()
    }
    # cell a: the invalid sample takes the worst baseline (0.5), not the v2B answer's 9.0
    assert got == {("claude-opus-5-5", "a"): (round((0.1 + 0.3 + 0.5) / 3, 3), "under 1 day"),
                   ("gpt-5.1-2025-11-13", "b"): (0.2, "1 to 7 days")}  # fmt: skip
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
    samples = samples.assign(variant="v2A", status="ok", d5=0.0, worst_base_d5=0.0, window="day",
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
            rows.append({"model": "gpt-5.1-2025-11-13", "effort": "medium", "variant": "v2A",
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
    # per cell: valid answers d5 - naive, the invalid one worst - naive (ADR 0018 decision 12)
    first = s[s["sequence_id"] == "s0"]
    want = (first["d5"].iloc[0] * 2 + 1.0) / 3 - 0.2
    assert float(cells.loc[cells["sequence_id"] == "s0", "d"].iloc[0]) == pytest.approx(want)
    t = C.contrasts(s, seqs, elapsed, ("gpt-5.1-2025-11-13",), sets).set_index("reference")
    assert bool(t.loc["generic_rj", "superior"])  # well below generic RJ
    lo, mid, up = (float(t.loc["etas", c]) for c in ("lower95", "mean", "upper95"))  # type: ignore[arg-type]
    assert lo < mid < up  # an interval, no test, against ETAS
    assert pd.isna(t.loc["etas", "superior"])


def test_assay_flags_a_test_that_cannot_separate_from_generic_rj():
    s = _contrast_samples(rj=0.0)  # generic RJ as good as the official forecast
    ids = {"sequence_id": s["sequence_id"].unique(), "issue_id": s["item_id"].unique()}
    cells = pd.DataFrame({"model": "m", **ids, "window": "day", "d": 0.0})
    noisy = s.assign(base_d5_generic_rj=np.random.default_rng(1).normal(0, 0.02, len(s)))
    assert C.assay(noisy, cells).iloc[0]["generic_rj_status"] == "noninferior"
    worse = s.assign(base_d5_generic_rj=0.5 + np.random.default_rng(2).normal(0, 0.02, len(s)))
    assert C.assay(worse, cells).iloc[0]["generic_rj_status"] == "inferior"
    near = s.assign(base_d5_generic_rj=0.1 + np.random.default_rng(4).normal(0, 0.3, len(s)))
    assert C.assay(near, cells).iloc[0]["generic_rj_status"] == "inconclusive"  # no claim
    one = cells.head(1)  # one sequence: no spread, so no claim either way
    assert C.assay(s, one).iloc[0]["generic_rj_status"] == "inconclusive"


def test_informative_sequences_use_the_official_mean_at_the_first_issue():
    p = np.linspace(0.0, 1.0, 101)
    rows = []
    for sid, cutoff, scale in (("big", 1, 1.0), ("big", 2, 0.0), ("small", 1, 0.1)):
        rows += [{"sequence_id": sid, "info_cutoff_ms": cutoff, "window": "1 Month",
                  "magnitude": 5.0, "p": q, "count": scale * q} for q in p]  # fmt: skip
    rows += [{"sequence_id": "small", "info_cutoff_ms": 1, "window": "1 Month", "magnitude": 4.0,
              "p": q, "count": 50.0} for q in p]  # M>=4 never counts  # fmt: skip
    tables = {
        "forecast_fractiles": pd.DataFrame(rows),
        "issue_times": pd.DataFrame(
            {"sequence_id": ["big", "big", "small"], "issue_ms": [2, 1, 1]}
        ),
    }
    # big: first issue (cutoff 1) has mean 0.5 (the integral of q on [0, 1]); small: 0.05
    assert C.informative(tables) == {"big"}


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
    with pytest.raises(SystemExit, match="v2B"):
        got("claude-opus-4-6", "confirmatory-v2b")
    with pytest.raises(SystemExit, match="test A"):
        got("claude-opus-4-6", "confirmatory-sens")
