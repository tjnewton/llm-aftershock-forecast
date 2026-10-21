import json
from pathlib import Path

import pytest

from laf import runner
from laf.items import Item

ITEMS = [
    Item.model_validate_json(line)
    for line in Path("data/processed/20261021T1027Z/items.jsonl").read_text("utf-8").splitlines()
]


@pytest.mark.parametrize(("block", "n"), [("core", 980), ("i0", 220), ("sonnet-low", 110)])
def test_blocks_match_the_design_table(block, n):
    reqs = runner.expand(ITEMS, block, "claude-haiku-5-5")
    assert len(reqs) == n
    assert len({r["custom_id"] for r in reqs}) == n
    assert all(len(r["custom_id"]) == 64 for r in reqs)


def test_requests_use_only_the_registered_settings():
    for r in runner.expand(ITEMS, "sonnet-low", "claude-sonnet-5-5"):
        p = r["params"]
        assert set(p) == {"model", "max_tokens", "system", "messages", "output_config"}
        assert p["max_tokens"] == 32_000
        assert p["output_config"]["effort"] == "low"
        assert p["output_config"]["format"]["type"] == "json_schema"
        assert r["meta"]["item_id"].split("@")[0] in {i.sequence_id for i in ITEMS}


def test_collect_refuses_before_scoring_is_frozen(monkeypatch):
    monkeypatch.setattr(runner, "scoring_frozen", lambda: False)
    with pytest.raises(SystemExit, match="scoring-v1"):
        runner.collect(None, "core-claude-haiku-5-5")


def test_spend_guard_refuses_before_writing_or_submitting(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "RUNS", tmp_path)
    monkeypatch.setattr(runner, "spent_usd", lambda: 194.0)
    with pytest.raises(SystemExit, match="spend guard"):
        runner.submit(None, "x", [], "S", estimate=5.0)
    assert not (tmp_path / "x").exists()


def test_spend_ignores_local_models(tmp_path):
    run = tmp_path / "core-gpt-oss-20b"
    run.mkdir()
    local = {"model": "openai/gpt-oss-20b", "usage": {"input_tokens": 9, "output_tokens": 9}}
    claude = {"model": "claude-haiku-5-5", "usage": {"input_tokens": 1e6, "output_tokens": 0}}
    (run / "results.jsonl").write_text(json.dumps(local) + "\n" + json.dumps(claude) + "\n")
    assert runner.spent_usd(tmp_path) == 0.05


def test_spend_counts_nested_run_folders(tmp_path):
    run = tmp_path / "e3" / "e3-claude-haiku-5-5"
    run.mkdir(parents=True)
    claude = {"model": "claude-haiku-5-5", "usage": {"input_tokens": 1e6, "output_tokens": 0}}
    (run / "results.jsonl").write_text(json.dumps(claude) + "\n")
    pending = tmp_path / "e3" / "e3-claude-opus-5-5"
    pending.mkdir()
    (pending / "batch.json").write_text(json.dumps({"estimate_usd": 2.0}))
    assert runner.spent_usd(tmp_path) == 2.05
