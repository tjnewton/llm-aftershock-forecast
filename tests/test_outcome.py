import json
import tomllib

import pandas as pd
import pytest

from laf import outcome, splits
from laf.freeze import sha256

DAY = 86_400_000
L = 100 * DAY


def _frozen(data_dir, snap):
    """s1 (retrospective) and s2 (origin after L: the prospective part), counts sealed."""
    d = data_dir / "processed" / snap
    d.mkdir(parents=True)
    seqs = pd.DataFrame({"sequence_id": ["s1", "s2"], "origin_ms": [0, L + DAY],
                         "catalog_end_ms": [5 * DAY, L + 2 * DAY],
                         "role": "test-post"})  # fmt: skip
    its = pd.DataFrame({"issue_id": ["s1@1", "s2@1"], "sequence_id": ["s1", "s2"],
                        "region_lat": 0.0, "region_lon": 0.0,
                        "region_radius_km": 50.0})  # fmt: skip
    oc = pd.DataFrame({"issue_id": "s1@1", "sequence_id": "s1", "window": "1 Week",
                       "magnitude": [4.0, 5.0], "time_start_ms": DAY, "time_end_ms": 8 * DAY,
                       "count": pd.array([None, None], dtype="Int64"), "closed": False,
                       "days_since_close": -3.0, "sealed": True})  # fmt: skip
    tables = {
        "sequences": seqs, "issue_times": its, "observed_counts": oc,
        "issue_catalogs": pd.DataFrame({"issue_id": ["s1@1", "s2@1"], "id": ["a", "b"]}),
        "etas_forecasts": pd.DataFrame({"issue_id": ["s1@1"], "sequence_id": ["s1"], "q500": [1]}),
        "forecast_fractiles": pd.DataFrame({"sequence_id": ["s1", "s2"], "info_cutoff_ms": [1, 2]}),
        "catalog": pd.DataFrame({"sequence_id": ["s1"], "id": ["old"]}),
    }  # fmt: skip
    for name, df in tables.items():
        df.to_parquet(d / f"{name}.parquet", index=False)
    items = [{"item_id": "s1@1", "sequence_id": "s1"}, {"item_id": "s2@1", "sequence_id": "s2"}]
    (d / "items_m3.jsonl").write_text("".join(json.dumps(i) + "\n" for i in items))
    return d


def _fresh(data_dir, snap, radius_km=200.0):
    d = data_dir / "processed" / snap
    d.mkdir(parents=True)
    cat = pd.DataFrame({  # s1: an M5.2 in the week inside the circle, an M4.1 outside it
        "id": ["e1", "e2", "e3"], "sequence_id": ["s1", "s1", "s3"],
        "latitude": [0.1, 3.0, 0.0], "longitude": [0.0, 0.0, 0.0],
        "mag": [5.2, 4.1, 5.0], "time_ms": [2 * DAY, 3 * DAY, L + 9 * DAY],
    })  # fmt: skip
    tables = {
        "sequences": pd.DataFrame({"sequence_id": ["s1", "s2", "s3"],
                                   "origin_ms": [0, L + DAY, L + 5 * DAY],
                                   "catalog_end_ms": [200 * DAY] * 3, "role": "test-post"}),
        "catalog": cat,
        "forecast_fractiles": pd.DataFrame({"sequence_id": ["s1", "s2", "s3"],
                                            "info_cutoff_ms": [9, 9, 9]}),
        "oaf_versions": pd.DataFrame({"sequence_id": ["s3"], "creation_ms": [9]}),
        "issue_times": pd.DataFrame({"issue_id": ["s1@9", "s2@9", "s3@9"],
                                     "sequence_id": ["s1", "s2", "s3"], "issue_ms": 9,
                                     "region_lat": 0.0, "region_lon": 0.0,
                                     "region_radius_km": 50.0}),
        "forecast_bins": pd.DataFrame({"sequence_id": ["s3"], "info_cutoff_ms": [9]}),
    }  # fmt: skip
    for name, df in tables.items():
        df.to_parquet(d / f"{name}.parquet", index=False)
    raw = data_dir / "raw" / "snapshots" / snap / "catalog"
    raw.mkdir(parents=True)
    for sid in ("s1", "s2", "s3"):
        meta = {"center_lat": 0.0, "center_lon": 0.0, "radius_km": radius_km}
        (raw / f"{sid}.meta.json").write_text(json.dumps(meta))


