from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from laf import analysis as A
from laf import splits
from laf.items import build_items
from laf.live import provisional_scores
from laf.outcome_training import outcomes
from laf.registry import Sequence

P = Path("data/processed/20261021T1027Z")
COLOMBIA = "us6000tjl2"
NEW = "us7000zzzz"  # in no development source


@pytest.fixture
def locked(monkeypatch):
    monkeypatch.setattr(splits, "unsealed", lambda: False)


def test_development_ids_cover_registered_e3_and_training_pool_and_nothing_else():
    assert splits.is_development(COLOMBIA)
    assert splits.is_development("us7000t0b5")  # E3
    assert splits.is_development("ak0138esnzr")  # adaptation pool
    assert not splits.is_development(NEW)


def test_cells_refuse_a_confirmatory_sequence_and_pass_development_ones(locked):
    t = A.load_tables(P)
    assert len(A.cells(t)) > 0
    oc = t["observed_counts"]
    extra = oc[oc["sequence_id"] == COLOMBIA].assign(sequence_id=NEW)
    with pytest.raises(SystemExit, match=NEW):
        A.cells({**t, "observed_counts": pd.concat([oc, extra])})


def test_sealed_counts_keep_their_windows_so_items_still_build(locked, monkeypatch):
    t = A.load_tables(P)
    monkeypatch.setattr(splits, "development_ids", lambda: frozenset())  # everything sealed
    oc = splits.seal_counts(t["observed_counts"])
    assert oc["count"].isna().all() and oc["sealed"].all()
    cols = ["issue_id", "window", "time_start_ms", "time_end_ms"]
    pd.testing.assert_frame_equal(oc[cols], t["observed_counts"][cols])
    items = build_items({**t, "observed_counts": oc})
    assert {i.item_id for i in items} == set(t["issue_times"]["issue_id"])
    with pytest.raises(SystemExit, match="sealed"):
        A.cells({**t, "observed_counts": oc})


def test_tables_built_while_sealed_are_refused_after_the_tag(monkeypatch):
    t = A.load_tables(P)
    oc = t["observed_counts"].assign(count=t["observed_counts"]["count"].astype("Int64"))
    oc.loc[oc.index[0], "count"] = pd.NA
    monkeypatch.setattr(splits, "unsealed", lambda: True)
    with pytest.raises(SystemExit, match="rebuild"):
        A.cells({**t, "observed_counts": oc})


def test_development_counts_are_untouched():
    t = A.load_tables(P)
    pd.testing.assert_frame_equal(splits.seal_counts(t["observed_counts"]), t["observed_counts"])


def test_every_other_outcome_counter_refuses_a_confirmatory_sequence(locked, tmp_path):
    cell = pd.DataFrame({"sequence_id": [NEW]})
    with pytest.raises(SystemExit, match=NEW):
        A.recount(cell, {}, {}, 1.0)
    seq = Sequence(id=NEW, name="x", role="test-post", catalog_min_mag=3.0)
    with pytest.raises(SystemExit, match=NEW):
        provisional_scores(tmp_path, "20261029T0000Z", seq, tmp_path, 0)
    with pytest.raises(SystemExit, match=NEW):
        outcomes(tmp_path, [SimpleNamespace(sequence_id=NEW, item_id="x", windows=[])])


def test_the_tag_unseals(monkeypatch):
    monkeypatch.setattr(splits, "unsealed", lambda: True)
    assert splits.sealed([NEW]) == []
    splits.require_outcomes([NEW])
