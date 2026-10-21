from itertools import pairwise

import numpy as np
import pytest
from scipy import integrate, special, stats

from laf.etas import (
    MREF,
    Draw,
    FitData,
    gr_magnitudes,
    kernel_terms,
    log_likelihood,
    omori_integral,
    omori_times,
    simulate_counts,
)


@pytest.mark.parametrize("p", [0.8, 1.0, 1.25])
def test_omori_integral_matches_quadrature(p):
    c = 0.02
    exact = integrate.quad(lambda s: (s + c) ** (-p), 0.3, 12.0)[0]
    assert float(omori_integral(0.3, 12.0, c, p)) == pytest.approx(exact, rel=1e-9)


def test_grid_likelihood_equals_brute_force():
    rng = np.random.default_rng(1)
    t = np.sort(rng.uniform(0.01, 5.0, 40))
    m = MREF + rng.exponential(0.43, 40)
    d = FitData(mag_main=7.5, t_c=0.2, t_end=5.0, t_trig=t, m_trig=m, target=t >= 0.2)
    c, p, ams, a = 0.05, 1.1, -2.0, -2.4
    A, S, IA, IS = kernel_terms(d, c, p)
    got = float(log_likelihood(ams + 7.5 - MREF, a, A, S, IA, IS))

    def lam(x):
        prev = t < x
        return 10 ** (ams + 7.5 - MREF) * (x + c) ** (-p) + np.sum(
            10 ** (a + m[prev] - MREF) * (x - t[prev] + c) ** (-p)
        )

    targets = t[t >= 0.2]
    breaks = np.concatenate([[0.2], targets, [5.0]])
    integral = sum(integrate.quad(lam, lo, hi)[0] for lo, hi in pairwise(breaks))
    expected = sum(np.log(lam(x)) for x in targets) - integral
    assert got == pytest.approx(expected, rel=1e-7)


def test_omori_times_follow_the_truncated_density():
    rng = np.random.default_rng(2)
    c, p, s0, s1 = 0.01, 1.2, 0.5, 30.0
    x = omori_times(rng, np.full(20000, s0), np.full(20000, s1), c, p)
    total = float(omori_integral(s0, s1, c, p))
    cdf = lambda v: omori_integral(s0, v, c, p) / total  # noqa: E731
    assert stats.kstest(x, cdf).pvalue > 0.01
    assert x.min() >= s0 and x.max() <= s1


def test_gr_magnitudes_have_b_value_one():
    m = gr_magnitudes(np.random.default_rng(3), 200_000)
    assert m.min() >= MREF
    assert np.mean(m >= MREF + 1.0) == pytest.approx(0.1, abs=0.003)


def test_without_secondary_triggering_counts_are_poisson_from_the_mainshock():
    rng = np.random.default_rng(4)
    dr = Draw(ams=-2.0, a=-30.0, c=0.02, p=1.05)
    draws = [dr] * 4000
    win = [(1.0, 8.0)]
    counts, capped = simulate_counts(rng, draws, 7.0, np.array([]), np.array([]), 1.0, win, (5.0,))
    mean = 10 ** (dr.ams + 7.0 - MREF) * float(omori_integral(1.0, 8.0, dr.c, dr.p))
    x = counts[:, 0, 0]
    assert not capped.any()
    assert x.mean() == pytest.approx(mean, rel=0.05)
    assert x.var() == pytest.approx(mean, rel=0.1)


def test_secondary_triggering_adds_overdispersion():
    rng = np.random.default_rng(5)
    base = Draw(ams=-2.0, a=-30.0, c=0.02, p=1.05)
    etas = Draw(ams=-2.0, a=-2.2, c=0.02, p=1.05)
    win = [(1.0, 31.0)]
    x0 = simulate_counts(rng, [base] * 2000, 7.0, np.array([]), np.array([]), 1.0, win, (5.0,))[0]
    x1 = simulate_counts(rng, [etas] * 2000, 7.0, np.array([]), np.array([]), 1.0, win, (5.0,))[0]
    assert x1.mean() > x0.mean()
    assert x1.var() / x1.mean() > 1.5 > x0.var() / x0.mean()


