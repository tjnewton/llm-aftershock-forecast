from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from laf import analysis as A
from laf import splits
from laf.items import build_items
from laf.live import provisional_scores
from laf.outcome_training import outcomes
from laf.probe import truth
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
    assert not splits.is_development("us7000pllu")  # training prompt input only (ADR 0013)
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
    with pytest.raises(SystemExit, match=NEW):
        truth({"sequence_id": NEW}, pd.DataFrame())


def test_an_added_file_cannot_make_a_sequence_development(tmp_path, monkeypatch):
    for d in ("a", "cfg"):
        (tmp_path / d).mkdir()
    (tmp_path / "a" / "ak1.csv").write_text("")
    seqs = tmp_path / "cfg" / "s.toml"
    seqs.write_text('[[sequence]]\nid = "us1"\n')
    cfg = tmp_path / "cfg" / "splits.toml"
    pin = "4cd4b1a6c3eb2e26a1ee3a5cfa78ab13e2e3e7ef1ac64b1be0fd17abc68c6d5c"  # wrong on purpose
    cfg.write_text(
        f'sequence_configs = ["{seqs.as_posix()}"]\n'  # posix: "\\U" in a Windows path escapes
        f'[[id_dir]]\npath = "{(tmp_path / "a").as_posix()}"\nn = 1\nsha256 = "{pin}"\n'
    )
    with pytest.raises(SystemExit, match="inventory"):
        splits.development_ids.__wrapped__(cfg)


def test_the_gates_unseal(monkeypatch):
    monkeypatch.setattr(splits, "unsealed", lambda: True)
    assert splits.sealed([NEW]) == []
    splits.require_outcomes([NEW])


def test_outcomes_open_only_after_the_tag_and_s_plus_90_days(monkeypatch):
    day = 86_400_000
    tags: set[str] = set()
    stop: list[int | None] = [None]
    monkeypatch.setattr(splits, "_tagged", lambda t: t in tags)
    monkeypatch.setattr(splits, "stop_ms", lambda: stop[0])
    assert not splits.unsealed(now_ms=10**15)  # no prereg-v2 tag
    tags.add("prereg-v2")
    assert not splits.unsealed(now_ms=10**15)  # tagged, live arm not stopped: no interim looks
    stop[0] = 1000 * day
    assert not splits.unsealed(now_ms=1089 * day)
    assert splits.unsealed(now_ms=1090 * day)


def test_the_stop_time_is_read_from_the_tagged_commit(tmp_path, monkeypatch):
    import os
    import subprocess

    for var in [v for v in os.environ if v.startswith("GIT_")]:  # e.g. set by pre-commit hooks
        monkeypatch.delenv(var)

    def git(*a):
        subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@example.invalid")
    git("config", "user.name", "t")
    (tmp_path / "config").mkdir()
    monkeypatch.chdir(tmp_path)
    assert splits.stop_ms() is None
    (tmp_path / splits.STOP_FILE).write_text("s_ms = 1793000000000\n")
    git("add", ".")
    git("commit", "-qm", "S")
    git("tag", splits.STOP_TAG)
    (tmp_path / splits.STOP_FILE).write_text("s_ms = 1\n")  # a later edit
    git("commit", "-qam", "edit")
    assert splits.stop_ms() == 1793000000000


def test_build_tables_never_counts_a_sealed_window(locked, monkeypatch):
    from laf import tables as T
    from laf.registry import load_sequences

    seq = next(s for s in load_sequences(Path("config/sequences.toml")) if s.id == COLOMBIA)
    monkeypatch.setattr(splits, "development_ids", lambda: frozenset())
    calls = []
    real = T.count_in_window

    def spy(cat, circle, t0, t1, m):
        calls.append((t0, t1))
        return real(cat, circle, t0, t1, m)

    monkeypatch.setattr(T, "count_in_window", spy)
    t = T.build_tables(Path("data"), "20261021T1027Z", [seq])
    issue_ms = set(t["issue_times"]["issue_ms"])
    assert t["observed_counts"]["count"].isna().all()
    assert calls and all(t1 in issue_ms for _, t1 in calls)  # only pre-cutoff counts
