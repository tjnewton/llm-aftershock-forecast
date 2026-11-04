"""Descriptive outputs of prereg v2 (section 2, row D; section 4), with no test: per model on
its own clean set, the mean dS against the official forecast at M>=4 and at M>=3 (M3 only
where the catalog is complete, ADR 0015), and the Brier score of P(M>=6) for the model, the
official forecast and the pipeline baselines on the model's cells, with each one's difference
from the official forecast. Means are over sequences of per-sequence means, as the primary
estimand. Valid answers only: the invalid-answer penalty is registered at M>=5 (section 7),
and invalid rates are reported beside the tests.
"""

import pandas as pd

from laf import confirmatory as C
from laf.d2 import BASELINES

COLUMNS = ("model", "measure", "forecaster", "sequences", "cells", "mean")


def descriptive(
    samples: pd.DataFrame, sequences: pd.DataFrame, elapsed: dict[str, float],
    min_mag: dict[str, float] | None = None, sets: dict[str, set[str]] | None = None,
) -> pd.DataFrame:  # fmt: skip
    """One row per model, measure and forecaster. `samples` is `laf.d2.analyze`'s per-sample
    table; the clean sets, study efforts and prompt are `confirmatory_cells`'s (`sets` replaces
    the clean sets, as in the development dry run)."""
    ok = samples[samples["status"] == "ok"]
    # every forecaster's Brier score on the same cells: those with the model's and the official
    # forecast's P(M>=6)
    both = ok["brier_m6"].notna() & ok["brier_m6_official"].notna()
    cols = {("dS_m4", "model"): ok["d4"], ("dS_m3", "model"): ok["d3"]}
    for f in ("model", "official", *BASELINES):
        b = ok["brier_m6"] if f == "model" else ok[f"brier_m6_{f}"]
        cols[("brier_m6", f)] = b.where(both)
        if f != "official":
            cols[("brier_m6_minus_official", f)] = (b - ok["brier_m6_official"]).where(both)
    rows = []
    for (measure, f), col in cols.items():
        cells = C.confirmatory_cells(ok.assign(d5=col), sequences, elapsed, min_mag, sets=sets)
        for m, g in cells.groupby("model"):
            rows.append({"model": m, "measure": measure, "forecaster": f,
                         "sequences": g["sequence_id"].nunique(), "cells": len(g),
                         "mean": float(C.sequence_effects(g).mean())})  # fmt: skip
    out = pd.DataFrame(rows, columns=list(COLUMNS))
    # a measure without cells (M>=3 where no catalog is complete) is listed with 0 cells
    keys = list(COLUMNS[:3])
    full = pd.MultiIndex.from_tuples(
        [(m, *k) for m in sorted(set(out["model"])) for k in cols], names=keys
    )
    out = out.set_index(keys).reindex(full).reset_index()
    return out.fillna({"sequences": 0, "cells": 0}).astype({"sequences": int, "cells": int})
