"""Count distributions from quantiles, and the scores of docs/adr/0015 (log score, N-test,
randomized PIT). Pure functions.

A forecast that gives only quantiles of a count N (the direct arm's nine, or an official
product's 197 or 399 fractiles) is turned into a full distribution through a continuous latent
Y with F_Y(n) = F_N(n) at every integer n. The tau-quantile of N is q, so the tau-quantile of Y
lies in (q - 1, q). Knots are placed inside that interval (ties spread evenly) and F_Y is
interpolated with a monotone cubic (PCHIP) on z = log(y + 1). Below the first knot F_Y rises
linearly from 0 at y = -1. Above the last knot 1 - F_Y decays as exp(-lam (z - z_K)), a power
law in y + 1, with lam matched to the last segment's slope. By construction the distribution
reproduces every input quantile exactly.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from scipy import optimize, special, stats
from scipy.interpolate import PchipInterpolator

from laf.scoring import LEVELS

Quantiles = Sequence[float] | np.ndarray
LOG_FLOOR = 1e-6  # p(n) floor before the log (ADR 0015); how often it binds is reported


@dataclass(frozen=True)
class QuantileCountDist:
    """F(n) of a count reconstructed from quantiles (module docstring)."""

    z: np.ndarray  # knots on z = log(y + 1), strictly increasing
    tau: np.ndarray  # F_Y at the knots, strictly increasing
    tail: float  # lam of the power-law upper tail
    nb: tuple[float, float] | None = None  # (r, p): negative-binomial-shaped upper tail instead

    def cdf(self, n) -> np.ndarray:
        y = np.asarray(n, dtype=float)
        out = np.zeros_like(y)
        z = np.log(np.maximum(y, -1 + 1e-12) + 1)
        y1 = math.exp(self.z[0]) - 1
        low = (y > -1) & (y <= y1)
        out[low] = self.tau[0] * (y[low] + 1) / (y1 + 1)
        mid = (z > self.z[0]) & (z <= self.z[-1])
        if mid.any():
            out[mid] = PchipInterpolator(self.z, self.tau)(z[mid])
        high = z > self.z[-1]
        if self.nb is not None:  # survival ratio of the NB, continuous in y (incomplete beta)
            r, p = self.nb
            yk = math.exp(self.z[-1]) - 1
            s = 1 - special.betainc(r, y[high] + 1, p)
            out[high] = 1 - (1 - self.tau[-1]) * s / (1 - special.betainc(r, yk + 1, p))
        else:
            out[high] = 1 - (1 - self.tau[-1]) * np.exp(-self.tail * (z[high] - self.z[-1]))
        return np.clip(out, 0.0, 1.0)

    def pmf(self, n) -> np.ndarray:
        n = np.asarray(n, dtype=float)
        return self.cdf(n) - self.cdf(n - 1)


def from_quantiles(
    counts: Quantiles, levels: Quantiles = LEVELS, tail: str = "power"
) -> QuantileCountDist:
    """tail="power" (module docstring) or "nb": 1 - F beyond the last knot follows the survival
    function of the negative binomial fitted to the same quantiles, scaled to match there."""
    q = np.asarray(counts, dtype=float)
    t = np.asarray(levels, dtype=float)
    if len(q) != len(t) or len(q) < 2:
        raise ValueError("need matching quantiles and levels, at least two")
    if np.any(np.diff(t) <= 0) or np.any(np.diff(q) < 0) or q[0] < 0:
        raise ValueError("levels must increase and quantiles must be non-decreasing and >= 0")
    q = np.round(q)
    y = np.empty_like(q)
    i = 0
    while i < len(q):  # a run of equal quantiles v: knots spread evenly inside (v - 1, v)
        j = i
        while j + 1 < len(q) and q[j + 1] == q[i]:
            j += 1
        k = j - i + 1
        y[i : j + 1] = q[i] - 1 + np.arange(1, k + 1) / (k + 1)
        i = j + 1
    z = np.log(y + 1)
    lam = (t[-1] - t[-2]) / (z[-1] - z[-2]) / (1 - t[-1])
    nb = None
    if tail == "nb":
        r, p = nb_fit(q, t)
        if 1 - special.betainc(r, float(y[-1]) + 1, p) > 1e-12:
            nb = (r, p)
    return QuantileCountDist(z, t, float(lam), nb)


def from_cdf_array(cdf: np.ndarray):
    """F(n) for a forecast given as cdf[n] = F(n), n = 0..len-1 (F = 1 beyond)."""
    c = np.asarray(cdf, dtype=float)

    def f(n) -> np.ndarray:
        n = np.asarray(n)
        out = np.ones(n.shape)
        out[n < 0] = 0.0
        inside = (n >= 0) & (n < len(c))
        out[inside] = c[n[inside].astype(int)]
        return out

    return f


def nb_fit(counts: Quantiles, levels: Quantiles = LEVELS) -> tuple[float, float]:
    """Negative binomial (size r, success probability p) whose CDF best matches the quantiles:
    least squares between tau and the CDF midway between q - 1 and q (smooth in r and mu)."""
    q = np.round(np.asarray(counts, dtype=float))
    t = np.asarray(levels, dtype=float)

    def loss(x):
        r, mu = math.exp(x[0]), math.exp(x[1])
        p = r / (r + mu)
        mid = 0.5 * (stats.nbinom.cdf(q - 1, r, p) + stats.nbinom.cdf(q, r, p))
        return float(np.sum((mid - t) ** 2))

    mu0 = max(float(np.median(q)), 0.05)
    starts = (0.3, 1.0, 5.0, 50.0)
    fits = [
        optimize.minimize(loss, (math.log(r0), math.log(mu0)), method="Nelder-Mead")
        for r0 in starts
    ]
    best = min(fits, key=lambda res: res.fun)
    r, mu = math.exp(best.x[0]), math.exp(best.x[1])
    return r, r / (r + mu)


def nb_from_quantiles(counts: Quantiles, levels: Quantiles = LEVELS):
    r, p = nb_fit(counts, levels)
    return lambda n: stats.nbinom.cdf(np.asarray(n), r, p)


def log_score(cdf, y: int, floor: float = LOG_FLOOR) -> tuple[float, bool]:
    """-log p(y) with p floored; also whether the floor bound."""
    p = float(cdf(np.array([y]))[0] - cdf(np.array([y - 1]))[0])
    return -math.log(max(p, floor)), p < floor


def n_test(cdf, y: int) -> tuple[float, float]:
    """CSEP N-test quantiles (Zechar et al. 2010): delta1 = P(N >= y), delta2 = P(N <= y)."""
    return 1.0 - float(cdf(np.array([y - 1]))[0]), float(cdf(np.array([y]))[0])


def pit(cdf, y: int, rng) -> float:
    """Randomized PIT: uniform on [F(y - 1), F(y)]."""
    return float(rng.uniform(cdf(np.array([y - 1]))[0], cdf(np.array([y]))[0]))
