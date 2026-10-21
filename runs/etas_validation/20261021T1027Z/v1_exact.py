"""V1: does the refit MAP equal the published MAP (all four values after %3.2f/%5.4f)? ADR 0010 section 4."""

import csv
from concurrent.futures import ProcessPoolExecutor
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pandas as pd

from laf.asof import as_of_or_hindsight, load_versions
from laf.etas import DAY_MS, fetched_events, fit_legacy, generic_etas
from laf.generic_rj import REFERENCE_REL
from laf.oaf import parse_forecast_lenient
from laf.usgs import read_raw

D = Path("data")
P = D / "processed/20261021T1027Z"
REF = D / REFERENCE_REL
GUI = [(None, 31, True)]  # code regime, 31-point grids, timeDepMc
SIX = [(None, n, True) for n in (21, 31, 41, (51, 31, 31, 21), (41, 41, 41, 21), (41, 41, 41, 31))]
REGIMES = [
    r["regionName"]
    for r in csv.DictReader(
        (REF / "etas/vdEGenericETASParams_080919.csv").open(encoding="utf-8-sig")
    )
]
ALL = [
    (g, n, tdm) for g in REGIMES for n in (21, 31, 41, (51, 31, 31, 21)) for tdm in (True, False)
]


def jr(x, d):
    return float(Decimal(repr(float(x))).quantize(Decimal(10) ** -d, rounding=ROUND_HALF_UP))


def job(a):
    t, m, mm, mc, b, lat, lon, t0, pub, configs = a
    out = []
    for regime, n, tdm in configs:
        post = fit_legacy(
            t, m, mm, mc, b, generic_etas(REF, lat, lon, regime=regime), t0, n=n, time_dep_mc=tdm
        )
        out.append(tuple(jr(x, 4 if i == 3 else 2) for i, x in enumerate(post.map)) == pub)
    return out


def exact(seq, configs, catalog="asof"):
    """Versions reproduced exactly, per configuration."""
    ov = pd.read_parquet(P / "oaf_versions.parquet")
    cat = pd.read_parquet(P / "catalog.parquet")
    origin = int(
        pd.read_parquet(P / "sequences.parquet").set_index("sequence_id").loc[seq, "origin_ms"]
    )
    hind = cat[(cat.sequence_id == seq) & (cat.id != seq)]
    hist = load_versions(D, hind.id) if catalog == "asof" else None
    jobs = []
    for r in ov[(ov.sequence_id == seq) & ov.valid & ~ov.duplicate.astype(bool)].to_dict("records"):
        f, _ = parse_forecast_lenient(read_raw(D, f"raw/oaf/{seq}/{r['update_ms']}.json"))
        p = f.model.parameters
        c = as_of_or_hindsight(hist, hind, f.creationTime)[0] if hist is not None else hind
        t, m = fetched_events(c, origin, min(f.time_start, f.creationTime), f.region)
        jobs.append(
            (
                t,
                m,
                float(p["magMain"]),
                float(p["Mc"]),
                float(p["b"]),
                f.region.lat,
                f.region.lon,
                (f.time_start - origin) / DAY_MS,
                tuple(float(p[k]) for k in ("ams", "a", "p", "c")),
                configs,
            )
        )
    with ProcessPoolExecutor(10) as pool:
        res = list(pool.map(job, jobs))
    return len(jobs), [sum(r[i] for r in res) for i in range(len(configs))]


if __name__ == "__main__":
    for seq in ("us6000u18k", "us6000tkt2", "us6000tjl2", "us6000t7zp"):
        n, k = exact(seq, GUI)
        print(f"{seq} GUI defaults, as-of: {k[0]}/{n}")
    n, k = exact("us6000u18k", GUI, catalog="hindsight")
    print(f"us6000u18k GUI defaults, hindsight: {k[0]}/{n}")
    n, k = exact("us6000qw60", SIX)
    print(f"us6000qw60 six grids, as-of: {dict(zip([c[1] for c in SIX], k))} of {n}; max {max(k)}")
    n, k = exact("us6000u18k", ALL)
    other = {
        c: x for c, x in zip(ALL, k) if x and c != ("SZ-GENERIC", 31, True)
    }  # Panama: SZ-GENERIC
    print(
        f"us6000u18k {len(ALL)} regime x grid x timeDepMc combinations; others with an exact version: {other}"
    )
