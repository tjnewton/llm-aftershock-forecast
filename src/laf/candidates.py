"""The supplementary candidates fetched at L (prereg v2 section 5): test B's retrospective part
runs to L, and qualifying sequences after the candidate snapshot (20261029T2000Z) are fetched
once at L by the same outcome-blind procedure.

A candidate is a ComCat event with an OAF product, origin in [since, until), that is not
development and is not an aftershock: no larger OAF event or ComCat M>=6 from the previous 365
days holds it inside its circle (the primary and secondary sets are selected at analysis time,
as for the candidate list). Only that backward half of
the ADR 0006 rule applies; its forward half (a later, larger event) can fall inside the
candidate's own windows, so it selects on outcomes (prereg v2 section 4). On the candidate
snapshot's window this procedure gives the 195 candidates plus the 3 forward-excluded ones. The
event lists are stored raw under data/raw/confirmatory/ with manifest lines; no outcome is read.
"""

from pathlib import Path

import pandas as pd

from laf.catalog import haversine_km, wells_coppersmith_radius_km
from laf.e3 import list_url
from laf.splits import development_ids
from laf.training import read_events
from laf.usgs import download, read_raw, store

RAW = "raw/confirmatory"
EMPTY_CSV = b"time,latitude,longitude,depth,mag,magType,net,id,updated,place,type,status\n"
DAY_MS = 86_400_000


def _events(data_dir: Path, name: str, url: str, get=download) -> pd.DataFrame:
    rel = f"{RAW}/{name}.csv"
    if not (data_dir / rel).exists():
        store(data_dir, rel, get(url), url)
    raw = read_raw(data_dir, rel)
    # ComCat answers a window without events with HTTP 204 and an empty body
    return read_events(raw if raw.strip() else EMPTY_CSV)


def is_aftershock(r: dict, context: pd.DataFrame) -> bool:
    """A larger context event from the previous 365 days holds `r` inside its circle."""
    big = context[(context["mag"] > r["mag"]) & (context["time_ms"] < r["time_ms"])
                  & (context["time_ms"] >= r["time_ms"] - 365 * DAY_MS)]  # fmt: skip
    dist = haversine_km(r["latitude"], r["longitude"], big["latitude"], big["longitude"])
    return bool((dist <= big["mag"].map(wells_coppersmith_radius_km)).any())


def select(data_dir: Path, since: str, until: str, get=download) -> pd.DataFrame:
    """The candidates with origin in [since, until) (dates, UTC)."""
    start = (pd.Timestamp(since) - pd.Timedelta(days=365)).date().isoformat()
    oaf = _events(data_dir, f"oaf_{since}_{until}", list_url(since, until, oaf=True), get)
    context = pd.concat([
        _events(data_dir, f"oaf_{start}_{until}", list_url(start, until, oaf=True), get),
        _events(data_dir, f"m6_{start}_{until}", list_url(start, until, min_mag=6.0), get),
    ]).drop_duplicates("id")  # fmt: skip
    # an empty list (no M>=6 in the window) would leave the numeric columns as objects
    context = context.astype({"latitude": float, "longitude": float, "mag": float,
                              "time_ms": "int64"})  # fmt: skip
    dev = development_ids()
    keep = [
        r for r in oaf.sort_values("time_ms").to_dict("records")
        if r["id"] not in dev and not is_aftershock(r, context)
    ]  # fmt: skip
    return pd.DataFrame(keep, columns=oaf.columns)


def write_config(sel: pd.DataFrame, path: Path, since: str, until: str) -> None:
    lines = [
        "# Supplementary candidates (prereg v2 section 5), written by `laf candidates`: OAF",
        f"# events with origin in [{since}, {until}) that qualify, are not development and are not",
        "# aftershocks (backward half of ADR 0006). Never scored before the second gate.",
    ]
    for r in sel.to_dict("records"):
        day = pd.Timestamp(r["time_ms"], unit="ms", tz="UTC").date()
        lines += ["", "[[sequence]]", f'id = "{r["id"]}"',
                  f'name = "{str(r.get("place") or r["id"]).replace(chr(34), "")} {day}"',
                  'role = "test-post"', "catalog_min_mag = 3.0"]  # fmt: skip
    if sel.empty:  # an empty set still loads (`registry.load_sequences`)
        lines += ["", "sequence = []"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