def _no_manifest(tmp_path):
    m = tmp_path / "empty_manifest.json"  # a manifest that lists no snapshot
    m.write_text(json.dumps({"snapshots": [], "files": {}}))
    return m


def test_frozen_forecast_inputs_with_fresh_outcomes(tmp_path, monkeypatch):
    monkeypatch.setattr(splits, "unsealed", lambda: True)
    _frozen(tmp_path, "F")
    _fresh(tmp_path, "N")
    t, lines, _ = outcome.assemble(
        tmp_path, ["F"], "N", L, manifests=(_no_manifest(tmp_path),), unlisted=True
    )
    oc = t["observed_counts"].set_index("magnitude")
    assert list(oc["count"]) == [1, 1]  # the M4.1 is outside the issue's 50 km circle
    assert oc["closed"].all() and oc["days_since_close"].iloc[0] == 192.0
    # s2 (origin after L) belongs to the prospective part: its rows come from the fresh fetch
    assert t["sequences"]["catalog_end_ms"].tolist() == [200 * DAY] * 3
    assert t["sequences"]["sequence_id"].tolist() == ["s1", "s2", "s3"]
    # frozen issues for s1; the prospective sequences' issues (first-issue metadata) are fresh
    assert t["issue_times"]["issue_id"].tolist() == ["s1@1", "s2@9", "s3@9"]
    assert t["observed_counts"]["issue_id"].unique().tolist() == ["s1@1"]  # no cells for them
    assert t["issue_times"]["query_covers_x1_5"].tolist()[0]  # 75 km within 200 km
    assert list(t["issue_catalogs"]["issue_id"]) == ["s1@1"]
    assert list(t["etas_forecasts"]["q500"]) == [1]
    ff = t["forecast_fractiles"]  # frozen versions for s1, fresh ones for the live sequences
    assert sorted(zip(ff["sequence_id"], ff["info_cutoff_ms"], strict=True)) == [
        ("s1", 1),
        ("s2", 9),
        ("s3", 9),
    ]
    assert list(t["catalog"]["id"]) == ["e1", "e2", "e3"]
    assert [json.loads(x)["item_id"] for x in lines] == ["s1@1"]
    d = outcome.write(tmp_path, "OUT", t, lines)
    assert (d / "items.jsonl").read_text().count("\n") == 1
    with pytest.raises(SystemExit, match="written once"):
        outcome.write(tmp_path, "OUT", t, lines)


def test_counts_stay_sealed_before_the_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(splits, "unsealed", lambda: False)
    _frozen(tmp_path, "F")
    _fresh(tmp_path, "N")
    t, _, _ = outcome.assemble(
        tmp_path, ["F"], "N", None, manifests=(_no_manifest(tmp_path),), unlisted=True
    )
    assert t["observed_counts"]["count"].isna().all()
    assert t["observed_counts"]["sequence_id"].unique().tolist() == ["s1"]
    assert {"s1@1", "s2@1", "s3@9"} == set(t["issue_times"]["issue_id"])  # no L: s2 frozen
    with pytest.raises(SystemExit, match="sealed"):  # written once: never with null counts
        outcome.write(tmp_path, "OUT", t, [])
    assert not (tmp_path / "processed/OUT").exists()


def test_the_manifests_are_the_committed_ones(tmp_path, monkeypatch):
    import os
    import subprocess

    for var in [v for v in os.environ if v.startswith("GIT_")]:  # e.g. set by pre-commit hooks
        monkeypatch.delenv(var)

    def git(*a):
        subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@example.invalid")
    git("config", "user.name", "t")
    git("config", "core.autocrlf", "false")  # as in the repository: committed bytes as on disk
    monkeypatch.chdir(tmp_path)
    (tmp_path / "results").mkdir()
    (tmp_path / outcome.MANIFEST).write_text('{"manifest_sha256": "a"}\n')
    git("add", ".")
    git("commit", "-qm", "freeze")
    with pytest.raises(SystemExit, match="committed at prereg-v2"):  # no tag yet
        outcome.check_committed()
    git("tag", "-a", "prereg-v2", "-m", "freeze")
    outcome.check_committed()
    (tmp_path / outcome.SUPPLEMENTARY_MANIFEST).write_text("{}\n")  # taken at L, not committed
    with pytest.raises(SystemExit, match="committed at HEAD"):
        outcome.check_committed()
    git("add", ".")
    git("commit", "-qm", "supplementary")
    outcome.check_committed()
    (tmp_path / outcome.MANIFEST).write_text('{"manifest_sha256": "b"}\n')  # rewritten later
    git("commit", "-qam", "rewrite")
    with pytest.raises(SystemExit, match="committed at prereg-v2"):
        outcome.check_committed()


