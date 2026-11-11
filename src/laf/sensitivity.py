"""Sensitivity analyses of prereg v2 section 6, reported in one table whatever their result.

Each row repeats a tested model's non-inferiority test against the official forecast on a
variant of its cells: the margin, the clean rule, the prompt, the invalid-answer rule, the
settling rule, a subset of cells, or one elapsed-time stratum. Scoring variants (other clips of
the probability, its Brier score, the count score through nine quantiles and its own variants)
and the outcome variants (region radius, the forward-excluded candidates) follow.
"""

from typing import Any

import pandas as pd

from laf import confirmatory as C

NON_OVERLAP = {"day": None, "week": ("first", "7d", "14d", "28d"), "month": ("first",)}
AB_MODELS = ("gpt-5.1-2025-11-13", "claude-opus-5-5")  # v3B runs for the A and B models only


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
    """Issue times whose as-of catalog (`issue_catalogs`, what the forecasters saw) reproduces the
    official product's own M>=5 observation count, counted as the V0 check counts
    (`asof.check_observations`): events other than the mainshock, after its origin, in the
    circle before the cutoff, at M >= 5 - 0.01. (`comcat_m5_at_cutoff` counts the revised
    catalog instead.)"""
    it, cats = tables["issue_times"], tables["issue_catalogs"]
    seq = cats["issue_id"].map(dict(zip(it["issue_id"], it["sequence_id"], strict=True)))
    origin = seq.map(tables["sequences"].set_index("sequence_id")["origin_ms"])
    after = cats[(cats["id"] != seq) & (cats["time_ms"] > origin) & (cats["mag"] >= 5.0 - 0.01)]
    asof = it["issue_id"].map(after.groupby("issue_id").size()).fillna(0)
    return set(it.loc[it["oaf_obs_m5"] == asof, "issue_id"])


def _row(
    analysis: str, cells: pd.DataFrame, models: tuple[str, ...], delta: float = C.DELTA
) -> list[dict]:
    rows = []
    for m, g in cells[cells["model"].isin(models)].groupby("model"):
        t = C.noninferiority(C.sequence_effects(g).to_numpy(), delta)
        if m not in C.PRIMARY:  # secondary models: an estimate and bound, no verdict
            t["noninferior"] = None
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
    for delta in C.SENSITIVITY_MARGINS:  # the same estimate and bound, read at another margin
        rows += _row(f"margin {delta:g}", main, models, delta)
    if sets is None:
        wide = {C.PRIMARY[0]: 0.0}
        rows += _row("test A on all clean candidates",
                     C.confirmatory_cells(samples, seqs, elapsed, wide), C.PRIMARY)  # fmt: skip
        for rule in ("unbuffered", "release"):
            rows += _row(f"{rule} clean rule", cells(rule=rule), models)
        # tests A, B and S1 with the 3 forward-excluded candidates (prereg v2 section 4)
        abs1 = tuple(m for m in models if m in (*C.PRIMARY, "claude-opus-5-5", "claude-opus-4-6"))
        rows += _row("with the 3 forward-excluded candidates", cells(include_forward=True), abs1)
    rows += _row("non-overlapping subset", main[non_overlapping(main)], models)
    rows += _row(C.ROBUSTNESS_PROMPT, cells(variant=C.ROBUSTNESS_PROMPT),
                 tuple(m for m in models if m in AB_MODELS))  # fmt: skip
    rows += _row("valid answers only", cells(s=samples[samples["status"] == "ok"]), models)
    if "worst_case_d5" in samples and samples["worst_case_d5"].notna().any():
        rows += _row("invalid answers at the worst case", cells(invalid="worst_case"), models)
    exact = exact_match(tables)
    rows += _row("as-of catalog matches the official count", main[main["issue_id"].isin(exact)],
                 models)  # fmt: skip
    if samples_2d is not None:
        rows += _row("2-day settling rule", cells(s=samples_2d), models)
    for _, name in C.STRATA:
        rows += _row(f"stratum: {name}", main[main["stratum"] == name], models)
    return pd.DataFrame(rows)


