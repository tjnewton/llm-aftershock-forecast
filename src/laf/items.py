"""Benchmark items: everything a forecaster may see at one issue time."""

from datetime import UTC, datetime
from typing import Literal

import pandas as pd
from pydantic import BaseModel

from laf.catalog import haversine_km
from laf.oaf import WindowLabel
from laf.registry import Role

CATALOG_FLOOR = 4.0
MAX_CATALOG_ROWS = 800
WINDOW_KEYS: dict[str, Literal["day", "week", "month"]] = {
    "1 Day": "day",
    "1 Week": "week",
    "1 Month": "month",
}
DAY_MS = 86_400_000


def utc(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, UTC).strftime("%Y-%m-%d %H:%M:%S")


class Mainshock(BaseModel):
    origin_ms: int
    origin_utc: str
    place: str
    lat: float
    lon: float
    depth_km: float
    mag: float
    mag_type: str


class Region(BaseModel):
    lat: float
    lon: float
    radius_km: float


class WindowSpec(BaseModel):
    key: Literal["day", "week", "month"]
    label: WindowLabel
    start_ms: int
    end_ms: int


class CatalogRow(BaseModel):
    t_days: float
    utc_time: str
    mag: float
    mag_type: str
    depth_km: float
    dist_km: float


class Item(BaseModel):
    item_id: str
    sequence_id: str
    role: Role
    issue_ms: int
    elapsed_days: float
    mainshock: Mainshock
    region: Region
    windows: list[WindowSpec]
    catalog: list[CatalogRow]
    truncated: bool
    daily_counts: list[dict] | None


def _daily_counts(rows: pd.DataFrame, floor: float = CATALOG_FLOOR) -> list[dict]:
    day = (rows["t_days"] // 1).astype(int)
    return [
        {
            "day": int(d),
            **({"m3": int((g["mag"] >= 3.0 - 1e-6).sum())} if floor < 4.0 else {}),
            "m4": int((g["mag"] >= 4.0).sum()),
            "m5": int((g["mag"] >= 5.0).sum()),
            "m6": int((g["mag"] >= 6.0).sum()),
        }
        for d, g in rows.groupby(day)
    ]


def build_items(tables: dict[str, pd.DataFrame], floor: float = CATALOG_FLOOR) -> list[Item]:
    """Items with catalog rows at or above `floor` (4.0 for the registered prompts; 3.0 for the
    v2 prompts, which also ask for M3 counts)."""
    seqs = {r["sequence_id"]: r for r in tables["sequences"].to_dict("records")}
    windows = tables["observed_counts"].drop_duplicates(["issue_id", "window"])
    cats = tables["issue_catalogs"]
    items = []
    for it in tables["issue_times"].to_dict("records"):
        s = seqs[it["sequence_id"]]
        issue_ms = int(it["issue_ms"])
        ms = Mainshock(
            origin_ms=int(s["origin_ms"]),
            origin_utc=utc(int(s["origin_ms"])),
            place=str(s["place"]),
            lat=float(s["lat"]),
            lon=float(s["lon"]),
            depth_km=float(s["depth_km"]),
            mag=float(it["mag_main"]),
            mag_type=str(s["mag_type"]),
        )
        rows = cats[(cats["issue_id"] == it["issue_id"]) & (cats["mag"] >= floor - 1e-6)]
        rows = rows[rows["time_ms"] < issue_ms].sort_values("time_ms")
        rows = rows.assign(dist=haversine_km(ms.lat, ms.lon, rows["latitude"], rows["longitude"]))
        truncated = len(rows) > MAX_CATALOG_ROWS
        shown = rows.tail(MAX_CATALOG_ROWS).to_dict("records")
        w = windows[windows["issue_id"] == it["issue_id"]].sort_values("time_end_ms")
        items.append(
            Item(
                item_id=it["issue_id"],
                sequence_id=it["sequence_id"],
                role=s["role"],
                issue_ms=issue_ms,
                elapsed_days=float(it["elapsed_days"]),
                mainshock=ms,
                region=Region(
                    lat=it["region_lat"], lon=it["region_lon"], radius_km=it["region_radius_km"]
                ),
                windows=[
                    WindowSpec(
                        key=WINDOW_KEYS[r["window"]],
                        label=r["window"],
                        start_ms=int(r["time_start_ms"]),
                        end_ms=int(r["time_end_ms"]),
                    )
                    for r in w.to_dict("records")
                ],
                catalog=[
                    CatalogRow(
                        t_days=round(r["t_days"], 4),
                        utc_time=utc(int(r["time_ms"])),
                        mag=float(r["mag"]),
                        mag_type=str(r["magType"]),
                        depth_km=round(float(r["depth"]), 1),
                        dist_km=round(float(r["dist"]), 1),
                    )
                    for r in shown
                ],
                truncated=truncated,
                daily_counts=_daily_counts(rows, floor) if truncated else None,
            )
        )
    return sorted(items, key=lambda i: i.item_id)
