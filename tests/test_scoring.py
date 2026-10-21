import math

import numpy as np
from scipy import stats

from laf import scoring as s


def test_pinball_and_log_quantile_score_by_hand():
    assert math.isclose(s.pinball(2.0, 0.9), 1.8)
    assert math.isclose(s.pinball(-2.0, 0.9), 0.2)
    qs = [0, 0, 1, 1, 2, 3, 4, 5, 6]
    want = (
        sum(
            2 * s.pinball(math.log(3) - math.log(q + 1), t)
            for q, t in zip(qs, s.LEVELS, strict=True)
        )
        / 9
    )
    assert math.isclose(s.quantile_score(qs, 2), want)
    assert s.quantile_score([2] * 9, 2) == 0.0
    assert s.quantile_score(qs, 2, log=False) > 0


def test_true_poisson_quantiles_minimize_expected_score():
    lam, n = 4.0, np.arange(60)
    pmf = stats.poisson.pmf(n, lam)
    true = [float(stats.poisson.ppf(t, lam)) for t in s.LEVELS]
    expected = lambda qs: sum(p * s.quantile_score(qs, int(y)) for y, p in zip(n, pmf, strict=True))  # noqa: E731
    best = expected(true)
    for shift in (-1, 1, 2):
        assert expected([max(q + shift, 0) for q in true]) > best


def test_interval_coverage_boundaries_are_inclusive():
    qs = [0, 1, 2, 3, 4, 5, 6, 7, 8]
    assert s.interval_covered(qs, 3, 50) and s.interval_covered(qs, 5, 50)
    assert not s.interval_covered(qs, 6, 50) and s.interval_covered(qs, 8, 95)


def test_randomized_pit_is_uniform_for_calibrated_forecasts():
    rng = np.random.default_rng(0)
    lam = 3.0
    cdf = stats.poisson.cdf(np.arange(40), lam)
    ys = rng.poisson(lam, 4000)
    full = [s.pit_cdf(cdf, int(y), rng) for y in ys]
    assert stats.kstest(full, "uniform").pvalue > 0.01
    # quantile-resolution PIT is uniform only when counts are effectively continuous
    big = 400.0
    qs_big = [float(stats.poisson.ppf(t, big)) for t in s.LEVELS]
    ranks = np.array([s.pit_rank(qs_big, int(y), rng) for y in rng.poisson(big, 8000)])
    edges = np.array((0.0, *s.LEVELS, 1.0))
    density = np.histogram(ranks, edges)[0] / len(ranks) / np.diff(edges)
    assert np.all(np.abs(density - 1) < 0.3)


def test_binary_scores_closed_form():
    assert s.brier(0.2, True) == (0.2 - 1) ** 2
    assert math.isclose(s.log_score_binary(0.0, True), -math.log(1e-3))
    assert math.isclose(s.log_score_binary(0.3, False), -math.log(0.7))


def test_bootstrap_intervals_cover_the_estimate():
    rng = np.random.default_rng(1)
    issues = [np.array([x, x + 0.1, x - 0.1]) for x in (0.1, 0.3, -0.2, 0.4, 0.0)]
    est, lo, hi = s.sequence_ci(issues, rng, b=2000)
    assert lo <= est <= hi
    est2, lo2, hi2 = s.pooled_ci([issues, issues[:3]], rng, b=2000)
    assert lo2 <= est2 <= hi2
    assert sorted(s.moving_block(5, rng)) != [] and len(s.moving_block(5, rng)) == 5
