import json
from pathlib import Path

import pandas as pd
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


CAP = "LAF_CLAUDE_MONTHLY_CAP_USD"
HAIKU_1M_IN = {"model": "claude-haiku-5-5", "usage": {"input_tokens": 1e6, "output_tokens": 0}}


def _batch(run: Path, created: str, estimate: float = 0.0, results: list | None = None) -> None:
    run.mkdir(parents=True)
    (run / "batch.json").write_text(json.dumps({"created_at": created, "estimate_usd": estimate}))
    if results is not None:
        (run / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in results))


def test_spend_guard_refuses_before_writing_or_submitting(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "RUNS", tmp_path)
    monkeypatch.setenv(CAP, "10")
    monkeypatch.setattr(runner, "month_spend_usd", lambda month, runs=tmp_path: 9.0)
    with pytest.raises(SystemExit, match="spend guard"):
        runner.submit(None, "x", [], "S", estimate=1.5)
    assert not (tmp_path / "x").exists()


def test_spend_ignores_local_models(tmp_path):
    local = {"model": "openai/gpt-oss-20b", "usage": {"input_tokens": 9, "output_tokens": 9}}
    run = tmp_path / "core-gpt-oss-20b"
    run.mkdir()
    (run / "results.jsonl").write_text(json.dumps(local) + "\n")  # no batch.json: free
    _batch(tmp_path / "core-claude-haiku-5-5", "2026-10-21 12:00:00+00:00", 0.0, [HAIKU_1M_IN])
    assert runner.spent_usd(tmp_path) == 0.05


def test_spend_counts_nested_run_folders(tmp_path):
    _batch(tmp_path / "e3" / "e3-claude-haiku-5-5", "2026-10-21 12:00:00+00:00", 9.0, [HAIKU_1M_IN])
    _batch(tmp_path / "e3" / "e3-claude-opus-5-5", "2026-10-21 13:00:00+00:00", 2.0)  # pending
    assert runner.spent_usd(tmp_path) == 2.05


def test_month_spend_dates_calls_results_and_pending_batches(tmp_path):
    _batch(tmp_path / "a", "2026-10-21 12:00:00+00:00", 9.0, [HAIKU_1M_IN])  # 0.05 in Oct
    _batch(tmp_path / "b", "2026-11-02 08:00:00+00:00", 3.0)  # pending: estimate in Nov
    calls = tmp_path / "live" / "calls.jsonl"
    calls.parent.mkdir()
    rec = {"model_requested": "claude-haiku-5-5", "usage": {"input_tokens": 1e6}}
    calls.write_text(
        json.dumps({**rec, "started_utc": "2026-10-31T23:59:59.0Z"})
        + "\n"
        + json.dumps({**rec, "started_utc": "2026-11-01T00:00:00.0Z"})
        + "\n"
    )
    assert runner.month_spend_usd("2026-10", tmp_path) == pytest.approx(0.15)
    assert runner.month_spend_usd("2026-11", tmp_path) == pytest.approx(3.10)
    assert runner.spent_usd(tmp_path) == pytest.approx(3.25)


def test_priced_results_without_a_batch_record_are_refused(tmp_path):
    run = tmp_path / "x"
    run.mkdir()
    (run / "results.jsonl").write_text(json.dumps(HAIKU_1M_IN) + "\n")
    with pytest.raises(SystemExit, match=r"batch\.json"):
        runner.spent_usd(tmp_path)


def test_check_budget_against_the_monthly_cap(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "month_spend_usd", lambda month, runs: 8.0)
    monkeypatch.setenv(CAP, "10")
    assert runner.check_budget(2.0, tmp_path) == 8.0  # at the cap: allowed
    with pytest.raises(SystemExit, match="spend guard"):
        runner.check_budget(2.01, tmp_path)
    for bad in ("nan", "inf", "-1"):
        monkeypatch.setenv(CAP, bad)
        with pytest.raises(SystemExit, match="finite"):
            runner.check_budget(0.0, tmp_path)
    monkeypatch.setenv(CAP, "50\u00df")  # a stray character typed into .env
    with pytest.raises(SystemExit, match="not a number"):
        runner.check_budget(0.0, tmp_path)
    monkeypatch.setenv(CAP, "10")
    with pytest.raises(SystemExit, match="finite"):
        runner.check_budget(float("nan"), tmp_path)
    monkeypatch.setattr(runner, "env_value", lambda var: "")  # unset, and .env never read
    with pytest.raises(SystemExit, match=CAP):
        runner.check_budget(0.0, tmp_path)


def test_every_paid_path_checks_the_budget_before_any_request(monkeypatch, tmp_path):
    from laf import live, pilot, probe

    class Refused(Exception):
        pass

    def refuse(*a, **k):
        raise Refused

    def no_client(*a, **k):
        raise AssertionError("client used before the budget check")

    for mod in (pilot, probe, live, runner):
        monkeypatch.setattr(mod, "check_budget", refuse)
    monkeypatch.setattr(pilot, "client", no_client)
    monkeypatch.setattr(runner, "RUNS", tmp_path)
    for call in (
        lambda: pilot.smoke(tmp_path),
        lambda: pilot.pilot(tmp_path, []),
        lambda: probe.run_probe(None, pd.DataFrame(), tmp_path),
        lambda: live.run_live(None, [], tmp_path),
        lambda: runner.submit(None, "x", [], "S", estimate=0.0),
    ):
        with pytest.raises(Refused):
            call()


def test_probe_and_live_claim_their_output_folder_before_paying(monkeypatch, tmp_path):
    from laf import live, probe

    for mod in (probe, live):
        monkeypatch.setattr(mod, "check_budget", lambda *a, **k: 0.0)
    (tmp_path / "p").mkdir()
    (tmp_path / "l").mkdir()
    with pytest.raises(FileExistsError):
        probe.run_probe(None, pd.DataFrame(), tmp_path / "p")  # client None: never reached
    with pytest.raises(FileExistsError):
        live.run_live(None, [], tmp_path / "l")
