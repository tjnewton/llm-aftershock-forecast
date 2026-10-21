"""ComCat catalog parsing, regions and window counts.

Times are epoch milliseconds UTC (matching OAF products). Windows are half-open
``[t0, t1)``. A magnitude threshold ``m`` counts events with ``mag >= m``.
"""

import io

import numpy as np
import pandas as pd

from laf.oaf import Circle

EARTH_RADIUS_KM = 6371.0
COLUMNS = ["id", "time", "latitude", "longitude", "depth", "mag", "magType", "updated", "status"]


def read_comcat_csv(raw: bytes) -> pd.DataFrame:
    """Parse a ComCat ``format=csv`` response; validates the columns we rely on."""
    df = pd.read_csv(io.BytesIO(raw), dtype={"id": str, "magType": str, "status": str})
    missing = set(COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"ComCat CSV missing columns {sorted(missing)}")
    df = df[COLUMNS].copy()
    for col in ("time", "updated"):
        df[col] = pd.to_datetime(df[col], utc=True, format="ISO8601")
    df["time_ms"] = df["time"].dt.as_unit("ms").astype("int64")
    if df["mag"].isna().any() or df["time"].isna().any():
        raise ValueError("ComCat CSV has events without magnitude or time")
    if not df["id"].is_unique:
        raise ValueError("ComCat CSV has duplicate event ids")
    return df.sort_values("time_ms", kind="stable").reset_index(drop=True)


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    h = (
        np.sin((lat2 - lat1) / 2) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(h, 0.0, 1.0)))


def wells_coppersmith_radius_km(magnitude: float) -> float:
    """1.5 x Wells & Coppersmith (1994) subsurface rupture length (all slip types), >= 10 km."""
    return round(max(10.0, 1.5 * 10 ** (-2.44 + 0.59 * magnitude)), 1)


def in_circle(cat: pd.DataFrame, circle: Circle) -> pd.Series:
    d = haversine_km(circle.lat, circle.lon, cat["latitude"], cat["longitude"])
    return pd.Series(d <= circle.radius_km, index=cat.index)


def count_in_window(cat: pd.DataFrame, circle: Circle, t0_ms: int, t1_ms: int, mag: float) -> int:
    sel = (
        (cat["time_ms"] >= t0_ms)
        & (cat["time_ms"] < t1_ms)
        & (cat["mag"] >= mag - 1e-6)
        & in_circle(cat, circle)
    )
    return int(sel.sum())
