"""Parse and validate USGS operational aftershock forecast (OAF) products.

A forecast.json holds four windows ("1 Day" .. "1 Year"); each window holds
magnitude bins (M>=3 .. M>=7 or 8) with the full predictive count distribution
as fractile values at ``fractileProbabilities``. Times are epoch milliseconds UTC.
"""

import math
import re
from dataclasses import dataclass
from itertools import pairwise
from typing import Literal, Self

import numpy as np
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

WindowLabel = Literal["1 Day", "1 Week", "1 Month", "1 Year"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class Observation(_Strict):
    magnitude: float
    count: int


class Model(_Strict):
    name: str
    parameters: dict[str, float | str]


class Bin(_Strict):
    magnitude: float
    probability: float
    median: int
    p95minimum: int
    p95maximum: int
    fractileValues: list[int]

    @model_validator(mode="after")
    def _check(self) -> Self:
        v = self.fractileValues
        if not 0.0 <= self.probability <= 1.0:
            raise ValueError(f"M{self.magnitude}: probability {self.probability} outside [0, 1]")
        if v and v[0] < 0:
            raise ValueError(f"M{self.magnitude}: negative count")
        if any(a > b for a, b in pairwise(v)):
            raise ValueError(f"M{self.magnitude}: fractile values not non-decreasing")
        if not self.p95minimum <= self.median <= self.p95maximum:
            raise ValueError(f"M{self.magnitude}: median outside its 95% range")
        return self


class Window(_Strict):
    label: WindowLabel
    timeStart: int
    timeEnd: int
    bins: list[Bin]

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.timeStart >= self.timeEnd:
            raise ValueError(f"{self.label}: timeStart >= timeEnd")
        mags = [b.magnitude for b in self.bins]
        if mags != sorted(set(mags)):
            raise ValueError(f"{self.label}: magnitude bins not strictly increasing")
        # Counts above a higher threshold can never exceed counts above a lower one.
        for lo, hi in pairwise(self.bins):
            if any(h > lw for lw, h in zip(lo.fractileValues, hi.fractileValues, strict=True)):
                raise ValueError(f"{self.label}: M{hi.magnitude} fractiles exceed M{lo.magnitude}")
        return self

    def bin(self, magnitude: float) -> Bin:
        for b in self.bins:
            if abs(b.magnitude - magnitude) < 1e-9:
                return b
        raise KeyError(f"{self.label}: no M>={magnitude} bin")


@dataclass(frozen=True)
class Circle:
    lat: float
    lon: float
    radius_km: float


class Forecast(_Strict):
    creationTime: int
    expireTime: int
    advisoryTimeFrame: str
    template: str
    observations: list[Observation]
    model: Model
    fractileProbabilities: list[float]
    forecast: list[Window]

    @model_validator(mode="after")
    def _check(self) -> Self:
        p = self.fractileProbabilities
        if not p or p[0] <= 0.0 or p[-1] >= 1.0:
            raise ValueError("fractile probabilities must lie in (0, 1)")
        if any(a >= b for a, b in pairwise(p)):
            raise ValueError("fractile probabilities not strictly increasing")
        if len({w.timeStart for w in self.forecast}) != 1:
            raise ValueError("windows do not share one timeStart")
        for w in self.forecast:
            for b in w.bins:
                if len(b.fractileValues) != len(p):
                    raise ValueError(f"{w.label} M{b.magnitude}: fractile length mismatch")
        params = self.model.parameters
        if params.get("regionType") != "circle":
            raise ValueError(f"unsupported regionType {params.get('regionType')!r}")
        for key in ("regionCenterLat", "regionCenterLon", "regionRadius"):
            if not isinstance(params.get(key), float | int):
                raise ValueError(f"missing numeric region parameter {key}")
        if not isinstance(params.get("Mc", params.get("Mcat")), float | int):
            raise ValueError("missing completeness magnitude (Mc or Mcat)")
        return self

    def window(self, label: WindowLabel) -> Window:
        for w in self.forecast:
            if w.label == label:
                return w
        raise KeyError(label)

    @property
    def region(self) -> Circle:
        p = self.model.parameters
        return Circle(
            float(p["regionCenterLat"]), float(p["regionCenterLon"]), float(p["regionRadius"])
        )

    @property
    def mc(self) -> float:
        """Completeness magnitude used by the model (ETAS ``Mc``, RJ ``Mcat``)."""
        return float(self.model.parameters.get("Mc", self.model.parameters.get("Mcat", 0.0)))

    @property
    def time_start(self) -> int:
        return self.forecast[0].timeStart

    @property
    def info_cutoff_ms(self) -> int:
        """Latest time whose events an LLM may see for this forecast.

        Many international versions have windows that start hours (Kamchatka: days) before
        creationTime, so creationTime alone would leak events inside the window.
        """
        return min(self.creationTime, self.time_start)

    @property
    def simulated_min_mag(self) -> float | None:
        """Minimum simulated magnitude of a legacy-ETAS forecast, when above its lowest bin.

        Below that minimum the legacy code reports 10^(b (minMag - M)) times an integer fractile
        count (docs/research/legacy-etas-formulas.md), so every large fractile of the lowest bin
        lies on that lattice. Kamchatka's 2025 products reveal 5.8 (docs/adr/0010 section 3.5).
        None when the lowest bin is unscaled or the model is not the legacy ETAS.
        """
        p = self.model.parameters
        b, mag_main = p.get("b"), p.get("magMain")
        if not self.model.name.startswith("Epidemic-Type") or not (
            isinstance(b, float | int) and isinstance(mag_main, float | int)
        ):
            return None
        m0 = min(bn.magnitude for w in self.forecast for bn in w.bins)
        values = np.array(
            [
                v
                for w in self.forecast
                for bn in w.bins
                if bn.magnitude == m0
                for v in bn.fractileValues
            ],
            float,
        )
        # Largest candidate first: a lattice for minMag is also one for every lower candidate.
        for k in range(round(mag_main * 100) - 1, round(m0 * 100), -1):
            s = 10.0 ** (b * (k / 100 - m0))
            # Any integer lies within s/2 of the lattice, so a random value passes with chance
            # 1.02/s: only s well above 1 discriminates. The count keeps a chance pass below
            # 1e-6 (and below 0.5^20 for the doubled lattice just above the true minMag). n >= 5
            # keeps clear of Poisson-interpolated small counts.
            if s < 1.5:
                break
            need = max(20, math.ceil(math.log(1e-6) / math.log(1.02 / s)))
            v = np.unique(values[values >= 5 * s])
            if v.size >= need and np.all(np.abs(s * np.round(v / s) - v) <= 0.51):
                return k / 100
        return None

    def event_mismatch(self, lat: float, lon: float, mag: float, origin_ms: int) -> str | None:
        """Why this forecast is not for the given mainshock, or None if it is.

        Some first versions carry another event's forecast.json (Kamchatka's first product
        is a Myanmar forecast created two days before the Kamchatka mainshock).
        """
        from laf.catalog import haversine_km

        if self.creationTime <= origin_ms:
            return "created before the mainshock"
        mag_main = self.model.parameters.get("magMain")
        # > 0.25: a forecast anchored on another event (Venezuela v1-v6 used the M7.2 foreshock
        # 33 s before the M7.5); genuine magnitude revisions in the benchmark are <= 0.1.
        if isinstance(mag_main, float | int) and abs(mag_main - mag) > 0.25:
            return f"magMain {mag_main} vs event magnitude {mag}"
        r = self.region
        offset = float(haversine_km(r.lat, r.lon, lat, lon))
        if offset > max(50.0, 0.5 * r.radius_km):
            return f"region centre {offset:.0f} km from the epicentre"
        return None


_TRAILING_COMMA = re.compile(rb",(\s*[\]}])")


def parse_forecast(raw: bytes) -> Forecast:
    return Forecast.model_validate_json(raw)


def parse_forecast_lenient(raw: bytes) -> tuple[Forecast, bool]:
    """Parse, repairing trailing commas (two 2025 Kamchatka versions have ``},],``).

    Returns (forecast, repaired). Only that one syntax repair is attempted.
    """
    try:
        return parse_forecast(raw), False
    except ValidationError as e:
        if not any(err["type"] == "json_invalid" for err in e.errors()):
            raise
    return parse_forecast(_TRAILING_COMMA.sub(rb"\1", raw)), True


@dataclass(frozen=True)
class Version:
    event_id: str
    source: str
    update_time_ms: int
    status: str
    url: str


def oaf_versions(event_doc: dict) -> list[Version]:
    """All OAF product versions in a ComCat event document, oldest first.

    ``event_doc`` must come from a query with ``includesuperseded=true``.
    """
    event_id = event_doc["id"]
    versions = [
        Version(
            event_id=event_id,
            source=p["source"],
            update_time_ms=int(p["updateTime"]),
            status=p["status"],
            url=p["contents"]["forecast.json"]["url"],
        )
        for p in event_doc["properties"]["products"].get("oaf", [])
        if "forecast.json" in p.get("contents", {})
    ]
    return sorted(versions, key=lambda v: v.update_time_ms)
