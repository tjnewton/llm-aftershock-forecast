import io
import json
import urllib.error
from datetime import UTC, datetime
from pathlib import Path

import pytest

from laf import llamacpp
from laf.items import Item
from laf.prompts import schema

ITEMS = [
    Item.model_validate_json(line)
    for line in Path("data/processed/20261021T1027Z/items.jsonl").read_text("utf-8").splitlines()
]
CLAUDE_FIELDS = {
    "started_utc", "latency_s", "attempts", "id", "model_requested", "model_reported",
    "stop_reason", "stop_details", "usage", "text", "error", "sdk_version", "base_url",
}  # fmt: skip
REPLY = {
    "id": "chatcmpl-1",
    "model": "openai/gpt-oss-20b",
    "choices": [{"finish_reason": "stop", "message": {"content": "{}", "reasoning_content": "r"}}],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    "timings": {"predicted_per_second": 250.0},
}


@pytest.mark.parametrize(("block", "n"), [("core", 294), ("i0", 132), ("dev", 72)])
@pytest.mark.parametrize("model", sorted(llamacpp.MODELS))
def test_blocks_match_the_design_table(block, n, model):
    jobs = llamacpp.expand(ITEMS, block, model)
    assert len(jobs) == n
    assert len({j["custom_id"] for j in jobs}) == n
    assert {j["body"]["seed"] for j in jobs} == {0, 1, 2}
    assert {j["meta"]["paraphrase"] for j in jobs} == {"p1"}
    assert all(j["meta"]["seed"] == j["meta"]["sample"] for j in jobs)


@pytest.mark.parametrize("model", sorted(llamacpp.MODELS))
def test_requests_use_only_the_registered_settings(model):
    for j in llamacpp.expand(ITEMS, "i0", model):
        b, item = j["body"], next(i for i in ITEMS if i.item_id == j["meta"]["item_id"])
        assert set(b) == {
            "model", "messages", "response_format", "max_tokens", "seed", "temperature",
            "top_p", "top_k", "min_p", "cache_prompt", "chat_template_kwargs",
        }  # fmt: skip
        assert b["cache_prompt"] is False and b["max_tokens"] == 16_000
        assert [m["role"] for m in b["messages"]] == ["system", "user"]
        assert b["response_format"]["json_schema"]["schema"] == schema(j["meta"]["arm"])
        assert b["temperature"] == llamacpp.MODELS[model]["sampling"]["temperature"]
        day = datetime.fromtimestamp(item.issue_ms / 1000, UTC).date().isoformat()
        assert b["chat_template_kwargs"] == {"current_date": day}


def test_templates_never_read_the_wall_clock():
    for model, spec in llamacpp.MODELS.items():
        text = (llamacpp.TEMPLATES / f"{model}.jinja").read_text(encoding="utf-8")
        assert "strftime_now" not in text
        assert ("current_date" in text) == spec["dated_template"]


def test_call_record_has_the_claude_fields(monkeypatch):
    monkeypatch.setattr(llamacpp, "_post", lambda url, payload, timeout=0: REPLY)
    rec = llamacpp.call("http://x", {"model": "openai/gpt-oss-20b"}, "b1")
    assert set(rec) >= CLAUDE_FIELDS
    assert rec["stop_reason"] == "end_turn" and rec["reasoning"] == "r" and rec["error"] is None


def test_only_transport_errors_are_retried(monkeypatch):
    monkeypatch.setattr(llamacpp.time, "sleep", lambda s: None)
    replies = []

    def post(url, payload, timeout=0):
        code = replies.pop(0)
        if code:
            raise urllib.error.HTTPError(url, code, "x", None, io.BytesIO(b"err"))  # type: ignore[arg-type]
        return REPLY

    monkeypatch.setattr(llamacpp, "_post", post)
    replies[:] = [503, 0]
    assert llamacpp.call("http://x", {"model": "m"}, "b1")["attempts"] == 2
    replies[:] = [400, 0]
    rec = llamacpp.call("http://x", {"model": "m"}, "b1")
    assert rec["error"].startswith("HTTPError 400") and replies == [0]


def test_run_appends_utf8_lf_records_and_skips_answered_samples(monkeypatch, tmp_path):
    item = next(i for i in ITEMS if i.role == "dev")
    calls = []
    info = {"build": "b1", "gguf_path": "missing.gguf"}
    monkeypatch.setattr(llamacpp, "server", lambda url, model: dict(info))
    monkeypatch.setattr(llamacpp, "check_date", lambda url, model, job: None)
    monkeypatch.setattr(llamacpp, "machine", lambda: {"os": "OS", "gpu": "GPU"})

    def post(url, payload, timeout=0):
        calls.append(payload["seed"])
        reply = json.loads(json.dumps(REPLY))
        reply["choices"][0]["message"]["content"] = '{"notes": "données"}'
        return reply

    monkeypatch.setattr(llamacpp, "_post", post)
    llamacpp.run("http://x", "gpt-oss-20b", "dev", [item], "20261021T1027Z", runs=tmp_path)
    llamacpp.run("http://x", "gpt-oss-20b", "dev", [item], "20261021T1027Z", runs=tmp_path)
    raw = (tmp_path / "local-gpt-oss-20b" / "calls.jsonl").read_bytes()
    assert calls == [0, 1, 2, 0, 1, 2] and b"\r" not in raw  # 2 arms x 3 seeds, once
    rows = [json.loads(x) for x in raw.decode("utf-8").splitlines()]
    assert len(rows) == 6 and "données" in rows[0]["text"] and rows[0]["machine"].startswith("OS")
    assert len((tmp_path / "local-gpt-oss-20b" / "manifest.jsonl").read_text("utf-8").split()) > 1
