"""Exact-MAP search for Colombia days 1-9 with c fixed at 0.003 (one-point c grid)."""
import csv
from concurrent.futures import ProcessPoolExecutor
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pandas as pd

from laf.asof import as_of_or_hindsight, load_versions
from laf.etas import DAY_MS, GenericETAS, fetched_events, fit_legacy
from laf.oaf import parse_forecast_lenient
from laf.usgs import read_raw

D = Path("data"); P = D / "processed/20261021T1027Z"
CSV = D / "raw/reference/opensha-oaf/08a274bde278/etas/vdEGenericETASParams_080919.csv"
REG = {}
for r in csv.DictReader(CSV.open(encoding="utf-8-sig")):
    x = {k: float(v) for k, v in r.items() if k != "regionName"}
    if r["regionName"] not in ("SOR-ABVSLAB", "SCR-ABVSLAB", "CALIFORNIA"):
        REG[r["regionName"]] = GenericETAS(r["regionName"], x["a"], x["asig"], x["p"], x["covpp"], x["covcc"], x["covap"],
                                           x["covac"], x["covcp"], x["Nms"], x["b"], x["mref"], x["mmax"])
MCP = [None] + [round(3.95 + 0.1 * i, 2) for i in range(16)]


def jr(x, d):
    return float(Decimal(repr(float(x))).quantize(Decimal(10) ** -d, rounding=ROUND_HALF_UP))


def job(a):
    import numpy as np
    upd, t_days, t, m, mm, mc, b, t0, pub = a
    out = []
    for rname, g in REG.items():
        for tdm in (True, False):
            post = fit_legacy(t, m, mm, mc, b, g, t0, n=(61, 61, 61, 1), time_dep_mc=tdm, c_range=(0.003, 0.003))
            w = post.weight
            sds = []
            for k, grid in enumerate((post.ams, post.a, post.p)):
                marg = w.sum(axis=tuple(i for i in range(4) if i != k)); mu = float((marg * grid).sum())
                sds.append(float(np.sqrt((marg * (grid - mu) ** 2).sum())))
            z = [(post.map[i] - pub[i]) / sds[i] for i in range(3)]
            out.append({"update_ms": upd, "t_days": t_days, "regime": rname, "tdm": tdm, "dist": float(np.sqrt(np.sum(np.square(z)))),
                        "map": tuple(round(x, 2) for x in post.map[:3])})
    return upd, t_days, sorted(out, key=lambda r: r["dist"])


if __name__ == "__main__":
    seq = "us6000tjl2"
    ov = pd.read_parquet(P / "oaf_versions.parquet"); cat = pd.read_parquet(P / "catalog.parquet")
    s = pd.read_parquet(P / "sequences.parquet").set_index("sequence_id")
    origin = int(s.loc[seq, "origin_ms"]); hind = cat[(cat.sequence_id == seq) & (cat.id != seq)]; hist = load_versions(D, hind.id)
    jobs = []
    for r in ov[(ov.sequence_id == seq) & ov.valid & ~ov.duplicate.astype(bool)].to_dict("records"):
        f, _ = parse_forecast_lenient(read_raw(D, f"raw/oaf/{seq}/{r['update_ms']}.json"))
        p = f.model.parameters
        if float(p["c"]) != 0.003:
            continue
        t0 = (f.time_start - origin) / DAY_MS
        c, _ = as_of_or_hindsight(hist, hind, f.creationTime)
        t, m = fetched_events(c, origin, min(f.time_start, f.creationTime), f.region)
        jobs.append((r["update_ms"], t0, t, m, float(p["magMain"]), float(p["Mc"]), float(p["b"]), t0, tuple(float(p[k]) for k in ("ams", "a", "p", "c"))))
    rows = []
    with ProcessPoolExecutor(10) as pool:
        for upd, td, out in pool.map(job, jobs):
            print(f"{td:6.2f}d", [(o["regime"], o["tdm"], round(o["dist"], 2), o["map"]) for o in out[:3]])
            rows += out
    pd.DataFrame(rows).to_parquet(Path(__file__).parent / "fixed_c_dist_colombia.parquet")
