"""Model access. Claude only through the official `anthropic` SDK.

Scored-run settings (docs/PLAN.md 4.5): no `thinking` (adaptive default), no sampling params,
no tools, no assistant prefill, no server-side refusal fallbacks; effort and JSON schema in
`output_config`. The SDK's own retries are disabled so every retry is ours and logged.
The 4.6 models run without thinking when the field is omitted, so their requests ask for
adaptive thinking explicitly (ADR 0014); the 5.5 requests stay as registered.
"""

import os
import time
from datetime import UTC, datetime
from pathlib import Path

import anthropic

MODELS = ("claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5")
# USD per MTok: input, output, cache read, 5-min cache write (pricing page).
PRICES = {
    "claude-opus-5-5": (4.00, 20.00, 0.20, 5.00),
    "claude-sonnet-5-5": (2.00, 10.00, 0.10, 2.50),
    "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125),
    "claude-opus-4-6": (5.00, 25.00, 0.50, 6.25),
    "claude-sonnet-4-6": (3.00, 15.00, 0.30, 3.75),
}
EXPLICIT_THINKING = ("claude-opus-4-6", "claude-sonnet-4-6")


def env_value(var: str, env_file: Path = Path(".env")) -> str:
    """`var` from the environment, else from the untracked .env; "" when unset."""
    value = os.environ.get(var, "")
    if not value and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            name, _, v = line.partition("=")
            if name.strip() == var:
                value = v.strip().strip('"').strip("'")
    return value


def api_key(env_file: Path = Path(".env")) -> str:
    """ANTHROPIC_API_KEY from the environment or .env. Never falls back to other credentials."""
    key = env_value("ANTHROPIC_API_KEY", env_file)
    if not key:
        raise SystemExit("ANTHROPIC_API_KEY not set (environment or .env)")
    return key


# Pinned so an inherited ANTHROPIC_BASE_URL (for example a local compression proxy configured
# for Claude Code) can never route, rewrite or log scored requests.
API_BASE_URL = "https://api.anthropic.com"


def client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key(), base_url=API_BASE_URL, max_retries=0)


def anthropic_params(
    model: str, system: str, user: str, schema: dict, *, effort: str, max_tokens: int
) -> dict:
    params = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "output_config": {"effort": effort, "format": {"type": "json_schema", "schema": schema}},
    }
    if model in EXPLICIT_THINKING:
        params["thinking"] = {"type": "adaptive"}
    return params


def cost_usd(model: str, usage: dict, *, batch: bool = False) -> float:
    pin, pout, pread, pwrite = PRICES[model]
    total = (
        usage.get("input_tokens", 0) * pin
        + usage.get("output_tokens", 0) * pout
        + (usage.get("cache_read_input_tokens") or 0) * pread
        + (usage.get("cache_creation_input_tokens") or 0) * pwrite
    ) / 1e6
    return total / 2 if batch else total


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def call_anthropic(c: anthropic.Anthropic, params: dict, *, attempts: int = 4) -> dict:
    """One Messages call; retries only 429/5xx/connection errors. Returns a loggable record."""
    started, t0, error = _now(), time.monotonic(), None
    for i in range(attempts):
        try:
            r = c.messages.create(**params)
            text = next((b.text for b in r.content if b.type == "text"), None)
            return {
                "started_utc": started,
                "latency_s": round(time.monotonic() - t0, 3),
                "attempts": i + 1,
                "id": r.id,
                "model_requested": params["model"],
                "model_reported": r.model,
                "stop_reason": r.stop_reason,
                "stop_details": r.stop_details.model_dump() if r.stop_details else None,
                "usage": r.usage.model_dump(),
                "text": text,
                "error": None,
                "sdk_version": anthropic.__version__,
                "base_url": str(c.base_url),
            }
        except (anthropic.RateLimitError, anthropic.InternalServerError) as e:
            error = f"{type(e).__name__}: {e}"
            retry_after = getattr(e, "response", None) and e.response.headers.get("retry-after")
            time.sleep(float(retry_after) if retry_after else 2 ** (i + 1))
        except anthropic.APIConnectionError as e:
            error = f"{type(e).__name__}: {e}"
            time.sleep(2 ** (i + 1))
        except anthropic.APIStatusError as e:  # 4xx other than 429: not retried
            error = f"{type(e).__name__} {e.status_code}: {e.message}"
            break
    return {
        "started_utc": started,
        "latency_s": round(time.monotonic() - t0, 3),
        "model_requested": params["model"],
        "error": error,
        "sdk_version": anthropic.__version__,
    }