# ---- legacy USGS ETAS ("Bayesian Combination") ----
from pathlib import Path  # noqa: E402

from laf.etas import (  # noqa: E402
    fit_legacy,
    generic_etas,
    legacy_logspace,
    legacy_terms,
    sample_posterior,
    simulate_legacy,
)
from laf.generic_rj import REFERENCE_REL  # noqa: E402

REF = Path(__file__).parents[1] / "data" / REFERENCE_REL


def test_c_grid_reproduces_published_values():
    # Kamchatka products publish c = 0.0055 (31-point grid) and 0.0042 (21-point grid).
    assert round(float(legacy_logspace(1e-5, 1.0, 31)[17]), 4) == 0.0055
    assert round(float(legacy_logspace(1e-5, 1.0, 21)[11]), 4) == 0.0042
    assert legacy_logspace(1e-5, 1.0, 31)[-1] == 1.0


def test_generic_etas_regime_and_mc_reference():
    g = generic_etas(REF, 7.587, -80.769)  # Panama
    assert (g.regime, g.a, g.mmax) == ("SZ-GENERIC", -2.268, 9.5)
    assert g.a0(4.95) == pytest.approx(-2.268 + np.log10(5.0 / 4.55))


def test_legacy_prior_is_the_documented_normal():
    from laf.etas import _log_prior

    g = generic_etas(REF, 7.587, -80.769)
    pts = [(-2.0, -2.3, 1.0, 0.01), (-2.5, -1.9, 0.9, 1e-4)]
    got = [float(_log_prior(g, 4.95, *x)) for x in pts]
    mvn = stats.multivariate_normal(mean=[g.a0(4.95), g.p, -2.5], cov=g.cov().tolist())
    ref = [
        mvn.logpdf([a, p, np.log10(c)]) + stats.norm.logpdf(ams, g.a0(4.95), g.asig)
        for ams, a, p, c in pts
    ]
    assert got[0] - got[1] == pytest.approx(ref[0] - ref[1], rel=1e-9)


def test_legacy_terms_use_magnitude_dependent_c():
    rng = np.random.default_rng(6)
    t = np.sort(rng.uniform(0.01, 3.0, 25))
    m = 5.0 + rng.exponential(0.43, 25)
    c0, p, ac, mc, mm = 0.002, 1.05, -2.2, 4.95, 7.6
    A, S, IA, _ = legacy_terms(t, m, mm, mc, c0, p, ac, 3.0, 1.0)
    k = 10 ** (m - mc)
    ci = c0 * (10**ac * k) ** (1 / p)
    j = 10
    assert S[j] == pytest.approx(np.sum(k[:j] * (t[j] - t[:j] + ci[:j]) ** (-p)))
    kms = 10 ** (mm - mc)
    cms = c0 * (10**ac * kms) ** (1 / p)
    assert A[j] == pytest.approx(kms * (t[j] + cms) ** (-p))
    assert pytest.approx(kms * integrate.quad(lambda x: (x + cms) ** (-p), 0, 3.0)[0]) == IA


def test_legacy_fit_recovers_a_synthetic_sequence():
    rng = np.random.default_rng(7)
    g = generic_etas(REF, 7.587, -80.769)
    truth = (-1.9, -2.4, 1.05, 0.01)  # ams, a, p, c
    cnt, _ = simulate_legacy(
        rng,
        np.array([truth[0]]),
        np.array([truth[1]]),
        np.array([truth[2]]),
        np.array([truth[3]]),
        7.7,
        4.95,
        1.0,
        9.5,
        np.array([]),
        np.array([]),
        4.95,
        0.0,
        [(0.0, 20.0)],
        (4.95,),
    )
    # Regenerate event times and magnitudes for the fit from a dedicated simulation.
    from laf.etas import omori_times

    n_ms = rng.poisson(
        10 ** (truth[0] + 7.7 - 4.95) * float(omori_integral(0.0, 20.0, truth[3], 1.05))
    )
    t = np.sort(omori_times(rng, np.zeros(n_ms), np.full(n_ms, 20.0), truth[3], 1.05))
    m = np.round(4.95 - np.log10(rng.random(n_ms)), 1)
    post = fit_legacy(t, m, 7.7, 4.95, 1.0, g, 20.0, n=15)
    assert post.weight.sum() == pytest.approx(1.0)
    ams_draws = sample_posterior(rng, post, 4000)[0]
    lo, hi = np.quantile(ams_draws, [0.005, 0.995])
    assert lo <= truth[0] <= hi
    assert cnt.shape == (1, 1, 1)


