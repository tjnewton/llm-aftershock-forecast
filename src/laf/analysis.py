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
        ev = cats[(cats["issue_id"] == iid) & (cats["t_days"] > 0)]
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
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


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
    worst = df[df["status"] == "ok"].groupby(["issue_id", "window"])["log_qs"].max()
    bad = df["status"] != "ok"
    df["log_qs_valid_only"] = df["log_qs"].where(~bad)
    df.loc[bad, "log_qs"] = [
        worst[(i, w)] for i, w in zip(df.loc[bad, "issue_id"], df.loc[bad, "window"], strict=True)
    ]
    meta = cell_df.drop(columns=[c for c in ("y4", "y5", "y6") if c not in cell_df])
    return df.merge(meta, on=["issue_id", "window"], how="left")
