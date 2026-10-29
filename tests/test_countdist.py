import numpy as np
import pytest
from scipy import stats

from laf.countdist import (
    from_cdf_array,
    from_quantiles,
    log_score,
    n_test,
    nb_fit,
    pit,
)
from laf.scoring import LEVELS


def _quantile(cdf, tau, top):
    return int(np.argmax(cdf(np.arange(0, top + 2)) >= tau))


@pytest.mark.parametrize("tail", ["power", "nb"])
def test_every_input_quantile_is_reproduced_exactly(tail):
    rng = np.random.default_rng(1)
    for _ in range(300):
        q = np.sort(rng.integers(0, rng.integers(1, 80), size=9)).astype(float)
        d = from_quantiles(q, tail=tail)
        assert [_quantile(d.cdf, t, int(q[-1])) for t in LEVELS] == list(q)


def test_cdf_is_a_count_distribution():
    d = from_quantiles((0, 0, 1, 2, 4, 7, 11, 14, 17))
    n = np.arange(-1, 500)
    f = d.cdf(n)
    assert f[0] == 0.0 and np.all(np.diff(f) >= 0) and f[-1] > 0.9999
    assert np.all(d.pmf(n) >= 0)


@pytest.mark.parametrize(
    "dist",
    [stats.poisson(0.2), stats.poisson(3), stats.poisson(50), stats.nbinom(0.5, 0.5 / 5.5)],
)
def test_nine_quantiles_recover_the_expected_log_score(dist):
    ys = np.arange(0, int(dist.ppf(0.9999)) + 1)
    w = dist.pmf(ys)
    true = float(np.sum(w * -np.log(np.maximum(w, 1e-6))))
    d = from_quantiles(dist.ppf(LEVELS))
    rec = float(np.sum(w * np.array([log_score(d.cdf, int(y))[0] for y in ys])))
    assert true <= rec + 1e-9 < true + 0.06  # proper score: never better than the truth


def test_fine_fractiles_are_nearly_exact():
    lam, fine = 10.0, np.arange(1, 400) * 0.0025
    d = from_quantiles(stats.poisson.ppf(fine, lam), fine)
    for y in range(5, 16):  # inside the fractile range; below 0.0025 the lower tail is crude
        assert abs(log_score(d.cdf, y)[0] + stats.poisson.logpmf(y, lam)) < 0.05


def test_n_test_pit_and_floor():
    cdf = lambda n: stats.poisson.cdf(n, 3.0)  # noqa: E731
    d1, d2 = n_test(cdf, 3)
    assert d1 == pytest.approx(1 - stats.poisson.cdf(2, 3)) and d2 == pytest.approx(
        stats.poisson.cdf(3, 3)
    )
    u = pit(cdf, 3, np.random.default_rng(0))
    assert stats.poisson.cdf(2, 3) <= u <= stats.poisson.cdf(3, 3)
    score, floored = log_score(lambda n: stats.poisson.cdf(n, 0.01), 40)
    assert floored and score == pytest.approx(-np.log(1e-6))


def test_cdf_arrays_end_at_one_and_start_at_zero():
    f = from_cdf_array(np.array([0.5, 0.9, 1.0]))
    assert list(f(np.array([-1, 0, 1, 2, 3, 10]))) == [0.0, 0.5, 0.9, 1.0, 1.0, 1.0]


def test_negative_binomial_fit_recovers_its_parameters():
    r, mu = 2.0, 20.0
    rr, pp = nb_fit(stats.nbinom.ppf(LEVELS, r, r / (r + mu)))
    assert abs(rr / r - 1) < 0.1 and abs(rr * (1 - pp) / pp / mu - 1) < 0.1


def test_bad_quantiles_are_refused():
    with pytest.raises(ValueError):
        from_quantiles((3, 2, 1, 0, 0, 0, 0, 0, 0))
    with pytest.raises(ValueError):
        from_quantiles((0, 1), (0.5, 0.25))
