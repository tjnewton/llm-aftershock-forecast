"""E1 training set (prereg section 11): historical M>=6.5 sequences, prompts from the registered
template (direct arm, I1, p1) at schedule issue times, legacy-ETAS refit completions.

No observed count enters training. The refit gives M>=5 quantiles and P(M>=6); the schema's
M>=4 quantiles are the same refit scaled by Gutenberg-Richter, round(10^b * q5), with the
refit's own b, so the completion is one coherent forecast.
"""

import io
import json
import urllib.parse
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from laf.catalog import haversine_km, read_comcat_csv, wells_coppersmith_radius_km
from laf.etas import forecast_item, issue_seed
from laf.generic_rj import REFERENCE_REL
from laf.items import Item, build_items
from laf.prompts import render
from laf.tables import FORESHOCK_LOOKBACK_MS, schedule_windows, select_issue_times
from laf.usgs import FDSN, download, read_raw, store

DAY_MS = 86_400_000
MIN_MAG = 6.5
MIN_ROWS = 1_000  # AutoScientist minimum for SFT
CATALOG_FLOOR = 3.95  # prompts show M >= 4.0; the refit fits M >= 4.95
LAST_TARGET_DAYS = 28
QKEYS = ("q025", "q050", "q100", "q250", "q500", "q750", "q900", "q950", "q975")
WINDOW_KEY = {"1 Day": "day", "1 Week": "week", "1 Month": "month"}
RAW = "raw/training"


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, UTC).strftime("%Y-%m-%dT%H:%M:%S")


def event_list_url(start: str, end: str) -> str:
    q = {
        "format": "csv",
        "starttime": start,
        "endtime": end,
        "minmagnitude": f"{MIN_MAG}",
        "eventtype": "earthquake",
        "orderby": "time-asc",
    }
    return f"{FDSN}/query?" + urllib.parse.urlencode(q)


def catalog_url(ev: dict) -> str:
    """Events inside the Wells & Coppersmith circle from 7 days before the mainshock to just
    after the last schedule issue time."""
    t0 = int(ev["time_ms"])
    q = {
        "format": "csv",
        "starttime": _iso(t0 - FORESHOCK_LOOKBACK_MS),
        "endtime": _iso(t0 + LAST_TARGET_DAYS * DAY_MS + 3_600_000),
        "latitude": f"{ev['latitude']:.4f}",
        "longitude": f"{ev['longitude']:.4f}",
        "maxradiuskm": f"{wells_coppersmith_radius_km(ev['mag']):.1f}",
        "minmagnitude": f"{CATALOG_FLOOR}",
        "eventtype": "earthquake",
        "orderby": "time-asc",
    }
    return f"{FDSN}/query?" + urllib.parse.urlencode(q)


def read_events(raw: bytes) -> pd.DataFrame:
    """The ComCat event list, keeping the place string shown in prompts."""
    ev = read_comcat_csv(raw)
    place = pd.read_csv(io.BytesIO(raw), dtype={"id": str})[["id", "place"]]
    return ev.merge(place, on="id", how="left")


def exclude_fore_aftershocks(ev: pd.DataFrame) -> pd.DataFrame:
    """ADR 0006 rule: drop events inside a larger listed event's circle within a year."""
    keep = []
    for r in ev.to_dict("records"):
        big = ev[(ev["mag"] > r["mag"]) & ((ev["time_ms"] - r["time_ms"]).abs() <= 365 * DAY_MS)]
        radius = big["mag"].map(wells_coppersmith_radius_km)
        dist = haversine_km(r["latitude"], r["longitude"], big["latitude"], big["longitude"])
        keep.append(not bool((dist <= radius).any()))
    return ev[keep].reset_index(drop=True)


def fetch(data_dir: Path, start: str, end: str) -> pd.DataFrame:
    """Store the event list and one catalog per kept event (raw files are never refetched)."""
    rel = f"{RAW}/events_m{MIN_MAG}_{start}_{end}.csv"
    if not (data_dir / rel).exists():
        store(data_dir, rel, download(event_list_url(start, end)), event_list_url(start, end))
    ev = exclude_fore_aftershocks(read_events(read_raw(data_dir, rel)))
    for r in ev.to_dict("records"):
        crel = f"{RAW}/catalogs/{r['id']}.csv"
        if not (data_dir / crel).exists():
            store(data_dir, crel, download(catalog_url(r)), catalog_url(r))
    return ev


