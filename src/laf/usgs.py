"""Fetch ComCat event documents, OAF forecast versions and catalogs into data/raw.

Layout (all under ``data/``):
  raw/oaf/<event>/<updateTime-ms>.json          immutable product versions, written once
  raw/snapshots/<snap>/event/<event>.geojson.gz event document incl. superseded products
  raw/snapshots/<snap>/catalog/<event>.csv      ComCat catalog for the query circle
  manifest.jsonl                                one line per stored file

Downloads are untrusted: they are only parsed (JSON/CSV), never executed.
"""

import contextlib
import gzip
import hashlib
import http.client
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

FDSN = "https://earthquake.usgs.gov/fdsnws/event/1"
USER_AGENT = "laf-benchmark/0.1"  # no personal identifiers in requests
LICENCE = "U.S. public domain (USGS); cite ANSS Comprehensive Earthquake Catalog (ComCat)"
COMCAT_MAX_ROWS = 20_000
PAUSE_S = 0.5
RATE_WINDOW_S = 300  # ComCat rate-limit window (HTTP 429: 500 requests per 5 minutes)


def iso(ms: int) -> str:
    """FDSN time parameter. FDSN truncates to whole seconds, so callers filter in ms locally."""
    return datetime.fromtimestamp(ms / 1000, UTC).strftime("%Y-%m-%dT%H:%M:%S")


def event_url(event_id: str) -> str:
    return f"{FDSN}/query?" + urllib.parse.urlencode(
        {"eventid": event_id, "format": "geojson", "includesuperseded": "true"}
    )


def _circle_params(lat: float, lon: float, radius_km: float, t0_ms: int, t1_ms: int, mag: float):
    return {
        "starttime": iso(t0_ms),
        "endtime": iso(t1_ms),
        "latitude": f"{lat:.4f}",
        "longitude": f"{lon:.4f}",
        "maxradiuskm": f"{radius_km:.1f}",
        "minmagnitude": f"{mag:.1f}",
        "eventtype": "earthquake",
    }


def catalog_url(lat, lon, radius_km, t0_ms, t1_ms, mag) -> str:
    params = _circle_params(lat, lon, radius_km, t0_ms, t1_ms, mag)
    return f"{FDSN}/query?" + urllib.parse.urlencode(
        {**params, "format": "csv", "orderby": "time-asc"}
    )


def count_url(lat, lon, radius_km, t0_ms, t1_ms, mag) -> str:
    params = _circle_params(lat, lon, radius_km, t0_ms, t1_ms, mag)
    return f"{FDSN}/count?" + urllib.parse.urlencode(params)


def download(url: str, *, attempts: int = 4) -> bytes:
    """GET with bounded retries on transport errors and HTTP 429/5xx."""
    for i in range(attempts):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = resp.read()
            time.sleep(PAUSE_S)
            return body
        except urllib.error.HTTPError as e:
            if (e.code != 429 and e.code < 500) or i == attempts - 1:
                raise
            if e.code == 429:  # ComCat: 500 requests per 5-minute window; it asks for 5 minutes
                time.sleep(RATE_WINDOW_S)
                continue
        except (urllib.error.URLError, http.client.IncompleteRead):  # incl. truncated bodies
            if i == attempts - 1:
                raise
        time.sleep(2**i)
    raise AssertionError("unreachable")


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def store(
    data_dir: Path,
    rel: str,
    body: bytes,
    url: str,
    *,
    compress: bool = False,
    licence: str = LICENCE,
) -> dict | None:
    """Write ``body`` to data_dir/rel atomically and append a manifest entry.

    Returns None (and writes nothing) if the file already exists: raw files are immutable.
    """
    path = data_dir / rel
    if path.exists():
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = gzip.compress(body, mtime=0) if compress else body
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_bytes(payload)
    tmp.replace(path)
    entry = {
        "path": rel,
        "url": url,
        "retrieved_utc": utc_now(),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "content_sha256": hashlib.sha256(body).hexdigest(),
        "gzip": compress,
        "licence": licence,
    }
    with (data_dir / "manifest.jsonl").open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def read_raw(data_dir: Path, rel: str) -> bytes:
    body = (data_dir / rel).read_bytes()
    return gzip.decompress(body) if rel.endswith(".gz") else body


