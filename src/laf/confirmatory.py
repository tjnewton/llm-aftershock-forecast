"""Confirmatory tests of ADR 0018: non-inferiority to the official forecast with a sequence
block bootstrap (one primary hypothesis since 2026-10-31, ADR 0018 decision 15; Holm across
the primary models when there are several). Pure functions on
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


def noninferiority(
    effects: np.ndarray, delta: float = DELTA, alpha: float = 0.05, b: int = B, seed: int = SEED,
    method: str = "student", strata: np.ndarray | None = None,
) -> dict:  # fmt: skip
    """H0: mean dS >= delta against H1: mean dS < delta (the model is not worse by delta or
    more), with resampled sequences.

    `method="student"` (registered, ADR 0018 decision 8): bootstrap-t. T* = (mean* - mean) /
    se*, the upper bound is mean - q_alpha(T*) se, and the p-value is the share of T* at or below
    (mean - delta) / se. `method="percentile"`: the (1 - alpha) quantile of the bootstrap means,
    and the share of them at or above delta. Either way p <= alpha and upper < delta agree, and
    `p_sup` tests H0: mean dS >= 0. Superiority: the upper bound is below 0.

    `strata` (one label per sequence; test B's retrospective and prospective parts) resamples
    each stratum separately at its own size, with the stratified standard error
    sqrt(sum_h (n_h/n)^2 s_h^2 / n_h). Strata with fewer than two sequences cannot give a
    spread, so then all sequences are resampled together."""
    x = np.asarray(effects, dtype=float)
    n = len(x)
    if strata is not None:
        labels = np.asarray(strata)
        levels = np.unique(labels)
        if len(levels) > 1 and all(int(np.sum(labels == h)) >= 2 for h in levels):
            if method != "student":  # the registered bound; no stratified percentile variant
                raise ValueError("strata take the registered bootstrap-t (method='student')")
            return _stratified(x, labels, levels, delta, alpha, b, seed)
    if n < 2:  # no spread to estimate from one sequence (or none): no claim
        return {"sequences": n, "mean": float(x.mean()) if n else float("nan"),
                "upper": float("inf"), "p": 1.0, "p_sup": 1.0,
                "noninferior": False, "superior": False}  # fmt: skip
    mean = float(x.mean())
    rng = np.random.default_rng(seed)
    draws = x[rng.integers(0, n, size=(b, n))]
    boot = draws.mean(axis=1)
    if method == "percentile":
        p = (1 + int(np.sum(boot >= delta))) / (b + 1)
        p_sup = (1 + int(np.sum(boot >= 0.0))) / (b + 1)
        upper = float(np.quantile(boot, 1 - alpha))
    elif method == "student":
        se = float(x.std(ddof=1)) / np.sqrt(n)
        se_b = draws.std(axis=1, ddof=1) / np.sqrt(n)
        diff = boot - mean
        # a resample with no spread keeps the direction of its difference: T* = +-inf (0 if none)
        degenerate = np.where(diff > 0, np.inf, np.where(diff < 0, -np.inf, 0.0))
        t = np.where(se_b > 0, diff / np.where(se_b > 0, se_b, 1.0), degenerate)
        if not np.isfinite(se) or se == 0:  # no spread to estimate: no claim
            upper, p, p_sup = float("inf"), 1.0, 1.0
        else:
            # an order statistic (no interpolation), so infinite T* stay infinite
            upper = float(mean - np.quantile(t, alpha, method="inverted_cdf") * se)
            p = (1 + int(np.sum(t <= (mean - delta) / se))) / (b + 1)
            p_sup = (1 + int(np.sum(t <= mean / se))) / (b + 1)
    else:
        raise ValueError(f"unknown method {method!r}")
    return {
        "sequences": n, "mean": mean, "upper": upper, "p": p, "p_sup": p_sup,
        "noninferior": upper < delta, "superior": upper < 0,
    }  # fmt: skip


def _stratified(x, labels, levels, delta, alpha, b, seed) -> dict:
    """The bootstrap-t of `noninferiority` with stratified resampling."""
    groups = [x[labels == h] for h in levels]
    n = len(x)
    rng = np.random.default_rng(seed)
    draws = [g[rng.integers(0, len(g), size=(b, len(g)))] for g in groups]
    mean = float(x.mean())
    boot = np.concatenate(draws, axis=1).mean(axis=1)

    def se_of(parts, axis=None):
        return np.sqrt(sum((len(g) / n) ** 2 * np.var(d, axis=axis, ddof=1) / len(g)
                           for g, d in zip(groups, parts, strict=True)))  # fmt: skip

    se = float(se_of(groups))
    se_b = se_of(draws, axis=1)
    diff = boot - mean
    degenerate = np.where(diff > 0, np.inf, np.where(diff < 0, -np.inf, 0.0))
    t = np.where(se_b > 0, diff / np.where(se_b > 0, se_b, 1.0), degenerate)
    if not np.isfinite(se) or se == 0:
        upper, p, p_sup = float("inf"), 1.0, 1.0
    else:
        upper = float(mean - np.quantile(t, alpha, method="inverted_cdf") * se)
        p = (1 + int(np.sum(t <= (mean - delta) / se))) / (b + 1)
        p_sup = (1 + int(np.sum(t <= mean / se))) / (b + 1)
    return {
        "sequences": n, "mean": mean, "upper": upper, "p": p, "p_sup": p_sup,
        "noninferior": upper < delta, "superior": upper < 0, "strata": len(levels),
    }  # fmt: skip


def size(
    effects: np.ndarray, n: int, delta: float = DELTA, alpha: float = 0.025, sims: int = 2000,
    b: int = 2000, seed: int = SEED, method: str = "student",
) -> float:  # fmt: skip
    """Simulated size of the test: draw `n` sequence effects with replacement from `effects`
    shifted so their mean is exactly delta (H0 true at its boundary), apply the test, and
    return the share of false non-inferiority claims. Before the freeze, a level is calibrated
    wherever this exceeds 0.03 (ADR 0018 decision 8)."""
    x = np.asarray(effects, dtype=float)
    x = x - x.mean() + delta
    rng = np.random.default_rng(seed)
    hits = 0
    for i in range(sims):
        sample = x[rng.integers(0, len(x), size=n)]
        r = noninferiority(sample, delta, alpha, b, seed + 1 + i, method)
        hits += r["noninferior"]
    return hits / sims


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


TEST_COLUMNS = ("upper", "p", "p_sup", "noninferior", "superior")


def report(
    cells: pd.DataFrame, primary: tuple[str, ...], delta: float = DELTA,
    descriptive: tuple[str, ...] = (),
) -> pd.DataFrame:  # fmt: skip
    """One row per model: the non-inferiority test and the robust summaries.

    The co-primary models (`primary`) are Holm-corrected, and their bound (`upper`) is reported
    at the level Holm tests them at (0.025 or 0.05). Superiority over the official forecast is a
    separate Holm family across the co-primary models, each tested only after its
    non-inferiority is supported. Other models are tested at 0.05 alone."""
    effects = {m: sequence_effects(g).to_numpy() for m, g in cells.groupby("model")}
    rows = {m: noninferiority(e, delta) | robust(e) for m, e in effects.items()}
    missing = [m for m in primary if m not in rows]
    if missing:  # a smaller Holm family would test the rest at a looser level
        raise ValueError(f"primary results missing: {missing}")
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
        if m in descriptive:  # no test for descriptive models (Sonnet 4.6, prereg v2 section 2)
            rows[m] |= dict.fromkeys(TEST_COLUMNS)
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
# primary model (ADR 0018 decision 15: test A, gpt-5.1; test B, Opus 5.5, is secondary).
CLEAN_FROM = {
    "gpt-5.1-2025-11-13": "2025-01-01",
    "claude-opus-4-6": "2025-12-01",
    "claude-sonnet-4-6": "2026-05-01",
    "gpt-6.1-sol": "2026-08-01",
    "claude-opus-5-5": "2026-10-01",
    "claude-sonnet-5-5": "2026-10-01",
    "claude-haiku-5-5": "2026-10-01",
}
PRIMARY = ("gpt-5.1-2025-11-13",)
SECONDARY = ("claude-opus-5-5", "claude-opus-4-6", "gpt-6.1-sol")  # B, S1, S2; others descriptive
PRIMARY_PROMPT = "v2A"  # ADR 0015 decision 4
# ADR 0014 decisions 6 and 7
OPENAI_EFFORT = {"gpt-5.1-2025-11-13": "medium", "gpt-6.1-sol": "high"}


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
    reference: str = "official",
    sets: dict[str, set[str]] | None = None,
) -> pd.DataFrame:
    """Per (model, cell) mean dS over the model's primary-prompt samples at its study effort,
    kept only on its eligible sequences, with the issue, window and stratum the hierarchical
    model needs. `samples` is `laf.d2.analyze`'s per-sample table (with `worst_base_d5`).
    `min_mag` lowers the M>=5 threshold for named models only (test A's sensitivity run widens
    gpt-5.1 alone; test B stays on M>=5).

    Invalid answers get the worst score in the cell among the five baselines (official, generic
    RJ, RJ-MLE, the rule of thumb, the ETAS refit; ADR 0018 decision 12), so the penalty does not
    depend on k or on which other runs are loaded; transport errors are left out.

    `reference` is the forecast dS is taken against: the official one, or a pipeline baseline
    (`laf.d2.BASELINES`) for the contrasts S3-S5; cells without that baseline drop out. `sets`
    replaces the clean eligible sets (the development dry run uses every sequence)."""
    s = samples[samples["status"] != "transport_error"]
    key = ["item_id", "window"]
    worst = s.groupby(key)["worst_base_d5"].max()  # the five baselines only (ADR 0018 decision 12)
    d = np.where(
        s["status"] == "ok", s["d5"], worst.reindex(pd.MultiIndex.from_frame(s[key])).to_numpy()
    )
    if reference != "official":  # LS(model) - LS(baseline) = dS - (LS(baseline) - LS(official))
        d = d - s[f"base_d5_{reference}"].to_numpy()
    s = s.assign(d=d)
    mags = min_mag or {}
    ok = {
        m: (study_effort(m), sets[m] if sets else eligible(sequences, m, mags.get(m, 5.0)))
        for m in set(s["model"]) & set(sets or CLEAN_FROM)
    }
    cols = zip(s["model"], s["effort"], s["variant"], s["sequence_id"], strict=True)
    keep = [
        m in ok and e == ok[m][0] and v == PRIMARY_PROMPT and sid in ok[m][1]
        for m, e, v, sid in cols
    ]
    cells = (
        s[np.asarray(keep, dtype=bool)]
        .groupby(["model", "sequence_id", "item_id", "window"])["d"]
        .mean()
    )
    cells = cells.dropna().reset_index().rename(columns={"item_id": "issue_id"})
    return cells.assign(stratum=[stratum(elapsed[i]) for i in cells["issue_id"]])


def _two_sided(
    effects: np.ndarray, alpha: float = 0.05, strata: np.ndarray | None = None
) -> tuple[float, float]:
    """The bootstrap-t interval at 1 - alpha: each bound one-sided at alpha / 2, the lower one
    as the upper bound of the negated effects (same resamples)."""
    up = noninferiority(effects, 0.0, alpha=alpha / 2, strata=strata)["upper"]
    neg = -np.asarray(effects, dtype=float)
    lo = -noninferiority(neg, 0.0, alpha=alpha / 2, strata=strata)["upper"]
    return lo, up


# S3 and S4 (prereg v2 section 2): superiority at 0.05 over the rule of thumb and generic RJ;
# against the legacy-ETAS refit an estimate and 95% interval only
CONTRASTS = (("S3", "naive", "superiority"), ("S4", "generic_rj", "superiority"),
             ("S4", "etas", "estimate"))  # fmt: skip


def contrasts(
    samples: pd.DataFrame, sequences: pd.DataFrame, elapsed: dict[str, float],
    models: tuple[str, ...], sets: dict[str, set[str]] | None = None,
    min_mag: dict[str, float] | None = None,
) -> pd.DataFrame:  # fmt: skip
    """One row per tested model and baseline: mean LS(model) - LS(baseline) over its test's
    sequences (its A, B, S1 or S2 set), with the superiority test or the 95% interval."""
    rows = []
    for hyp, ref, kind in CONTRASTS:
        cells = confirmatory_cells(samples, sequences, elapsed, min_mag, reference=ref, sets=sets)
        for m, g in cells[cells["model"].isin(models)].groupby("model"):
            e = sequence_effects(g).to_numpy()
            row = {"hypothesis": hyp, "model": m, "reference": ref, "kind": kind}
            if kind == "superiority":
                t = noninferiority(e, 0.0)
                row |= {k: t[k] for k in ("sequences", "mean", "upper", "p_sup", "superior")}
            else:
                lo, up = _two_sided(e)
                row |= {"sequences": len(e), "mean": float(e.mean()), "lower95": lo,
                        "upper95": up}  # fmt: skip
            rows.append(row)
    return pd.DataFrame(rows)


def assay(samples: pd.DataFrame, cells: pd.DataFrame, delta: float = DELTA) -> pd.DataFrame:
    """Assay sensitivity (prereg v2 section 2): the non-inferiority test for generic RJ against
    the official forecast on each model's own test cells, read with the prereg's decision rule:
    `noninferior` (upper bound below delta: that model's test cannot separate it from the
    generic default), `inferior` (lower bound above delta: the cells do separate) or
    `inconclusive`."""
    rj = samples.groupby(["item_id", "window"])["base_d5_generic_rj"].first()
    rows = []
    for m, g in cells.groupby("model"):
        d = rj.reindex(pd.MultiIndex.from_frame(g[["issue_id", "window"]])).to_numpy()
        gc = g.assign(d=d).dropna(subset=["d"])
        e = sequence_effects(gc).to_numpy()
        t = noninferiority(e, delta)
        lower = -noninferiority(-e, -delta)["upper"]
        status = "noninferior" if t["noninferior"] else "inferior" if lower > delta else (
            "inconclusive")  # fmt: skip
        rows.append({"model": m, "generic_rj_mean": t["mean"], "generic_rj_lower": lower,
                     "generic_rj_upper": t["upper"], "generic_rj_status": status})  # fmt: skip
    return pd.DataFrame(rows)


INFORMATIVE_MEAN = 0.5  # official mean N(M>=5) in the month window of the first issue


def informative(tables: dict[str, pd.DataFrame]) -> set[str]:
    """Sequences for the informative-sequence estimand (prereg v2 section 2), outcome-blind:
    the official forecast at the sequence's first issue has a mean N(M>=5) of at least 0.5 in
    the month window. The mean integrates the official quantile function over its published
    fractile grid (trapezoid in p)."""
    it = tables["issue_times"].sort_values("issue_ms").drop_duplicates("sequence_id")
    f = tables["forecast_fractiles"]
    f = f[(f["magnitude"] == 5.0) & (f["window"] == "1 Month")].sort_values("p")
    mean = {
        k: np.trapezoid(g["count"].to_numpy(float), g["p"].to_numpy(float))
        for k, g in f.groupby(["sequence_id", "info_cutoff_ms"])
    }
    first = zip(it["sequence_id"], it["issue_ms"], strict=True)
    return {sid for sid, cutoff in first if mean.get((sid, cutoff), 0.0) >= INFORMATIVE_MEAN}


def secondary(
    samples: pd.DataFrame, tables: dict[str, pd.DataFrame], elapsed: dict[str, float],
    cells: pd.DataFrame, models: tuple[str, ...], sets: dict[str, set[str]] | None = None,
    min_mag: dict[str, float] | None = None,
) -> pd.DataFrame:  # fmt: skip
    """The secondary table beside the tests against the official forecast: the contrasts S3
    and S4, the assay-sensitivity test, and the informative-sequence estimand (non-inferiority
    on each model's informative sequences), for the tested `models` on their `cells`."""
    tested = cells[cells["model"].isin(models)]
    keep = informative(tables)
    rows = [
        {"hypothesis": "informative", "model": m}
        | {k: t[k] for k in ("sequences", "mean", "upper", "noninferior")}
        for m, g in tested[tested["sequence_id"].isin(keep)].groupby("model")
        for t in [noninferiority(sequence_effects(g).to_numpy())]
    ]
    return pd.concat(
        [contrasts(samples, tables["sequences"], elapsed, models, sets, min_mag),
         assay(samples, tested).assign(hypothesis="assay"), pd.DataFrame(rows)],
        ignore_index=True,
    )  # fmt: skip


B_MODEL, S2_MODEL = "claude-opus-5-5", "gpt-6.1-sol"


def live_report(
    samples: pd.DataFrame, live: pd.DataFrame, sequences: pd.DataFrame,
    elapsed: dict[str, float], live_start_ms: int, stop_ms: int | None,
) -> pd.DataFrame:  # fmt: skip
    """Test B in its two parts, S2 and S5 (prereg v2 sections 2, 5 and 6).

    `samples` are the batch answers (`laf.d2.analyze`), `live` the released live answers
    (`laf.live_scores.live_samples`). L (`live_start_ms`) splits the parts: B's retrospective
    part is Opus 5.5's clean M>=5 sequences with origin before L; its prospective part, the
    sequences included as primary at first detection (`tier`) with origin in [L, S), on-time
    matched items only.
    Test B resamples the parts separately and is also reported for each part alone. S2:
    gpt-6.1-sol on the prospective matched items. S5: the strict items of the same sequences
    against each pipeline baseline (superiority over the rule of thumb and generic RJ, an
    interval against ETAS)."""
    origin = sequences.set_index("sequence_id")["origin_ms"]
    retro = confirmatory_cells(samples, sequences, elapsed)
    retro = retro[(retro["model"] == B_MODEL)
                  & (retro["sequence_id"].map(origin) < live_start_ms)]  # fmt: skip
    first = live.sort_values("elapsed_days").drop_duplicates("sequence_id").set_index("sequence_id")
    end = stop_ms if stop_ms is not None else np.inf
    pro_ids = {str(sid) for sid, r in first.iterrows()
               if live_start_ms <= r["origin_ms"] < end and r["tier"] == "primary"}  # fmt: skip
    live_elapsed = dict(zip(live["item_id"], live["elapsed_days"], strict=True))
    sets = {m: pro_ids for m in (B_MODEL, S2_MODEL)}
    matched = live[(live["kind"] == "matched") & live["on_time"]]
    pro = confirmatory_cells(matched, sequences, live_elapsed, sets=sets) if len(matched) else (
        retro.iloc[:0])  # fmt: skip

    def test(label: str, cells: pd.DataFrame, strata: np.ndarray | None = None) -> dict:
        e = sequence_effects(cells)
        t = noninferiority(e.to_numpy(), strata=strata)
        return {"hypothesis": label} | {k: t[k] for k in TEST_COLUMNS} | {
            "sequences": t["sequences"], "mean": t["mean"]}  # fmt: skip

    b_retro, b_pro = retro, pro[pro["model"] == B_MODEL]
    both = pd.concat([b_retro.assign(part="retrospective"), b_pro.assign(part="prospective")])
    parts = both.groupby("sequence_id")["part"].first()
    rows = [
        {"model": B_MODEL}
        | test("B", both, parts.reindex(sequence_effects(both).index).to_numpy()),
        {"model": B_MODEL} | test("B retrospective part", b_retro),
        {"model": B_MODEL} | test("B prospective part", b_pro),
        {"model": S2_MODEL} | test("S2", pro[pro["model"] == S2_MODEL]),
    ]
    # S3 and S4 on each model's full test set: B's two parts for Opus 5.5, S2's for gpt-6.1-sol
    for hyp, ref, kind in CONTRASTS:
        r = confirmatory_cells(samples, sequences, elapsed, reference=ref)
        r = r[(r["model"] == B_MODEL) & (r["sequence_id"].map(origin) < live_start_ms)]
        p = confirmatory_cells(matched, sequences, live_elapsed, reference=ref, sets=sets) if (
            len(matched)) else r.iloc[:0]  # fmt: skip
        for model, label, retro_part in ((B_MODEL, "B", r), (S2_MODEL, "S2", r.iloc[:0])):
            both = pd.concat([retro_part.assign(part="retrospective"),
                              p[p["model"] == model].assign(part="prospective")])  # fmt: skip
            e = sequence_effects(both)
            st = both.groupby("sequence_id")["part"].first().reindex(e.index).to_numpy()
            mean = float(e.mean()) if len(e) else np.nan
            row = {"hypothesis": hyp, "model": model, "reference": ref, "kind": kind,
                   "set": label, "sequences": len(e), "mean": mean}  # fmt: skip
            if kind == "superiority":
                t = noninferiority(e.to_numpy(), 0.0, strata=st)
                row |= {k: t[k] for k in ("upper", "p_sup", "superior")}
            else:
                row["lower95"], row["upper95"] = _two_sided(e.to_numpy(), strata=st)
            rows.append(row)
    strict = live[(live["kind"] == "strict") & live["on_time"]]  # sealed before its windows
    s5 = contrasts(strict, sequences, live_elapsed, (B_MODEL, S2_MODEL), sets) if len(strict) else (
        pd.DataFrame())  # fmt: skip
    return pd.concat([pd.DataFrame(rows), s5.assign(hypothesis="S5")], ignore_index=True)
