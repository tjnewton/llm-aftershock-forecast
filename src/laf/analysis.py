"""From tables, items and collected runs to one scores table (prereg sections 4-7).

One row per forecaster x sample x cell. A cell is an issue time x window (1 Day, 1 Week,
1 Month). Invalid samples get the worst log-QS of any forecaster in the cell (prereg sec. 7).
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from laf.forecast import (
    DAY_MS,
    CellForecast,
    direct_forecast,
    etas_forecast,
    fit_rj_mle,
    generic_rj,
    naive_forecast,
    official_forecast,
    rj_mle_forecast,
    rj_predictive,
)
from laf.generic_rj import MagComp
from laf.items import Item
from laf.schemas import validate
from laf.scoring import CENTRAL, brier, log_score_binary, pit_cdf, pit_rank, quantile_score
from laf.splits import require_outcome_table, require_outcomes

WINDOW_KEY = {"1 Day": "day", "1 Week": "week", "1 Month": "month"}
PRIMARY_SETTLING_DAYS = 21
SENSITIVITY_SETTLING_DAYS = 2
PIT_SEED = 20261021


def load_tables(processed: Path) -> dict[str, pd.DataFrame]:
    return {p.stem: pd.read_parquet(p) for p in processed.glob("*.parquet")}


def load_items(processed: Path) -> dict[str, Item]:
    lines = (processed / "items.jsonl").read_text(encoding="utf-8").splitlines()
    return {i.item_id: i for i in (Item.model_validate_json(x) for x in lines if x)}


def cells(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Scored cells with outcomes at M>=4, M>=5 and M>=6 and settling flags."""
    oc = tables["observed_counts"]
    require_outcome_table(oc)  # docs/adr/0013-data-splits.md
    wide = oc.pivot_table(
        index=["issue_id", "sequence_id", "window"], columns="magnitude", values="count"
    ).reset_index()
    meta = oc.drop_duplicates(["issue_id", "window"])[
        ["issue_id", "window", "time_start_ms", "time_end_ms", "closed", "days_since_close"]
    ]
    c = wide.merge(meta, on=["issue_id", "window"]).rename(
        columns={4.0: "y4", 5.0: "y5", 6.0: "y6"}
    )
    its = tables["issue_times"]
    seqs = tables["sequences"].set_index("sequence_id")
    c = c.merge(
        its[
            ["issue_id", "source", "issue_ms", "elapsed_days", "oaf_obs_m5", "comcat_m5_at_cutoff"]
        ],
        on="issue_id",
    )
    c["role"] = c["sequence_id"].map(seqs["role"])
    c["name"] = c["sequence_id"].map(seqs["name"])
    c["primary"] = c["closed"] & (c["days_since_close"] >= PRIMARY_SETTLING_DAYS)
    c["settled_2d"] = c["closed"] & (c["days_since_close"] >= SENSITIVITY_SETTLING_DAYS)
    c["oaf_cell"] = c["source"].eq("oaf")
    return c[[k for k in c.columns if not isinstance(k, float)]]


def _t(item: Item, window: str) -> tuple[float, float]:
    w = next(w for w in item.windows if w.label == window)
    o = item.mainshock.origin_ms
    return (w.start_ms - o) / DAY_MS, (w.end_ms - o) / DAY_MS


def baselines(
    tables: dict[str, pd.DataFrame], items: dict[str, Item], cell_df: pd.DataFrame
) -> dict[tuple[str, str, str], CellForecast]:
    """(forecaster, issue_id, window) -> forecast for official, generic RJ, RJ-MLE, naive and
    the legacy-ETAS refits."""
    seqs = {r["sequence_id"]: r for r in tables["sequences"].to_dict("records")}
    cats = tables["issue_catalogs"]
    etas = {
        name: {(r["issue_id"], r["window"]): r for r in tables[name].to_dict("records")}
        for name in ("etas_forecasts", "etas_forecasts_hindsight", "etas_forecasts_analyst")
        if name in tables
    }
    out: dict[tuple[str, str, str], CellForecast] = {}
    fits = {}
    for c in cell_df.to_dict("records"):
        iid, win = c["issue_id"], c["window"]
        item, s = items[iid], seqs[c["sequence_id"]]
        t1, t2 = _t(item, win)
        mm = item.mainshock.mag
        out[("generic_rj", iid, win)] = generic_rj(s, mm, t1, t2)
        ev = cats[
            (cats["issue_id"] == iid) & (cats["t_days"] > 0) & (cats["id"] != c["sequence_id"])
        ]
        n5 = int((ev["mag"] >= 5.0 - 1e-6).sum())
        out[("naive", iid, win)] = naive_forecast(n5, item.elapsed_days, t1, t2)
        if iid not in fits:
            mc = MagComp(
                s["magcomp_region"],
                s["magcomp_mcat"],
                s["magcomp_F"],
                s["magcomp_G"],
                s["magcomp_H"],
            )
            t_start = mc.complete_after_days(mm, 4.95)
            fits[iid] = fit_rj_mle(
                ev["t_days"].to_numpy(), ev["mag"].to_numpy(), mm, t_start, item.elapsed_days
            )
        fit = fits[iid]
        out[("rj_mle", iid, win)] = (
            rj_mle_forecast(fit, mm, t1, t2) if fit else out[("generic_rj", iid, win)]
        )
        if c["oaf_cell"]:
            out[("official", iid, win)] = official_forecast(
                tables["forecast_fractiles"],
                tables["forecast_bins"],
                c["sequence_id"],
                int(c["issue_ms"]),
                win,
            )
        for name, label in (
            ("etas_forecasts", "etas"),
            ("etas_forecasts_hindsight", "etas_hindsight"),
            ("etas_forecasts_analyst", "etas_analyst"),
        ):
            row = etas.get(name, {}).get((iid, win))
            if row is not None:
                out[(label, iid, win)] = etas_forecast(row)
    return out


