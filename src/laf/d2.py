"""D2 prompt-robustness results (docs/proposals/d2-prompt-robustness.md), development data
only. Unlike `analysis.llm_samples`, which serves the registered requests, this loader
validates v2 answers with their M3 quantiles (`schemas.TARGETS_V2`)."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from laf.prompts import V2
from laf.schemas import QKEYS, TARGETS, TARGETS_V2, WINDOWS, validate


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").split("\n") if x.strip()]


def samples(run_dirs: list[Path]) -> list[dict]:
    """One record per sample and window: request metadata, status, warnings and, for valid
    answers, the quantile lists of every target the prompt asked for."""
    out = []
    for d in run_dirs:
        meta = {r["custom_id"]: r for r in _jsonl(d / "requests.jsonl")}
        for res in _jsonl(d / "results.jsonl"):
            m = meta[res["custom_id"]]
            targets = TARGETS_V2 if m["paraphrase"] in V2 else TARGETS
            if res["result"] != "succeeded":
                status, parsed, warn = "transport_error", None, []
            else:
                status, parsed, warn = validate(
                    m["arm"], res.get("text"), res.get("stop_reason"), targets
                )
            for w in WINDOWS:
                rec = {**m, "window": w, "status": status, "warnings": ",".join(warn)}
                for t in targets:
                    rec[t] = [parsed[w][t][k] for k in QKEYS] if parsed and status == "ok" else None
                out.append(rec)
    return out


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
    floor: float | None = None, radius: float = 1.0,
):  # fmt: skip
    """Per-sample scores and a summary per model, effort and variant (development data only).

    Scores are the representation-matched log score (ADR 0015) minus the official forecast's,
    at M>=5, M>=4 and M>=3. M>=3 counts only where the catalog is complete at M3 for the whole
    window (ADR 0015): the official product's own Mc is at most 3.0, the regional completeness
    magnitude is at most 3.0, and the time-dependent completeness after the mainshock
    (`MagComp`) reaches 3.0 before the window starts."""
    from laf import analysis as A
    from laf.generic_rj import MagComp

    # `score` and `floor`: the sensitivity variants (prereg v2 section 6), at M>=5 only
    ls = scorer(score, floor)

    tables, items = A.load_tables(proc), A.load_items(proc)
    cells = A.cells(tables)  # refuses confirmatory sequences (docs/adr/0013)
    # `settle`: "primary" (21 days) or "settled_2d" (the 2-day sensitivity rule)
    cells = cells[cells[settle] & cells["oaf_cell"] & (cells["role"] == "test-post")]
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
        q3 = _official_m3(
            tables["forecast_fractiles"], c["sequence_id"], int(c["issue_ms"]), c["window"]
        )
        info[k] = {
            "sequence_id": c["sequence_id"],
            "y5": y5, "y4": int(c["y4"]), "y3": int(y3.get(k, -1)),
            "m3_ok": bool(m3_ok and q3 is not None and k in y3.index),
            "off5": ls(off.m5 if off else None, y5, off, "official"),
            "off4": _ls(off.m4 if off else None, int(c["y4"])),  # variants change M>=5 only
            "off3": _ls(q3, int(y3[k])) if k in y3.index else np.nan,
        }  # fmt: skip
        # the worst valid baseline at M5, as dLS (prereg v1 section 7 rule for invalid answers)
        info[k]["worst_base_d5"] = max(
            ls(fc.m5, y5, fc, name) - info[k]["off5"] for name, fc in by_cell.get(k, []) if fc.m5
        )
        # each baseline's dLS at M5, for the contrasts S3-S5 and the assay-sensitivity test
        for b in BASELINES:
            fc = base.get((b, *k))
            info[k][f"base_d5_{b}"] = (
                ls(fc.m5, y5, fc, b) - info[k]["off5"] if fc and fc.m5 else np.nan
            )
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
            **{f"base_d5_{b}": ci[f"base_d5_{b}"] for b in BASELINES},
        }  # fmt: skip
        if r["status"] == "ok":
            for m, t in (
                (5, "m5_count_quantiles"),
                (4, "m4_count_quantiles"),
                (3, "m3_count_quantiles"),
            ):
                sc = (ls if m == 5 else _ls)(r[t], ci[f"y{m}"])
                row[f"d{m}"] = sc - ci[f"off{m}"] if (m != 3 or ci["m3_ok"]) else np.nan
            row["m3_over_m4_median"] = (r["m3_count_quantiles"][4] + 1) / (
                r["m4_count_quantiles"][4] + 1
            )
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
