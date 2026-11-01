"""Sensitivity analyses of prereg v2 section 6, reported in one table whatever their result.

Each row repeats a tested model's non-inferiority test against the official forecast on a
variant of its cells: the clean rule, the prompt, the invalid-answer rule, the settling rule, a
subset of cells, or one elapsed-time stratum. Scoring variants (the log-scale quantile score,
full distributions, the negative-binomial tail, other log floors) and the outcome variants
(region radius, the forward-excluded candidates) come in their own modules.
"""

import pandas as pd

from laf import confirmatory as C

NON_OVERLAP = {"day": None, "week": ("first", "7d", "14d", "28d"), "month": ("first",)}
AB_MODELS = ("gpt-5.1-2025-11-13", "claude-opus-5-5")  # v2B runs for the A and B models only


def non_overlapping(cells: pd.DataFrame) -> pd.Series:
    """One window per issue time, as `analysis.non_overlapping` (prereg v1): every day window,
    week windows of the first, 7, 14 and 28 day issues, the month window of the first issue."""
    target = cells["issue_id"].str.split("@").str[1]
    keep = pd.Series(False, index=cells.index)
    for win, targets in NON_OVERLAP.items():
        sel = cells["window"] == win
        keep |= sel if targets is None else sel & target.apply(
            lambda t, ts=targets: any(x in t.split("+") for x in ts))  # fmt: skip
    return keep


def exact_match(tables: dict[str, pd.DataFrame]) -> set[str]:
    """Issue times whose as-of catalog reproduces the official product's own M>=5 count."""
    it = tables["issue_times"]
    return set(it.loc[it["oaf_obs_m5"] == it["comcat_m5_at_cutoff"], "issue_id"])


def _row(analysis: str, cells: pd.DataFrame, models: tuple[str, ...]) -> list[dict]:
    rows = []
    for m, g in cells[cells["model"].isin(models)].groupby("model"):
        t = C.noninferiority(C.sequence_effects(g).to_numpy())
        rows.append({"analysis": analysis, "model": m}
                    | {k: t[k] for k in ("sequences", "mean", "upper", "noninferior")})  # fmt: skip
    return rows


def sensitivity(
    samples: pd.DataFrame, tables: dict[str, pd.DataFrame], elapsed: dict[str, float],
    models: tuple[str, ...], samples_2d: pd.DataFrame | None = None,
    sets: dict[str, set[str]] | None = None,
) -> pd.DataFrame:  # fmt: skip
    """The table. `samples_2d` is `laf.d2.analyze(..., settle="settled_2d")` for the 2-day
    settling rule; `sets` (the development rehearsal) replaces the clean sets, and then the
    clean-rule variants are left out."""
    seqs = tables["sequences"]

    def cells(s=samples, **kw):
        return C.confirmatory_cells(s, seqs, elapsed, sets=sets, **kw)

    main = cells()
    rows = _row("main", main, models)
    if sets is None:
        wide = {C.PRIMARY[0]: 0.0}
        rows += _row("test A on all clean candidates",
                     C.confirmatory_cells(samples, seqs, elapsed, wide), C.PRIMARY)  # fmt: skip
        for rule in ("unbuffered", "release"):
            rows += _row(f"{rule} clean rule", cells(rule=rule), models)
    rows += _row("non-overlapping subset", main[non_overlapping(main)], models)
    rows += _row("v2B", cells(variant="v2B"), tuple(m for m in models if m in AB_MODELS))
    rows += _row("valid answers only", cells(s=samples[samples["status"] == "ok"]), models)
    exact = exact_match(tables)
    rows += _row("as-of catalog matches the official count", main[main["issue_id"].isin(exact)],
                 models)  # fmt: skip
    if samples_2d is not None:
        rows += _row("2-day settling rule", cells(s=samples_2d), models)
    for _, name in C.STRATA:
        rows += _row(f"stratum: {name}", main[main["stratum"] == name], models)
    return pd.DataFrame(rows)


def invalid_rates(samples: pd.DataFrame) -> pd.DataFrame:
    """Invalid answers per model, effort and prompt, by status; transport errors apart (they
    are retried and left out, not penalized)."""
    s = samples.drop_duplicates(["model", "effort", "variant", "item_id", "sample"])
    g = s.groupby(["model", "effort", "variant"])["status"]
    out = g.value_counts().unstack(fill_value=0)
    scored = out.drop(columns=["transport_error"], errors="ignore").sum(axis=1)
    out["invalid_rate"] = 1 - out.get("ok", 0) / scored.where(scored > 0)
    return out.reset_index()


