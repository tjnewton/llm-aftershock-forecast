"""Hindsight bias from catalog revisions (docs/adr/0016). Development data only: outcomes go
through `analysis.cells`, which refuses confirmatory sequences (docs/adr/0013).

Each catalog-based baseline is computed twice, on the catalog as ComCat showed it at the issue
time (`issue_catalogs`, ADR 0011) and on today's catalog with the same selection (origin before
the information cutoff, from 7 days before the mainshock, inside the scoring circle). Only
issue times with full as-of histories enter. Scores are the representation-matched log score
(ADR 0015: nine quantiles through the latent-PCHIP reconstruction) and the registered log-scale
quantile score; dS = S(today's catalog) - S(as-of), so a negative dS means hindsight looks better.
"""

import numpy as np
import pandas as pd

from laf import analysis as A
from laf.catalog import haversine_km
from laf.countdist import from_quantiles, log_score
from laf.scoring import BOOT_SEED, pooled_ci, quantile_score
from laf.tables import FORESHOCK_LOOKBACK_MS

# forecaster -> (name in the as-of baselines, name in the hindsight baselines)
PAIRS = {
    "naive": ("naive", "naive"),
    "rj_mle": ("rj_mle", "rj_mle"),
    "etas": ("etas", "etas_hindsight"),  # ETAS hindsight comes from etas_forecasts_hindsight
}


def hindsight_catalogs(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """`issue_catalogs` rebuilt from today's catalog with the same event selection."""
    cat = tables["catalog"]
    origin = tables["sequences"].set_index("sequence_id")["origin_ms"]
    parts = []
    for it in tables["issue_times"].to_dict("records"):
        c = cat[cat["sequence_id"] == it["sequence_id"]]
        d = haversine_km(it["region_lat"], it["region_lon"], c["latitude"], c["longitude"])
        keep = (
            (c["time_ms"] < it["issue_ms"])
            & (c["time_ms"] >= origin[it["sequence_id"]] - FORESHOCK_LOOKBACK_MS)
            & (d <= it["region_radius_km"])
        )
        parts.append(c[keep].drop(columns="sequence_id").assign(issue_id=it["issue_id"]))
    return pd.concat(parts, ignore_index=True)


def _scores(fc, y5: int, y4: int) -> dict:
    return {
        "ls5": log_score(from_quantiles(fc.m5).cdf, y5)[0],
        "qs5": quantile_score(fc.m5, y5),
        "ls4": log_score(from_quantiles(fc.m4).cdf, y4)[0] if fc.m4 else np.nan,
        "q50_5": float(fc.m5[4]),
    }


def compare(tables: dict[str, pd.DataFrame], items: dict) -> pd.DataFrame:
    """One row per forecaster and primary cell: scores on the as-of and on today's catalog."""
    its = tables["issue_times"].set_index("issue_id")
    cells = A.cells(tables)
    cells = cells[
        (cells["role"] != "dev")
        & cells["primary"]
        & cells["issue_id"].map(its["catalog_source"]).eq("asof")
    ]
    asof = A.baselines(tables, items, cells)
    hind = A.baselines({**tables, "issue_catalogs": hindsight_catalogs(tables)}, items, cells)
    rows = []
    for c in cells.to_dict("records"):
        key = (c["issue_id"], c["window"])
        for name, (a_name, h_name) in PAIRS.items():
            fa = asof.get((a_name, *key))
            fh = (asof if name == "etas" else hind).get((h_name, *key))
            if fa is None or fh is None:
                continue
            a, h = _scores(fa, int(c["y5"]), int(c["y4"])), _scores(fh, int(c["y5"]), int(c["y4"]))
            rows.append(
                {
                    "forecaster": name,
                    "sequence_id": c["sequence_id"],
                    "issue_id": c["issue_id"],
                    "issue_ms": int(c["issue_ms"]),
                    "window": c["window"],
                    "elapsed_days": c["elapsed_days"],
                    "y5": int(c["y5"]),
                    **{f"{k}_asof": v for k, v in a.items()},
                    **{f"{k}_hind": v for k, v in h.items()},
                }
            )
    df = pd.DataFrame(rows)
    for k in ("ls5", "qs5", "ls4"):
        df[f"d_{k}"] = df[f"{k}_hind"] - df[f"{k}_asof"]
    return df


def summary(df: pd.DataFrame, b: int = 10_000) -> pd.DataFrame:
    """Mean dS per forecaster and score with the registered two-stage bootstrap (sequences,
    then issue times by moving blocks), and the share of cells whose score changed."""
    rng = np.random.default_rng(BOOT_SEED)
    out = []
    for (name, score), g in (
        df.melt(
            id_vars=["forecaster", "sequence_id", "issue_ms"],
            value_vars=["d_ls5", "d_qs5", "d_ls4"],
            var_name="score",
        )
        .dropna(subset=["value"])
        .groupby(["forecaster", "score"])
    ):
        seqs = [
            [gi["value"].to_numpy() for _, gi in gs.groupby("issue_ms", sort=True)]
            for _, gs in g.groupby("sequence_id")
        ]
        est, lo, hi = pooled_ci(seqs, rng, b)
        v = g["value"]
        out.append(
            {
                "forecaster": name,
                "score": score,
                "cells": len(v),
                "sequences": len(seqs),
                "mean": est,
                "ci_lo": lo,
                "ci_hi": hi,
                "share_better": float((v < 0).mean()),
                "share_worse": float((v > 0).mean()),
            }
        )
    return pd.DataFrame(out)
