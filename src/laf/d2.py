"""D2 prompt-robustness results (docs/proposals/d2-prompt-robustness.md), development data
only. Unlike `analysis.llm_samples`, which serves the registered requests, this loader
validates v2 answers with their M3 quantiles and v3 answers with their four probabilities
(`schemas.fields`)."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from laf.schemas import QKEYS, WINDOWS, fields, validate


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").split("\n") if x.strip()]


def samples(run_dirs: list[Path]) -> list[dict]:
    """One record per sample and window: request metadata, status, warnings and, for valid
    answers, the quantile lists of every target the prompt asked for."""
    out = []
    for d in run_dirs:
        meta = {r["custom_id"]: r for r in _jsonl(d / "requests.jsonl")}
        results = _jsonl(d / "results.jsonl")
        # a request the provider never returned is a transport error too (`runner.retry_plan`)
        seen = {r["custom_id"] for r in results}
        results += [{"custom_id": c, "result": "missing"} for c in meta if c not in seen]
        for res in results:
            m = meta[res["custom_id"]]
            targets, probs = fields(m["paraphrase"])
            if res["result"] != "succeeded":
                status, parsed, warn = "transport_error", None, []
            elif res.get("model_reported") != m["model"]:  # invalid (prereg v2 section 3)
                status, parsed, warn = "model_mismatch", None, []
            else:
                status, parsed, warn = validate(
                    m["arm"], res.get("text"), res.get("stop_reason"), targets, probs
                )
            for w in WINDOWS:
                rec = {**m, "window": w, "status": status, "warnings": ",".join(warn)}
                for t in targets:
                    rec[t] = [parsed[w][t][k] for k in QKEYS] if parsed and status == "ok" else None
                for p in probs:  # p_m6, and for v3 answers p_m5, p_m4 and p_m3
                    rec[p[:4]] = float(parsed[w][p]) if parsed and status == "ok" else None
                out.append(rec)
    # a transport error that a later attempt answered (`runner.retry_plan`) drops out; the
    # rest are the persistent failures, listed and left out (prereg v2 section 7)
    answered = {_attempt_key(r) for r in out if r["status"] != "transport_error"}
    return [r for r in out if r["status"] != "transport_error" or _attempt_key(r) not in answered]


def _attempt_key(r: dict) -> tuple:
    return tuple(r[k] for k in ("model", "item_id", "effort", "paraphrase", "sample", "window"))


def rerun_items(items: list, sequences: pd.DataFrame, model: str) -> list:
    """The items a model's development rerun sends (block `d3`): every development sequence in
    the model's clean period; for a model with none under the 3-month buffer (Opus 5.5), those
    after its training cutoff. Never a confirmatory sequence."""
    from laf.confirmatory import clean_from
    from laf.splits import development_ids

    dev = sequences[sequences["sequence_id"].isin(development_ids())]
    ids: set[str] = set()
    for rule in ("buffered", "unbuffered"):
        start_ms = clean_from(model, rule).value // 1_000_000
        ids = set(dev.loc[dev["origin_ms"] >= start_ms, "sequence_id"])
        if ids:
            break
    return [i for i in items if i.sequence_id in ids]


SCORES = ("registered", "nb_tail", "full", "log_qs")


def scorer(score: str = "registered", floor: float | None = None):
    """(quantiles, y, forecast=None) -> score, for the sensitivity analyses (prereg v2 section
    6). `registered`: the representation-matched log score (ADR 0015); `nb_tail`: the same with
    the negative-binomial tail; `full`: the official forecast through its whole published
    fractile grid and the ETAS refit through its simulated histogram, the rest as registered;
    `log_qs`: the registered log-scale quantile score (prereg v1). `floor` replaces the log
    floor (1e-6)."""
    from laf.countdist import LOG_FLOOR, from_cdf_array, from_quantiles, log_score
    from laf.scoring import quantile_score

    fl = LOG_FLOOR if floor is None else floor
    if score not in SCORES:
        raise ValueError(f"unknown score {score!r}")

    def ls(quantiles, y: int, fc=None, name: str | None = None) -> float:
        if not quantiles:
            return float("nan")
        if score == "log_qs":
            return quantile_score(list(quantiles), y)
        if score == "full" and name == "official" and fc is not None and fc.fractiles_m5:
            levels, counts = fc.fractiles_m5  # the official product's 197-point grid
            return log_score(from_quantiles(counts, levels).cdf, y, fl)[0]
        if score == "full" and name == "etas" and fc is not None and fc.cdf_m5 is not None:
            return log_score(from_cdf_array(fc.cdf_m5), y, fl)[0]  # its simulated distribution
        tail = "nb" if score == "nb_tail" else "power"
        return log_score(from_quantiles(quantiles, tail=tail).cdf, y, fl)[0]

    return ls


def _ls(quantiles, y: int) -> float:
    """Representation-matched log score of nine quantiles (ADR 0015); NaN without a forecast."""
    from laf.countdist import from_quantiles, log_score

    return log_score(from_quantiles(quantiles).cdf, y)[0] if quantiles else float("nan")


def _brier(p: float | None, event: bool | None) -> float:
    """The Brier score of P(M>=6) (`scoring.brier`); NaN without a forecast or an outcome."""
    from laf.scoring import brier

    return brier(p, event) if p is not None and event is not None else float("nan")


def _official_m3(fractiles, sequence_id: str, cutoff_ms: int, window: str) -> list[float] | None:
    """The official M>=3 fractiles at the nine levels, as `forecast.official_forecast` takes them
    at M>=5 and M>=4."""
    from laf.scoring import LEVELS

    f = fractiles[
        (fractiles["sequence_id"] == sequence_id)
        & (fractiles["info_cutoff_ms"] == cutoff_ms)
        & (fractiles["window"] == window)
        & (fractiles["magnitude"] == 3.0)
    ]
    if f.empty:
        return None
    return [float(f.loc[np.isclose(f["p"], t), "count"].iloc[0]) for t in LEVELS]


def m3_complete(product_mc, regional, mag_main: float, t1_days: float) -> bool:
    """ADR 0015: M>=3 is complete for a window starting t1_days after the mainshock when the
    official product's own Mc (ETAS `Mc` or RJ `Mcat`) is at most 3.0, the regional catalog's is
    at most 3.0, and the time-dependent completeness (`MagComp`) has reached 3.0 by then."""
    if product_mc is None or product_mc != product_mc:  # NaN: no official Mc
        return False
    return bool(
        product_mc <= 3.0 + 1e-9 and regional.mag_cat <= 3.0 + 1e-9
        and regional.complete_after_days(mag_main, 3.0) <= t1_days
    )  # fmt: skip


# the pipeline's baselines (`analysis.baselines` names): generic RJ, RJ-MLE, the rule of thumb,
# the legacy-ETAS refit
BASELINES = ("generic_rj", "rj_mle", "naive", "etas")


def recount_m5(tables: dict, cells, scale: float) -> dict[tuple, int | None]:
    """M>=5 counts per (issue, window) with each issue's region radius times `scale`, from its
    own sequence's catalog (the radius sensitivity analyses, prereg v2 section 6). Above 1 a
    cell counts only where the catalog query covered 1.5 times the radius; else None."""
    from laf.catalog import count_in_window
    from laf.oaf import Circle
    from laf.splits import require_outcomes

    require_outcomes(cells["sequence_id"].unique())  # an outcome counter: sealed sequences refused
    its = tables["issue_times"].set_index("issue_id")
    cat = tables["catalog"]
    by_seq = {sid: g for sid, g in cat.groupby("sequence_id")}
    out: dict[tuple, int | None] = {}
    for c in cells.to_dict("records"):
        it = its.loc[c["issue_id"]]
        if scale > 1.0 and not bool(it["query_covers_x1_5"]):
            out[(c["issue_id"], c["window"])] = None
            continue
        circle = Circle(it["region_lat"], it["region_lon"], it["region_radius_km"] * scale)
        own = by_seq.get(c["sequence_id"], cat.iloc[:0])
        out[(c["issue_id"], c["window"])] = count_in_window(
            own, circle, int(c["time_start_ms"]), int(c["time_end_ms"]), 5.0
        )
    return out


def analyze(
    proc: Path, run_dirs: list[Path], settle: str = "primary", score: str = "registered",
    floor: float | None = None, radius: float = 1.0, roles: tuple[str, ...] = ("test-post",),
    clip: float | None = None,
):  # fmt: skip
    """Per-sample scores and a summary per model, effort and variant (development data only).

    `score` "probability" (docs/proposals/prereg-v2-revision.md, P2) puts the log score of the
    probability of at least one M>=5 earthquake in the M>=5 columns (`d5`, `base_d5_*`,
    `worst_base_d5`): the model's own `p_m5` (v3 answers; NaN for v2 ones), the official
    product's published probability, and each baseline's from its own distribution, all clipped
    to [`clip`, 1 - `clip`] (0.001, `scoring.P_CLIP`). Cells without a published probability
    drop out. `worst_case_d5` is then the dS of the clipped probability on the wrong side, the
    strictest rule for an invalid answer. `roles` are the hackathon roles kept (the v3 rerun
    covers every development sequence).

    Scores are the representation-matched log score (ADR 0015) minus the official forecast's,
    at M>=5, M>=4 and M>=3. M>=3 counts only where the catalog is complete at M3 for the whole
    window (ADR 0015): the official product's own Mc is at most 3.0, the regional completeness
    magnitude is at most 3.0, and the time-dependent completeness after the mainshock
    (`MagComp`) reaches 3.0 before the window starts."""
    from laf import analysis as A
    from laf.generic_rj import MagComp
    from laf.scoring import P_CLIP, brier, log_score_binary

    # `score` and `floor`: the sensitivity variants (prereg v2 section 6), at M>=5 only
    prob, eps = score in ("probability", "brier"), P_CLIP if clip is None else clip
    ls = scorer("registered" if prob else score, floor)

    def sp(p: float, event: bool) -> float:
        """The score of a probability: its clipped log score, or its Brier score."""
        return brier(p, event) if score == "brier" else log_score_binary(p, event, eps)

    def s5(fc, name: str, y5: int, p_off) -> float:
        """The M>=5 score of a forecast record: its counts, or its probability of any."""
        if not prob:
            return ls(fc.m5 if fc else None, y5, fc, name)
        if name == "official":
            return sp(float(p_off), y5 >= 1)
        if fc is None or fc.cdf_m5 is None:
            return float("nan")
        return sp(float(1.0 - fc.cdf_m5[0]), y5 >= 1)

    tables, items = A.load_tables(proc), A.load_items(proc)
    cells = A.cells(tables)  # refuses confirmatory sequences (docs/adr/0013)
    # `settle`: "primary" (21 days) or "settled_2d" (the 2-day sensitivity rule)
    cells = cells[cells[settle] & cells["oaf_cell"] & cells["role"].isin(roles)]
    base = A.baselines(tables, items, cells)
    oc = tables["observed_counts"]
    y3 = oc[oc["magnitude"] == 3.0].set_index(["issue_id", "window"])["count"]
    seqs = tables["sequences"].set_index("sequence_id")
    key_window = {"day": "1 Day", "week": "1 Week", "month": "1 Month"}
    by_cell: dict[tuple, list] = {}  # every baseline forecast per cell, for the worst score
    for (name, iid, win), fc in base.items():
        if name not in ("etas_analyst", "etas_hindsight"):
            by_cell.setdefault((iid, win), []).append((name, fc))
    # the official product's completeness magnitude (ETAS `Mc` or RJ `Mcat`, oaf_versions.mc)
    ov = tables["oaf_versions"]
    ov = ov[ov["valid"]].drop_duplicates(["sequence_id", "creation_ms"])
    official_mc = (
        tables["issue_times"][["issue_id", "sequence_id", "creation_ms"]]
        .merge(
            ov[["sequence_id", "creation_ms", "mc"]], on=["sequence_id", "creation_ms"], how="left"
        )
        .set_index("issue_id")["mc"]
    )
    # the official product's published probability of at least one earthquake, per magnitude
    fb = tables["forecast_bins"].set_index(["sequence_id", "info_cutoff_ms", "window"])
    p_official = fb.loc[fb["magnitude"] == 5.0, "probability"]
    p_off_low = {m: fb.loc[fb["magnitude"] == float(m), "probability"] for m in (4, 3)}
    info = {}
    # `radius`: outcomes recounted in the scaled region (a sensitivity analysis, M>=5 only)
    y5_of = recount_m5(tables, cells, radius) if radius != 1.0 else None
    for c in cells.to_dict("records"):
        k = (c["issue_id"], c["window"])
        y5 = int(c["y5"]) if y5_of is None else y5_of[k]
        if y5 is None:
            continue  # the catalog query does not cover the scaled region
        s = seqs.loc[c["sequence_id"]]
        mc = MagComp(
            s["magcomp_region"], s["magcomp_mcat"], s["magcomp_F"], s["magcomp_G"], s["magcomp_H"]
        )
        mag_main = items[c["issue_id"]].mainshock.mag
        t1 = (c["time_start_ms"] - items[c["issue_id"]].mainshock.origin_ms) / 86_400_000
        m3_ok = m3_complete(official_mc.get(c["issue_id"]), mc, mag_main, t1)
        off = base.get(("official", *k))
        p_off = p_official.get((c["sequence_id"], int(c["issue_ms"]), c["window"]))
        if prob and (p_off is None or pd.isna(p_off)):
            continue  # no published probability to score against
        q3 = _official_m3(
            tables["forecast_fractiles"], c["sequence_id"], int(c["issue_ms"]), c["window"]
        )
        info[k] = {
            "sequence_id": c["sequence_id"],
            "y5": y5, "y4": int(c["y4"]), "y3": int(y3.get(k, -1)),
            "m3_ok": bool(m3_ok and q3 is not None and k in y3.index),
            "off5": s5(off, "official", y5, p_off),
            "off4": _ls(off.m4 if off else None, int(c["y4"])),  # variants change M>=5 only
            "off3": _ls(q3, int(y3[k])) if k in y3.index else np.nan,
        }  # fmt: skip
        # descriptive: the published probabilities at M>=4 and M>=3 (None where not published)
        for m in (4, 3):
            p_low = p_off_low[m].get((c["sequence_id"], int(c["issue_ms"]), c["window"]))
            info[k][f"poff{m}"] = None if p_low is None or pd.isna(p_low) else float(p_low)
        # the worst valid baseline at M5, as dLS (prereg v1 section 7 rule for invalid answers)
        info[k]["worst_base_d5"] = np.nanmax(
            [s5(fc, n, y5, p_off) - info[k]["off5"] for n, fc in by_cell.get(k, []) if fc.m5]
        )
        # the clipped probability on the wrong side: nothing valid can score worse
        worst = 1.0 if score == "brier" else -np.log(eps)
        info[k]["worst_case_d5"] = worst - info[k]["off5"] if prob else np.nan
        # each baseline's dLS at M5, for the contrasts S3-S5 and the assay-sensitivity test
        for b in BASELINES:
            fc = base.get((b, *k))
            info[k][f"base_d5_{b}"] = (
                s5(fc, b, y5, p_off) - info[k]["off5"] if fc and fc.m5 else np.nan
            )
        # the Brier score of P(M>=6) per baseline (prereg v2 section 4; `laf.descriptive`)
        y6 = c.get("y6", np.nan)
        info[k]["m6_event"] = None if pd.isna(y6) else bool(y6 > 0)
        for b in ("official", *BASELINES):
            fc = base.get((b, *k))
            info[k][f"brier_m6_{b}"] = _brier(fc.p_m6 if fc else None, info[k]["m6_event"])
    rows = []
    for r in samples(run_dirs):
        k = (r["item_id"], key_window[r["window"]])
        if k not in info:
            continue
        ci = info[k]
        row = {
            "model": r["model"], "effort": r["effort"], "variant": r["paraphrase"],
            "item_id": r["item_id"], "window": r["window"], "sample": r["sample"],
            "sequence_id": ci["sequence_id"], "status": r["status"], "warnings": r["warnings"],
            "m3_ok": ci["m3_ok"], "worst_base_d5": ci["worst_base_d5"],
            "worst_case_d5": ci["worst_case_d5"], "m5_event": bool(ci["y5"] >= 1),
            **{f"base_d5_{b}": ci[f"base_d5_{b}"] for b in BASELINES},
            **{f"brier_m6_{b}": ci[f"brier_m6_{b}"] for b in ("official", *BASELINES)},
            "brier_m6": _brier(r["p_m6"], ci["m6_event"]),
        }  # fmt: skip
        if r["status"] == "ok":
            for m, t in (
                (5, "m5_count_quantiles"),
                (4, "m4_count_quantiles"),
                (3, "m3_count_quantiles"),
            ):
                if m == 5 and prob:  # the answer's own probability, not its quantiles
                    p5 = r.get("p_m5")
                    sc = np.nan if p5 is None else sp(p5, ci["y5"] >= 1)
                else:
                    sc = (ls if m == 5 else _ls)(r[t], ci[f"y{m}"])
                row[f"d{m}"] = sc - ci[f"off{m}"] if (m != 3 or ci["m3_ok"]) else np.nan
            row["m3_over_m4_median"] = (r["m3_count_quantiles"][4] + 1) / (
                r["m4_count_quantiles"][4] + 1
            )
            # v3 answers: the probability's score at M>=4 and M>=3 minus the official one's
            for m in (4, 3):
                p, p_low, event = r.get(f"p_m{m}"), ci[f"poff{m}"], ci[f"y{m}"] >= 1
                row[f"dp{m}"] = np.nan
                if p is not None and p_low is not None and (m != 3 or ci["m3_ok"]):
                    row[f"dp{m}"] = sp(p, event) - sp(p_low, event)
        rows.append(row)
    if not rows:  # e.g. the x1.5 radius variant where no catalog query covers 1.5 times
        return pd.DataFrame(), pd.DataFrame()
    df = pd.DataFrame(rows)
    ok = df[df["status"] == "ok"]
    summary = (
        df.groupby(["model", "effort", "variant"])
        .agg(samples=("status", "size"), invalid=("status", lambda s: float((s != "ok").mean())))
        .join(
            ok.groupby(["model", "effort", "variant"]).agg(
                d5=("d5", "mean"),
                d4=("d4", "mean"),
                d3=("d3", "mean"),
                m3_cells=("d3", lambda s: int(s.notna().sum())),
                incoherent=(
                    "warnings",
                    lambda s: float(s.str.contains("incoherent_magnitudes").mean()),
                ),
                m3_over_m4=("m3_over_m4_median", "median"),
            )
        )
        .reset_index()
    )
    return df, summary


def robustness(df: pd.DataFrame) -> pd.DataFrame:
    """Per model and effort: the spread of an answer's M>=5 score across prompt variants
    (SD of the per-variant answer means, per cell) against the spread across samples within a
    variant (mean SD over variants), on cells where every variant answered validly."""
    import pandas as pd

    ok = df[df["status"] == "ok"]
    out = []
    for (model, effort), g in ok.groupby(["model", "effort"]):
        if g["variant"].nunique() < 2:
            continue
        per = g.groupby(["item_id", "window", "variant"])["d5"]
        means = per.mean().unstack("variant").dropna()
        within = per.std().unstack("variant").reindex(means.index).mean(axis=1)
        out.append({
            "model": model, "effort": effort, "cells": len(means),
            "between_variant_sd": float(means.std(axis=1).mean()),
            "within_variant_sd": float(within.mean()),
        })  # fmt: skip
    return pd.DataFrame(out)
