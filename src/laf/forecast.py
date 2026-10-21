"""Every forecaster in the common representation (docs/PLAN.md 5.1): nine quantiles of N(M>=5)
and N(M>=4), P(N(M>=6) >= 1), and the full M>=5 distribution where one exists."""

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.polynomial.hermite import hermgauss
from numpy.polynomial.legendre import leggauss
from scipy import optimize, stats

from laf.scoring import LEVELS

DAY_MS = 86_400_000
M5, M4, M6 = 5.0, 4.0, 6.0
MC_FIT = 4.95  # RJ-MLE fit threshold: catalog M >= 4.95 (magnitudes are binned at 0.1)
_X, _W = hermgauss(128)
GH_X, GH_W = _X[_X > 0], 2 * _W[_X > 0] / math.sqrt(math.pi)  # 64 nodes per half-normal


@dataclass
class CellForecast:
    m5: tuple[float, ...]
    m4: tuple[float, ...] | None
    p_m6: float | None
    cdf_m5: np.ndarray | None = None  # F(n), n = 0, 1, ...
    fractiles_m5: tuple[tuple[float, ...], tuple[float, ...]] | None = None  # (levels, counts)


def omori_integral(c: float, p: float, t1: float, t2: float) -> float:
    if abs(p - 1.0) < 1e-6:
        return math.log((t2 + c) / (t1 + c))
    return ((t2 + c) ** (1 - p) - (t1 + c) ** (1 - p)) / (1 - p)


def rj_expected(a, b, p, c, mag_main, mag, t1_days, t2_days) -> float:
    """Expected count of M >= mag in [t1, t2] days: 10^(a + b(Mm - M)) * integral (t+c)^-p."""
    return 10 ** (a + b * (mag_main - mag)) * omori_integral(c, p, t1_days, t2_days)


def poisson_mixture(lams: np.ndarray, weights: np.ndarray) -> tuple[tuple[float, ...], np.ndarray]:
    """Quantiles at LEVELS (smallest n with F(n) >= tau) and the cdf of a Poisson mixture."""
    # support up to the mixture's 1 - 1e-6 point: extreme quadrature nodes carry ~0 weight
    order = np.argsort(lams)
    upper = (
        lams[order][np.searchsorted(np.cumsum(weights[order]), 1 - 1e-6)]
        if len(lams) > 1
        else lams[0]
    )
    nmax = min(int(stats.poisson.ppf(1 - 1e-9, max(float(upper), 1e-12))) + 2, 2_000_000)
    n = np.arange(nmax + 1)
    cdf = (weights[:, None] * stats.poisson.cdf(n[None, :], lams[:, None])).sum(axis=0)
    qs = tuple(float(np.searchsorted(cdf, tau - 1e-12)) for tau in LEVELS)
    return qs, cdf


def split_normal_nodes(a05: float, a50: float, a95: float) -> tuple[np.ndarray, np.ndarray]:
    """Nodes and weights for a split normal with median a50 and 5/95% points a05, a95."""
    sl, su = (a50 - a05) / 1.645, (a95 - a50) / 1.645
    if sl + su <= 0:
        return np.array([a50]), np.array([1.0])
    nodes = np.concatenate([a50 - sl * math.sqrt(2) * GH_X, a50 + su * math.sqrt(2) * GH_X])
    weights = np.concatenate([GH_W / 2, GH_W / 2])  # half the mass each side: a50 is the median
    return nodes, weights


def rj_mixture(
    a_nodes: np.ndarray, a_weights: np.ndarray, b: float, p: float, c: float, mag_main: float,
    t1: float, t2: float,
) -> CellForecast:  # fmt: skip
    """Poisson mixture over the distribution of a, for one window [t1, t2] days."""
    lam = lambda m: np.array([rj_expected(a, b, p, c, mag_main, m, t1, t2) for a in a_nodes])  # noqa: E731
    q5, cdf5 = poisson_mixture(lam(M5), a_weights)
    q4, _ = poisson_mixture(lam(M4), a_weights)
    p6 = float(1.0 - (a_weights * np.exp(-lam(M6))).sum())
    return CellForecast(q5, q4, p6, cdf5)


