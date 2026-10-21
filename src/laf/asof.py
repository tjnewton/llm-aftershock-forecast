"""ComCat catalog as it stood at a past time, from product histories (docs/adr/0011).

ComCat keeps every version of every product when queried with ``includesuperseded=true``. An
event is visible at time T if one of its origin products has a version available by T that is
not a deletion. Its preferred origin at T is the available origin product with the highest
``preferredWeight`` (ties: the latest version), which gives the time, location and magnitude an
operational forecast fetching ComCat at T would have seen.

Layout: raw/events/<event id>.geojson.gz (one history per event, shared by all snapshots, since
versions older than the fetch never change) and raw/snapshots/<snap>/deleted/<seq>.geojson.gz
(the snapshot's query circle with ``includedeleted=true``, to find events deleted since).
"""

import gzip
import json
import threading
import time
import urllib.parse
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from laf.catalog import read_comcat_csv
from laf.usgs import FDSN, _circle_params, download, event_url, read_raw, store

DAY_MS = 86_400_000
MAX_RATE_PER_S = 1.0  # 300 requests per 5 minutes; ComCat allows 500
WINDOW_MS = (-7 * DAY_MS, 90 * DAY_MS)  # foreshock lookback .. end of the snapshot catalog
VERSION_COLUMNS = [
    "event_id",
    "source",
    "code",
    "status",
    "update_ms",
    "index_ms",
    "weight",
    "time_ms",
    "latitude",
    "longitude",
    "depth",
    "mag",
    "magType",
    "review",
]


def history_rel(event_id: str) -> str:
    return f"raw/events/{event_id}.geojson.gz"


def deleted_url(meta: dict) -> str:
    params = _circle_params(
        meta["center_lat"],
        meta["center_lon"],
        meta["radius_km"],
        meta["catalog_start_ms"],
        meta["catalog_end_ms"],
        meta["min_mag"],
    )
    return f"{FDSN}/query?" + urllib.parse.urlencode(
        {**params, "format": "geojson", "includedeleted": "true"}
    )


def _event_ids(
    data_dir: Path, snapshot: str, seq_id: str, min_mag: float = -9.0, max_days: float = 90.0
) -> tuple[list[str], dict]:
    """Catalog event ids from 7 days before the mainshock to ``max_days`` after it with current
    magnitude >= ``min_mag`` (choose a margin below the magnitudes that matter: revisions)."""
    snap = f"raw/snapshots/{snapshot}"
    event = json.loads(read_raw(data_dir, f"{snap}/event/{seq_id}.geojson.gz"))
    origin = int(event["properties"]["time"])
    meta = json.loads(read_raw(data_dir, f"{snap}/catalog/{seq_id}.meta.json"))
    cat = read_comcat_csv(read_raw(data_dir, f"{snap}/catalog/{seq_id}.csv"))
    lo, hi = origin + WINDOW_MS[0], origin + min(WINDOW_MS[1], int(max_days * DAY_MS))
    keep = (cat["time_ms"] >= lo) & (cat["time_ms"] <= hi) & (cat["mag"] >= min_mag)
    ids = cat.loc[keep, "id"].tolist()
    return [i for i in ids if i != seq_id], {"origin_ms": origin, "meta": meta, "lo": lo, "hi": hi}


