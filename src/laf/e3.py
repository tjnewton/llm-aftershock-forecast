"""E3 extended exploratory set (ADR 0012). Candidates are ComCat events with an OAF product:
every one with origin in POST and magnitude >= MIN_MAG, the N_PRE most recent such events in
PRE. Registered sequences and
foreshocks/aftershocks of a larger listed event (inside its circle within a year, ADR 0006
rule) are dropped. The event lists are stored raw with manifest lines; no outcome is read."""

import json
import urllib.parse
from pathlib import Path

import pandas as pd

from laf.catalog import haversine_km, wells_coppersmith_radius_km
from laf.training import read_events
from laf.usgs import FDSN, download, read_raw, store

POST = ("2026-07-01", "2026-10-01")  # [start, end)
PRE = ("2026-01-01", "2026-06-01")
N_PRE = 60
MIN_MAG = 5.0  # smaller mainshocks almost never have M>=5 (or M>=4) aftershocks to score
# ComCat truncates this event's document (superseded products) at ~1.2 MB on every request
UNRETRIEVABLE = {"nn00914068"}
CONTEXT = ("2025-01-01", "2026-10-15")  # events that can claim a candidate as fore/aftershock
DAY_MS = 86_400_000
RAW = "raw/e3"


def list_url(start: str, end: str, *, oaf: bool = False, min_mag: float | None = None) -> str:
    q = {"format": "csv", "starttime": start, "endtime": end, "orderby": "time-asc"}
    if oaf:
        q["producttype"] = "oaf"
    if min_mag is not None:
        q["minmagnitude"] = f"{min_mag}"
    return f"{FDSN}/query?" + urllib.parse.urlencode(q)


def _events(data_dir: Path, name: str, url: str) -> pd.DataFrame:
    rel = f"{RAW}/{name}.csv"
    if not (data_dir / rel).exists():
        store(data_dir, rel, download(url), url)
    return read_events(read_raw(data_dir, rel))


def claimed(cand: pd.DataFrame, context: pd.DataFrame) -> pd.Series:
    """True where a larger context event within 365 days has the candidate inside its circle."""
    out = []
    for r in cand.to_dict("records"):
        big = context[
            (context["mag"] > r["mag"])
            & ((context["time_ms"] - r["time_ms"]).abs() <= 365 * DAY_MS)
        ]
        dist = haversine_km(r["latitude"], r["longitude"], big["latitude"], big["longitude"])
        out.append(bool((dist <= big["mag"].map(wells_coppersmith_radius_km)).any()))
    return pd.Series(out, index=cand.index)


def select(data_dir: Path, registered: set[str]) -> pd.DataFrame:
    post = _events(data_dir, "oaf_post", list_url(*POST, oaf=True))
    pre = _events(data_dir, "oaf_pre", list_url(*PRE, oaf=True))
    context = pd.concat(
        [
            _events(data_dir, "oaf_context", list_url(*CONTEXT, oaf=True)),
            _events(data_dir, "m6_context", list_url(*CONTEXT, min_mag=6.0)),
        ]
    ).drop_duplicates("id")
    keep = []
    for role, df in (("test-post", post), ("test-pre", pre)):
        df = df[(df["mag"] >= MIN_MAG) & ~df["id"].isin(registered | UNRETRIEVABLE)]
        df = df[~claimed(df, context)].sort_values("time_ms")
        if role == "test-pre":
            df = df.tail(N_PRE)
        keep.append(df.assign(role=role))
    return pd.concat(keep).reset_index(drop=True)


def write_config(sel: pd.DataFrame, path: Path) -> None:
    lines = [
        "# E3 extended exploratory set (docs/adr/0012-e3-extended-set.md), written by",
        "# `laf e3-select`. Roles reuse the registered names so the frozen code applies; these",
        "# sequences are exploratory and never enter the registered analysis.",
    ]
    for r in sel.to_dict("records"):
        lines += [
            "",
            "[[sequence]]",
            f"id = {json.dumps(r['id'])}",
            f"name = {json.dumps(str(r['place']) + ' ' + r['time'].strftime('%Y-%m-%d'))}",
            f"role = {json.dumps(r['role'])}",
            "catalog_min_mag = 3.0",
        ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