def test_posterior_is_normalized_and_nonnegative():
    g = generic_etas(REF, 52.4948, 160.2395)
    post = fit_legacy(np.array([0.5, 1.0]), np.array([5.3, 5.6]), 8.8, 5.15, 1.0, g, 2.0, n=9)
    assert np.all(post.weight >= 0) and post.weight.sum() == pytest.approx(1.0)


def test_min_mag_rule_follows_the_code_in_force():
    from laf.etas import MIN_MAG_RULE_CHANGE_MS, legacy_min_mag

    rng = np.random.default_rng(8)
    ams, a, p, c = (np.full(100, x) for x in (-2.0, -2.3, 1.0, 0.01))
    t, m = np.array([0.1, 0.5]), np.array([6.1, 5.4])
    old = legacy_min_mag(
        rng, ams, a, p, c, 7.7, 4.95, 1.0, 9.5, t, m, 1.0, made_ms=MIN_MAG_RULE_CHANGE_MS - 1
    )
    new = legacy_min_mag(
        rng, ams, a, p, c, 7.7, 4.95, 1.0, 9.5, t, m, 1.0, made_ms=MIN_MAG_RULE_CHANGE_MS
    )
    assert old == 3.0  # before 2026-10-14: start at 3.0
    assert new == pytest.approx(7.7 - 4.0)  # after: max(Mms, aftershocks) - 4


def test_low_min_mag_lowers_counts_when_b_exceeds_alpha():
    # alpha = min(b, 1) = 1 < b = 1.12: the expected M>=5 count rises with minMag, which is why
    # the minMag rule matters for the late Flores and Kamchatka versions.
    rng = np.random.default_rng(9)
    ams, a, p, c = (np.full(3000, x) for x in (-2.0, -2.3, 1.0, 0.01))
    lo = simulate_legacy(
        rng,
        ams,
        a,
        p,
        c,
        7.7,
        4.95,
        1.12,
        9.5,
        np.array([]),
        np.array([]),
        3.0,
        1.0,
        [(1.0, 8.0)],
        (5.0,),
    )[0].mean()
    hi = simulate_legacy(
        rng,
        ams,
        a,
        p,
        c,
        7.7,
        4.95,
        1.12,
        9.5,
        np.array([]),
        np.array([]),
        4.7,
        1.0,
        [(1.0, 8.0)],
        (5.0,),
    )[0].mean()
    assert hi > 1.2 * lo


def test_legacy_fractiles_scale_counts_below_the_simulated_minimum():
    from laf.etas import LEVELS, _poisson_quantile, legacy_fractiles

    rng = np.random.default_rng(10)
    n = rng.poisson(6.0, 10_000)
    plain = legacy_fractiles(n, 1.1, 5.0, 3.0)
    assert list(plain) == list(np.quantile(n, LEVELS, method="inverted_cdf").astype(int))
    s = 10 ** (1.1 * 0.8)
    assert list(legacy_fractiles(n, 1.1, 5.0, 5.8)) == [int(s * v + 0.5) for v in plain]
    # Fractiles <= 1 become continuous Poisson quantiles at the rate implied by P(N = 0).
    sparse = rng.poisson(0.7, 10_000)
    lam = -np.log(np.mean(sparse == 0))
    disc = np.quantile(sparse, LEVELS, method="inverted_cdf")
    got = legacy_fractiles(sparse, 1.0, 5.0, 5.8)
    for f, v, g in zip(LEVELS, disc, got, strict=True):
        x = _poisson_quantile(lam, f) if v <= 1 else v
        assert g == int(10**0.8 * x + 0.5)
    for f in (0.3, 0.6, 0.9):
        assert special.gammaincc(_poisson_quantile(lam, f), lam) == pytest.approx(f, abs=1e-8)


