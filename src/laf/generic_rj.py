"""Generic Reasenberg-Jones parameters and completeness, as the USGS OAF system assigns them.

Source: the USGS operational aftershock forecasting code `opensha/opensha-oaf` (CC0) at commit
08a274bd (2026-10-14), stored unmodified under data/raw/reference/opensha-oaf/08a274bde278/:
- GenericRJ_ParametersFetch.json  generic RJ parameters per tectonic regime (Page et al. 2016
  for the 15 Garcia et al. 2012 regimes; separate values for California regions)
- PageEtAlGenericParams_032116.csv  the Page et al. (2016) table, used as a cross-check
- TectonicRegimeTable.dat  Garcia regime of every 0.05-degree grid point (STREC names)
- MagCompPage_ParametersFetch.json  Page et al. (2016) time-dependent completeness per region
Lookup order follows OAFParameterSet.getRegion: special regions (first match wins), then a
world entry if present, then the Garcia table. Ported from TectonicRegimeTable.java,
SphRegionMercPolygon.java and GenericRJ_Parameters.java.
"""

import json
import math
from dataclasses import dataclass
from functools import cache
from pathlib import Path

REFERENCE_REL = Path("raw/reference/opensha-oaf/08a274bde278")
LAT_COUNT, LON_COUNT = 3601, 7201  # 0.05-degree grid, -90..90 and -180..180 inclusive

# org.opensha.commons.data.siteData.impl.TectonicRegime: STREC name -> Garcia regime name.
STREC_TO_GARCIA = {
    "ACR (deep)": "ANSR-DEEPCON",
    "ACR (hot spot)": "ANSR-HOTSPOT",
    "ACR (oceanic boundary)": "ANSR-OCEANBD",
    "ACR (shallow)": "ANSR-SHALCON",
    "ACR deep (above slab)": "ANSR-ABSLDEC",
    "ACR oceanic boundary (above slab)": "ANSR-ABSLOCB",
    "ACR shallow (above slab)": "ANSR-ABSLSHC",
    "SCR (above slab)": "SCR-ABVSLAB",
    "SCR (generic)": "SCR-GENERIC",
    "SOR (above slab)": "SOR-ABVSLAB",
    "SOR (generic)": "SOR-GENERIC",
    "SZ (generic)": "SZ-GENERIC",
    "SZ (inland/back-arc)": "SZ-INLBACK",
    "SZ (on-shore)": "SZ-ONSHORE",
    "SZ (outer-trench)": "SZ-OUTERTR",
}
STREC_NAMES = list(STREC_TO_GARCIA)  # index order of TectonicRegimeTable.java strec_name


@dataclass(frozen=True)
class GenericRJ:
    regime: str
    a_mean: float
    a_sigma: float  # magnitude-independent sigma (not used by the generic model)
    a_sigma0: float
    a_sigma1: float
    a_min: float
    a_max: float
    b: float
    p: float
    c: float  # days

    def sigma_a(self, mag_main: float) -> float:
        """Magnitude-dependent a sigma used by RJ_AftershockModel_Generic."""
        m = max(mag_main, 6.0)
        return math.sqrt(self.a_sigma0**2 + self.a_sigma1**2 / 10**m)


@dataclass(frozen=True)
class MagComp:
    region: str
    mag_cat: float
    F: float
    G: float
    H: float

    def mc(self, mag_main: float, t_days: float) -> float:
        """Page et al. (2016) completeness: max(Mcat, F*Mm - G - H*log10(t))."""
        return max(self.mag_cat, self.F * mag_main - self.G - self.H * math.log10(t_days))

    def complete_after_days(self, mag_main: float, mag: float) -> float:
        """Earliest time (days) at which the catalog is complete down to `mag`."""
        return 10 ** ((self.F * mag_main - self.G - mag) / self.H)


def _java_round(x: float) -> int:
    return math.floor(x + 0.5)


