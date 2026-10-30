"""Power for the confirmatory contrasts (docs/adr/0018), from development data only.

Per cell, dS = LS(forecaster) - LS(reference) with every forecast scored through its nine
quantiles (ADR 0015). Sequence effects are the per-sequence means of dS. A simulated study
draws N sequence effects with replacement from the development ones, centred and shifted to a
chosen true difference, and tests equivalence (TOST: the 90% interval inside +-margin) or
superiority (the one-sided 95% bound below 0). Its interval uses the normal approximation to
the sequence-level mean, which is what the sequence block bootstrap converges to.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from laf import analysis as A
from laf.countdist import from_quantiles, log_score

Z90 = 1.6448536269514722  # one-sided 95% = two-sided 90%


def cell_differences(proc: Path, run_dirs: list[Path], reference: str = "official") -> pd.DataFrame:
    """dLS per (model, sequence, cell) for direct-arm I1 answers: the mean over an answer's
    valid samples minus the reference forecaster, on primary cells where it exists."""
    tables, items = A.load_tables(proc), A.load_items(proc)
    cells = A.cells(tables)  # refuses confirmatory sequences (docs/adr/0013)
    cells = cells[cells["primary"] & (cells["role"] != "dev")]
    base = A.baselines(tables, items, cells)
    y5 = {(c["issue_id"], c["window"]): int(c["y5"]) for c in cells.to_dict("records")}
    seq = {(c["issue_id"], c["window"]): c["sequence_id"] for c in cells.to_dict("records")}
    ref = {
        k[1:]: log_score(from_quantiles(fc.m5).cdf, y5[k[1:]])[0]
        for k, fc in base.items()
        if k[0] == reference and k[1:] in y5
    }
    rows = []
    for d in run_dirs:
        for s in A.llm_samples([d], items):
            key = (s["issue_id"], s["window"])
            # the confirmatory estimand: direct-arm answers with the catalog (I1)
            if key not in ref or s["forecast"] is None or (s["arm"], s["info"]) != ("direct", "I1"):
                continue
            ls = log_score(from_quantiles(s["forecast"].m5).cdf, y5[key])[0]
            rows.append(
                {"model": s["model"], "sequence_id": seq[key], "cell": key, "d": ls - ref[key]}
            )
    df = pd.DataFrame(rows)
    return df.groupby(["model", "sequence_id", "cell"])["d"].mean().reset_index()


def sequence_effects(cells: pd.DataFrame) -> pd.Series:
    return cells.groupby("sequence_id")["d"].mean()


def power(
    effects: np.ndarray,
    n: int,
    margin: float | None,
    true_diff: float = 0.0,
    sims: int = 20_000,
    seed: int = 20261030,
) -> float:
    """Share of simulated studies of n sequences that conclude equivalence (margin given) or
    superiority (margin None: the one-sided 95% upper bound below 0)."""
    rng = np.random.default_rng(seed)
    e = np.asarray(effects, dtype=float)
    e = e - e.mean() + true_diff
    draw = rng.choice(e, size=(sims, n), replace=True)
    mean = draw.mean(axis=1)
    se = draw.std(axis=1, ddof=1) / np.sqrt(n)
    if margin is None:
        return float(np.mean(mean + Z90 * se < 0))
    return float(np.mean((mean - Z90 * se > -margin) & (mean + Z90 * se < margin)))


def power_table(
    effects: np.ndarray,
    ns: tuple[int, ...],
    margins: tuple[float | None, ...],
    true_diff: float = 0.0,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "n_sequences": n,
                "margin": m,
                "true_diff": true_diff,
                "power": power(effects, n, m, true_diff),
            }
            for n in ns
            for m in margins
        ]
    )
