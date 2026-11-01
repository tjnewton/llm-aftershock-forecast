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
    m = F.manifest(Path("data"), "20261021T2300Z", [])
    files = m["files"]
    assert {"docs/preregistration-v2.md", "prompts/v2/HASHES.json", "data/manifest.jsonl",
            "config/splits.toml", "config/sequences_confirmatory.toml",
            "data/processed/20261021T2300Z/sequences.parquet"} <= set(files)  # fmt: skip
    assert "src/laf/freeze.py" in m["src_files"]
    assert F.manifest(Path("data"), "20261021T2300Z", [])["manifest_sha256"] == m["manifest_sha256"]


def test_the_download_inventory_comes_from_the_data_directory(tmp_path):
    proc = tmp_path / "processed/S"
    proc.mkdir(parents=True)
    (proc / "sequences.parquet").write_bytes(b"x")
    (tmp_path / "manifest.jsonl").write_text('{"path": "raw/x"}\n')
    files = F.manifest(tmp_path, "S", [])["files"]
    assert str(tmp_path / "manifest.jsonl") in files and "data/manifest.jsonl" not in files


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
