import io
import json
import urllib.error
from datetime import UTC, datetime
from pathlib import Path

import pytest

from laf import analysis as A
from laf import llamacpp
from laf.items import Item
from laf.prompts import schema
from laf.schemas import QKEYS

P = Path("data/processed/20261021T1027Z")
ITEMS = [Item.model_validate_json(x) for x in (P / "items.jsonl").read_text("utf-8").splitlines()]
GPT = "gpt-oss-20b"


def _reply(text: str, finish: str = "stop") -> dict:
    return {
        "id": "chatcmpl-1",
        "model": "openai/gpt-oss-20b",
        "choices": [
            {"finish_reason": finish, "message": {"content": text, "reasoning_content": "r"}}
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        "timings": {"predicted_per_second": 250.0},
    }


def _direct_text() -> str:
    w = {
        "m5_count_quantiles": dict(zip(QKEYS, (0, 0, 0, 1, 1, 2, 3, 4, 5), strict=True)),
        "m4_count_quantiles": dict(zip(QKEYS, (1, 2, 3, 4, 6, 9, 12, 15, 18), strict=True)),
        "p_m6_at_least_one": 0.05,
    }
    return json.dumps(
        {"day": w, "week": w, "month": w, "notes": "Fake\u2028données."}, ensure_ascii=False
    )


PARAMS_TEXT = json.dumps(
    {"b": 1.0, "p": 1.1, "c_days": 0.05, "a_p05": -2.6, "a_p50": -2.1, "a_p95": -1.6, "notes": "F."}
)


@pytest.fixture
def server(monkeypatch):
    """Fake llama-server: records the seeds it was sent; fails the seeds listed in `fail`."""
    state: dict = {"seeds": [], "fail": set()}
    monkeypatch.setattr(llamacpp, "server", lambda url, model: {"build": "b1", "gguf_path": "x"})
    monkeypatch.setattr(llamacpp, "check_prompt", lambda url, model, job: None)
    monkeypatch.setattr(llamacpp, "machine", lambda: {"os": "OS", "gpu": "GPU"})
    monkeypatch.setattr(llamacpp.time, "sleep", lambda s: None)

    def post(url, payload, timeout=0):
        state["seeds"].append(payload["seed"])
        if payload["seed"] in state["fail"]:
            raise urllib.error.HTTPError(url, 400, "x", None, io.BytesIO(b"bad"))  # type: ignore[arg-type]
        arm = payload["response_format"]["json_schema"]["name"]
        return _reply(_direct_text() if arm == "direct" else PARAMS_TEXT)

    monkeypatch.setattr(llamacpp, "_post", post)
    return state


@pytest.mark.parametrize(
    ("block", "n"),
    [("core", 294), ("i0", 132), ("dev", 72), ("e1", 147), ("e3", 66), ("e3all", 114)],
)
@pytest.mark.parametrize("model", sorted(llamacpp.MODELS))
def test_blocks_match_the_design_table(block, n, model):
    jobs = llamacpp.expand(ITEMS, block, model)
    assert len(jobs) == n
    assert len({j["custom_id"] for j in jobs}) == n
    assert {j["body"]["seed"] for j in jobs} == {0, 1, 2}
    assert {j["meta"]["paraphrase"] for j in jobs} == {"p1"}
    assert all(j["meta"]["seed"] == j["meta"]["sample"] for j in jobs)
    assert {j["meta"]["effort"] for j in jobs} == {llamacpp.MODELS[model]["effort"]}


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
    for model in llamacpp.MODELS:
        text = llamacpp.template_path(model).read_text(encoding="utf-8")
        assert "strftime_now" not in text
    assert "current_date" in (llamacpp.TEMPLATES / f"{GPT}.jinja").read_text(encoding="utf-8")


def test_only_transport_errors_are_retried(monkeypatch):
    monkeypatch.setattr(llamacpp.time, "sleep", lambda s: None)
    codes = []

    def post(url, payload, timeout=0):
        code = codes.pop(0)
        if code:
            raise urllib.error.HTTPError(url, code, "x", None, io.BytesIO(b"err"))  # type: ignore[arg-type]
        return _reply("{}", finish="length")

    monkeypatch.setattr(llamacpp, "_post", post)
    codes[:] = [503, 0]
    rec = llamacpp.call("http://x", {}, "b1")
    assert rec["attempts"] == 2 and rec["stop_reason"] == "max_tokens" and rec["error"] is None
    codes[:] = [400, 0]
    rec = llamacpp.call("http://x", {}, "b1")
    assert rec["error"].startswith("HTTPError 400") and rec["attempts"] == 1 and codes == [0]


def test_run_writes_the_batch_layout_and_retries_only_failed_requests(server, tmp_path):
    item = next(i for i in ITEMS if i.role == "dev")
    server["fail"] = {1}
    llamacpp.run("http://x", GPT, "dev", [item], "20261021T1027Z", runs=tmp_path)
    out = tmp_path / f"dev-{GPT}"
    assert sorted(p.name for p in out.iterdir()) == [
        "local_log.jsonl",
        "requests.jsonl",
        "results.jsonl",
    ]
    first = llamacpp._jsonl(out / "results.jsonl")
    assert [r["result"] for r in first].count("errored") == 2  # seed 1 of both arms
    server["fail"], server["seeds"] = set(), []
    llamacpp.run("http://x", GPT, "dev", [item], "20261021T1027Z", runs=tmp_path)
    assert server["seeds"] == [1, 1]  # only the two failed requests are sent again
    for name in ("requests.jsonl", "results.jsonl", "local_log.jsonl"):
        assert b"\r" not in (out / name).read_bytes()
    reqs = llamacpp._jsonl(out / "requests.jsonl")
    res = llamacpp._jsonl(out / "results.jsonl")
    assert [r["custom_id"] for r in res] == [r["custom_id"] for r in reqs]  # one row each
    assert {r["result"] for r in res} == {"succeeded"} and "données" in res[0]["text"]
    assert res[0]["usage"] == {"input_tokens": 10, "output_tokens": 5}
    assert {"model", "effort", "item_id", "arm", "info", "paraphrase", "sample", "block"} <= set(
        reqs[0]
    )


def test_extension_runs_stay_outside_the_frozen_analysis_glob(server, tmp_path):
    item = next(i for i in ITEMS if i.role == "dev")
    llamacpp.run("http://x", "gpt-oss-20b-e1", "dev", [item], "20261021T1027Z", runs=tmp_path)
    assert (tmp_path / "extensions" / "dev-gpt-oss-20b-e1" / "results.jsonl").exists()
    assert list(tmp_path.glob("*/results.jsonl")) == []  # the analysis notebook's glob


def test_local_runs_load_and_score_with_the_frozen_analysis(server, tmp_path):
    item = next(i for i in ITEMS if i.item_id == "us6000tkt2@3d")
    server["fail"] = {2}
    llamacpp.run("http://x", GPT, "core", [item], "20261021T1027Z", runs=tmp_path)
    tables, items = A.load_tables(P), A.load_items(P)
    c = A.cells(tables)
    c = c[c["issue_id"] == item.item_id]
    samples = A.llm_samples([tmp_path / f"core-{GPT}"], items)
    df = A.score_all(c, A.baselines(tables, items, c), samples)
    llm = df[df["model"] == "openai/gpt-oss-20b"]
    assert len(llm) == 2 * 3 * 3  # arms x seeds x windows
    assert set(llm["forecaster"]) == {
        "openai/gpt-oss-20b|direct|I1|medium",
        "openai/gpt-oss-20b|params|I1|medium",
    }
    assert set(llm.loc[llm["sample"] != 2, "status"]) == {"ok"}
    errored = llm[llm["sample"] == 2]
    assert set(errored["status"]) == {"transport_error"}
    assert errored["log_qs_valid_only"].isna().all()
    assert llm.loc[llm["status"] == "ok", "log_qs"].notna().all()