def rj_predictive(params: dict, mag_main: float, t1: float, t2: float) -> CellForecast:
    """Parameter arm: split-normal a from the elicited 5/50/95% values (PLAN 5.1)."""
    nodes, weights = split_normal_nodes(params["a_p05"], params["a_p50"], params["a_p95"])
    return rj_mixture(nodes, weights, params["b"], params["p"], params["c_days"], mag_main, t1, t2)


def generic_rj(seq: dict, mag_main: float, t1: float, t2: float) -> CellForecast:
    """USGS generic RJ (ADR 0009): a ~ Normal(mean, sigma(Mm)) truncated to [a_min, a_max]."""
    sigma = math.sqrt(
        seq["generic_a_sigma0"] ** 2 + seq["generic_a_sigma1"] ** 2 / 10 ** max(mag_main, 6.0)
    )
    x, w = leggauss(200)
    lo, hi = seq["generic_a_min"], seq["generic_a_max"]
    nodes = lo + (x + 1) * (hi - lo) / 2
    weights = w * stats.norm.pdf(nodes, seq["generic_a_mean"], sigma)
    return rj_mixture(
        nodes, weights / weights.sum(), seq["generic_b"], seq["generic_p"],
        seq["generic_c_days"], mag_main, t1, t2,
    )  # fmt: skip


@dataclass
class RJFit:
    a: float
    sigma_a: float
    b: float
    p: float
    c: float
    n: int


def fit_rj_mle(
    t_days: np.ndarray, mags: np.ndarray, mag_main: float, t_start: float, t_end: float
) -> RJFit | None:
    """Omori-Utsu MLE (Ogata 1983) on M >= 4.95 events in [t_start, t_end) days, c in
    [1e-4, 2], p in [0.5, 2]; Aki-Utsu b (binning-corrected) if >= 50 events, else 1.0.
    None with fewer than 10 events."""
    sel = (mags >= MC_FIT) & (t_days >= t_start) & (t_days < t_end) & (t_days > 0)
    t, m = t_days[sel], mags[sel]
    n = len(t)
    if n < 10:
        return None

    def nll(x):  # x = (ln K, ln c, p)
        k, c, p = math.exp(x[0]), math.exp(x[1]), x[2]
        return -(n * x[0] - p * np.log(t + c).sum() - k * omori_integral(c, p, t_start, t_end))

    def profile(y):  # K at its closed-form optimum n / integral
        c, p = math.exp(y[0]), y[1]
        return nll((math.log(n / omori_integral(c, p, t_start, t_end)), y[0], p))

    res = optimize.minimize(
        profile, x0=(math.log(0.05), 1.0), method="L-BFGS-B",
        bounds=[(math.log(1e-4), math.log(2.0)), (0.5, 2.0)],
    )  # fmt: skip
    lc, p = float(res.x[0]), float(res.x[1])
    c = math.exp(lc)
    lnk = math.log(n / omori_integral(c, p, t_start, t_end))
    x0 = np.array([lnk, lc, p])
    h = np.array([1e-4, 1e-4, 1e-4])
    hess = np.empty((3, 3))
    for i in range(3):
        for j in range(3):
            ei, ej = np.eye(3)[i] * h[i], np.eye(3)[j] * h[j]
            hess[i, j] = (
                nll(x0 + ei + ej) - nll(x0 + ei - ej) - nll(x0 - ei + ej) + nll(x0 - ei - ej)
            ) / (4 * h[i] * h[j])
    try:
        var = float(np.linalg.inv(hess)[0, 0])
        sigma_lnk = math.sqrt(var) if var > 0 else 1 / math.sqrt(n)
    except np.linalg.LinAlgError:
        sigma_lnk = 1 / math.sqrt(n)
    b = math.log10(math.e) / (m.mean() - (MC_FIT)) if n >= 50 else 1.0
    a = lnk / math.log(10) - b * (mag_main - M5)  # rate of M >= 5 is K
    return RJFit(a, sigma_lnk / math.log(10), b, p, c, n)