def _jsonl(path: Path) -> list[dict]:
    # "\n" only, as in runner._jsonl: str.splitlines also breaks on U+2028 inside strings
    return [json.loads(x) for x in path.read_text(encoding="utf-8").split("\n") if x.strip()]


def llm_samples(run_dirs: list[Path], items: dict[str, Item]) -> list[dict]:
    """One record per sample x window: meta, status, warnings and the forecast (None if
    invalid). Errored or expired batch requests are transport_error."""
    recs = []
    for d in run_dirs:
        meta = {r["custom_id"]: r for r in _jsonl(d / "requests.jsonl")}
        for res in _jsonl(d / "results.jsonl"):
            m = meta[res["custom_id"]]
            item = items[m["item_id"]]
            if res["result"] != "succeeded":
                status, parsed, warn = "transport_error", None, []
            else:
                status, parsed, warn = validate(m["arm"], res.get("text"), res.get("stop_reason"))
            for w in item.windows:
                fc = None
                if parsed is not None:
                    if m["arm"] == "direct":
                        fc = direct_forecast(parsed, WINDOW_KEY[w.label])
                    else:
                        fc = rj_predictive(parsed, item.mainshock.mag, *_t(item, w.label))
                recs.append(
                    {
                        "forecaster": f"{m['model']}|{m['arm']}|{m['info']}|{m['effort']}",
                        "model": m["model"],
                        "arm": m["arm"],
                        "info": m["info"],
                        "effort": m["effort"],
                        "paraphrase": m["paraphrase"],
                        "sample": m["sample"],
                        "block": m["block"],
                        "issue_id": m["item_id"],
                        "window": w.label,
                        "status": status,
                        "warnings": ",".join(warn),
                        "forecast": fc,
                    }
                )
    return recs


def _score(fc: CellForecast, c: dict, rng) -> dict:
    y5, y4 = int(c["y5"]), int(c["y4"])
    row = {
        "m5": list(fc.m5),
        "log_qs": quantile_score(fc.m5, y5),
        "nat_qs": quantile_score(fc.m5, y5, log=False),
        "log_qs_m4": quantile_score(fc.m4, y4) if fc.m4 else np.nan,
        **{
            f"cov{lv}": float(fc.m5[CENTRAL[lv][0]] <= y5 <= fc.m5[CENTRAL[lv][1]])
            for lv in CENTRAL
        },
        "pit_rank": pit_rank(fc.m5, y5, rng),
        "pit_full": (
            pit_cdf(fc.cdf_m5, y5, rng)
            if fc.cdf_m5 is not None
            else pit_rank(fc.fractiles_m5[1], y5, rng, fc.fractiles_m5[0])
            if fc.fractiles_m5
            else np.nan
        ),
    }
    if fc.p_m6 is not None:
        event = bool(c["y6"] > 0)
        row |= {
            "p_m6": fc.p_m6,
            "brier_m6": brier(fc.p_m6, event),
            "log_m6": log_score_binary(fc.p_m6, event),
        }
    return row


