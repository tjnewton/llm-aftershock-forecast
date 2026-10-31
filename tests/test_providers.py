import pytest

from laf import providers
from laf.providers import anthropic_params, api_key, cost_usd


def test_scored_params_have_only_the_allowed_controls():
    p = anthropic_params(
        "claude-opus-5-5", "sys", "user", {"type": "object"}, effort="high", max_tokens=16000
    )
    assert set(p) == {"model", "max_tokens", "system", "messages", "output_config"}
    assert p["output_config"]["effort"] == "high"
    assert p["output_config"]["format"]["type"] == "json_schema"
    for banned in ("temperature", "top_p", "top_k", "tools", "thinking", "fallbacks"):
        assert banned not in p


def test_study_settings_of_the_46_models_and_unchanged_55_requests():
    # ADR 0014 decision 5: omitting `thinking` runs the 4.6 models without thinking
    p = anthropic_params("claude-opus-4-6", "s", "u", {}, effort="medium", max_tokens=99)
    assert p["thinking"] == {"type": "adaptive"}
    assert providers.study_effort("claude-opus-4-6") == "medium"
    thinking, effort = providers.STUDY_SETTINGS["claude-sonnet-4-6"]
    p = anthropic_params("claude-sonnet-4-6", "s", "u", {}, effort=effort, max_tokens=99)
    assert ("thinking" in p) == thinking
    assert providers.study_effort("claude-opus-5-5") == "high"
    p = anthropic_params("claude-sonnet-5-5", "s", "u", {}, effort="high", max_tokens=99)
    assert "thinking" not in p
    usage = {"input_tokens": 1_000_000, "output_tokens": 1_000_000}
    assert cost_usd("claude-opus-4-6", usage, batch=True) == pytest.approx(15.0)
    assert cost_usd("claude-sonnet-4-6", usage) == pytest.approx(18.0)


def test_cost_uses_list_prices_and_batch_discount():
    usage = {"input_tokens": 1_000_000, "output_tokens": 1_000_000}
    assert cost_usd("claude-opus-5-5", usage) == pytest.approx(24.0)
    assert cost_usd("claude-sonnet-5-5", usage, batch=True) == pytest.approx(6.0)


def test_api_key_never_falls_back_to_other_credentials(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "not-used")
    with pytest.raises(SystemExit):
        api_key(tmp_path / "missing.env")
    env = tmp_path / ".env"
    env.write_text("OTHER=1\nANTHROPIC_API_KEY='sk-test'\n")
    assert api_key(env) == "sk-test"


def test_sdk_retries_are_disabled(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert providers.client().max_retries == 0


def test_inherited_base_url_is_ignored(monkeypatch):
    # Claude Code users may export ANTHROPIC_BASE_URL for a local proxy; scored calls must
    # still go straight to the official API.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://127.0.0.1:8787/w/claude")
    assert str(providers.client().base_url).rstrip("/") == "https://api.anthropic.com"


def test_a_stream_broken_after_it_started_is_retried(monkeypatch):
    from types import SimpleNamespace

    import httpx2

    monkeypatch.setattr(providers.time, "sleep", lambda s: None)
    calls = {"n": 0}

    class Stream:
        def __init__(self, **params):
            self.params = params

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get_final_message(self):
            calls["n"] += 1
            if calls["n"] == 1:
                raise httpx2.ReadTimeout("read timed out mid-stream")  # the SDK's transport
            usage = SimpleNamespace(model_dump=lambda: {"input_tokens": 1, "output_tokens": 1})
            return SimpleNamespace(id="m", model="claude-opus-5-5", stop_reason="end_turn",
                                   stop_details=None, usage=usage,
                                   content=[SimpleNamespace(type="text", text="{}")])  # fmt: skip

    c = SimpleNamespace(messages=SimpleNamespace(stream=Stream), base_url="x")
    rec = providers.call_anthropic(c, {"model": "claude-opus-5-5"}, stream=True)  # type: ignore[arg-type]
    assert rec["attempts"] == 2 and rec["error"] is None
