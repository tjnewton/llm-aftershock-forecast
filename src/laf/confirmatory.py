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
    p_sup = (1 + int(np.sum(boot >= 0.0))) / (b + 1)  # superiority: H0 mean dS >= 0
    upper = float(np.quantile(boot, 1 - alpha))
    return {
        "sequences": len(x), "mean": mean, "upper": upper, "p": p, "p_sup": p_sup,
        "noninferior": upper < delta, "superior": upper < 0,
    }  # fmt: skip


def holm_levels(p_values: dict[str, float], alpha: float = 0.05) -> dict[str, float]:
    """The level at which Holm tests each hypothesis: alpha / (m - k) for the k-th smallest
    p-value (k from 0)."""
    m = len(p_values)
    ranked = sorted(p_values.items(), key=lambda kv: kv[1])
    return {name: alpha / (m - k) for k, (name, _) in enumerate(ranked)}


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
    """One row per model: the non-inferiority test and the robust summaries.

    The co-primary models (`primary`) are Holm-corrected, and their bound (`upper`) is reported
    at the level Holm tests them at (0.025 or 0.05). Superiority over the official forecast is a
    separate Holm family across the co-primary models, each tested only after its
    non-inferiority is supported. Other models are tested at 0.05 alone."""
    effects = {m: sequence_effects(g).to_numpy() for m, g in cells.groupby("model")}
    rows = {m: noninferiority(e, delta) | robust(e) for m, e in effects.items()}
    missing = [m for m in primary if m not in rows]
    if missing:  # a smaller Holm family would test the rest at a looser level
        raise ValueError(f"co-primary results missing: {missing}")
    p_ni = {m: rows[m]["p"] for m in primary}
    levels, rej = holm_levels(p_ni), holm(p_ni)
    sup = holm({m: rows[m]["p_sup"] for m in primary})
    for m in primary:  # the bound at the model's Holm level
        at = noninferiority(effects[m], delta, alpha=levels[m])
        rows[m] |= {"holm_level": levels[m], "upper": at["upper"]}
        rows[m]["noninferior"] = rej[m]
        rows[m]["superior"] = bool(rej[m] and sup[m])
    for m in rows:
        if m not in primary:
            rows[m]["superior"] = bool(rows[m]["noninferior"] and rows[m]["superior"])
    out = pd.DataFrame.from_dict(rows, orient="index")
    out["co_primary"] = out.index.isin(primary)
    out["holm_noninferior"] = [rej.get(m) for m in out.index]
    return out.rename_axis("model").reset_index()


# Robustness check (ADR 0018 decision 6): a hierarchical model with sequence and issue random
# effects, window and elapsed-time stratum as fixed effects (sum coding, so the intercept is the
# mean over their levels). Normal random effects misfit heavy tails; the bootstrap stays primary.
STRATA = ((1.0, "under 1 day"), (7.0, "1 to 7 days"), (float("inf"), "7 days or more"))


def stratum(elapsed_days: float) -> str:
    return next(name for upper, name in STRATA if elapsed_days < upper)


def hierarchical(cells: pd.DataFrame, delta: float = DELTA, alpha: float = 0.05) -> dict:
    """dS_ijk = mu + u_i + v_ij + e_ijk (sequence i, issue j, window k), REML. `cells` needs
    sequence_id, issue_id, window, stratum and d. Non-inferior when mu's one-sided (1 - alpha)
    Wald bound is below delta."""
    import warnings

    import statsmodels.formula.api as smf
    from scipy import stats

    fixed = [f"C({c}, Sum)" for c in ("window", "stratum") if cells[c].nunique() > 1]
    formula = " + ".join(["d ~ 1", *fixed])
    model = smf.mixedlm(
        formula, cells, groups=cells["sequence_id"], re_formula="1",
        vc_formula={"issue": "0 + C(issue_id)"},
    )  # fmt: skip
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fit = model.fit(reml=True, method=["lbfgs"])
    mu, se = float(fit.fe_params["Intercept"]), float(fit.bse_fe["Intercept"])
    upper = mu + float(stats.norm.ppf(1 - alpha)) * se
    return {
        "hier_mu": mu, "hier_se": se, "hier_upper": upper, "hier_noninferior": upper < delta,
        "hier_sd_sequence": float(np.sqrt(fit.cov_re.iloc[0, 0])),
        "hier_sd_issue": float(np.sqrt(fit.vcomp[0])), "hier_sd_cell": float(np.sqrt(fit.scale)),
        "hier_converged": bool(fit.converged), "hier_warnings": len(caught),
    }  # fmt: skip


