import numpy as np
import pandas as pd
import pytest

from laf import confirmatory as C


def test_holm_step_down():
    assert C.holm({"a": 0.01, "b": 0.04}) == {"a": True, "b": True}
    assert C.holm({"a": 0.03, "b": 0.04}) == {"a": False, "b": False}  # 0.03 > 0.025 stops
    assert C.holm({"a": 0.02, "b": 0.06}) == {"a": True, "b": False}


def test_noninferiority_decisions_and_p_value():
    rng = np.random.default_rng(0)
    good = rng.normal(0.0, 0.05, 80)
    r = C.noninferiority(good, 0.10)
    assert r["noninferior"] and r["p"] < 0.001
    bad = rng.normal(0.2, 0.05, 80)
    assert not C.noninferiority(bad, 0.10)["noninferior"]
    better = rng.normal(-0.1, 0.05, 80)
    assert C.noninferiority(better, 0.10)["superior"]
    # the p-value and the percentile bound agree on the decision, also for skewed effects
    for x in (good, bad, better, rng.normal(0.09, 0.1, 30), np.r_[np.zeros(17), 1.0]):
        r = C.noninferiority(x, 0.10)
        assert (r["p"] <= 0.05) == r["noninferior"]


def test_heavy_tail_moves_the_mean_not_the_median():
    x = np.r_[np.zeros(17), 1.0]
    r = C.robust(x)
    assert r["median"] == 0.0 and r["trimmed_mean"] == 0.0
    assert x.mean() == pytest.approx(1 / 18)


def test_report_corrects_only_the_co_primary_models():
    rng = np.random.default_rng(1)
    cells = pd.DataFrame({
        "model": ["A"] * 400 + ["B"] * 400 + ["C"] * 400,
        "sequence_id": [f"s{i % 80}" for i in range(1200)],
        "d": np.r_[
            rng.normal(0, 0.05, 400), rng.normal(0.02, 0.05, 400), rng.normal(0.3, 0.05, 400)
        ],
    })  # fmt: skip
    t = C.report(cells, ("A", "B")).set_index("model")
    assert t.loc["A", "holm_noninferior"] and t.loc["B", "holm_noninferior"]
    assert t.loc["C", "holm_noninferior"] is None and not t.loc["C", "noninferior"]
