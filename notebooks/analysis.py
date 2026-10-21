import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    from pathlib import Path

    import marimo as mo
    import numpy as np
    import pandas as pd

    from laf import analysis as A

    _SNAPSHOT = "20261021T1027Z"
    PROCESSED = Path("data/processed") / _SNAPSHOT
    RUN_DIRS = sorted(
        p.parent
        for p in Path("runs").glob("*/results.jsonl")
        if (p.parent / "requests.jsonl").exists()
    )
    B = 10_000
    SEED = 20261021
    MODELS = ("claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5")
    return A, B, MODELS, PROCESSED, RUN_DIRS, SEED, mo, np, pd


@app.cell
def _(A, PROCESSED, RUN_DIRS, mo):
    tables = A.load_tables(PROCESSED)
    items = A.load_items(PROCESSED)
    cell_df = A.cells(tables)
    cell_df = cell_df[cell_df["role"] != "dev"].reset_index(drop=True)  # dev is never scored
    base = A.baselines(tables, items, cell_df)
    samples = A.llm_samples(RUN_DIRS, items)
    df = A.score_all(cell_df, base, samples)
    mo.md(f"""# Preregistered analysis (prereg-v1; scoring code tagged scoring-v1)
Snapshot `{PROCESSED.name}`; runs: {", ".join(p.name for p in RUN_DIRS) or "none collected"};
{len(cell_df)} scored cells ({int(cell_df["primary"].sum())} primary); {len(df)} scored rows.""")
    return base, cell_df, df, items, samples, tables


@app.cell
def _(A, df):
    answers = A.answer_scores(df)
    answers_valid = A.answer_scores(df, "log_qs_valid_only").rename(
        columns={"log_qs_valid_only": "log_qs"}
    )
    return answers, answers_valid


@app.cell
def _(answers, mo, pd):
    prim = answers[answers["primary"]]
    _per_seq = prim.pivot_table(index="forecaster", columns="name", values="log_qs")
    _per_seq["all primary cells"] = prim.groupby("forecaster")["log_qs"].mean()
    mo.vstack(
        [
            mo.md("## 5. Primary outcome: log-QS for N(M>=5), primary cells (lower is better)"),
            pd.DataFrame(_per_seq).round(3),
        ]
    )
    return (prim,)


@app.cell
def _(A, df, mo):
    mo.vstack(
        [
            mo.md("## 5/7. Co-primary: output status shares by model, arm and information"),
            A.invalid_table(df).round(3),
        ]
    )
    return


@app.cell
def _(A, df, mo, pd):
    _oaf = df["primary"] & df["oaf_cell"]
    _allp = df["primary"]
    _cov = pd.concat(
        {"OAF cells": A.coverage_table(df, _oaf), "all primary cells": A.coverage_table(df, _allp)},
        axis=1,
    )
    _ks = pd.concat(
        {
            "rank PIT, OAF": A.pit_ks(df, _oaf),
            "rank PIT, all": A.pit_ks(df, _allp),
            "full PIT, all": A.pit_ks(df, _allp, "pit_full"),
        },
        axis=1,
    )
    mo.vstack(
        [
            mo.md("## 5. Secondary: central-interval coverage (nominal 0.50/0.80/0.90/0.95)"),
            _cov.round(3),
            mo.md("Randomized PIT, Kolmogorov-Smirnov distance from uniform"),
            _ks.round(3),
        ]
    )
    return


@app.cell
def _(df, mo, pd):
    _m6 = df[df["primary"] & df["status"].eq("ok") & df["p_m6"].notna()]
    _nat = df[df["primary"]].groupby("forecaster")[["nat_qs", "log_qs_m4"]].mean()
    _tab = pd.concat([_m6.groupby("forecaster")[["brier_m6", "log_m6"]].mean(), _nat], axis=1)
    mo.vstack(
        [
            mo.md(f"""## 5. P(M>=6): Brier and clipped log score, pooled over all scored roles
({int((_m6.drop_duplicates(["issue_id", "window"])["y6"] > 0).sum())} positive primary cells);
natural-scale QS; exploratory M>=4 log-QS"""),
            _tab.round(4),
        ]
    )
    return