def fetch_histories(
    data_dir: Path,
    snapshot: str,
    seq_ids: Iterable[str],
    *,
    workers: int = 3,
    deleted: bool = False,
    min_mag: float = -9.0,
    max_days: float = 90.0,
    get=download,
) -> int:
    """Store the product history of every catalog event near each mainshock. Idempotent;
    returns the number of files stored.

    With ``deleted``, also query the snapshot's circle with ``includedeleted=true`` and fetch
    events ComCat now lists as deleted. Off by default: every such query (even one
    day, worldwide, M>=4) ended in HTTP 504 after 60 s, so deleted events are not reconstructed.
    """
    wanted: dict[str, None] = {}
    stored = 0
    for seq_id in seq_ids:
        ids, ctx = _event_ids(data_dir, snapshot, seq_id, min_mag, max_days)
        wanted.update(dict.fromkeys(ids))
        if not deleted:
            continue
        rel = f"raw/snapshots/{snapshot}/deleted/{seq_id}.geojson.gz"
        url = deleted_url(ctx["meta"])
        if not (data_dir / rel).exists():
            stored += store(data_dir, rel, get(url), url, compress=True) is not None
        for f in json.loads(read_raw(data_dir, rel))["features"]:
            t = f["properties"]["time"]
            if f["properties"].get("status") == "deleted" and ctx["lo"] <= t <= ctx["hi"]:
                wanted[f["id"]] = None
    todo = [i for i in wanted if not (data_dir / history_rel(i)).exists()]

    lock, next_start = threading.Lock(), [0.0]

    def fetch(event_id: str) -> tuple[str, bytes | None]:
        with lock:  # shared pacing below ComCat's 500 requests per 5 minutes
            wait = next_start[0] - time.monotonic()
            next_start[0] = max(next_start[0], time.monotonic()) + 1.0 / MAX_RATE_PER_S
        if wait > 0:
            time.sleep(wait)
        try:
            return event_id, get(event_url(event_id))
        except Exception:  # reported below; the next run retries
            return event_id, None

    missing = []
    with ThreadPoolExecutor(workers) as pool:
        for event_id, body in pool.map(fetch, todo):
            if body is None:
                missing.append(event_id)
                continue
            stored += (
                store(data_dir, history_rel(event_id), body, event_url(event_id), compress=True)
                is not None
            )
    if missing:
        print(f"no history for {len(missing)} events: {missing[:10]}")
    return stored


