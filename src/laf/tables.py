"""Build tidy benchmark tables from one raw snapshot.

Tables (one parquet each under data/processed/<snapshot>/):
  sequences           one row per sequence: mainshock, scoring circle, catalog extent
  oaf_versions        one row per OAF product version, with validation status
  forecast_bins       version x window x magnitude bin: probability, median, p95 range
  forecast_fractiles  version x window x magnitude x fractile probability: count value
  issue_times         selected issue times (docs/adr/0004-issue-times.md)
  observed_counts     issue time x window x magnitude threshold: ComCat count
  catalog             every ComCat event in the query circle, with t_days and distance
  issue_catalogs      catalog as ComCat showed it at each issue time (docs/adr/0011), or the
                      hindsight catalog (origin time < issue time) where histories are missing
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from pydantic import ValidationError

from laf.asof import as_of_or_hindsight, load_versions, origin_versions
from laf.catalog import count_in_window, haversine_km, read_comcat_csv, wells_coppersmith_radius_km
from laf.generic_rj import REFERENCE_REL, generic_rj, mag_comp
from laf.oaf import Circle, Forecast, oaf_versions, parse_forecast_lenient
from laf.registry import Sequence
from laf.splits import seal_counts, sealed
from laf.usgs import read_raw

DAY_MS = 86_400_000
TARGET_DAYS = (1, 3, 7, 14, 28)
SCORED_WINDOWS = ("1 Day", "1 Week", "1 Month")
THRESHOLDS = (3.0, 4.0, 4.5, 5.0, 6.0, 7.0)
FORESHOCK_LOOKBACK_MS = 7 * DAY_MS
FIRST_SCHEDULE_DAYS = 0.3  # median latency of the first archived international OAF (0.27-0.29 d)


@dataclass(frozen=True)
class Pick:
    target: str
    issue_ms: int


def select_issue_times(
    origin_ms: int, creations: list[int] | None, targets_days=TARGET_DAYS
) -> list[Pick]:
    """Issue times for one sequence.

    With OAF versions: the first version, plus for each target t the earliest version
    created in [origin + t, origin + t + max(1 d, t/4)). Targets that land on the same
    version are merged ("first+1d"). Without OAF: origin + 0.3 d ("first") and origin + t.
    """
    if creations is None:
        first = Pick("first", origin_ms + int(FIRST_SCHEDULE_DAYS * DAY_MS))
        return [first] + [Pick(f"{d}d", origin_ms + d * DAY_MS) for d in targets_days]
    cs = sorted(set(creations))
    picks: dict[int, list[str]] = {}
    if cs:
        picks.setdefault(cs[0], []).append("first")
    for d in targets_days:
        lo = origin_ms + d * DAY_MS
        hi = lo + max(DAY_MS, d * DAY_MS // 4)
        c = next((c for c in cs if lo <= c < hi), None)
        if c is not None:
            picks.setdefault(c, []).append(f"{d}d")
    return [Pick("+".join(v), k) for k, v in sorted(picks.items())]


def add_months(ms: int, n: int) -> int:
    """Calendar-month offset (OAF "1 Month" windows are 30 or 31 days)."""
    t = datetime.fromtimestamp(ms / 1000, UTC)
    y, m = divmod(t.month - 1 + n, 12)
    for day in (t.day, 30, 29, 28):
        try:
            return int(t.replace(year=t.year + y, month=m + 1, day=day).timestamp() * 1000)
        except ValueError:
            continue
    raise AssertionError("unreachable")


def schedule_windows(issue_ms: int) -> dict[str, tuple[int, int]]:
    return {
        "1 Day": (issue_ms, issue_ms + DAY_MS),
        "1 Week": (issue_ms, issue_ms + 7 * DAY_MS),
        "1 Month": (issue_ms, add_months(issue_ms, 1)),
    }


def _generic(ref_dir: Path, lat: float, lon: float, depth_km: float) -> dict:
    """USGS generic RJ parameters and completeness for the epicentre (docs/adr/0009)."""
    g, m = generic_rj(ref_dir, lat, lon, depth_km), mag_comp(ref_dir, lat, lon, depth_km)
    return {
        "generic_regime": g.regime,
        "generic_a_mean": g.a_mean,
        "generic_a_sigma0": g.a_sigma0,
        "generic_a_sigma1": g.a_sigma1,
        "generic_a_min": g.a_min,
        "generic_a_max": g.a_max,
        "generic_b": g.b,
        "generic_p": g.p,
        "generic_c_days": g.c,
        "magcomp_region": m.region,
        "magcomp_mcat": m.mag_cat,
        "magcomp_F": m.F,
        "magcomp_G": m.G,
        "magcomp_H": m.H,
    }


def _num(x) -> float | None:
    return float(x) if isinstance(x, float | int) else None


def _obs(f: Forecast, m: float) -> int | None:
    return next((o.count for o in f.observations if abs(o.magnitude - m) < 1e-9), None)


def build_tables(data_dir: Path, snapshot: str, seqs: list[Sequence]) -> dict[str, pd.DataFrame]:
    snap = f"raw/snapshots/{snapshot}"
    rows: dict[str, list[dict]] = {
        k: []
        for k in (
            "sequences",
            "oaf_versions",
            "forecast_bins",
            "forecast_fractiles",
            "issue_times",
            "observed_counts",
            "catalog",
            "issue_catalogs",
        )
    }
    hidden = set(sealed([s.id for s in seqs]))  # outcomes not counted (docs/adr/0013)
    for seq in seqs:
        event = json.loads(read_raw(data_dir, f"{snap}/event/{seq.id}.geojson.gz"))
        props = event["properties"]
        lon, lat, depth = event["geometry"]["coordinates"]
        origin_ms = int(props["time"])

        # Keyed by info cutoff = min(creationTime, window start): the issue time.
        forecasts: dict[int, Forecast] = {}
        for v in oaf_versions(event):
            raw = read_raw(data_dir, f"raw/oaf/{seq.id}/{v.update_time_ms}.json")
            row = {"sequence_id": seq.id, "update_ms": v.update_time_ms, "status": v.status}
            try:
                f, repaired = parse_forecast_lenient(raw)
            except ValidationError as e:
                rows["oaf_versions"].append({**row, "valid": False, "error": str(e)[:500]})
                continue
            mismatch = f.event_mismatch(lat, lon, float(props["mag"]), origin_ms)
            if mismatch:
                rows["oaf_versions"].append({**row, "valid": False, "error": mismatch})
                continue
            duplicate = f.info_cutoff_ms in forecasts
            rows["oaf_versions"].append(
                {
                    **row,
                    "valid": True,
                    "error": None,
                    "repaired_json": repaired,
                    "duplicate": duplicate,
                    "creation_ms": f.creationTime,
                    "time_start_ms": f.time_start,
                    "info_cutoff_ms": f.info_cutoff_ms,
                    "window_offset_min": (f.time_start - f.creationTime) / 60_000,
                    "late_post_hours": (v.update_time_ms - f.creationTime) / 3_600_000,
                    "model": f.model.name,
                    "mc": f.mc,
                    "sim_min_mag": f.simulated_min_mag,
                    "advisory": f.advisoryTimeFrame,
                    "region_lat": f.region.lat,
                    "region_lon": f.region.lon,
                    "region_radius_km": f.region.radius_km,
                    **{f"obs_m{m}": _obs(f, float(m)) for m in range(3, 9)},
                }
            )
            if duplicate:
                continue
            forecasts[f.info_cutoff_ms] = f
            for w in f.forecast:
                for b in w.bins:
                    key = {
                        "sequence_id": seq.id,
                        "info_cutoff_ms": f.info_cutoff_ms,
                        "window": w.label,
                        "magnitude": b.magnitude,
                    }
                    rows["forecast_bins"].append(
                        {
                            **key,
                            "time_start_ms": w.timeStart,
                            "time_end_ms": w.timeEnd,
                            "probability": b.probability,
                            "median": b.median,
                            "p95minimum": b.p95minimum,
                            "p95maximum": b.p95maximum,
                        }
                    )
                    rows["forecast_fractiles"].extend(
                        {**key, "p": p, "count": c}
                        for p, c in zip(f.fractileProbabilities, b.fractileValues, strict=True)
                    )

        if forecasts:
            latest = forecasts[max(forecasts)]
            circle, region_source = latest.region, "oaf"
        else:
            radius = wells_coppersmith_radius_km(float(props["mag"]))
            circle, region_source = Circle(lat, lon, radius), "wells-coppersmith"

        meta = json.loads(read_raw(data_dir, f"{snap}/catalog/{seq.id}.meta.json"))
        catalog_end_ms = int(meta["catalog_end_ms"])
        cat = read_comcat_csv(read_raw(data_dir, f"{snap}/catalog/{seq.id}.csv"))
        cat["sequence_id"] = seq.id
        cat["t_days"] = (cat["time_ms"] - origin_ms) / DAY_MS
        cat["dist_km"] = haversine_km(circle.lat, circle.lon, cat["latitude"], cat["longitude"])
        rows["catalog"].extend(cat.drop(columns=["time", "updated"]).to_dict("records"))
        hist = load_versions(data_dir, cat.loc[cat["id"] != seq.id, "id"])
        if len(hist):  # the mainshock's own history is in its event document
            hist = pd.concat([hist, pd.DataFrame(origin_versions(event))], ignore_index=True)

        rows["sequences"].append(
            {
                "sequence_id": seq.id,
                "name": seq.name,
                "role": seq.role,
                "origin_ms": origin_ms,
                "mag": float(props["mag"]),
                "mag_type": props["magType"],
                "lat": lat,
                "lon": lon,
                "depth_km": depth,
                "place": props["products"]["origin"][0]["properties"].get("title", props["place"]),
                "n_oaf_versions": len(forecasts),
                "region_source": region_source,
                "region_lat": circle.lat,
                "region_lon": circle.lon,
                "region_radius_km": circle.radius_km,
                "catalog_end_ms": catalog_end_ms,
                **_generic(data_dir / REFERENCE_REL, lat, lon, depth),
            }
        )

        picks = select_issue_times(origin_ms, list(forecasts) or None)
        for pick in picks:
            issue_id = f"{seq.id}@{pick.target}"
            f = forecasts.get(pick.issue_ms)
            scoring = f.region if f else circle
            mag_main = f.model.parameters.get("magMain") if f else None
            after = cat[(cat["time_ms"] > origin_ms) & (cat["time_ms"] < pick.issue_ms)]
            comcat_m5 = count_in_window(after, scoring, origin_ms + 1, pick.issue_ms, 5.0)
            covered = (
                float(
                    haversine_km(meta["center_lat"], meta["center_lon"], scoring.lat, scoring.lon)
                )
                + 1.5 * scoring.radius_km
                <= float(meta["radius_km"]) + 1e-6
            )
            rows["issue_times"].append(
                {
                    "issue_id": issue_id,
                    "sequence_id": seq.id,
                    "target": pick.target,
                    "issue_ms": pick.issue_ms,
                    "source": "oaf" if f else "schedule",
                    "creation_ms": f.creationTime if f else None,
                    "elapsed_days": (pick.issue_ms - origin_ms) / DAY_MS,
                    "region_lat": scoring.lat,
                    "region_lon": scoring.lon,
                    "region_radius_km": scoring.radius_km,
                    "mag_main": float(mag_main)
                    if isinstance(mag_main, float | int)
                    else float(props["mag"]),
                    "oaf_obs_m5": _obs(f, 5.0) if f else None,
                    "comcat_m5_at_cutoff": comcat_m5,
                    "catalog_source": "asof" if len(hist) else "hindsight",
                    "query_covers_x1_5": covered,
                    **{
                        f"oaf_{k.lower()}": _num(f.model.parameters.get(k)) if f else None
                        for k in ("Mc", "b", "ams", "a", "p", "c")
                    },
                    "oaf_sim_min_mag": f.simulated_min_mag if f else None,
                }
            )
            windows = (
                {w.label: (w.timeStart, w.timeEnd) for w in f.forecast if w.label in SCORED_WINDOWS}
                if f
                else schedule_windows(pick.issue_ms)
            )
            for label, (t0, t1) in windows.items():
                for m in THRESHOLDS:
                    rows["observed_counts"].append(
                        {
                            "issue_id": issue_id,
                            "sequence_id": seq.id,
                            "window": label,
                            "magnitude": m,
                            "time_start_ms": t0,
                            "time_end_ms": t1,
                            "count": None
                            if seq.id in hidden
                            else count_in_window(cat, scoring, t0, t1, m),
                            "closed": t1 <= catalog_end_ms,
                            "days_since_close": (catalog_end_ms - t1) / DAY_MS,
                        }
                    )
            if len(hist):
                seen, fallback = as_of_or_hindsight(hist, cat, pick.issue_ms)
                seen = seen.assign(
                    t_days=(seen["time_ms"] - origin_ms) / DAY_MS,
                    dist_km=haversine_km(
                        circle.lat, circle.lon, seen["latitude"], seen["longitude"]
                    ),
                    from_hindsight=fallback.to_numpy(),
                )
            else:
                seen = cat.assign(from_hindsight=True)
            visible = seen[
                (seen["time_ms"] < pick.issue_ms)
                & (seen["time_ms"] >= origin_ms - FORESHOCK_LOOKBACK_MS)
                & (
                    haversine_km(scoring.lat, scoring.lon, seen["latitude"], seen["longitude"])
                    <= scoring.radius_km
                )
            ]
            rows["issue_catalogs"].extend(
                {"issue_id": issue_id, **r}
                for r in visible[
                    [
                        "id",
                        "time_ms",
                        "t_days",
                        "latitude",
                        "longitude",
                        "depth",
                        "mag",
                        "magType",
                        "dist_km",
                        "from_hindsight",
                    ]
                ].to_dict("records")
            )
            # events shown to forecasters (M >= 4) that lack a history; 0 expected
            rows["issue_times"][-1]["n_hindsight_m4"] = int(
                (visible["from_hindsight"] & (visible["mag"] >= 4.0 - 1e-6)).sum()
            )
    out = {k: pd.DataFrame(v) for k, v in rows.items()}
    out["observed_counts"] = seal_counts(out["observed_counts"])
    return out


def write_tables(tables: dict[str, pd.DataFrame], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_parquet(out_dir / f"{name}.parquet", index=False)