def invalid_rates(samples: pd.DataFrame, live: pd.DataFrame | None = None) -> pd.DataFrame:
    """Invalid answers per arm (the retrospective batches; with `live`, the prospective
    answers of `live_scores.live_samples`), model, effort and prompt, by status; transport
    errors apart (they are retried and left out, not penalized)."""
    arms = [samples.assign(arm="retrospective")]
    if live is not None and len(live):
        arms.append(live.assign(arm="prospective"))
    s = pd.concat(arms).drop_duplicates(["arm", "model", "effort", "variant", "item_id", "sample"])
    g = s.groupby(["arm", "model", "effort", "variant"], dropna=False)["status"]
    out = g.value_counts().unstack(fill_value=0)
    scored = out.drop(columns=["transport_error"], errors="ignore").sum(axis=1)
    out["invalid_rate"] = 1 - out.get("ok", 0) / scored.where(scored > 0)
    return out.reset_index()


def invalid_by_cell(samples: pd.DataFrame, cells: pd.DataFrame) -> pd.DataFrame:
    """Invalid answers of the retrospective batches by elapsed-time stratum and by whether an
    M>=5 earthquake occurred in the cell (prereg v2 section 7): a fixed penalty is mild where
    a valid answer would have lost more, so a concentration in hard cells must be visible.
    One row per model, stratum and event, counted over the tests' cells (`cells`)."""
    if "m5_event" not in samples or not len(cells):
        return pd.DataFrame()
    stratum = dict(zip(cells["issue_id"], cells["stratum"], strict=True))
    s = samples[samples["status"].ne("transport_error") & samples["item_id"].isin(stratum)]
    s = s[s["model"].isin(set(cells["model"])) & (s["variant"] == C.PRIMARY_PROMPT)]
    s = s.assign(stratum=s["item_id"].map(stratum), invalid=s["status"].ne("ok"))
    g = s.groupby(["model", "stratum", "m5_event"])["invalid"]
    return g.agg(answers="size", invalid="sum", invalid_rate="mean").reset_index()


def failures(samples: pd.DataFrame) -> pd.DataFrame:
    """The persistent transport failures, one row per answer: left out and listed (prereg v2
    section 7). Failures a retry answered are already gone (`d2.samples`)."""
    keys = ["model", "effort", "variant", "item_id", "sample", "sequence_id"]
    bad = samples[samples["status"] == "transport_error"]
    return bad.drop_duplicates(keys[:-1])[keys].reset_index(drop=True)


def extras(
    samples: pd.DataFrame, cells: pd.DataFrame, live: pd.DataFrame | None = None,
    b_parts: dict | None = None, timeliness: pd.DataFrame | None = None,
) -> dict[str, pd.DataFrame]:  # fmt: skip
    """The registered outputs beside the tests: persistent failures, invalid rates by arm and
    by stratum and event, and the leave-one-sequence-out influence on A and on B (both parts
    given `b_parts`, else its retrospective part), and on-time against late items when given."""
    inf = []
    for label, model in (("A", C.PRIMARY[0]), ("B retrospective part", C.B_MODEL)):
        g = cells[cells["model"] == model]
        if len(g) and not (b_parts and model == C.B_MODEL):
            inf.append(C.influence(g).assign(hypothesis=label, model=model))
    if b_parts and len(b_parts["both"]):
        b = C.influence(b_parts["both"], b_parts["parts"])
        inf.append(b.assign(hypothesis="B", model=C.B_MODEL))
    out = {"failures": failures(samples), "invalid": invalid_rates(samples, live),
           "invalid_cells": invalid_by_cell(samples, cells),
           "influence": pd.concat(inf, ignore_index=True) if inf else pd.DataFrame()}  # fmt: skip
    if timeliness is not None:
        out["timeliness"] = timeliness
    return out


# scoring and outcome variants (prereg v2 section 6): (label, `laf.d2.analyze` arguments)
# The count score keeps its own rule for an invalid answer (the worst of the five baselines)
_COUNT: dict[str, Any] = {"invalid": "worst_baseline"}
SCORE_VARIANTS: tuple[tuple[str, dict[str, Any]], ...] = (
    ("probability clipped at 0.0001", {"score": "probability", "clip": 1e-4}),
    ("probability clipped at 0.01", {"score": "probability", "clip": 1e-2}),
    ("Brier score of the probability", {"score": "brier", "invalid": "worst_case"}),
    ("count score (nine quantiles)", {"score": "registered", **_COUNT}),
    ("count score, log floor 1e-4", {"floor": 1e-4, **_COUNT}),
    ("count score, log floor 1e-8", {"floor": 1e-8, **_COUNT}),
    ("count score, negative-binomial tail", {"score": "nb_tail", **_COUNT}),
    ("count score, full distributions (official, ETAS)", {"score": "full", **_COUNT}),
    ("log-scale quantile score", {"score": "log_qs", **_COUNT}),
    ("region radius x0.5", {"score": "probability", "radius": 0.5}),
    ("region radius x1.5", {"score": "probability", "radius": 1.5}),
)


