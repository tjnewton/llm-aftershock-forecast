import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from laf import openai_runner as O
from laf import runner
from laf.analysis import load_tables
from laf.items import build_items
from laf.schemas import TARGETS_V2, validate

E3 = Path("data/processed/20261021T2300Z")


@pytest.fixture(scope="module")
def items():
    return build_items(load_tables(E3), 3.0)


def test_scored_params_have_only_the_allowed_controls(items):
    reqs = O.expand(items, "gpt-5.1-2025-11-13", "high")
    assert len(reqs) == 3 * sum(i.role == "test-post" for i in items)
    assert len({r["custom_id"] for r in reqs}) == len(reqs)
    p = reqs[0]["params"]
    assert set(p) == {
        "model", "instructions", "input", "reasoning", "text", "max_output_tokens", "store"
    }  # fmt: skip
    assert p["reasoning"] == {"effort": "high"} and p["store"] is False
    assert p["text"]["format"]["type"] == "json_schema" and p["text"]["format"]["strict"]
    for banned in ("temperature", "top_p", "tools", "user", "safety_identifier"):
        assert banned not in p


def test_the_client_pins_the_official_api(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:9999/proxy")
    c = O.client()
    assert str(c.base_url).rstrip("/") == "https://api.openai.com/v1"
    assert c.max_retries == 0


def _body(text=None, status="completed", reason=None, refusal=False):
    content = [{"type": "refusal", "refusal": "no"}] if refusal else []
    if text is not None:
        content.append({"type": "output_text", "text": text})
    return {
        "id": "resp_1", "model": "gpt-5.1-2025-11-13", "status": status,
        "incomplete_details": {"reason": reason} if reason else None,
        "output": [{"type": "reasoning"}, {"type": "message", "content": content}],
        "usage": {"input_tokens": 2000, "output_tokens": 3000},
    }  # fmt: skip


def test_stop_reasons_map_to_the_validator():
    assert O.stop_reason(_body("{}")) == "completed"
    assert O.stop_reason(_body(None, "incomplete", "max_output_tokens")) == "max_tokens"
    assert O.stop_reason(_body(None, "incomplete", "content_filter")) == "refusal"
    assert O.stop_reason(_body(None, refusal=True)) == "refusal"
    assert validate("direct", None, "max_tokens", TARGETS_V2)[0] == "max_tokens"
    assert O.output_text(_body('{"a": 1}')) == '{"a": 1}'


class FakeClient:
    def __init__(self, bodies):
        self.bodies, self.uploaded = bodies, None
        self.files = SimpleNamespace(create=self._upload, content=self._content)
        self.batches = SimpleNamespace(create=self._create, retrieve=self._retrieve)

    def _upload(self, file, purpose):
        assert purpose == "batch"
        self.uploaded = [json.loads(x) for x in file.read().decode().splitlines()]
        return SimpleNamespace(id="file_in")

    def _create(self, input_file_id, endpoint, completion_window):
        assert (endpoint, completion_window) == ("/v1/responses", "24h")
        return SimpleNamespace(id="batch_1", created_at=1_793_400_000)

    def _retrieve(self, batch_id):
        return SimpleNamespace(
            id=batch_id, status="completed", output_file_id="file_out", error_file_id=None,
            request_counts=SimpleNamespace(model_dump=lambda: {"total": 2}),
        )  # fmt: skip

    def _content(self, fid):
        lines = [
            {"custom_id": cid, "response": {"status_code": 200, "body": b}, "error": None}
            for cid, b in self.bodies.items()
        ]
        return SimpleNamespace(text="\n".join(json.dumps(x) for x in lines))


def test_submit_and_collect_round_trip(items, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data/processed/S").mkdir(parents=True)
    (tmp_path / "data/processed/S/items_m3.jsonl").write_text("x")
    (tmp_path / "prompts/v2").mkdir(parents=True)
    monkeypatch.setattr(O, "PROMPT_DIR", tmp_path / "prompts")
    (tmp_path / "prompts/v2/HASHES.json").write_text("{}")
    monkeypatch.setattr(O, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(runner, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(O, "scoring_frozen", lambda: True)
    monkeypatch.setenv("LAF_OPENAI_MONTHLY_CAP_USD", "5")
    reqs = O.expand(O.pilot_items(items, 2), "gpt-5.1-2025-11-13", "medium", k=1)
    c = FakeClient(
        {
            reqs[0]["custom_id"]: _body("{}"),
            reqs[1]["custom_id"]: _body(None, "incomplete", "max_output_tokens"),
        }
    )
    O.submit(c, "d2/x", reqs, "S", estimate=0.1)
    assert c.uploaded is not None
    assert [x["url"] for x in c.uploaded] == ["/v1/responses"] * 2
    assert not (tmp_path / "runs/d2/x/batch_input.jsonl").exists()
    rec = json.loads((tmp_path / "runs/d2/x/batch.json").read_text())
    assert rec["provider"] == "openai" and rec["base_url"] == "https://api.openai.com/v1"
    # OpenAI estimates never count against the Claude cap, and vice versa
    assert runner.spend_records(tmp_path / "runs") == []
    assert O.spend_records(tmp_path / "runs") == [(rec["created_at"][:7], 0.1)]
    assert O.collect(c, "d2/x") == 2
    rows = [json.loads(x) for x in (tmp_path / "runs/d2/x/results.jsonl").read_text().splitlines()]
    assert {r["stop_reason"] for r in rows} == {"completed", "max_tokens"}
    assert all(r["result"] == "succeeded" and r["model"] == "gpt-5.1-2025-11-13" for r in rows)
    usd = sum(x[1] for x in O.spend_records(tmp_path / "runs"))
    assert usd == pytest.approx(2 * (2000 * 1.25 + 3000 * 10) / 1e6 / 2)


def test_openai_guard_needs_its_own_cap(tmp_path, monkeypatch):
    monkeypatch.delenv("LAF_OPENAI_MONTHLY_CAP_USD", raising=False)
    monkeypatch.chdir(tmp_path)  # no .env here
    with pytest.raises(SystemExit, match="LAF_OPENAI_MONTHLY_CAP_USD"):
        O.check_openai_budget(0.1, tmp_path)


def test_submit_sends_nothing_without_its_provenance_files(items, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(O, "RUNS", tmp_path / "runs")
    monkeypatch.setenv("LAF_OPENAI_MONTHLY_CAP_USD", "5")
    reqs = O.expand(O.pilot_items(items, 1), "gpt-5.1-2025-11-13", "medium", k=1)
    c = FakeClient({})
    with pytest.raises(FileNotFoundError):
        O.submit(c, "x", reqs, "missing-snapshot", estimate=0.1)
    assert c.uploaded is None and not (tmp_path / "runs/x").exists()
