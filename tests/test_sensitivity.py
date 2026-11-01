import numpy as np
import pandas as pd
import pytest

from laf import confirmatory as C
from laf import sensitivity as S


def test_clean_rules():
    assert C.clean_from("gpt-5.1-2025-11-13") == pd.Timestamp("2025-01-01", tz="UTC")
    assert C.clean_from("gpt-5.1-2025-11-13", "unbuffered") == pd.Timestamp("2024-10-01", tz="UTC")
    assert C.clean_from("gpt-5.1-2025-11-13", "release") == pd.Timestamp("2025-11-10", tz="UTC")
    with pytest.raises(ValueError):
        C.clean_from("gpt-5.1-2025-11-13", "other")


def test_non_overlapping_keeps_one_window_per_issue_time():
    cells = pd.DataFrame({
        "issue_id": ["s@first", "s@first", "s@first", "s@1d", "s@1d", "s@7d", "s@first+1d"],
        "window": ["day", "week", "month", "day", "week", "week", "month"],
    })  # fmt: skip
    assert S.non_overlapping(cells).tolist() == [True, True, True, True, False, True, True]


def test_exact_match_subset():
    it = pd.DataFrame({"issue_id": ["a", "b"], "oaf_obs_m5": [3, 2], "comcat_m5_at_cutoff": [3, 1]})
    assert S.exact_match({"issue_times": it}) == {"a"}


def _samples():
    rng = np.random.default_rng(0)
    rows = []
    for i in range(8):
        for target, win in (("first", "day"), ("1d", "week")):
            for st, v in (("ok", "v2A"), ("ok", "v2A"), ("max_tokens", "v2A"), ("ok", "v2B")):
                rows.append({"model": "claude-opus-5-5", "effort": "high", "variant": v,
                             "status": st, "sequence_id": f"s{i}", "item_id": f"s{i}@{target}",
                             "window": win, "sample": len(rows),
                             "d5": float(rng.normal(-0.05, 0.05)) if st == "ok" else None,
                             "worst_base_d5": 0.4})  # fmt: skip
    return pd.DataFrame(rows)


def test_one_table_with_every_variant():
    s = _samples()
    tables = {"sequences": pd.DataFrame({"sequence_id": s["sequence_id"].unique()}),
              "issue_times": pd.DataFrame({"issue_id": s["item_id"].unique(), "oaf_obs_m5": 1,
                                           "comcat_m5_at_cutoff": 1})}  # fmt: skip
    elapsed = {i: (0.5 if i.endswith("first") else 3.0) for i in s["item_id"]}
    sets = {"claude-opus-5-5": set(s["sequence_id"])}
    t = S.sensitivity(s, tables, elapsed, ("claude-opus-5-5",), samples_2d=s, sets=sets)
    got = dict(zip(t["analysis"], t["mean"], strict=True))
    assert {"main", "non-overlapping subset", "v2B", "valid answers only", "2-day settling rule",
            "as-of catalog matches the official count", "stratum: under 1 day",
            "stratum: 1 to 7 days"} <= set(got)  # fmt: skip
    assert got["valid answers only"] < got["main"]  # the penalty raised the main mean
    rates = S.invalid_rates(s).set_index("variant")
    assert rates.loc["v2A", "invalid_rate"] == pytest.approx(1 / 3)


def test_the_release_rule_skips_models_without_a_release_date(monkeypatch):
    from laf import splits

    monkeypatch.setattr(splits, "development_ids", lambda: frozenset())
    s = _samples()
    other = s.assign(model="claude-haiku-5-5")  # clean period known, release date not recorded
    both = pd.concat([s, other], ignore_index=True)
    origin = pd.Timestamp("2026-10-15", tz="UTC").value // 1_000_000
    seqs = pd.DataFrame({"sequence_id": s["sequence_id"].unique(), "origin_ms": origin,
                         "mag": 5.5})  # fmt: skip
    elapsed = {i: 0.5 for i in s["item_id"]}
    cells = C.confirmatory_cells(both, seqs, elapsed, rule="release")
    assert set(cells["model"]) == {"claude-opus-5-5"}
