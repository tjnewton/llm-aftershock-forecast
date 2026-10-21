"""Distance (posterior sd units) between published MAP and our MAP, per regime x timeDepMc."""
import csv
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
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
    if r["regionName"] in ("SOR-ABVSLAB", "SCR-ABVSLAB", "CALIFORNIA"):
        continue
    REG[r["regionName"]] = GenericETAS(r["regionName"], x["a"], x["asig"], x["p"], x["covpp"], x["covcc"], x["covap"],
                                       x["covac"], x["covcp"], x["Nms"], x["b"], x["mref"], x["mmax"])


def stats(post):
    w = post.weight
    out = []
    for k, g in enumerate((post.ams, post.a, post.p, np.log10(post.c))):
        marg = w.sum(axis=tuple(i for i in range(4) if i != k))
        mu = float(np.sum(marg * g)); sd = float(np.sqrt(np.sum(marg * (g - mu) ** 2)))
        out.append(sd)
    return out


def job(a):
    seq, upd, t_days, t, m, mm, mc, b, t0, pub = a
    rows = []
    for name, g in REG.items():
        for tdm in (True, False):
            post = fit_legacy(t, m, mm, mc, b, g, t0, n=41, time_dep_mc=tdm)
            sd = stats(post)
            mp = list(post.map); mp[3] = np.log10(mp[3])
            pb = list(pub); pb[3] = np.log10(pb[3])
            z = [(x - y) / max(s, 1e-6) for x, y, s in zip(mp, pb, sd, strict=True)]
            rows.append({"seq": seq, "update_ms": upd, "t_days": t_days, "regime": name, "tdm": tdm,
                         "dist": float(np.sqrt(np.sum(np.square(z)))), **{f"z_{k}": v for k, v in zip(("ams", "a", "p", "lc"), z, strict=True)}})
    return rows


if __name__ == "__main__":
    seqs = sys.argv[1:]
    ov = pd.read_parquet(P / "oaf_versions.parquet"); cat = pd.read_parquet(P / "catalog.parquet")
    s = pd.read_parquet(P / "sequences.parquet").set_index("sequence_id")
    jobs = []
    for seq in seqs:
        origin = int(s.loc[seq, "origin_ms"]); end_cat = int(s.loc[seq, "catalog_end_ms"])
        hind = cat[(cat.sequence_id == seq) & (cat.id != seq)]; hist = load_versions(D, hind.id)
        for r in ov[(ov.sequence_id == seq) & ov.valid & ~ov.duplicate.astype(bool)].to_dict("records"):
            f, _ = parse_forecast_lenient(read_raw(D, f"raw/oaf/{seq}/{r['update_ms']}.json"))
            end = min(f.time_start, f.creationTime)
            if end > end_cat:
                continue
            c, _ = as_of_or_hindsight(hist, hind, f.creationTime)
            t, m = fetched_events(c, origin, end, f.region)
            p = f.model.parameters
            jobs.append((seq, r["update_ms"], (f.time_start - origin) / DAY_MS, t, m, float(p["magMain"]), float(p["Mc"]),
                         float(p["b"]), (f.time_start - origin) / DAY_MS, tuple(float(p[k]) for k in ("ams", "a", "p", "c"))))
    with ProcessPoolExecutor(10) as pool:
        df = pd.DataFrame([r for out in pool.map(job, jobs) for r in out])
    df.to_parquet(Path(__file__).parent / f"regime_dist_{'_'.join(seqs)}.parquet")
    for seq, g in df.groupby("seq"):
        print("==", seq, g.update_ms.nunique(), "versions")
        agg = g.groupby(["regime", "tdm"]).dist.agg(["median", "mean"]).sort_values("median")
        print(agg.head(8).round(2).to_string())
        best = g.loc[g.groupby("update_ms").dist.idxmin()]
        print("per-version best:", best.groupby(["regime", "tdm"]).size().sort_values(ascending=False).head(6).to_dict())
