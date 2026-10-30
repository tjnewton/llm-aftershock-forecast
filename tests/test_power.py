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