def build(data_dir: Path, ev: pd.DataFrame) -> tuple[list[Item], dict[str, dict], dict]:
    """Items at schedule issue times (origin + 0.3 d, 1/3/7/14/28 d) with today's catalog."""
    seqs, its, windows, cats_rows, cats = [], [], [], [], {}
    for r in ev.to_dict("records"):
        sid, t0 = r["id"], int(r["time_ms"])
        cat = read_comcat_csv(read_raw(data_dir, f"{RAW}/catalogs/{sid}.csv"))
        cat["t_days"] = (cat["time_ms"] - t0) / DAY_MS
        cats[sid] = cat
        radius = wells_coppersmith_radius_km(r["mag"])
        seqs.append(
            {
                "sequence_id": sid,
                "place": str(r["place"]),
                "lat": r["latitude"],
                "lon": r["longitude"],
                "depth_km": r["depth"],
                "mag_type": r["magType"],
                "origin_ms": t0,
                "role": "dev",
            }
        )
        for pick in select_issue_times(t0, None):
            iid = f"{sid}@{pick.target}"
            its.append(
                {
                    "issue_id": iid,
                    "sequence_id": sid,
                    "issue_ms": pick.issue_ms,
                    "elapsed_days": (pick.issue_ms - t0) / DAY_MS,
                    "mag_main": r["mag"],
                    "region_lat": r["latitude"],
                    "region_lon": r["longitude"],
                    "region_radius_km": radius,
                }
            )
            windows += [
                {"issue_id": iid, "window": w, "time_start_ms": a, "time_end_ms": b}
                for w, (a, b) in schedule_windows(pick.issue_ms).items()
            ]
            seen = cat[
                (cat["time_ms"] < pick.issue_ms) & (cat["time_ms"] >= t0 - FORESHOCK_LOOKBACK_MS)
            ]
            cats_rows += [{"issue_id": iid, **x} for x in seen.to_dict("records")]
    tables = {
        "sequences": pd.DataFrame(seqs),
        "issue_times": pd.DataFrame(its),
        "observed_counts": pd.DataFrame(windows),
        "issue_catalogs": pd.DataFrame(cats_rows),
    }
    rows = {
        r["issue_id"]: {**r, "oaf_mc": np.nan, "oaf_b": np.nan, "oaf_sim_min_mag": np.nan}
        for r in its
    }
    return build_items(tables), rows, cats


def _refit(job):
    item, row, cat, ref = job
    after = cat[cat["id"] != item.sequence_id]  # the mainshock enters the fit separately
    return item.item_id, forecast_item(item, row, after, ref, issue_seed(item.item_id))


def completion(refit_rows: list[dict]) -> dict:
    """The refit in the direct-arm schema (M>=4 by Gutenberg-Richter from the same refit)."""
    out = {}
    for r in refit_rows:
        q5 = [int(r[k]) for k in QKEYS]
        q4 = [max(round(10 ** r["b"] * q), q) for q in q5]
        out[WINDOW_KEY[r["window"]]] = {
            "m5_count_quantiles": dict(zip(QKEYS, q5, strict=True)),
            "m4_count_quantiles": dict(zip(QKEYS, q4, strict=True)),
            "p_m6_at_least_one": round(float(r["p_m6"]), 4),
        }
    out["notes"] = "Legacy-ETAS refit of the catalog so far."
    return out


def dataset(data_dir: Path, items, rows, cats, workers: int = 8) -> list[dict]:
    ref = data_dir / REFERENCE_REL
    jobs = [(i, rows[i.item_id], cats[i.sequence_id], ref) for i in items]
    with ProcessPoolExecutor(workers) as pool:
        refits = dict(pool.map(_refit, jobs, chunksize=4))
    out = []
    for item in items:
        system, user = render(item, "direct", "I1", "p1")
        out.append(
            {
                "item_id": item.item_id,
                "sequence_id": item.sequence_id,
                "prompt": f"{system}\n\n{user}",
                "completion": json.dumps(completion(refits[item.item_id])),
            }
        )
    return out
