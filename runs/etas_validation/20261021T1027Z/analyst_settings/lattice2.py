"""Which (regime, n, Mc used for the ranges) put a block of published values on the legacy grid?"""
import csv
import math
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import numpy as np
import pandas as pd

from laf.etas import GenericETAS, _round2, legacy_linspace, legacy_logspace
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


def jr(x, d):
    return float(Decimal(repr(float(x))).quantize(Decimal(10) ** -d, rounding=ROUND_HALF_UP))


def printed(grid, d):
    return {jr(v, d) for v in grid}


NS = (11, 15, 21, 25, 31, 41, 51, 61, 81, 101)
MCS = [round(3.95 + 0.1 * i, 2) for i in range(16)]
seq, lo_d, hi_d = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
ov = pd.read_parquet(P / "oaf_versions.parquet"); s = pd.read_parquet(P / "sequences.parquet").set_index("sequence_id")
origin = int(s.loc[seq, "origin_ms"])
vals = {"ams": set(), "a": set(), "p": set(), "c": set()}
for r in ov[(ov.sequence_id == seq) & ov.valid & ~ov.duplicate.astype(bool)].to_dict("records"):
    f, _ = parse_forecast_lenient(read_raw(D, f"raw/oaf/{seq}/{r['update_ms']}.json"))
    t = (f.time_start - origin) / 86400000
    if lo_d <= t <= hi_d:
        for k in vals:
            vals[k].add(float(f.model.parameters[k]))
print(seq, f"days {lo_d}-{hi_d}", {k: sorted(v) for k, v in vals.items()})
hits = []
for name, g in REG.items():
    sp = math.sqrt(g.covpp * g.nms)
    for n in NS:
        pg = legacy_linspace(_round2(max(0.1, g.p - 4 * sp)), _round2(g.p + 4 * sp), n)
        if vals["p"] <= printed(pg, 2):
            hits.append(("p", name, n, None))
        for mc in MCS:
            a0 = g.a + math.log10((g.mmax - g.mref) / (g.mmax - mc))
            ag = legacy_linspace(_round2(a0 - 4 * g.asig), _round2(a0 + 4 * g.asig), n)
            pa = printed(ag, 2)
            if vals["a"] <= pa:
                hits.append(("a", name, n, mc))
            if vals["ams"] <= pa:
                hits.append(("ams", name, n, mc))
for n in NS:
    for lo, hi in ((1e-5, 1.0), (1e-4, 0.1), (1e-4, 1.0), (1e-5, 0.1)):
        if vals["c"] <= printed(legacy_logspace(lo, hi, n), 4):
            hits.append(("c", f"[{lo:g},{hi:g}]", n, None))
h = pd.DataFrame(hits, columns=["param", "regime", "n", "mc_range"])
for k in ("p", "a", "ams", "c"):
    x = h[h.param == k]
    print(f"  {k}: {len(x)} configs;", x.drop(columns="param").head(14).to_dict("records"))
# joint: same regime and Mc for a and ams, any n each
ja = h[h.param == "a"][["regime", "mc_range", "n"]].rename(columns={"n": "n_a"})
jm = h[h.param == "ams"][["regime", "mc_range", "n"]].rename(columns={"n": "n_ams"})
jp = h[h.param == "p"][["regime", "n"]].rename(columns={"n": "n_p"})
j = ja.merge(jm, on=["regime", "mc_range"]).merge(jp, on="regime")
print("  joint (regime, mc_range, n_a, n_ams, n_p):", len(j)); print(j.head(30).to_string(index=False))
