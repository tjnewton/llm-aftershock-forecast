from pathlib import Path

import pandas as pd

from laf import probe

P = Path("data/processed/20261021T1027Z")


def test_render_and_truth_and_scoring_rules():
    seqs = pd.read_parquet(P / "sequences.parquet")
    s = seqs[seqs["sequence_id"] == "us6000tkt2"].iloc[0].to_dict()
    text = probe.render_probe(s)
    assert "2026-08-14" in text and "$" not in text
    t = probe.truth(s, pd.read_parquet(P / "catalog.parquet"))
    assert t["largest"] is not None and t["largest"] < s["mag"] and t["n_m5"] >= 0
    assert probe.correct_largest(6.1, 6.3) and not probe.correct_largest(6.0, 6.3)
    assert probe.correct_count(5, 10) and probe.correct_count(20, 10)
    assert not probe.correct_count(4, 10) and probe.correct_count(0, 0)
    assert not probe.correct_count(1, 0) and not probe.correct_count(None, 3)
