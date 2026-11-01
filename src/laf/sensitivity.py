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