def test_fetched_events_keep_only_the_forecast_circle_before_the_cutoff():
    import pandas as pd

    from laf.etas import fetched_events
    from laf.oaf import Circle

    cat = pd.DataFrame(
        {
            "time_ms": [1_000, 2_000, 2_500, 3_000, 4_000],
            "latitude": [0.0, 0.0, 5.0, 0.0, 0.0],  # the M7 lies 556 km away
            "longitude": [0.0, 0.5, 0.0, 0.0, 0.0],
            "mag": [5.0, 6.0, 7.0, 4.5, 6.5],
        }
    )
    t, m = fetched_events(cat, 0, 3_500, Circle(0.0, 0.0, 100.0))
    assert list(m) == [5.0, 6.0, 4.5]
    assert list(t * 86_400_000) == pytest.approx([1_000, 2_000, 3_000])


def test_v2_rule_uses_smoothed_median_ratio_and_sequence_pass_rates():
    import pandas as pd

    from laf.etas import v2_decision, v2_evaluate

    ours = [0, 1, 71, 3, 4, 5]
    official = [0, 0, 95, 2, 3, 4]  # ratios 1.0, 2.0, 0.75, 4/3, 1.25, 1.2
    ids = ["A@1d", "A@3d", "A@7d", "B@1d", "B@3d", "B@7d"]
    val = pd.DataFrame({"issue_id": ids, "window": "1 Day", "q500": ours})
    times = list(range(len(ids)))  # one official version per issue time
    its = pd.DataFrame({"issue_id": ids, "sequence_id": [i[0] for i in ids], "issue_ms": times})
    fr = pd.DataFrame(
        [
            {"sequence_id": i[0], "info_cutoff_ms": t, "window": "1 Day", "magnitude": 5.0,
             "p": p, "count": c}
            for i, t, c in zip(ids, times, official, strict=True)
            for p in (0.025, 0.5, 0.975)
        ]
    )  # fmt: skip
    seqs = pd.DataFrame({"sequence_id": ["A", "B"], "name": ["Alpha", "Beta"]})
    v = v2_evaluate(val, its, fr, seqs)
    assert v["ok"].tolist() == [True, False, True, True, True, True]  # bounds 0.75, 1/0.75
    rate, by_seq, eligible = v2_decision(v)
    assert rate == pytest.approx(5 / 6)
    assert by_seq == pytest.approx({"Alpha": 2 / 3, "Beta": 1.0})
    assert eligible == ["Beta"]
    with pytest.raises(ValueError, match="official"):
        v2_evaluate(val, its, fr[fr["count"] != 95], seqs)


def test_fetched_events_keep_ties_at_the_largest_events_cut(monkeypatch):
    import pandas as pd

    import laf.etas as etas
    from laf.oaf import Circle

    monkeypatch.setattr(etas, "MAX_FETCHED", 3)
    cat = pd.DataFrame(
        {"time_ms": [1, 2, 3, 4, 5], "latitude": 0.0, "longitude": 0.0,
         "mag": [5.0, 4.5, 4.5, 6.0, 4.0]}
    )  # fmt: skip
    _, m = etas.fetched_events(cat, 0, 10, Circle(0.0, 0.0, 10.0))
    assert list(m) == [5.0, 4.5, 4.5, 6.0]  # both M4.5 events tie at the 3rd-largest magnitude


JAVA = Path(__file__).parent / "golden" / "java"


def _java_catalog(path: Path):
    """Catalog file written for the USGS Java command line (times truncated to seconds)."""
    from datetime import UTC, datetime

    import pandas as pd

    rows = []
    for line in path.read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            y, mo, d, h, mi, s, lat, lon, _, mag = line.split()
            t = datetime(int(y), int(mo), int(d), int(h), int(mi), int(float(s)), tzinfo=UTC)
            rows.append({"time_ms": int(t.timestamp() * 1000), "latitude": float(lat),
                         "longitude": float(lon), "mag": float(mag)})  # fmt: skip
    return pd.DataFrame(rows)


