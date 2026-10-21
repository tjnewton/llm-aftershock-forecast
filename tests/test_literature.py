import json

import pandas as pd
import pytest

from laf import literature as L


def _paper(pid, doi, day):
    return {"id": pid, "doi": doi, "title": pid, "dates": {"first_available": {"value": day}}}


def test_papers_dedupe_and_counts(tmp_path):
    raw = tmp_path / L.RAW
    raw.mkdir(parents=True)
    q1 = [_paper("2606.00001v2", "", "2026-06-30"), _paper("x1", "10.1/A", "2026-07-01")]
    q2 = [_paper("x2", "10.1/a", "2026-07-02")]  # same DOI as x1, other case
    (raw / "us1_q1.json").write_text(json.dumps({"papers": q1}), encoding="utf-8")
    (raw / "us1_q2.json").write_text(json.dumps({"papers": q2}), encoding="utf-8")
    screen = tmp_path / "screen.csv"
    screen.write_text(
        "sequence_id,paper_id,include\nus1,2606.00001,true\nus1,x1,true\nus1,x2,true\n"
        "us1,x9,false\n",
        encoding="utf-8",
    )
    pap = L.papers(tmp_path, screen)
    assert sorted(pap["paper_id"]) == ["2606.00001", "x1"]
    issue = pd.Timestamp("2026-07-01T12:00", tz="UTC").value // 1_000_000
    issues = pd.DataFrame({"sequence_id": ["us1"], "issue_ms": [issue]})
    row = L.exposure(pap, issues, {"us1": "One"}).iloc[0]
    assert row["n_papers"] == 2
    assert row["before_claude-5-5"] == 1  # 2026-07-01 is the first day after the cutoff month
    assert row["before_first_issue"] == 2  # a paper counts from 00:00 UTC of its day

    screen.write_text("sequence_id,paper_id,include\nus1,x9,true\n", encoding="utf-8")
    with pytest.raises(ValueError, match="x9"):
        L.papers(tmp_path, screen)
