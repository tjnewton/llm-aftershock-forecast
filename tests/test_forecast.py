import math

import numpy as np
from scipy import integrate, stats

from laf import forecast as f
from laf.scoring import LEVELS


def test_rj_expected_matches_quadrature():
    for p in (0.8, 1.0, 1.3):
        num = integrate.quad(lambda t, p=p: (t + 0.02) ** -p, 1.0, 8.0)[0]
        want = 10 ** (-2.4 + 1.0 * (7.7 - 5.0)) * num
        got = f.rj_expected(-2.4, 1.0, p, 0.02, 7.7, 5.0, 1.0, 8.0)
        assert math.isclose(got, want, rel_tol=1e-6)


def test_zero_uncertainty_equals_poisson():
    params = {"a_p05": -2.4, "a_p50": -2.4, "a_p95": -2.4, "b": 1.0, "p": 1.1, "c_days": 0.05}
    cell = f.rj_predictive(params, 7.7, 1.0, 8.0)
    lam5 = f.rj_expected(-2.4, 1.0, 1.1, 0.05, 7.7, 5.0, 1.0, 8.0)
    assert cell.m5 == tuple(float(stats.poisson.ppf(t, lam5)) for t in LEVELS)
    lam6 = f.rj_expected(-2.4, 1.0, 1.1, 0.05, 7.7, 6.0, 1.0, 8.0)
    assert cell.p_m6 is not None and math.isclose(cell.p_m6, 1 - math.exp(-lam6), rel_tol=1e-9)


def test_equal_scales_equal_a_normal_mixture():
    params = {"a_p05": -2.9, "a_p50": -2.4, "a_p95": -1.9, "b": 1.0, "p": 1.0, "c_days": 0.05}
    cell = f.rj_predictive(params, 7.5, 0.0, 30.0)
    sigma = 0.5 / 1.645
    lam6 = lambda a: f.rj_expected(a, 1.0, 1.0, 0.05, 7.5, 6.0, 0.0, 30.0)  # noqa: E731
    density = lambda a: stats.norm.pdf(a, -2.4, sigma) * math.exp(-lam6(a))  # noqa: E731
    want = 1 - integrate.quad(density, -6, 2)[0]
    assert cell.p_m6 is not None and math.isclose(cell.p_m6, want, rel_tol=1e-6)


def test_rj_mle_recovers_omori_parameters():
    rng = np.random.default_rng(3)
    k, c, p, t_end = 30.0, 0.05, 1.1, 20.0
    n = rng.poisson(k * f.omori_integral(c, p, 0.0, t_end))
    u = rng.uniform(size=n)  # inverse transform of the Omori-Utsu density on [0, t_end)
    t = ((c ** (1 - p) + u * ((t_end + c) ** (1 - p) - c ** (1 - p))) ** (1 / (1 - p))) - c
    mags = 4.95 + rng.exponential(math.log10(math.e), n) * math.log(10) / math.log(10)
    fit = f.fit_rj_mle(t, np.round(mags, 1), 7.5, 0.0, t_end)
    assert fit is not None
    assert abs(fit.p - p) < 0.15
    assert abs(10 ** (fit.a + fit.b * (7.5 - 5.0)) - k) / k < 0.35
    assert f.fit_rj_mle(t[:5], mags[:5], 7.5, 0.0, t_end) is None


def test_naive_never_counts_the_mainshock_and_scales_by_b():
    cell = f.naive_forecast(0, 3.0, 3.0, 10.0)
    assert cell.m5 == (0.0,) * 9 and cell.p_m6 == 0.0
    cell = f.naive_forecast(10, 3.0, 3.0, 10.0)
    k = 10 / math.log(3.05 / 0.05)
    lam5 = k * math.log(10.05 / 3.05)
    assert cell.m5[4] == float(stats.poisson.ppf(0.5, lam5))
    assert cell.p_m6 is not None and math.isclose(cell.p_m6, 1 - math.exp(-lam5 / 10))
