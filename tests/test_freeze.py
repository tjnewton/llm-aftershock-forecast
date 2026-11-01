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
