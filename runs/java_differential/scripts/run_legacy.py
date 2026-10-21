"""Run the legacy ETAS command-line forecast (opensha-oaf AftershockStatsGUI_ETAS) for one issue.

usage: python3 -I run_legacy.py ISSUE_ID VARIANT RUN_TAG
  VARIANT: official_circle  -> -catalog file built from ComCat events in the official circle
           cli_default      -> program fetches ComCat itself (10 km + 3*WC94 circle at centroid)
"""

import json
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

J = Path(__file__).resolve().parent.parent
JAVA = J / "jdk/jdk-21.0.12.1+1/Contents/Home/bin/java"
JAR = J / "opensha-oaf/build/libs/AftershockGUI_ETAS-current-2026_10_20.jar"
FDSN = "https://earthquake.usgs.gov/fdsnws/event/1/query"
DAY_MS = 86400000

# issue_id: (event, forecast start ms, Mc, b, lat, lon, radius km)
ISSUES = {
    "us6000tjl2@3d": ("us6000tjl2", 1786635382364, 4.15, 1.00, 4.8869, -76.3222, 125.4),
    "us6000tkt2@7d": ("us6000tkt2", 1787424265615, 4.95, 1.08, -8.1726, 120.8153, 195.8),
    "us6000u18k@1d": ("us6000u18k", 1791733799061, 4.85, 1.00, 7.5575, -80.7130, 381.6),
    "us6000t7zp@3d": ("us6000t7zp", 1782619226446, 4.45, 1.01, 10.5686, -67.5276, 249.9),
    "us6000qw60@1d": ("us6000qw60", 1753920030370, 5.25, 1.11, 51.2758, 159.1098, 1076.8),
}


def get(params):
    url = FDSN + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=120) as r:
        return json.load(r), url


def cat_line(t_ms, lat, lon, dep, mag):
    # legacy catalog format: yyyy MM dd HH mm ss lat lon depth mag (whole seconds, UTC)
    d = datetime.fromtimestamp(t_ms // 1000, tz=UTC)
    return f"{d:%Y\t%m\t%d\t%H\t%M\t%S}\t{lat}\t{lon}\t{dep}\t{mag}"


def build_catalog(run_dir, ev, start_ms, lat, lon, rad):
    ms, ms_url = get({"eventid": ev, "format": "geojson"})
    origin = ms["properties"]["time"]
    mlon, mlat, mdep = ms["geometry"]["coordinates"]
    # mirror the legacy query: depth 0..1000 km, no eventtype/magnitude filter
    q = {
        "format": "geojson",
        "starttime": iso(origin),
        "endtime": iso(start_ms),
        "latitude": lat,
        "longitude": lon,
        "maxradiuskm": rad,
        "mindepth": "0.000",
        "maxdepth": "1000.000",
        "limit": 20000,
        "orderby": "time-asc",
    }
    fc, url = get(q)
    (run_dir / "comcat_query.json").write_text(json.dumps(fc))
    rows = []
    for f in fc["features"]:
        p, (elon, elat, edep) = f["properties"], f["geometry"]["coordinates"]
        if f["id"] == ev or p["mag"] is None or not (origin <= p["time"] < start_ms):
            continue
        rows.append(cat_line(p["time"], elat, elon, max(edep, 0.0), p["mag"]))
    trunc_origin = origin // 1000 * 1000
    days = (start_ms - trunc_origin) / DAY_MS
    text = (
        f"# Header: eventID {ev} dataEndTime {days!r}\n"
        "# Year\tMonth\tDay\tHour\tMinute\tSec\tLat\tLon\tDepth\tMagnitude\n"
        "# Main Shock:\n"
        f"# {cat_line(origin, mlat, mlon, mdep, ms['properties']['mag'])}\n"
        + "".join(r + "\n" for r in rows)
    )
    (run_dir / "catalog.txt").write_text(text)
    (run_dir / "comcat_urls.txt").write_text(ms_url + "\n" + url + "\n")
    return days, len(rows), origin


def iso(t_ms):
    return datetime.fromtimestamp(t_ms / 1000, tz=UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]


def main():
    issue, variant, tag = sys.argv[1:4]
    ev, start_ms, mc, b, lat, lon, rad = ISSUES[issue]
    run_dir = J / "out" / issue / f"{variant}_{tag}"
    run_dir.mkdir(parents=True, exist_ok=False)
    # the program writes <user.home>/Forecasts/<eventID>/<eventID>_t<dataEnd>.json but never creates the dir
    (run_dir / "Forecasts" / ev).mkdir(parents=True)
    meta = {"issue_id": issue, "variant": variant, "tag": tag, "forecast_start_ms": start_ms}
    args = []
    if variant == "official_circle" and len(sys.argv) > 4:
        # reuse a previously fetched catalog: zero ComCat requests
        src = Path(sys.argv[4])
        for f in ("catalog.txt", "comcat_query.json", "comcat_urls.txt"):
            shutil.copy(src / f, run_dir / f)
        sm = json.loads((src / "meta.json").read_text())
        origin, n = sm["origin_ms"], sm["n_catalog_events"]
        days = (start_ms - origin // 1000 * 1000) / DAY_MS
        args = ["-catalog", "catalog.txt"]
        meta.update(
            n_catalog_events=n,
            origin_ms=origin,
            origin_used_ms=origin // 1000 * 1000,
            catalog_from=str(src),
        )
    elif variant == "official_circle":
        days, n, origin = build_catalog(run_dir, ev, start_ms, lat, lon, rad)
        args = ["-catalog", "catalog.txt"]
        meta.update(n_catalog_events=n, origin_ms=origin, origin_used_ms=origin // 1000 * 1000)
    else:
        ms, _ = get({"eventid": ev, "format": "geojson"})
        origin = ms["properties"]["time"]
        days = (start_ms - origin) / DAY_MS
        meta.update(origin_ms=origin, origin_used_ms=origin)
    # legacy code maps -Mc X to floor(X/0.1)*0.1 - 0.05, so pass official+0.06 (0.05 can hit FP floor bug, 5.3/0.1=52.99..)
    mc_arg = f"{mc + 0.06:.2f}"
    cmd = [
        str(JAVA),
        "-Dapple.awt.UIElement=true",
        f"-Duser.home={run_dir}",
        "-jar",
        str(JAR),
        "-eventID",
        ev,
        "-forecastStartTime",
        repr(days),
        "-Mc",
        mc_arg,
        "-b",
        f"{b:.2f}",
        "-debug",
        "-verbose",
        *args,
    ]
    meta.update(cmd=cmd, forecast_start_days=days, mc_official=mc, mc_arg=mc_arg, b=b)
    t0 = time.time()
    with open(run_dir / "run.log", "w") as log:
        # perl alarm = portable timeout on macOS
        rc = subprocess.call(
            ["perl", "-e", "alarm shift; exec @ARGV", "1800", *cmd],
            stdout=log,
            stderr=subprocess.STDOUT,
            cwd=run_dir,
        )
    meta.update(returncode=rc, runtime_s=round(time.time() - t0, 1))
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=1))
    print(issue, variant, tag, "rc", rc, "runtime", meta["runtime_s"])


if __name__ == "__main__":
    main()