# Clean periods (ADR 0014 decision 3: training cutoff plus a 3-month buffer) and the
# co-primary models (ADR 0018: test A gpt-5.1, test B Claude 5.5 Opus).
CLEAN_FROM = {
    "gpt-5.1-2025-11-13": "2025-01-01",
    "claude-opus-4-6": "2025-12-01",
    "claude-sonnet-4-6": "2026-05-01",
    "gpt-6.1-sol": "2026-08-01",
    "claude-opus-5-5": "2026-10-01",
    "claude-sonnet-5-5": "2026-10-01",
    "claude-haiku-5-5": "2026-10-01",
}
CO_PRIMARY = ("gpt-5.1-2025-11-13", "claude-opus-5-5")
PRIMARY_PROMPT = "v2A"  # ADR 0015 decision 4
OPENAI_EFFORT = {"gpt-5.1-2025-11-13": "medium"}  # ADR 0014 decision 6


def study_effort(model: str) -> str:
    """The effort a model's confirmatory answers must have (ADR 0014 decisions 5 and 6)."""
    from laf.providers import study_effort as claude_effort

    return OPENAI_EFFORT.get(model) or claude_effort(model)


def eligible(sequences: pd.DataFrame, model: str, min_mag: float = 5.0) -> set[str]:
    """Sequences whose mainshock is in the model's clean period and at least `min_mag` (the
    M>=5 primary set; 0 gives every clean candidate, test A's sensitivity analysis)."""
    from laf.splits import development_ids

    clean_ms = pd.Timestamp(CLEAN_FROM[model], tz="UTC").value // 1_000_000
    s = sequences[(sequences["origin_ms"] >= clean_ms) & (sequences["mag"] >= min_mag - 1e-9)]
    return set(s["sequence_id"]) - development_ids()  # development data is never confirmatory


def confirmatory_cells(
    samples: pd.DataFrame,
    sequences: pd.DataFrame,
    elapsed: dict[str, float],
    min_mag: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Per (model, cell) mean dS over the model's primary-prompt samples at its study effort,
    kept only on its eligible sequences, with the issue, window and stratum the hierarchical
    model needs. `samples` is `laf.d2.analyze`'s per-sample table (with `worst_base_d5`).
    `min_mag` lowers the M>=5 threshold for named models only (test A's sensitivity run widens
    gpt-5.1 alone; test B stays on M>=5).

    Invalid answers get the worst score of any valid forecast in the cell, over every valid
    answer and every baseline (prereg v1 section 7; Tyler, 2026-10-31); transport errors are
    left out."""
    s = samples[samples["status"] != "transport_error"]
    key = ["item_id", "window"]
    worst = pd.concat(
        [s[s["status"] == "ok"].groupby(key)["d5"].max(), s.groupby(key)["worst_base_d5"].max()],
        axis=1,
    ).max(axis=1)
    d = np.where(
        s["status"] == "ok", s["d5"], worst.reindex(pd.MultiIndex.from_frame(s[key])).to_numpy()
    )
    s = s.assign(d=d)
    mags = min_mag or {}
    ok = {
        m: (study_effort(m), eligible(sequences, m, mags.get(m, 5.0)))
        for m in set(s["model"]) & set(CLEAN_FROM)
    }
    cols = zip(s["model"], s["effort"], s["variant"], s["sequence_id"], strict=True)
    keep = [
        m in ok and e == ok[m][0] and v == PRIMARY_PROMPT and sid in ok[m][1]
        for m, e, v, sid in cols
    ]
    cells = s[keep].groupby(["model", "sequence_id", "item_id", "window"])["d"].mean()
    cells = cells.reset_index().rename(columns={"item_id": "issue_id"})
    return cells.assign(stratum=[stratum(elapsed[i]) for i in cells["issue_id"]])