def rj_mle_forecast(fit: RJFit, mag_main: float, t1: float, t2: float) -> CellForecast:
    s = 1.645 * fit.sigma_a
    nodes, weights = split_normal_nodes(fit.a - s, fit.a, fit.a + s)
    return rj_mixture(nodes, weights, fit.b, fit.p, fit.c, mag_main, t1, t2)


def naive_forecast(n_m5_so_far: int, elapsed_days: float, t1: float, t2: float) -> CellForecast:
    """Omori-scaled persistence: p = 1, c = 0.05 d; K from the M>=5 count so far; M>=4 and
    M>=6 by b = 1; Poisson."""
    c = 0.05
    k = n_m5_so_far / math.log((elapsed_days + c) / c)
    lam5 = k * math.log((t2 + c) / (t1 + c))
    one = np.array([1.0])
    q5, cdf5 = poisson_mixture(np.array([lam5]), one)
    q4, _ = poisson_mixture(np.array([10 * lam5]), one)
    return CellForecast(q5, q4, float(1 - math.exp(-lam5 / 10)), cdf5)


def direct_forecast(parsed: dict, window_key: str) -> CellForecast:
    w = parsed[window_key]
    keys = ("q025", "q050", "q100", "q250", "q500", "q750", "q900", "q950", "q975")
    return CellForecast(
        tuple(float(w["m5_count_quantiles"][k]) for k in keys),
        tuple(float(w["m4_count_quantiles"][k]) for k in keys),
        float(w["p_m6_at_least_one"]),
    )


def official_forecast(
    fractiles: pd.DataFrame, bins: pd.DataFrame, sequence_id: str, cutoff_ms: int, window: str
) -> CellForecast:
    """The matched official version: fractiles at the nine levels (exact grid points), the full
    fractile grid for PIT, and the published probability of the M>=6 bin."""
    f = fractiles[
        (fractiles["sequence_id"] == sequence_id)
        & (fractiles["info_cutoff_ms"] == cutoff_ms)
        & (fractiles["window"] == window)
    ]

    def at(mag: float) -> tuple[float, ...] | None:
        g = f[f["magnitude"] == mag].sort_values("p")
        if g.empty:
            return None
        return tuple(float(g.loc[np.isclose(g["p"], tau), "count"].iloc[0]) for tau in LEVELS)

    g5 = f[f["magnitude"] == M5].sort_values("p")
    b6 = bins[
        (bins["sequence_id"] == sequence_id)
        & (bins["info_cutoff_ms"] == cutoff_ms)
        & (bins["window"] == window)
        & (bins["magnitude"] == M6)
    ]
    m5 = at(M5)
    if m5 is None:
        raise ValueError(f"no official M>=5 fractiles for {sequence_id} {cutoff_ms} {window}")
    return CellForecast(
        m5,
        at(M4),
        float(b6["probability"].iloc[0]) if len(b6) else None,
        fractiles_m5=(tuple(g5["p"]), tuple(float(x) for x in g5["count"])),
    )


def etas_forecast(row: dict) -> CellForecast:
    """Legacy-ETAS refit (ADR 0010): M>=5 quantiles, P(M>=6), histogram of simulated counts."""
    hist = np.asarray(row["hist_m5"], dtype=float)
    cdf = np.cumsum(hist) / hist.sum() if hist.sum() > 0 else None
    keys = ("q025", "q050", "q100", "q250", "q500", "q750", "q900", "q950", "q975")
    return CellForecast(tuple(float(row[k]) for k in keys), None, float(row["p_m6"]), cdf)