def test_refusals(tmp_path):
    f = _frozen(tmp_path, "F")
    _fresh(tmp_path, "N", radius_km=40.0)
    with pytest.raises(SystemExit, match="misses issues s1@1"):
        outcome.assemble(
            tmp_path, ["F"], "N", L, manifests=(_no_manifest(tmp_path),), unlisted=True
        )
    with pytest.raises(SystemExit, match="no freeze manifest"):
        outcome.assemble(tmp_path, ["F"], "N", L, manifests=(tmp_path / "absent.json",))
    m = tmp_path / "manifest.json"
    files = {f"data/processed/F/{p.name}": sha256(p) for p in f.iterdir()}
    m.write_text(json.dumps({"snapshots": ["F"], "files": files}))
    (f / "items_m3.jsonl").write_text((f / "items_m3.jsonl").read_text() + "\n")
    with pytest.raises(SystemExit, match=r"items_m3\.jsonl: differs from"):
        outcome.assemble(tmp_path, ["F"], "N", L, manifests=(m,))


def test_config_adds_live_sequences(tmp_path):
    c = tmp_path / "a.toml"
    c.write_text('[[sequence]]\nid = "s1"\nname = "one \\"A\\""\nrole = "test-post"\n'
                 "catalog_min_mag = 3.0\n")  # fmt: skip
    issue = tmp_path / "live" / "s9" / "1700"
    issue.mkdir(parents=True)
    items = [{"sequence_id": "s9"}, {"sequence_id": "s1"}, {"sequence_id": "s9b"}]
    (issue / "items.jsonl").write_text("".join(json.dumps(i) + "\n" for i in items))
    for sid, tier in (("s7", "primary"), ("s8", None)):  # included but never issued; not included
        (tmp_path / "live" / sid).mkdir()
        (tmp_path / "live" / sid / "inclusion.json").write_text(json.dumps({"tier": tier}))
    out = tmp_path / "out.toml"
    assert outcome.config([c], tmp_path / "live", out) == 4
    seqs = tomllib.loads(out.read_text())["sequence"]
    assert [s["id"] for s in seqs] == ["s1", "s9", "s9b", "s7"]
    assert seqs[0]["name"] == 'one "A"' and seqs[1]["catalog_min_mag"] == 3.0


def test_coverage_flag_follows_the_fresh_query_circle(tmp_path):
    _frozen(tmp_path, "F")
    _fresh(tmp_path, "N", radius_km=60.0)  # holds the 50 km circle, not 1.5 times it
    t, _, _ = outcome.assemble(
        tmp_path, ["F"], "N", L, manifests=(_no_manifest(tmp_path),), unlisted=True
    )
    assert not t["issue_times"]["query_covers_x1_5"].tolist()[0]


def test_each_frozen_snapshot_must_be_in_a_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(splits, "unsealed", lambda: False)
    f = _frozen(tmp_path, "F")
    _fresh(tmp_path, "N")
    with pytest.raises(SystemExit, match="F: in no manifest"):
        outcome.assemble(tmp_path, ["F"], "N", L, manifests=(_no_manifest(tmp_path),))
    supp = tmp_path / "supplementary_manifest.json"  # the snapshot at L, hashed when taken
    files = {f"data/processed/F/{p.name}": sha256(p) for p in f.iterdir()}
    supp.write_text(json.dumps({"snapshots": ["F"], "files": files}))
    _, _, notes = outcome.assemble(
        tmp_path, ["F"], "N", L, manifests=(_no_manifest(tmp_path), supp)
    )
    assert notes[0] == f"F: matches {supp}"