def load_manifest(data_dir: Path) -> list[dict]:
    path = data_dir / "manifest.jsonl"
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def verify_manifest(data_dir: Path) -> list[str]:
    """Problems found: missing files, hash mismatches, duplicate entries."""
    problems, seen = [], set()
    for e in load_manifest(data_dir):
        rel = e["path"]
        if rel in seen:
            problems.append(f"duplicate manifest entry {rel}")
        seen.add(rel)
        path = data_dir / rel
        if not path.exists():
            problems.append(f"missing {rel}")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != e["sha256"]:
            problems.append(f"sha256 mismatch {rel}")
    return problems


Getter = Callable[[str], bytes]

DAY_MS = 86_400_000
CATALOG_BEFORE_MS = 30 * DAY_MS  # foreshock context
CATALOG_AFTER_MS = 90 * DAY_MS  # covers the 28-day target plus a 1-month window
QUERY_RADIUS_FACTOR = 1.5  # room for region-size sensitivity analyses


def fetch_sequence(
    data_dir: Path,
    snapshot: str,
    event_id: str,
    min_mag: float,
    *,
    now_ms: int,
    get: Getter = download,
) -> list[dict]:
    """Fetch one sequence into ``snapshot``; skips files already stored (idempotent)."""
    from laf.catalog import haversine_km, wells_coppersmith_radius_km
    from laf.oaf import oaf_versions, parse_forecast_lenient

    snap = f"raw/snapshots/{snapshot}"
    stored: list[dict] = []

    def keep(entry: dict | None) -> None:
        if entry:
            stored.append(entry)

    rel = f"{snap}/event/{event_id}.geojson.gz"
    if not (data_dir / rel).exists():
        keep(store(data_dir, rel, get(event_url(event_id)), event_url(event_id), compress=True))
    event = json.loads(read_raw(data_dir, rel))
    if event.get("id") != event_id:
        raise ValueError(f"{event_id}: event document has id {event.get('id')!r}")

    lon, lat, _ = event["geometry"]["coordinates"]
    origin_ms = int(event["properties"]["time"])
    mag = float(event["properties"]["mag"])
    regions = []
    for v in oaf_versions(event):
        rel = f"raw/oaf/{event_id}/{v.update_time_ms}.json"
        if not (data_dir / rel).exists():
            keep(store(data_dir, rel, get(v.url), v.url))
        with contextlib.suppress(ValueError):  # invalid versions are recorded by `laf tables`
            f = parse_forecast_lenient(read_raw(data_dir, rel))[0]
            if f.event_mismatch(lat, lon, mag, origin_ms) is None:
                regions.append(f.region)

    # Centred on the epicentre and large enough that every scoring circle, scaled x1.5 for the
    # region sensitivity analysis, lies inside it.
    if regions:
        radius = max(r.radius_km + float(haversine_km(lat, lon, r.lat, r.lon)) for r in regions)
    else:
        radius = wells_coppersmith_radius_km(mag)
    radius *= QUERY_RADIUS_FACTOR
    t0, t1 = origin_ms - CATALOG_BEFORE_MS, min(now_ms, origin_ms + CATALOG_AFTER_MS)

    # now_ms comes from the snapshot id, so a resumed fetch rebuilds the identical query, and
    # the CSV and its meta file are each stored if missing.
    rel = f"{snap}/catalog/{event_id}.csv"
    meta_rel = f"{snap}/catalog/{event_id}.meta.json"
    if not (data_dir / rel).exists() or not (data_dir / meta_rel).exists():
        n = int(get(count_url(lat, lon, radius, t0, t1, min_mag)).strip())
        if n >= COMCAT_MAX_ROWS:
            raise ValueError(f"{event_id}: {n} events exceed the ComCat limit; split the query")
        url = catalog_url(lat, lon, radius, t0, t1, min_mag)
        if not (data_dir / rel).exists():
            keep(store(data_dir, rel, get(url), url))
        meta = {
            "event_id": event_id,
            "query_url": url,
            "expected_rows": n,
            "catalog_start_ms": t0,
            "catalog_end_ms": t1,
            "center_lat": lat,
            "center_lon": lon,
            "radius_km": radius,
            "min_mag": min_mag,
        }
        keep(
            store(
                data_dir,
                meta_rel,
                json.dumps(meta, indent=1).encode(),
                url,
            )
        )
    return stored