# scoring variants (prereg v2 section 6): (label, laf.d2 score, log floor)
SCORE_VARIANTS = (
    ("log floor 1e-4", "registered", 1e-4),
    ("log floor 1e-8", "registered", 1e-8),
    ("negative-binomial tail", "nb_tail", None),
    ("full distributions (official, ETAS)", "full", None),
    ("log-scale quantile score", "log_qs", None),
)


def scoring_variants(
    proc, run_dirs, tables: dict[str, pd.DataFrame], elapsed: dict[str, float],
    models: tuple[str, ...], sets: dict[str, set[str]] | None = None,
) -> pd.DataFrame:  # fmt: skip
    """The non-inferiority rows again under each scoring variant. The quantile score has
    another unit, so delta does not apply to it: its row gives the estimate and bound only."""
    from laf.d2 import analyze

    rows = []
    for label, score, floor in SCORE_VARIANTS:
        s, _ = analyze(proc, run_dirs, score=score, floor=floor)
        r = _row(label, C.confirmatory_cells(s, tables["sequences"], elapsed, sets=sets), models)
        if score == "log_qs":
            for x in r:
                x["noninferior"] = None
        rows += r
    return pd.DataFrame(rows)


FLOORS = (1e-6, 1e-4, 1e-8)


def diagnostics(proc, run_dirs, models: tuple[str, ...]) -> pd.DataFrame:
    """Per forecaster at M>=5 on the scored cells (prereg v2 section 6, ADR 0015): how often
    each log floor binds, the cells above its 97.5% quantile, CSEP N-test failures (either
    quantile below 0.025), the KS distance of its randomized PIT from uniform, and the
    information gain per earthquake against the official forecast (official log score minus
    its own, summed over cells, over the earthquakes counted)."""
    import numpy as np
    from scipy import stats

    from laf import analysis as A
    from laf.countdist import from_quantiles, log_score, n_test, pit
    from laf.d2 import BASELINES, samples

    tables, items = A.load_tables(proc), A.load_items(proc)
    cells = A.cells(tables)  # refuses sealed outcomes
    cells = cells[cells["primary"] & cells["oaf_cell"] & (cells["role"] == "test-post")]
    base = A.baselines(tables, items, cells)
    y5 = {(c["issue_id"], c["window"]): int(c["y5"]) for c in cells.to_dict("records")}
    label = {"day": "1 Day", "week": "1 Week", "month": "1 Month"}
    by: dict[str, list] = {}
    for (name, iid, win), fc in base.items():
        if (iid, win) in y5 and (name == "official" or name in BASELINES) and fc.m5:
            by.setdefault(name, []).append(((iid, win), fc.m5))
    for r in samples(run_dirs):
        key = (r["item_id"], label[r["window"]])
        if (r["model"] in models and r["status"] == "ok" and r["paraphrase"] == C.PRIMARY_PROMPT
                and r["effort"] == C.study_effort(r["model"]) and key in y5):  # fmt: skip
            by.setdefault(r["model"], []).append((key, r["m5_count_quantiles"]))
    rng = np.random.default_rng(A.PIT_SEED)
    ls_off = {k: log_score(from_quantiles(q).cdf, y5[k])[0] for k, q in by.get("official", [])}
    rows = []
    for name, fcs in sorted(by.items()):
        bound = {f: 0 for f in FLOORS}
        above = fails = 0
        pits, gain = [], {}
        for k, q in fcs:
            y, cdf = y5[k], from_quantiles(q).cdf
            for f in FLOORS:
                bound[f] += log_score(cdf, y, f)[1]
            above += y > q[-1]
            d1, d2 = n_test(cdf, y)
            fails += min(d1, d2) < 0.025
            pits.append(pit(cdf, y, rng))
            if k in ls_off:
                gain.setdefault(k, []).append(ls_off[k] - log_score(cdf, y)[0])
        quakes = sum(y5[k] for k in gain)
        rows.append({
            "forecaster": name, "answers": len(fcs),
            **{f"floor_{f:g}_binds": bound[f] / len(fcs) for f in FLOORS},
            "above_q975": above, "n_test_fail": fails / len(fcs),
            "pit_ks": float(stats.kstest(pits, "uniform").statistic),
            "ig_per_quake": (sum(np.mean(v) for v in gain.values()) / quakes) if quakes else None,
        })  # fmt: skip
    return pd.DataFrame(rows)
