# Model registry

Sources: Claude models overview and pricing pages; bundled `claude-api` skill (cached 2026-10-06); local models in
docs/research/models-and-tooling.md. Smoke-test results are appended below once run.

| Model (exact id) | Access | Documented cutoff | Effort / thinking | Max tokens | Price $/MTok (in / out / cache read) | Role |
|---|---|---|---|---|---|---|
| `claude-opus-5-5` | `anthropic` SDK 1.15.0, Messages + Batches | reliable knowledge and training data: Jun 2026 | effort `high` (default would be `medium`); adaptive thinking, cannot be disabled | 16,000 | 4 / 20 / 0.20 (batch 2 / 10) | primary |
| `claude-sonnet-5-5` | same | Jun 2026 | `high` (default `high`); `low` sensitivity block | 16,000 | 2 / 10 / 0.10 (batch 1 / 5) | primary |
| `claude-haiku-5-5` | same | Jun 2026 | `high` (default `medium`) | 16,000 | 0.10 / 0.50 / 0.01, prompts <= 100K tokens (batch 0.05 / 0.25) | primary |
| `openai/gpt-oss-20b` (GGUF `ggml-org/gpt-oss-20b-GGUF`, MXFP4, 12.1 GB) | llama.cpp `llama-server` v0.7.0, Windows RTX 5090 (or M3 Max) | Jun 2024 (model card, arXiv 2508.10925 sec. 2.4; template says `Knowledge cutoff: 2024-06`) | reasoning effort via template: `medium` (default) | 16,000 | local | secondary |
| `allenai/Olmo-3.1-32B-Instruct` (GGUF Q4_K_M 19.5 GB) | llama.cpp `llama-server`, RTX 5090 | Dec 2024 (model card "Date cutoff: Dec. 2024"); training data open | not a reasoning model | 16,000 | local | secondary |

Contamination classes (ADR 0006): every candidate sequence (2025-07 to 2026-10) is after the
local models' cutoffs. For Claude, origin on or after 2026-07-01 is post-cutoff, June 2026 is
ambiguous, earlier is pre-cutoff.

## Settings shared by every scored call
- Claude: no `thinking`, no `temperature`/`top_p`/`top_k`, no tools, no assistant prefill, no
  `fallbacks`; `output_config = {"effort": "high", "format": {"type": "json_schema", "schema":
  ...}}`; SDK retries off (`max_retries=0`), our retries logged; `response.model`, `usage`,
  `stop_reason`, `stop_details` logged.
- Local: system message always present (Olmo's template otherwise injects its own date-cutoff
  text; gpt-oss's template otherwise injects today's date, which we replace with the issue
  date); `response_format` json_schema; seeds 0/1/2; temperature from the model card;
  `cache_prompt: false`.
- Retired/not used: Qwen3.8-27B (cutoff undocumented, released 2026-08-14); gpt-oss-120b
  (about 63 GB; does not fit 48 GB unified memory or the 32 GB GPU without offload; stretch only).

## Expected cost
See docs/PLAN.md section 9 (about $100 at batch prices under stated assumptions; $150 cap).

## Smoke test and pilot results
- **discarded** (`runs/smoke-via-proxy-discarded/`): one structured-output
  call per model at effort high returned valid JSON with `stop_reason=end_turn` and
  `response.model` equal to the requested id (cost $0.0021), but the calls were routed through
  a local proxy via an inherited `ANTHROPIC_BASE_URL`, and the Batch API call failed there
  (404 from the proxy). Endpoint now pinned; key rotated.
- **direct** (`runs/smoke/`, base_url https://api.anthropic.com): same
  result for all three models (valid JSON, `end_turn`, reported id = requested id); cost
  $0.0021. Batch with structured outputs and `max_tokens=32000` accepted
  (`msgbatch_01VKkjXAfvbhR21diYn9XKTJ`): 3 of 3 succeeded (valid JSON, `end_turn`, reported id =
  requested id), but it took **39.5 min** for 3 tiny requests (2026-10-19 20:06:22 to 20:45:49 UTC).
  Results in `runs/smoke/batch.json`.
- **dev pilot** (`runs/pilot/`, Aomori@28d and Sanriku@28d, both
  arms, p1, I1, k = 2, effort high, synchronous): 24 of 24 calls `end_turn`, 24 valid JSON;
  all 12 direct samples had monotone quantiles. Mean / max output tokens
  (thinking included): Haiku 7,064 / 10,342; Sonnet 1,230 / 1,551; Opus 1,601 / 1,875. Cost $0.56.
  count_tokens over all 61 items (I1, both arms; schema included): median 2,855, mean over
  scored items 4,332, max 25,596 (Kamchatka 14d, 759 rows).
- Budget rule (prereg section 9) applied to the pilot: projected full T2 cost $54.29 (Haiku
  $3.08, Sonnet $15.96, Opus $35.25, output x 1.25), below $135, so no reduction step.