def score_all(
    cell_df: pd.DataFrame, base: dict, samples: list[dict], seed: int = PIT_SEED
) -> pd.DataFrame:
    """Scores for every baseline and sample in every cell; then the worst-in-cell penalty."""
    rng = np.random.default_rng(seed)
    by_cell = {(c["issue_id"], c["window"]): c for c in cell_df.to_dict("records")}
    rows = []
    for (name, iid, win), fc in sorted(base.items()):
        rows.append(
            {
                "forecaster": name,
                "model": name,
                "arm": "baseline",
                "info": "I1",
                "effort": "",
                "paraphrase": "",
                "sample": 0,
                "block": "baseline",
                "issue_id": iid,
                "window": win,
                "status": "ok",
                "warnings": "",
                **_score(fc, by_cell[(iid, win)], rng),
            }
        )
    for s in samples:
        key = (s["issue_id"], s["window"])
        if key not in by_cell:
            continue
        r = {k: v for k, v in s.items() if k != "forecast"}
        if s["forecast"] is not None:
            r |= _score(s["forecast"], by_cell[key], rng)
        rows.append(r)
    df = pd.DataFrame(rows)
    # worst valid sample or baseline; the analyst and hindsight refits are not baselines
    pool = df["status"].eq("ok") & ~df["forecaster"].isin(["etas_analyst", "etas_hindsight"])
    worst = df[pool].groupby(["issue_id", "window"])["log_qs"].max()
    df["log_qs_valid_only"] = df["log_qs"].where(df["status"] == "ok")
    # invalid samples get the worst score; transport errors are excluded and counted
    bad = ~df["status"].isin(["ok", "transport_error"])
    df.loc[bad, "log_qs"] = [
        worst[(i, w)] for i, w in zip(df.loc[bad, "issue_id"], df.loc[bad, "window"], strict=True)
    ]
    meta = cell_df.drop(columns=[c for c in ("y4", "y5", "y6") if c not in cell_df])
    return df.merge(meta, on=["issue_id", "window"], how="left")


# --- Aggregation for the preregistered tables (prereg sections 2, 5, 6) ---

NON_OVERLAP = {"1 Day": None, "1 Week": ("first", "7d", "14d", "28d"), "1 Month": ("first",)}


def answer_scores(df: pd.DataFrame, metric: str = "log_qs") -> pd.DataFrame:
    """Estimand: a single chatbot answer, so the mean over samples (and paraphrases) per
    forecaster x cell; baselines have one sample."""
    keys = [
        "forecaster",
        "model",
        "arm",
        "info",
        "effort",
        "issue_id",
        "window",
        "sequence_id",
        "name",
        "role",
        "primary",
        "settled_2d",
        "oaf_cell",
        "elapsed_days",
    ]
    return df.groupby(keys)[metric].mean().reset_index()


def non_overlapping(cell_df: pd.DataFrame) -> pd.Series:
    target = cell_df["issue_id"].str.split("@").str[1]
    keep = pd.Series(False, index=cell_df.index)
    for win, targets in NON_OVERLAP.items():
        sel = cell_df["window"] == win
        if targets is None:
            keep |= sel
        else:
            keep |= sel & target.apply(lambda t, ts=targets: any(x in t.split("+") for x in ts))
    return keep


def dqs(
    scores: pd.DataFrame,
    x: str,
    ref: str,
    cell_mask: pd.Series | None = None,
    metric: str = "log_qs",
) -> pd.DataFrame:
    """Per cell dQS = score(x) - score(ref), on cells where both exist (and the mask)."""
    s = scores if cell_mask is None else scores[cell_mask.reindex(scores.index, fill_value=False)]
    a = s[s["forecaster"] == x].set_index(["issue_id", "window"])
    b = s[s["forecaster"] == ref].set_index(["issue_id", "window"])[metric]
    out = a.join(b.rename("ref"), how="inner")
    out["d"] = out[metric] - out["ref"]
    return out.dropna(subset=["d"]).reset_index()  # e.g. all samples transport errors


def ci_table(d: pd.DataFrame, rng, b: int = 10_000) -> pd.DataFrame:
    """Per-sequence mean dQS with moving-block bootstrap CIs, then the pooled two-stage CI."""
    from laf.scoring import pooled_ci, sequence_ci

    rows, pooled = [], []
    for name, g in d.groupby("name"):
        issues = [
            x["d"].to_numpy()
            for _, x in g.sort_values("elapsed_days").groupby("issue_id", sort=False)
        ]
        est, lo, hi = sequence_ci(issues, rng, b)
        rows.append({"sequence": name, "cells": len(g), "dQS": est, "lo": lo, "hi": hi})
        pooled.append(issues)
    if pooled:
        est, lo, hi = pooled_ci(pooled, rng, b)
        rows.append({"sequence": "pooled", "cells": len(d), "dQS": est, "lo": lo, "hi": hi})
    return pd.DataFrame(rows)


def supported(table: pd.DataFrame, direction: int) -> bool:
    """Prereg section 2: sign agreement in every sequence and the pooled CI excludes 0.
    direction = +1 when the hypothesis predicts dQS > 0, -1 when it predicts dQS < 0."""
    seqs = table[table["sequence"] != "pooled"]
    pooled = table[table["sequence"] == "pooled"]
    if seqs.empty or pooled.empty:
        return False
    agree = bool((direction * seqs["dQS"] > 0).all())
    p = pooled.iloc[0]
    excl = p["lo"] > 0 if direction > 0 else p["hi"] < 0
    return agree and bool(excl)


