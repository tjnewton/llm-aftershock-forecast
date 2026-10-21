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