@app.cell
def _(A, B, MODELS, SEED, answers, df, mo, np, pd):
    def hyp(pairs, mask, direction, scores=answers):
        out, flags = [], {}
        for model, x, ref in pairs:
            d = A.dqs(scores, x, ref, mask)
            if d.empty:
                continue
            t = A.ci_table(d, np.random.default_rng(SEED), B).assign(model=model)
            flags[model] = A.supported(t, direction)
            out.append(t)
        return (pd.concat(out) if out else pd.DataFrame()), flags

    oaf_mask = answers["primary"] & answers["oaf_cell"] & answers["role"].eq("test-post")
    _post_mask = answers["primary"] & answers["role"].eq("test-post")
    _h1, _h1s = hyp([(m, f"{m}|direct|I1|high", "official") for m in MODELS], oaf_mask, +1)
    _h2, _h2s = hyp(
        [(m, f"{m}|params|I1|high", f"{m}|direct|I1|high") for m in MODELS], _post_mask, -1
    )
    _p1 = A.answer_scores(df[(df["paraphrase"] == "p1") | (df["arm"] == "baseline")])
    _post_p1 = _p1["primary"] & _p1["role"].eq("test-post")
    _h4, _h4s = hyp(
        [(m, f"{m}|direct|I1|high", f"{m}|direct|I0|high") for m in MODELS], _post_p1, -1, _p1
    )
    mo.vstack(
        [
            mo.md(
                "## 6. H1: dQS(model direct I1, official) on OAF cells; supported if > 0 everywhere"
            ),
            _h1.round(4),
            mo.md(f"supported: {_h1s}"),
            mo.md("## 6. H2: dQS(params, direct), test-post cells; supported if < 0 everywhere"),
            _h2.round(4),
            mo.md(f"supported: {_h2s}"),
            mo.md(
                "## 6. H4: dQS(I1, I0), direct, p1, test-post cells; supported if < 0 everywhere"
            ),
            _h4.round(4),
            mo.md(f"supported: {_h4s}"),
        ]
    )
    return hyp, oaf_mask


@app.cell
def _(A, MODELS, df, mo):
    _mask = df["primary"] & df["oaf_cell"] & df["role"].eq("test-post")
    _h3 = A.h3_table(df, MODELS, _mask)
    mo.vstack(
        [
            mo.md("""## 6. H3: coverage error and PIT KS distance minus the official's and RJ-MLE's,
per OAF sequence; supported if the LLM's coverage error is larger in every OAF sequence"""),
            _h3.round(3),
        ]
    )
    return


@app.cell
def _(B, SEED, A, answers, mo, np):
    _prim = answers["primary"]
    _cat = A.ci_table(
        A.dqs(answers, "etas_hindsight", "etas", _prim), np.random.default_rng(SEED), B
    )
    _code = A.ci_table(
        A.dqs(answers, "etas", "official", _prim & answers["oaf_cell"]),
        np.random.default_rng(SEED),
        B,
    )
    _analyst_mask = _prim & answers["oaf_cell"] & answers["name"].isin(["Colombia", "Venezuela"])
    _analyst = A.ci_table(
        A.dqs(answers, "etas_analyst", "official", _analyst_mask), np.random.default_rng(SEED), B
    )
    mo.vstack(
        [
            mo.md("## 6. Catalog effect: dQS(refit on today's catalog, as-of refit), all cells"),
            _cat.round(4),
            mo.md("## 6. Code-and-analyst effect: dQS(as-of refit, official), OAF cells"),
            _code.round(4),
            mo.md("## 6. Sensitivity variant: dQS(analyst-settings refit, official)"),
            _analyst.round(4),
        ]
    )
    return


