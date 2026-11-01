import json
from pathlib import Path

from laf import prospective as P
from laf import rehearsal as R
from laf.cli import snapshot_ms
from laf.registry import load_sequences

SEQ = next(s for s in load_sequences(Path("config/sequences_e3.toml")) if s.id == "us7000ti1p")


def test_the_rehearsal_runs_the_real_pipeline_with_synthetic_answers(tmp_path):
    scheduled = P.scheduled_slot
    d = R.build(Path("data"), "20261021T2300Z", SEQ, tmp_path, snapshot_ms("20261021T2300Z"))
    assert P.scheduled_slot is scheduled  # the schedule override does not leak
    names = {p.name for p in d.iterdir()}
    want = {"items.jsonl", "calls.jsonl", "spend.jsonl", "answers.seal.json", "baselines.jsonl",
            "baselines.seal.json", "receipt.json", "NOTICE.txt"}  # fmt: skip
    assert want <= names
    calls = [json.loads(x) for x in (d / "calls.jsonl").read_text().splitlines()]
    assert calls and all(R.SYNTHETIC_NOTE in c["text"] for c in calls)
    assert {c["model_requested"] for c in calls} == set(P.LIVE_MODELS)
    assert json.loads((d / "receipt.json").read_text())["synthetic"]