def scoring_variants(
    proc, run_dirs, tables: dict[str, pd.DataFrame], elapsed: dict[str, float],
    models: tuple[str, ...], sets: dict[str, set[str]] | None = None,
    roles: tuple[str, ...] = ("test-post",),
) -> pd.DataFrame:  # fmt: skip
    """The non-inferiority rows again under each scoring variant. The margin is defined for the
    probability's log score, so only its variants (clips, region radius) carry a verdict: the
    Brier score, the count score and the quantile score give the estimate and bound only."""
    from laf.d2 import analyze

    rows = []
    for label, variant in SCORE_VARIANTS:
        kw = dict(variant)
        invalid = kw.pop("invalid", C.INVALID)
        s, _ = analyze(proc, run_dirs, roles=roles, **kw)
        if s.empty:  # no cell can be scored under this variant: reported as such
            rows += [{"analysis": label, "model": m, "sequences": 0} for m in models]
            continue
        cells = C.confirmatory_cells(s, tables["sequences"], elapsed, sets=sets, invalid=invalid)
        r = _row(label, cells, models)
        if kw.get("score") != C.PRIMARY_SCORE:
            for x in r:
                x["noninferior"] = None
        rows += r
    return pd.DataFrame(rows)


FLOORS = (1e-6, 1e-4, 1e-8)


def diagnostics(
    proc, run_dirs, models: tuple[str, ...], sets: dict[str, set[str]] | None = None,
    roles: tuple[str, ...] = ("test-post",),
) -> pd.DataFrame:  # fmt: skip
    """Per forecaster's count quantiles at M>=5 on the scored cells (prereg v2 section 6, ADR
    0015): how often each log floor binds, the cells above its 97.5% quantile, CSEP N-test
    failures (either quantile below 0.025), the KS distance of its randomized PIT from
    uniform, and the
    information gain per earthquake against the official forecast (official log score minus
    its own, summed over cells, over the earthquakes counted). Each model counts on its own
    eligible sequences (its test set), the baselines on those of any tested model; `sets`
    replaces them (the development rehearsal)."""
    import numpy as np
    from scipy import stats

    from laf import analysis as A
    from laf.countdist import from_quantiles, log_score, n_test, pit
    from laf.d2 import BASELINES, samples

    tables, items = A.load_tables(proc), A.load_items(proc)
    cells = A.cells(tables)  # refuses sealed outcomes
    cells = cells[cells["primary"] & cells["oaf_cell"] & cells["role"].isin(roles)]
    base = A.baselines(tables, items, cells)
    sets = sets or {m: C.eligible(tables["sequences"], m) for m in models}
    union = set().union(*sets.values())
    cells = cells[cells["sequence_id"].isin(union)]
    seq_of = dict(zip(zip(cells["issue_id"], cells["window"], strict=True), cells["sequence_id"],
                      strict=True))  # fmt: skip
    y5 = {(c["issue_id"], c["window"]): int(c["y5"]) for c in cells.to_dict("records")}
    label = {"day": "1 Day", "week": "1 Week", "month": "1 Month"}
    by: dict[str, list] = {}
    for (name, iid, win), fc in base.items():
        if (iid, win) in y5 and (name == "official" or name in BASELINES) and fc.m5:
            by.setdefault(name, []).append(((iid, win), fc.m5))
    for r in samples(run_dirs):
        key = (r["item_id"], label[r["window"]])
        if (r["model"] in models and r["status"] == "ok" and r["paraphrase"] == C.PRIMARY_PROMPT
                and r["effort"] == C.study_effort(r["model"]) and key in y5
                and seq_of[key] in sets.get(r["model"], set())):  # fmt: skip
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
