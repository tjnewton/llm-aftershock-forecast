"""Outcome-aware training data and a recalibrated ETAS baseline (exploratory, after the freeze).

Every candidate is the legacy-ETAS refit forecast of a training item, transformed on the
log(x + 1) scale by a rate factor k (shift) and a spread factor s around the median. Realized
outcomes of the historical training windows (2010-2025, never a benchmark sequence) score
the candidates with the registered log-scale quantile score.
- Recalibration: the single (k, s) with the lowest mean score over all training windows
  (on the E1 training set this is the identity: the refit is already calibrated in this
  family, so no recalibrated baseline or E1c targets differ from E1).
- E1b preference pairs: per training item, the best candidate (summed over its windows) is
  chosen against up to N_PAIRS rejected ones: the untransformed ETAS forecast (unless it is
  best), then the worst-scoring candidates.
"""

import json
import math
from itertools import product

import numpy as np

from laf.catalog import read_comcat_csv
from laf.scoring import quantile_score
from laf.splits import require_outcomes
from laf.training import QKEYS, RAW

KS = (0.5, 0.7, 1.0, 1.4, 2.0)
SPREADS = (0.7, 1.0, 1.3, 1.6, 2.0)
N_PAIRS = 5  # Adaption alignment needs >= 12,000 preference rows


def transform(q: list[float], k: float, s: float) -> list[int]:
    """Quantiles scaled by k and spread by s around the median, on the log(x + 1) scale."""
    z = [math.log(x + 1.0) for x in q]
    zm = z[len(z) // 2]
    out = [max(0, round(math.exp(zm + s * (v - zm) + math.log(k)) - 1.0)) for v in z]
    return [max(out[: i + 1]) for i in range(len(out))]  # monotone


def transform_completion(comp: dict, k: float, s: float) -> dict:
    out = {}
    for key, w in comp.items():
        if key == "notes":
            continue
        q5 = transform([w["m5_count_quantiles"][q] for q in QKEYS], k, s)
        q4 = transform([w["m4_count_quantiles"][q] for q in QKEYS], k, s)
        out[key] = {
            "m5_count_quantiles": dict(zip(QKEYS, q5, strict=True)),
            "m4_count_quantiles": dict(
                zip(QKEYS, [max(a, b) for a, b in zip(q4, q5, strict=True)], strict=True)
            ),
            "p_m6_at_least_one": round(1 - (1 - w["p_m6_at_least_one"]) ** k, 4),
        }
    out["notes"] = comp.get("notes", "")
    return out


def outcomes(data_dir, items) -> dict[tuple[str, str], int]:
    """N(M>=5) in each training window from the outcome catalogs (mainshock excluded)."""
    from laf.usgs import read_raw

    items = list(items)
    require_outcomes({it.sequence_id for it in items})
    cats, out = {}, {}
    for it in items:
        if it.sequence_id not in cats:
            raw = read_raw(data_dir, f"{RAW}/outcomes/{it.sequence_id}.csv")
            c = read_comcat_csv(raw)
            cats[it.sequence_id] = c[(c["id"] != it.sequence_id) & (c["mag"] >= 5.0 - 1e-6)]
        c = cats[it.sequence_id]
        for w in it.windows:
            n = ((c["time_ms"] >= w.start_ms) & (c["time_ms"] < w.end_ms)).sum()
            out[(it.item_id, w.key)] = int(n)
    return out


def score(comp: dict, ys: dict[str, int]) -> float:
    return sum(
        quantile_score([comp[w]["m5_count_quantiles"][q] for q in QKEYS], y) for w, y in ys.items()
    )


def build(rows: list[dict], ys: dict[tuple[str, str], int]) -> tuple[dict, list[dict]]:
    """(recalibration fit, E1b preference rows) from the E1 training rows."""
    grid = list(product(KS, SPREADS))
    per_item = []
    for r in rows:
        comp = json.loads(r["completion"])
        y = {w: ys[(r["item_id"], w)] for w in ("day", "week", "month")}
        cands = {g: transform_completion(comp, *g) for g in grid}
        per_item.append((r, y, cands, {g: score(c, y) for g, c in cands.items()}))
    mean = {g: float(np.mean([s[g] for *_, s in per_item])) for g in grid}
    best = min(mean, key=mean.__getitem__)
    fit = {
        "k": best[0],
        "s": best[1],
        "mean_score": mean[best],
        "etas_mean_score": mean[(1.0, 1.0)],
    }
    dpo = []
    for r, _, cands, s in per_item:
        top = min(s, key=s.__getitem__)
        worst = sorted(s, key=s.__getitem__, reverse=True)
        rejected = ([(1.0, 1.0)] if top != (1.0, 1.0) else []) + worst
        rejected = [g for g in dict.fromkeys(rejected) if s[g] - s[top] > 1e-9][:N_PAIRS]
        for low in rejected:
            pair = {"chosen": json.dumps(cands[top]), "rejected": json.dumps(cands[low])}
            dpo.append({"item_id": r["item_id"], "prompt": r["prompt"], **pair})
    return fit, dpo
