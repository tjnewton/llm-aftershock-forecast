import numpy as np
import pandas as pd
import pytest

from laf.descriptive import descriptive


def test_descriptive_means_and_brier_on_the_valid_cells():
    base = {f"brier_m6_{x}": 0.5 for x in ("generic_rj", "rj_mle", "naive", "etas")}

    def row(seq, item, d4, d3, b, b_off, status="ok", sample=0):
        return {"model": "claude-opus-4-6", "effort": "medium", "variant": "v2A",
                "sequence_id": seq, "item_id": item, "window": "day", "sample": sample,
                "status": status, "worst_base_d5": 1.0, "d5": 0.0, "d4": d4, "d3": d3,
                "brier_m6": b, "brier_m6_official": b_off, **base}  # fmt: skip

    samples = pd.DataFrame([
        row("s1", "s1@first", 0.2, np.nan, 0.1, 0.3, sample=0),
        row("s1", "s1@first", 0.4, np.nan, 0.3, 0.3, sample=1),  # k samples: the cell's mean
        row("s1", "s1@7d", 0.0, np.nan, 0.0, 0.0),
        row("s2", "s2@first", -0.6, np.nan, 0.2, 0.4),
        row("s2", "s2@1d", 9.0, 9.0, 9.0, 9.0, status="schema_invalid"),  # invalid: left out
    ])  # fmt: skip
    elapsed = {"s1@first": 0.1, "s1@7d": 7.0, "s2@first": 0.2, "s2@1d": 1.0}
    t = descriptive(samples, pd.DataFrame(), elapsed, sets={"claude-opus-4-6": {"s1", "s2"}})
    r = {(x["measure"], x["forecaster"]): x for x in t.to_dict("records")}
    # sequence means: s1 = mean(0.3, 0.0) = 0.15, s2 = -0.6; over sequences: -0.225
    m4 = r[("dS_m4", "model")]
    assert m4["mean"] == pytest.approx(-0.225) and (m4["sequences"], m4["cells"]) == (2, 3)
    m3 = r[("dS_m3", "model")]  # no complete M3 catalog: listed with 0 cells, no mean
    assert m3["cells"] == 0 and np.isnan(m3["mean"])
    # Brier: s1 = mean(0.2, 0.0) = 0.1, s2 = 0.2 -> 0.15; official s1 0.15, s2 0.4 -> 0.275
    assert r[("brier_m6", "model")]["mean"] == pytest.approx(0.15)
    assert r[("brier_m6", "official")]["mean"] == pytest.approx(0.275)
    assert r[("brier_m6_minus_official", "model")]["mean"] == pytest.approx(-0.125)
    assert r[("brier_m6_minus_official", "etas")]["mean"] == pytest.approx(0.5 - 0.275)
