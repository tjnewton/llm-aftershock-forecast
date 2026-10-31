"""Confirmatory tests of ADR 0018: non-inferiority to the official forecast with a sequence
block bootstrap, and a Holm correction across the co-primary tests. Pure functions on
per-cell score differences (dS = S(model) - S(official), primary score, ADR 0015); loading and
the snooping guard stay with the callers (laf.splits, ADR 0013).
"""

import numpy as np
import pandas as pd

DELTA = 0.10  # nats per cell (Tyler, 2026-10-31)
B = 10_000
SEED = 20261031


def sequence_effects(cells: pd.DataFrame) -> pd.Series:
    """Mean dS per sequence: every cell of a sequence counts once, sequences equally."""
    return cells.groupby("sequence_id")["d"].mean()


def bootstrap_means(effects: np.ndarray, b: int = B, seed: int = SEED) -> np.ndarray:
    """Means of `b` resamples of the sequence effects (sequences drawn with replacement)."""
    x = np.asarray(effects, dtype=float)
    rng = np.random.default_rng(seed)
    return x[rng.integers(0, len(x), size=(b, len(x)))].mean(axis=1)


def noninferiority(
    effects: np.ndarray, delta: float = DELTA, alpha: float = 0.05, b: int = B, seed: int = SEED
) -> dict:
    """H0: mean dS >= delta against H1: mean dS < delta (the model is not worse by delta or
    more). Percentile bootstrap: the upper bound is the (1 - alpha) quantile of the bootstrap
    means and the p-value the share of them at or above delta, so p <= alpha and
    upper < delta agree. Superiority: the upper bound is below 0."""
    x = np.asarray(effects, dtype=float)
    mean = float(x.mean())
    boot = bootstrap_means(x, b, seed)
    p = (1 + int(np.sum(boot >= delta))) / (b + 1)
    upper = float(np.quantile(boot, 1 - alpha))
    return {
        "sequences": len(x), "mean": mean, "upper": upper, "p": p,
        "noninferior": upper < delta, "superior": upper < 0,
    }  # fmt: skip


def holm(p_values: dict[str, float], alpha: float = 0.05) -> dict[str, bool]:
    """Holm's step-down rejections: the k-th smallest p-value is tested at alpha / (m - k + 1),
    and testing stops at the first non-rejection."""
    m, out, go = len(p_values), {}, True
    for k, (name, p) in enumerate(sorted(p_values.items(), key=lambda kv: kv[1])):
        go = go and p <= alpha / (m - k)
        out[name] = go
    return out


def robust(effects: np.ndarray, b: int = B, seed: int = SEED) -> dict:
    """Reported beside the mean (ADR 0018): the 10% trimmed mean and the median, each with a
    95% sequence-bootstrap interval."""
    x = np.sort(np.asarray(effects, dtype=float))
    rng = np.random.default_rng(seed)
    draws = np.sort(x[rng.integers(0, len(x), size=(b, len(x)))], axis=1)
    k = int(0.1 * len(x))

    def trim(a: np.ndarray) -> np.ndarray:
        return a[..., k : a.shape[-1] - k].mean(axis=-1)

    t, med = trim(draws), np.median(draws, axis=1)
    return {
        "trimmed_mean": float(trim(x)), "trimmed_lo": float(np.quantile(t, 0.025)),
        "trimmed_hi": float(np.quantile(t, 0.975)), "median": float(np.median(x)),
        "median_lo": float(np.quantile(med, 0.025)), "median_hi": float(np.quantile(med, 0.975)),
    }  # fmt: skip


def report(cells: pd.DataFrame, primary: tuple[str, ...], delta: float = DELTA) -> pd.DataFrame:
    """One row per model: the non-inferiority test and the robust summaries; the co-primary
    models (`primary`) are Holm-corrected, the rest tested at 0.05 alone."""
    rows = {}
    for model, g in cells.groupby("model"):
        e = sequence_effects(g).to_numpy()
        rows[model] = noninferiority(e, delta) | robust(e)
    missing = [m for m in primary if m not in rows]
    if missing:  # a smaller Holm family would test the rest at a looser level
        raise ValueError(f"co-primary results missing: {missing}")
    rej = holm({m: rows[m]["p"] for m in primary})
    out = pd.DataFrame.from_dict(rows, orient="index")
    out["co_primary"] = out.index.isin(primary)
    out["holm_noninferior"] = [rej.get(m) for m in out.index]
    return out.rename_axis("model").reset_index()