@app.cell
def _(A, MODELS, answers, answers_valid, base, cell_df, df, hyp, items, mo, pd, samples, tables):
    _target = answers["issue_id"].str.split("@").str[1]
    _post_oaf = answers["oaf_cell"] & answers["role"].eq("test-post")
    _nonover = A.non_overlapping(answers)
    _gap = answers.merge(
        cell_df[["issue_id", "comcat_m5_at_cutoff", "oaf_obs_m5"]].drop_duplicates("issue_id"),
        on="issue_id",
        how="left",
    )
    _small_gap = (_gap["comcat_m5_at_cutoff"] - _gap["oaf_obs_m5"]).abs().le(1).to_numpy()
    _variants = {
        "primary": answers["primary"],
        "2-day settling": answers["settled_2d"],
        "1-Day windows only": answers["primary"] & answers["window"].eq("1 Day"),
        "issues later than 1 day": answers["primary"] & answers["elapsed_days"].gt(1),
        "without Kamchatka": answers["primary"] & answers["name"].ne("Kamchatka"),
        "without Chiapas": answers["primary"] & answers["name"].ne("Offshore Chiapas"),
        "|comcat - obs| <= 1": answers["primary"] & _small_gap,
        "non-overlapping subset": answers["primary"] & _nonover,
        "elapsed < 1 d": answers["primary"] & answers["elapsed_days"].lt(1),
        "elapsed 1-7 d": answers["primary"] & answers["elapsed_days"].between(1, 7),
        "elapsed > 7 d": answers["primary"] & answers["elapsed_days"].gt(7),
    }
    _rows = []
    for _label, _mask in _variants.items():
        _t, _ = hyp([(m, f"{m}|direct|I1|high", "official") for m in MODELS], _mask & _post_oaf, +1)
        if not _t.empty:
            _rows.append(_t[_t["sequence"] == "pooled"].assign(variant=_label))
    _tv, _ = hyp(
        [(m, f"{m}|direct|I1|high", "official") for m in MODELS],
        answers_valid["primary"] & _post_oaf,
        +1,
        answers_valid,
    )
    if not _tv.empty:
        _rows.append(_tv[_tv["sequence"] == "pooled"].assign(variant="valid-only"))
    for _factor in (0.5, 1.5):
        _scaled = A.score_all(A.recount(cell_df, tables, items, _factor), base, samples)
        _sa = A.answer_scores(_scaled)
        _t, _ = hyp(
            [(m, f"{m}|direct|I1|high", "official") for m in MODELS],
            _sa["primary"] & _sa["oaf_cell"] & _sa["role"].eq("test-post"),
            +1,
            _sa,
        )
        if not _t.empty:
            _rows.append(_t[_t["sequence"] == "pooled"].assign(variant=f"radius x{_factor}"))
    _sl, _ = hyp(
        [
            (
                "claude-sonnet-5-5",
                "claude-sonnet-5-5|direct|I1|low",
                "claude-sonnet-5-5|direct|I1|high",
            )
        ],
        answers["primary"] & answers["role"].eq("test-post"),
        -1,
    )
    mo.vstack(
        [
            mo.md(
                "## 6. Sensitivity analyses: H1 pooled dQS(direct I1, official) under each variant"
            ),
            (
                pd.concat(_rows)[["variant", "model", "cells", "dQS", "lo", "hi"]].round(4)
                if _rows
                else pd.DataFrame()
            ),
            mo.md("Sonnet effort low vs high (direct, I1, test-post cells)"),
            _sl.round(4) if not _sl.empty else pd.DataFrame(),
            mo.md(
                f"Ensembles are reported beside single answers: {len(df)} rows scored; "
                f"targets present: {sorted(_target.unique())[:6]}..."
            ),
        ]
    )
    return


@app.cell
def _(A, df, mo, pd):
    _ens = A.ensemble_scores(df)
    _tab = (
        _ens[_ens["primary"]].pivot_table(index="forecaster", columns="name", values="log_qs")
        if not _ens.empty
        else pd.DataFrame()
    )
    mo.vstack([mo.md("## 5. Quantile-averaged ensembles: log-QS, primary cells"), _tab.round(3)])
    return


@app.cell
def _(df, mo):
    _warn = df[df["arm"] != "baseline"]["warnings"].str.get_dummies(sep=",").mean()
    mo.vstack([mo.md("## 7. Warning rates (scored anyway)"), _warn.round(3)])
    return


@app.cell
def _(mo):
    mo.md("""## 8. Recall probe
The probe block is scored by `laf.analysis` once its run exists; no probe run is collected in
this snapshot.""")
    return


if __name__ == "__main__":
    app.run()
