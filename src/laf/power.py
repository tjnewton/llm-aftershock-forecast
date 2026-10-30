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


def cell_differences(
    proc: Path, run_dirs: list[Path], reference: str = "official", valid_only: bool = False
) -> pd.DataFrame:
    """dLS per (model, sequence, cell) for direct-arm I1 answers: the mean over an answer's
    samples minus the reference forecaster, on primary cells where it exists. Invalid samples
    get the worst score of any valid forecast in the cell (prereg section 7, as in
    `analysis.score_all`); transport errors are left out. `valid_only` is the sensitivity
    variant that drops invalid samples."""
    tables, items = A.load_tables(proc), A.load_items(proc)
    cells = A.cells(tables)  # refuses confirmatory sequences (docs/adr/0013)
    cells = cells[cells["primary"] & (cells["role"] != "dev")]
    base = A.baselines(tables, items, cells)
    y5 = {(c["issue_id"], c["window"]): int(c["y5"]) for c in cells.to_dict("records")}
    seq = {(c["issue_id"], c["window"]): c["sequence_id"] for c in cells.to_dict("records")}
    scores: dict[tuple, list[float]] = {}  # every valid forecast's score per cell, for the worst
    for (name, iid, win), fc in base.items():
        k = (iid, win)
        if k in y5 and name not in ("etas_analyst", "etas_hindsight"):
            scores.setdefault(k, []).append(log_score(from_quantiles(fc.m5).cdf, y5[k])[0])
    ref = {
        k[1:]: log_score(from_quantiles(fc.m5).cdf, y5[k[1:]])[0]
        for k, fc in base.items()
        if k[0] == reference and k[1:] in y5
    }
    samples = []
    for d in run_dirs:
        for s in A.llm_samples([d], items):
            key = (s["issue_id"], s["window"])
            # the confirmatory estimand: direct-arm answers with the catalog (I1)
            if key not in ref or (s["arm"], s["info"]) != ("direct", "I1"):
                continue
            if s["status"] == "transport_error":
                continue
            ls = (
                None
                if s["forecast"] is None
                else log_score(from_quantiles(s["forecast"].m5).cdf, y5[key])[0]
            )
            if ls is not None:
                scores[key].append(ls)
            samples.append((s["model"], key, ls))
    rows = []
    for model, key, ls in samples:
        if ls is None:
            if valid_only:
                continue
            ls = max(scores[key])
        rows.append({"model": model, "sequence_id": seq[key], "cell": key, "d": ls - ref[key]})
    df = pd.DataFrame(rows)
    return df.groupby(["model", "sequence_id", "cell"])["d"].mean().reset_index()


def d2_cell_differences(proc: Path, run_dirs: list[Path]) -> pd.DataFrame:
    """dLS5 per (model, sequence, cell) from D2-style runs (`laf.d2.analyze`: v2 prompts, M3
    targets), with the model labelled by effort and prompt variant. Valid answers only, as
    `--valid-only` (D2 had almost no invalid answers)."""
    from laf.d2 import analyze

    df, _ = analyze(proc, run_dirs)
    ok = df[df["status"] == "ok"]
    ok = ok.assign(
        model=ok["model"] + " " + ok["effort"] + " " + ok["variant"],
        cell=pd.Series(list(zip(ok["item_id"], ok["window"], strict=True)), index=ok.index),
    )
    return ok.groupby(["model", "sequence_id", "cell"])["d5"].mean().rename("d").reset_index()


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
