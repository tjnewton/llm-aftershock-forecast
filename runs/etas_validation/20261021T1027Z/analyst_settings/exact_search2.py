"""Exact-MAP search over (regime, grid, timeDepMc, Mc at which prior/ranges were set)."""
import csv
import sys
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
    REG[r["regionName"]] = GenericETAS(r["regionName"], x["a"], x["asig"], x["p"], x["covpp"], x["covcc"], x["covap"],
                                       x["covac"], x["covcp"], x["Nms"], x["b"], x["mref"], x["mmax"])
GRIDS = {"g31": 31, "g41": 41, "g21": 21, "cli": (51, 31, 31, 21)}
CRANGES = {"1": (1e-5, 1.0), "0.9998": (1e-5, 0.9998), "1e-3": (1e-3, 1.0), "1e-4": (1e-4, 1.0)}
MCP = [None] + [round(3.95 + 0.1 * i, 2) for i in range(16)]


def jr(x, d):
    return float(Decimal(repr(float(x))).quantize(Decimal(10) ** -d, rounding=ROUND_HALF_UP))


def job(a):
    seq, upd, t_days, t, m, mm, mc, b, t0, pub, regimes = a
    out = []
    for rname in regimes:
        g = REG[rname]
        for gname, grid in GRIDS.items():
            for tdm in (True,):
              for cname, cr in CRANGES.items():
                for mcp in MCP:
                    post = fit_legacy(t, m, mm, mc, b, g, t0, n=grid, time_dep_mc=tdm, mc_prior=mcp, c_range=cr)
                    got = tuple(jr(x, 4 if i == 3 else 2) for i, x in enumerate(post.map))
                    k = sum(x == y for x, y in zip(got, pub, strict=True))
                    if k >= 3:
                        out.append({"seq": seq, "update_ms": upd, "t_days": t_days, "regime": rname, "grid": gname,
                                    "tdm": cname, "mc_prior": mcp, "n_match": k, "got": got, "pub": pub})
    return upd, out


if __name__ == "__main__":
    seq, lo, hi, regimes = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4].split(",")
    ov = pd.read_parquet(P / "oaf_versions.parquet"); cat = pd.read_parquet(P / "catalog.parquet")
    s = pd.read_parquet(P / "sequences.parquet").set_index("sequence_id")
    origin = int(s.loc[seq, "origin_ms"]); hind = cat[(cat.sequence_id == seq) & (cat.id != seq)]; hist = load_versions(D, hind.id)
    jobs = []
    for r in ov[(ov.sequence_id == seq) & ov.valid & ~ov.duplicate.astype(bool)].to_dict("records"):
        f, _ = parse_forecast_lenient(read_raw(D, f"raw/oaf/{seq}/{r['update_ms']}.json"))
        t0 = (f.time_start - origin) / DAY_MS
        if not lo <= t0 <= hi:
            continue
        c, _ = as_of_or_hindsight(hist, hind, f.creationTime)
        t, m = fetched_events(c, origin, min(f.time_start, f.creationTime), f.region)
        p = f.model.parameters
        jobs.append((seq, r["update_ms"], t0, t, m, float(p["magMain"]), float(p["Mc"]), float(p["b"]), t0,
                     tuple(float(p[k]) for k in ("ams", "a", "p", "c")), regimes))
    rows, nver = [], len(jobs)
    with ProcessPoolExecutor(10) as pool:
        for upd, out in pool.map(job, jobs):
            rows += out
    df = pd.DataFrame(rows)
    df.to_parquet(Path(__file__).parent / f"exact2_{seq}_{lo:g}_{hi:g}.parquet")
    ex = df[df.n_match == 4] if len(df) else df
    print(f"{seq} days {lo}-{hi}: {nver} versions; versions with an exact config: {ex.update_ms.nunique() if len(ex) else 0}")
    if len(ex):
        cfg = ex.groupby(["regime", "grid", "tdm", "mc_prior"], dropna=False).update_ms.nunique().sort_values(ascending=False)
        print(cfg.head(12).to_string())
    if len(df):
        print("3-of-4 matches per config (top):")
        print(df[df.n_match == 3].groupby(["regime", "grid", "tdm", "mc_prior"], dropna=False).update_ms.nunique().sort_values(ascending=False).head(8).to_string())
