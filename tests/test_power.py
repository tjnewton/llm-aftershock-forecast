import numpy as np

from laf.power import power


def test_power_grows_with_sequences_and_margin():
    rng = np.random.default_rng(0)
    eff = rng.normal(0, 0.1, size=40)
    assert power(eff, 20, 0.02, sims=4000) < power(eff, 194, 0.02, sims=4000)
    assert power(eff, 60, 0.02, sims=4000) < power(eff, 60, 0.1, sims=4000)
    assert power(eff, 194, 0.1, sims=4000) > 0.99


def test_equivalence_fails_when_the_true_difference_exceeds_the_margin():
    eff = np.random.default_rng(1).normal(0, 0.05, size=40)
    assert power(eff, 194, 0.03, true_diff=0.06, sims=4000) < 0.01


def test_superiority_needs_a_true_advantage():
    eff = np.random.default_rng(2).normal(0, 0.05, size=40)
    assert power(eff, 100, None, true_diff=0.0, sims=4000) < 0.1
    assert power(eff, 100, None, true_diff=-0.03, sims=4000) > 0.9


def test_invalid_answers_get_the_worst_score_in_the_cell():
    from pathlib import Path

    from laf.power import cell_differences

    proc, run = Path("data/processed/20261021T2300Z"), [Path("runs/e3/e3all-olmo-3.1-32b-instruct")]
    penalized = cell_differences(proc, run)
    valid = cell_differences(proc, run, valid_only=True)
    assert len(penalized) >= len(valid)  # cells with only invalid answers stay in
    assert penalized["d"].mean() > valid["d"].mean()


def test_d2_cell_differences_label_models_and_average_samples(monkeypatch):
    from pathlib import Path

    import pandas as pd
    import pytest

    from laf import d2, power

    df = pd.DataFrame({
        "model": ["m"] * 4, "effort": ["high"] * 4, "variant": ["v2A"] * 3 + ["v2B"],
        "item_id": ["a", "a", "b", "a"], "window": ["day"] * 4, "sequence_id": ["s"] * 4,
        "status": ["ok", "ok", "ok", "ok"], "d5": [0.1, 0.3, -0.2, 1.0],
    })  # fmt: skip
    monkeypatch.setattr(d2, "analyze", lambda proc, runs: (df, None))
    cells = power.d2_cell_differences(Path("x"), [])
    got = {(r.model, r.cell): r.d for r in cells.itertuples()}
    assert got == {
        ("m high v2A", ("a", "day")): pytest.approx(0.2),
        ("m high v2A", ("b", "day")): pytest.approx(-0.2),
        ("m high v2B", ("a", "day")): pytest.approx(1.0),
    }


def test_stricter_level_lowers_power():
    import numpy as np

    from laf.power import Z90, Z95

    e = np.random.default_rng(1).normal(0.01, 0.1, 40)
    assert power(e, 60, 0.05, z=Z95) < power(e, 60, 0.05, z=Z90)
