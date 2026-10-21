"""Summarize legacy ETAS runs under out/: MAP params, minSimMag, M>=5 median and 2.5/97.5% per window."""

import json
import re
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "out"


def last(pat, text, cast=float):
    m = re.findall(pat, text)
    return cast(m[-1]) if m else None


def summarize(run_dir):
    log = (run_dir / "run.log").read_text(errors="replace")
    meta = json.loads((run_dir / "meta.json").read_text())
    bayes = log.split("Computing Bayesian forecast", 1)[-1]
    row = {
        "run": f"{meta['issue_id']}/{run_dir.name}",
        "runtime_s": meta["runtime_s"],
        "ams": last(r"getMaxLikelihood_ams\(\)=(\S+)", log),
        "a": last(r"getMaxLikelihood_a\(\)=(\S+)", log),
        "p": last(r"getMaxLikelihood_p\(\)=(\S+)", log),
        "c": last(r"getMaxLikelihood_c\(\)=(\S+)", log),
        "Mc": last(r"Mc\(t\):\s+\S+ Mc = (\S+)", log),
        "numAS": last(r"numAS: (\d+)", log, int),
        "minSimMag": last(r"minSimMag=(\S+) Mmax=\S+ nSims=10000", bayes),
        "radius_km": last(r"Collecting Aftershocks within 10 km \+ 3 WC94 Lengths: (\S+) km", log),
    }
    js = list((run_dir / "Forecasts").rglob("*.json"))
    if js:
        fc = json.loads(js[0].read_text())
        row["json"] = str(js[0].relative_to(OUT))
        row["json_params"] = fc["model"]["parameters"]
        for w in fc["forecast"]:
            b5 = next(b for b in w["bins"] if b["magnitude"] == 5.0)
            fv = b5[
                "fractileValues"
            ]  # 0.0025..0.9975 step 0.0025 -> idx 9 = 2.5%, 199 = 50%, 389 = 97.5%
            row[w["label"]] = {
                "median": b5["median"],
                "p2.5": b5["p95minimum"],
                "p97.5": b5["p95maximum"],
                "prob": b5["probability"],
                "fv2.5/50/97.5": [fv[9], fv[199], fv[389]],
            }
    return row


if __name__ == "__main__":
    runs = sorted(p.parent for p in OUT.glob("*/*/meta.json"))
    rows = [summarize(r) for r in runs]
    json.dump(rows, sys.stdout, indent=1)
    print()