@pytest.mark.parametrize("case", sorted(p.name for p in JAVA.iterdir()))
def test_fit_reproduces_the_usgs_java_map_exactly(case):
    # opensha-oaf 08a274bde278 command line on the same catalog, Mc, b and forecast start
    # (runs/java_differential): the grid MAP must be the same node, to full precision.
    import json

    from laf.etas import DAY_MS, fetched_events
    from laf.oaf import parse_forecast

    d = JAVA / case
    exp = json.loads((d / "expected.json").read_text())
    f = parse_forecast((d / "forecast.json").read_bytes())
    par = f.model.parameters
    origin = exp["origin_used_ms"]
    cutoff = origin + round(exp["forecast_start_days"] * DAY_MS)
    t, m = fetched_events(_java_catalog(d / "catalog.txt"), origin, cutoff, f.region)
    g = generic_etas(REF, f.region.lat, f.region.lon)
    post = fit_legacy(t, m, float(par["magMain"]), float(par["Mc"]), float(par["b"]), g,
                      exp["forecast_start_days"], n=tuple(exp["grid"]))  # fmt: skip
    assert post.map == pytest.approx(tuple(exp["map"]), rel=1e-9, abs=1e-12)


def test_legacy_probability_is_one_minus_weight_at_the_smallest_count():
    from laf.etas_validate import legacy_probability

    n = np.array([0, 0, 1, 2, 5])
    assert legacy_probability(n, 1.0, 6.0, 3.0) == pytest.approx(0.6)  # P(N >= 1)
    n = np.array([1, 1, 2, 3])  # no zero catalog: the legacy value is not P(N >= 1) = 1
    assert legacy_probability(n, 1.0, 6.0, 3.0) == pytest.approx(0.5)
    # Below minMag: 1 - (1 - P)^(10^(b (minMag - M)))
    p = legacy_probability(np.array([0, 1, 1, 1]), 1.1, 5.0, 5.8)
    assert p == pytest.approx(1 - 0.25 ** (10 ** (1.1 * 0.8)))


def test_fit_options_for_analyst_settings():
    from laf.etas import legacy_grids

    rng = np.random.default_rng(11)
    g = generic_etas(REF, 7.587, -80.769)
    t = np.sort(rng.uniform(0.01, 3.0, 12))
    m = np.round(4.95 - np.log10(rng.random(12)), 1)
    base = fit_legacy(t, m, 7.7, 4.95, 1.0, g, 3.0, n=15)
    assert fit_legacy(t, m, 7.7, 4.95, 1.0, g, 3.0, n=15, mc_prior=4.95).map == base.map
    fixed = fit_legacy(t, m, 7.7, 4.95, 1.0, g, 3.0, n=(15, 15, 15, 1), c_range=(0.003, 0.003))
    assert fixed.map[3] == 0.003 and fixed.weight.shape[3] == 1  # c pinned (Colombia 2026)
    # prior and ranges set at another Mc shift the a and ams grids by log10 of the Mc ratio
    a1 = legacy_grids(g, 4.95)[1]
    a2 = legacy_grids(g, 4.25)[1]
    shift = np.log10((g.mmax - 4.95) / (g.mmax - 4.25))
    assert np.median(a2 - a1) == pytest.approx(shift, abs=0.006)


def test_analyst_settings_rules_match_the_version_window_start():
    from laf.etas import analyst_kwargs, load_analyst_settings

    rules = load_analyst_settings(Path(__file__).parents[1] / "config" / "analyst_settings.toml")
    assert analyst_kwargs(rules, "us6000t7zp", 3.247) == {
        "regime": "SZ-GENERIC",
        "time_dep_mc": True,
    }
    assert analyst_kwargs(rules, "us6000t7zp", 39.7) == {}  # code defaults after the first month
    kw = analyst_kwargs(rules, "us6000tjl2", 3.143)
    assert kw["c_range"] == (0.003, 0.003) and kw["grid"] == (31, 31, 31, 1)
    assert (
        analyst_kwargs(rules, "us6000u18k", 1.0) == {}
        and analyst_kwargs(rules, "us6000tjl2", None) == {}
    )
