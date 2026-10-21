"""Proper scores for count-quantile forecasts (docs/adr/0001) and bootstrap intervals
(prereg section 6). Pure functions."""

import math
from collections.abc import Sequence

import numpy as np

LEVELS = (0.025, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.975)
CENTRAL = {50: (3, 5), 80: (2, 6), 90: (1, 7), 95: (0, 8)}  # indices of the interval ends
P_CLIP = 1e-3
BOOT_B = 10_000
BOOT_SEED = 20261021
BLOCK = 2  # moving-block length in issue times; about n**(1/3) for 4-6 issues per sequence


def pinball(u: float, tau: float) -> float:
    """rho_tau(u) = u * (tau - 1{u < 0})."""
    return u * (tau - (u < 0))


def quantile_score(qs: Sequence[float], y: int, *, log: bool = True) -> float:
    """(1/9) sum_k 2 rho_tau_k(f(y) - f(q_k)), f = log(x + 1) or identity. Lower is better."""
    f = (lambda x: math.log(x + 1.0)) if log else float
    return sum(2 * pinball(f(y) - f(q), t) for q, t in zip(qs, LEVELS, strict=True)) / len(LEVELS)


def interval_covered(qs: Sequence[float], y: int, level: int) -> bool:
    lo, hi = CENTRAL[level]
    return qs[lo] <= y <= qs[hi]


def pit_rank(qs: Sequence[float], y: float, rng, levels: Sequence[float] = LEVELS) -> float:
    """Randomized PIT at quantile resolution: uniform between the highest level whose quantile
    is below y and the lowest level whose quantile is above y (ties broken uniformly)."""
    lo = max((t for q, t in zip(qs, levels, strict=True) if q < y), default=0.0)
    hi = min((t for q, t in zip(qs, levels, strict=True) if q > y), default=1.0)
    return float(rng.uniform(lo, hi))


def pit_cdf(cdf: np.ndarray, y: int, rng) -> float:
    """Randomized PIT for a count forecast with cdf[n] = F(n): uniform on [F(y-1), F(y)]."""
    lo = float(cdf[y - 1]) if 0 < y <= len(cdf) else (0.0 if y <= 0 else 1.0)
    hi = float(cdf[y]) if y < len(cdf) else 1.0
    return float(rng.uniform(lo, hi))


def brier(p: float, event: bool) -> float:
    return (p - float(event)) ** 2


def log_score_binary(p: float, event: bool, eps: float = P_CLIP) -> float:
    p = min(max(p, eps), 1.0 - eps)
    return -math.log(p if event else 1.0 - p)


def moving_block(n: int, rng, block: int = BLOCK) -> np.ndarray:
    """Indices of one moving-block resample of n time-ordered units."""
    b = min(block, n)
    starts = rng.integers(0, n - b + 1, size=-(-n // b))
    return np.concatenate([np.arange(s, s + b) for s in starts])[:n]


def sequence_ci(issues: list[np.ndarray], rng, b: int = BOOT_B) -> tuple[float, float, float]:
    """Mean over cells and a 95% percentile interval from the within-sequence moving-block
    bootstrap over issue times (issues: time-ordered arrays of cell values)."""
    est = float(np.concatenate(issues).mean())
    reps = [
        np.concatenate([issues[i] for i in moving_block(len(issues), rng)]).mean() for _ in range(b)
    ]
    lo, hi = np.quantile(reps, [0.025, 0.975])
    return est, float(lo), float(hi)


def pooled_ci(seqs: list[list[np.ndarray]], rng, b: int = BOOT_B) -> tuple[float, float, float]:
    """Mean over all cells; two-stage bootstrap: sequences with replacement, then issue times
    by moving blocks within each drawn sequence."""
    est = float(np.concatenate([np.concatenate(s) for s in seqs]).mean())
    reps = []
    for _ in range(b):
        drawn = [seqs[j] for j in rng.integers(0, len(seqs), size=len(seqs))]
        reps.append(np.concatenate([s[i] for s in drawn for i in moving_block(len(s), rng)]).mean())
    lo, hi = np.quantile(reps, [0.025, 0.975])
    return est, float(lo), float(hi)