def coverage_table(df: pd.DataFrame, mask: pd.Series) -> pd.DataFrame:
    """Empirical coverage of central intervals per forecaster (valid samples only)."""
    s = df[mask & df["status"].eq("ok")]
    return s.groupby("forecaster")[[f"cov{lv}" for lv in (50, 80, 90, 95)]].mean()


def pit_ks(df: pd.DataFrame, mask: pd.Series, column: str = "pit_rank") -> pd.Series:
    """Kolmogorov-Smirnov distance of randomized PIT values from uniform, per forecaster."""
    from scipy import stats

    s = df[mask & df["status"].eq("ok")].dropna(subset=[column])
    return s.groupby("forecaster")[column].apply(lambda v: stats.kstest(v, "uniform").statistic)


def invalid_table(df: pd.DataFrame) -> pd.DataFrame:
    """Status shares by model, arm and information (co-primary outcome)."""
    s = df[df["arm"] != "baseline"].drop_duplicates(
        ["forecaster", "paraphrase", "sample", "issue_id"]
    )
    return pd.crosstab(
        [s["model"], s["arm"], s["info"], s["effort"]], s["status"], normalize="index"
    )


def recount(
    cell_df: pd.DataFrame, tables: dict[str, pd.DataFrame], items: dict[str, Item], factor: float
) -> pd.DataFrame:
    """Outcomes recounted in the scoring circle scaled by `factor` (radius sensitivity)."""
    from laf.catalog import count_in_window
    from laf.oaf import Circle

    require_outcomes(cell_df["sequence_id"].unique())
    cat = tables["catalog"]
    out = cell_df.copy()
    for col, m in (("y4", 4.0), ("y5", 5.0), ("y6", 6.0)):
        out[col] = [
            count_in_window(
                cat[cat["sequence_id"] == r["sequence_id"]],
                Circle(
                    items[r["issue_id"]].region.lat,
                    items[r["issue_id"]].region.lon,
                    items[r["issue_id"]].region.radius_km * factor,
                ),
                int(r["time_start_ms"]),
                int(r["time_end_ms"]),
                m,
            )
            for r in out.to_dict("records")
        ]
    return out


def ensemble_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Quantile-averaged ensemble of the valid samples per forecaster x cell, scored like a
    single forecast (reported beside single answers)."""
    llm = df[(df["arm"] != "baseline") & df["status"].eq("ok")]
    rows = []
    for (f, iid, win), g in llm.groupby(["forecaster", "issue_id", "window"]):
        qs = np.mean(np.vstack(g["m5"].to_list()), axis=0).tolist()
        first = g.iloc[0]
        rows.append(
            {
                "forecaster": f,
                "issue_id": iid,
                "window": win,
                "n_samples": len(g),
                "log_qs": quantile_score(qs, int(first["y5"])),
                "name": first["name"],
                "primary": first["primary"],
                "oaf_cell": first["oaf_cell"],
                "role": first["role"],
            }
        )
    return pd.DataFrame(rows)


def h3_table(df: pd.DataFrame, models, mask: pd.Series) -> pd.DataFrame:
    """H3 per OAF sequence and pooled: |coverage - nominal| of the central 50% and 90% intervals
    and the randomized-PIT KS distance, each minus the official's (and minus RJ-MLE's)."""
    from scipy import stats

    s = df[mask & df["status"].eq("ok")]
    rows = []
    groups = [(n, g) for n, g in s.groupby("name")] + [("pooled", s)]
    for name, g in groups:

        def err(f, lv, g=g):
            v = g.loc[g["forecaster"] == f, f"cov{lv}"]
            return abs(v.mean() - lv / 100) if len(v) else np.nan

        def ks(f, g=g):
            v = g.loc[g["forecaster"] == f, "pit_rank"].dropna()
            return stats.kstest(v, "uniform").statistic if len(v) else np.nan

        for m in models:
            f = f"{m}|direct|I1|high"
            rows.append(
                {
                    "sequence": name,
                    "model": m,
                    **{
                        f"cov{lv}_err_minus_official": err(f, lv) - err("official", lv)
                        for lv in (50, 90)
                    },
                    **{
                        f"cov{lv}_err_minus_rj_mle": err(f, lv) - err("rj_mle", lv)
                        for lv in (50, 90)
                    },
                    "pit_ks_minus_official": ks(f) - ks("official"),
                    "pit_ks_minus_rj_mle": ks(f) - ks("rj_mle"),
                }
            )
    return pd.DataFrame(rows)