def origin_versions(doc: dict) -> list[dict]:
    """One row per version of each origin product in a history document."""
    rows = []
    for p in doc["properties"]["products"].get("origin", []):
        q = p.get("properties", {})

        def num(key: str, q=q) -> float | None:
            v = q.get(key)
            return float(v) if v not in (None, "") else None

        t = q.get("eventtime")
        rows.append(
            {
                "event_id": doc["id"],
                "source": p["source"],
                "code": p["code"],
                "status": p["status"],
                "update_ms": int(p["updateTime"]),
                "index_ms": int(p.get("indexTime") or p["updateTime"]),
                "weight": float(p.get("preferredWeight") or 0),
                "time_ms": int(pd.Timestamp(t).value // 1_000_000) if t else None,
                "latitude": num("latitude"),
                "longitude": num("longitude"),
                "depth": num("depth"),
                "mag": num("magnitude"),
                "magType": q.get("magnitude-type"),
                "review": q.get("review-status"),
            }
        )
    return rows


def load_versions(data_dir: Path, event_ids: Iterable[str]) -> pd.DataFrame:
    rows = []
    for event_id in event_ids:
        path = data_dir / history_rel(event_id)
        if path.exists():
            rows += origin_versions(json.loads(gzip.decompress(path.read_bytes())))
    return pd.DataFrame(rows, columns=VERSION_COLUMNS)


def as_of(versions: pd.DataFrame, t_ms: int, clock: str = "index_ms") -> pd.DataFrame:
    """Catalog visible at t_ms: one row per event with its preferred origin at that time.

    ``clock`` is the availability time of a version: ``index_ms`` (ComCat indexing) or
    ``update_ms`` (the source's own time).
    """
    v = versions[versions[clock] <= t_ms]
    v = v.sort_values(clock).groupby(["event_id", "source", "code"], sort=False).tail(1)
    v = v[(v["status"] != "DELETE") & v["mag"].notna() & v["time_ms"].notna()]
    v = v.sort_values(["weight", clock]).groupby("event_id", sort=False).tail(1)
    cols = ["event_id", "time_ms", "latitude", "longitude", "depth", "mag", "magType"]
    return v[cols].rename(columns={"event_id": "id"}).sort_values("time_ms").reset_index(drop=True)


def as_of_or_hindsight(
    versions: pd.DataFrame, hindsight: pd.DataFrame, t_ms: int
) -> tuple[pd.DataFrame, pd.Series]:
    """As-of catalog at t_ms, plus the hindsight row of every event without a history.

    Events whose history was not fetched (below a fetch floor, or a failed request) must not
    vanish: they keep their current ComCat origin. Returns (catalog, fallback mask over its
    rows) so callers can count and report the fallbacks.
    """
    have = set(versions["event_id"])
    cols = ["id", "time_ms", "latitude", "longitude", "depth", "mag", "magType"]
    extra = hindsight.loc[~hindsight["id"].isin(have) & (hindsight["time_ms"] < t_ms), cols]
    seen = as_of(versions, t_ms) if len(versions) else extra.iloc[0:0]
    out = pd.concat([seen, extra], ignore_index=True)
    fallback = pd.Series([False] * len(seen) + [True] * len(extra))
    order = out["time_ms"].argsort(kind="stable")
    return out.iloc[order].reset_index(drop=True), fallback.iloc[order].reset_index(drop=True)


OBS_MAGS = (3.0, 5.0, 6.0, 7.0)  # legacy forecast.json observations (GraphicalForecast:803-806)


def check_observations(
    data_dir: Path,
    oaf_versions: pd.DataFrame,
    catalog: pd.DataFrame,
    sequences: pd.DataFrame,
    *,
    lag_ms: int = 0,
    clock: str = "index_ms",
) -> pd.DataFrame:
    """V0: each valid OAF version's published observation counts against the same counts from
    the as-of catalog at creationTime - lag_ms and from the hindsight catalog.

    Counts use the port's own event selection (``etas.fetched_events``: forecast circle,
    after the mainshock, before the data end = window start, 1,000 largest with ties). A
    threshold is checked only where every hindsight event within 0.5 of it has a history.
    """
    from laf.etas import fetched_events
    from laf.oaf import Circle

    rows = []
    v = oaf_versions[oaf_versions["valid"] & ~oaf_versions["duplicate"].astype(bool)]
    origins = dict(zip(sequences["sequence_id"], sequences["origin_ms"], strict=True))
    ends = dict(zip(sequences["sequence_id"], sequences["catalog_end_ms"], strict=True))
    data_end = np.minimum(v["time_start_ms"], v["creation_ms"])
    v = v[data_end <= v["sequence_id"].map(ends)]  # data window inside the snapshot catalog
    for seq_id, group in v.groupby("sequence_id"):
        hind = catalog[catalog["sequence_id"] == seq_id]
        origin = int(origins[seq_id])
        versions = load_versions(data_dir, hind.loc[hind["id"] != seq_id, "id"])
        have = set(versions["event_id"])
        for r in group.to_dict("records"):
            circle = Circle(
                float(r["region_lat"]), float(r["region_lon"]), float(r["region_radius_km"])
            )
            created = int(r["creation_ms"])
            end = min(int(r["time_start_ms"]), created)
            now = as_of(versions, created - lag_ms, clock)
            _, m_now = fetched_events(now, origin, end, circle)
            _, m_hind = fetched_events(hind, origin, end, circle)
            window = hind[(hind["time_ms"] > origin) & (hind["time_ms"] < end)]
            for mag in OBS_MAGS:
                obs = r[f"obs_m{int(mag)}"]
                near = window[window["mag"] >= mag - 0.5]
                rows.append(
                    {
                        "sequence_id": seq_id,
                        "update_ms": r["update_ms"],
                        "creation_ms": created,
                        "elapsed_days": (end - origin) / DAY_MS,
                        "mag": mag,
                        "official": obs,
                        "asof": int((m_now >= mag - 0.01).sum()),
                        "hindsight": int((m_hind >= mag - 0.01).sum()),
                        "checkable": bool(obs == obs and near["id"].isin(have).all()),
                    }
                )
    return pd.DataFrame(rows)