def _contains(vertices: list[dict], lat: float, lon: float) -> bool:
    """SphRegionMercPolygon.contains: equirectangular ray casting with date-line wrapping."""
    lons = [v["lon"] for v in vertices]
    wrap = max(lons) - min(lons) > 180.0
    if wrap:
        lons = [x + 360.0 if x < 0.0 else x for x in lons]
        lon = lon + 360.0 if lon < 0.0 else lon
    elif lon > 180.0:
        lon -= 360.0
    lats = [v["lat"] for v in vertices]
    inside = False
    for i in range(len(vertices)):
        x1, y1, x2, y2 = lons[i - 1], lats[i - 1], lons[i], lats[i]
        if (y1 > lat) != (y2 > lat) and lon < x1 + (lat - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def _special_region(regions: list[dict], lat: float, lon: float, depth_km: float) -> str | None:
    for r in regions:
        if r["min_depth"] <= depth_km <= r["max_depth"] and _contains(
            r["region"]["vertex_list"], lat, lon
        ):
            return r["regime"]
    return None


@cache
def _regime_table(path: Path) -> tuple[list[list[int]], list[list[int]]]:
    tokens = path.read_text(encoding="utf-8").split()
    pos = len(STREC_NAMES)
    counts = [int(t) for t in tokens[:pos]]
    if sum(counts) != LAT_COUNT * LON_COUNT:
        raise ValueError("TectonicRegimeTable: point counts do not cover the grid")
    cols, doms = [], []
    for _ in range(LAT_COUNT):
        n = int(tokens[pos])
        cols.append([int(t) for t in tokens[pos + 1 : pos + 1 + n]])
        doms.append([int(t) for t in tokens[pos + 1 + n : pos + 1 + 2 * n]])
        pos += 1 + 2 * n
    if pos != len(tokens):
        raise ValueError("TectonicRegimeTable: trailing data")
    return cols, doms


def garcia_regime(ref_dir: Path, lat: float, lon: float) -> str:
    """Garcia et al. (2012) regime of the nearest 0.05-degree grid point."""
    cols, doms = _regime_table(ref_dir / "TectonicRegimeTable.dat")
    row = min(max(_java_round((lat + 90.0) / 180.0 * (LAT_COUNT - 1)), 0), LAT_COUNT - 1)
    while lon > 180.0:
        lon -= 360.0
    while lon < -180.0:
        lon += 360.0
    col = min(max(_java_round((lon + 180.0) / 360.0 * (LON_COUNT - 1)), 0), LON_COUNT - 1)
    group = max(i for i, c in enumerate(cols[row]) if c <= col)
    return STREC_TO_GARCIA[STREC_NAMES[doms[row][group]]]


def generic_rj(ref_dir: Path, lat: float, lon: float, depth_km: float) -> GenericRJ:
    doc = json.loads((ref_dir / "GenericRJ_ParametersFetch.json").read_text(encoding="utf-8"))
    regime = _special_region(doc["regions"], lat, lon, depth_km) or garcia_regime(ref_dir, lat, lon)
    p = next(r["params"] for r in doc["regimes"] if r["regime"] == regime)
    return GenericRJ(
        regime=regime,
        a_mean=p["aValue_mean"],
        a_sigma=p["aValue_sigma"],
        a_sigma0=p["aValue_sigma0"],
        a_sigma1=p["aValue_sigma1"],
        a_min=p["aValue_min"],
        a_max=p["aValue_max"],
        b=p["bValue"],
        p=p["pValue"],
        c=p["cValue"],
    )


def mag_comp(ref_dir: Path, lat: float, lon: float, depth_km: float) -> MagComp:
    doc = json.loads((ref_dir / "MagCompPage_ParametersFetch.json").read_text(encoding="utf-8"))
    region = _special_region(doc["regions"], lat, lon, depth_km) or "WORLD"
    p = next(r["params"] for r in doc["regimes"] if r["regime"] == region)
    f = p["magCompFn"]
    return MagComp(region, p["magCat"], f["capF"], f["capG"], f["capH"])
