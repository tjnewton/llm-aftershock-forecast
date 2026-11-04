from pathlib import Path

import pandas as pd

from laf import freeze as F


def test_window_cells_never_read_the_counts():
    oc = pd.DataFrame({
        "issue_id": ["s@first"] * 4, "sequence_id": "s", "window": ["1 Day", "1 Day", "1 Week",
                                                                    "1 Week"],
        "magnitude": [4.0, 5.0, 4.0, 5.0], "count": pd.array([pd.NA] * 4, dtype="Int64"),
    })  # fmt: skip
    it = pd.DataFrame({"issue_id": ["s@first"], "source": ["oaf"], "issue_ms": [1]})
    c = F.window_cells({"observed_counts": oc, "issue_times": it})  # sealed counts are enough
    assert sorted(c["window"]) == ["1 Day", "1 Week"] and c["oaf_cell"].all()
    assert "count" not in c.columns


def test_the_manifest_hashes_every_listed_artifact():
    m = F.manifest(Path("data"), ["20261021T2300Z"], [])
    files = m["files"]
    assert {"docs/preregistration-v2.md", "prompts/v2/HASHES.json", "data/manifest.jsonl",
            "config/splits.toml", "config/sequences_confirmatory.toml",
            "config/sequences_forward_excluded.toml",
            "data/processed/20261021T2300Z/sequences.parquet"} <= set(files)  # fmt: skip
    assert "src/laf/freeze.py" in m["src_files"]
    # POSIX keys: the same manifest on Windows, the live host (ADR 0017 decision 14)
    assert not [k for k in (*m["files"], *m["src_files"]) if "\\" in k]
    assert (
        F.manifest(Path("data"), ["20261021T2300Z"], [])["manifest_sha256"] == m["manifest_sha256"]
    )


def test_the_download_inventory_comes_from_the_data_directory(tmp_path):
    proc = tmp_path / "processed/S"
    proc.mkdir(parents=True)
    (proc / "sequences.parquet").write_bytes(b"x")
    (tmp_path / "manifest.jsonl").write_text('{"path": "raw/x"}\n')
    files = F.manifest(tmp_path, ["S"], [])["files"]
    assert (tmp_path / "manifest.jsonl").as_posix() in files and "data/manifest.jsonl" not in files


def test_the_freeze_refuses_an_incomplete_etas_refit(tmp_path):
    import pytest

    proc = tmp_path / "processed/S"
    proc.mkdir(parents=True)
    pd.DataFrame({"issue_id": ["s@first", "s@first"], "sequence_id": "s",
                  "window": ["1 Day", "1 Week"], "magnitude": 5.0}).to_parquet(
        proc / "observed_counts.parquet")  # fmt: skip
    pd.DataFrame({"issue_id": ["s@first"], "source": ["oaf"], "issue_ms": [1]}).to_parquet(
        proc / "issue_times.parquet")  # fmt: skip
    pd.DataFrame({"issue_id": ["s@first"], "window": ["1 Day"]}).to_parquet(
        proc / "etas_forecasts.parquet"
    )  # the week window is missing
    with pytest.raises(SystemExit, match="lacks 1 cells"):
        F.write_frozen_inputs(tmp_path, "S")


def test_a_rebuild_matches_the_committed_file_up_to_libm_noise(tmp_path, monkeypatch):
    import json

    import pytest

    row = {"forecaster": "etas", "item_id": "s@first", "window": "1 Day", "m5": [0.0, 1.0],
           "m4": None, "p_m6": 0.0016403508771929824}  # fmt: skip
    committed = json.dumps(row, sort_keys=True) + "\n"
    noisy = json.dumps(row | {"p_m6": 0.0016403508771929828}, sort_keys=True) + "\n"
    assert F.same_jsonl(committed, noisy)  # macOS vs Windows: last bits differ
    assert not F.same_jsonl(committed, committed.replace("0.00164", "0.00165"))
    assert not F.same_jsonl(committed, committed.replace('"m4": null', '"m4": [1.0]'))
    assert not F.same_jsonl(committed, committed * 2)

    # a present file is checked, never rewritten, so the manifest hashes the committed bytes
    proc = tmp_path / "processed/S"
    proc.mkdir(parents=True)
    (proc / "etas_forecasts.parquet").write_bytes(b"")
    (proc / "baselines_m3.jsonl").write_text(committed, encoding="utf-8", newline="\n")
    (proc / "items_m3.jsonl").write_text("", encoding="utf-8")
    empty = pd.DataFrame({"issue_id": [], "window": []})
    monkeypatch.setattr(pd, "read_parquet", lambda p: empty)
    monkeypatch.setattr(F, "window_cells", lambda t: empty)
    monkeypatch.setattr(F, "baseline_rows", lambda t, i: [row | {"p_m6": 0.0016403508771929828}])
    monkeypatch.setattr("laf.pilot.load_items", lambda *a: [])
    F.write_frozen_inputs(tmp_path, "S")
    assert (proc / "baselines_m3.jsonl").read_text(encoding="utf-8") == committed
    monkeypatch.setattr(F, "baseline_rows", lambda t, i: [row | {"p_m6": 0.5}])
    with pytest.raises(SystemExit, match="differs from a fresh rebuild"):
        F.write_frozen_inputs(tmp_path, "S")
