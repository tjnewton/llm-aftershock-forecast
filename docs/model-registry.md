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
| `laf/gpt-oss-20b-e1` (E1: `gpt-oss-20b-MXFP4.gguf` plus LoRA `gpt-oss-20b-e1-lora-f16.gguf`, converted by llama.cpp `convert_lora_to_gguf.py` from the AutoScientist checkpoint in `runs/e1-adaption/checkpoint.json`) | as gpt-oss-20b, plus `--lora`; runs in `runs/extensions/` | as gpt-oss-20b; training sequences end 2025-06-30 | as gpt-oss-20b | 16,000 | local | extension (prereg sec. 11), descriptive |

Contamination classes (ADR 0006): every candidate sequence (2025-07 to 2026-10) is after the
local models' cutoffs. For Claude, origin on or after 2026-07-01 is post-cutoff, June 2026 is
ambiguous, earlier is pre-cutoff.

## Settings shared by every scored call
- Claude: no `thinking`, no `temperature`/`top_p`/`top_k`, no tools, no assistant prefill, no
  `fallbacks`; `output_config = {"effort": "high", "format": {"type": "json_schema", "schema":
  ...}}`; SDK retries off (`max_retries=0`), the harness's retries logged; `response.model`, `usage`,
  `stop_reason`, `stop_details` logged.
- Local: system message always present (Olmo's template otherwise injects its own date-cutoff
  text; gpt-oss's template otherwise injects today's date, which is replaced with the issue
  date); `response_format` json_schema; seeds 0/1/2; temperature from the model card;
  `cache_prompt: false`. Exact values in the next section.

## Local serving (exact settings, `laf.llamacpp`)
- Engine: llama.cpp `llama-server` build b11739 (commit 0ce8cd114, reports `0.7.0-dev`), release
  zip `llama-b11739-bin-win-cuda-13.4-x64.zip` plus the cudart 13.4 DLLs, on Windows 11 with an
  RTX 5090 (driver 610.88, CUDA 13.3). The build's CUDA archs include 1200 (sm_120) and it runs
  on this driver; all layers are offloaded to the GPU.
- Weights (SHA-256 of the GGUF file): `gpt-oss-20b-MXFP4.gguf`
  27cd6c432c7672cb812a92f611cf3ba7bbc35928262bb1e1253ff4ee6ae35901;
  `allenai_Olmo-3.1-32B-Instruct-Q4_K_M.gguf`
  437635de32ed770b1ac5d175f5245bbddcba6860ca70b16dea5fd8ca11c6bb3c.
- Server, one model at a time: `llama-server -m <gguf> --alias <model id> -c 49152 -ngl all
  -fit off -np 1 --no-cache-prompt --cache-ram 0 --host 127.0.0.1 --port 9931 --no-webui --jinja
  --chat-template-file config/llamacpp/<model>.jinja`. `--reasoning-format` stays `auto`, so
  gpt-oss reasoning arrives in `reasoning_content` (logged as `reasoning`). The longest scored
  prompt is 23,945 gpt-oss tokens (23,898 Olmo), so 49,152 holds it plus `max_tokens`.
- Request (`/v1/chat/completions`): messages `[system, user]` from `laf.prompts.render`;
  `response_format = {"type": "json_schema", "json_schema": {"name": <arm>, "schema":
  prompts/schema_<arm>.json}}`; `max_tokens` 16,000; `seed` = sample index (0, 1, 2);
  `cache_prompt: false`; `chat_template_kwargs = {"current_date": <UTC date of the issue
  time>}`; `model` = the model id below.
- Sampling, set on every request:

  | Model | temperature | top_p | top_k | min_p | Source |
  |---|---|---|---|---|---|
  | `openai/gpt-oss-20b` | 1.0 | 1.0 | 0 (off) | 0 (off) | openai/gpt-oss README, "Recommended Sampling Parameters" (the HF card and generation_config.json give none) |
  | `allenai/Olmo-3.1-32B-Instruct` | 0.6 | 0.95 | 50 | 0 (off) | generation_config.json (temperature, top_p; also the GGUF's `general.sampling.*`); the card's inference example (top_k); the card text gives no temperature |

  `min_p` 0 and gpt-oss `top_k` 0 switch off llama.cpp's own defaults (min_p 0.05, top_k 40),
  which no model card asks for. Every other sampler is at the b11739 default, all neutral:
  repeat_penalty 1.0, presence and frequency penalty 0, DRY multiplier 0, XTC probability 0,
  typical_p 1.0, top_n_sigma -1, dynatemp_range 0, mirostat 0. Sampler order: penalties, dry,
  top_n_sigma, top_k, typ_p, top_p, min_p, xtc, temperature.
- gpt-oss reasoning effort: template default `medium` (not overridden), recorded as effort
  `medium`; Olmo is recorded as effort `none`. The forecaster key is model|arm|info|effort.
- Chat templates (`config/llamacpp/`, each one the template embedded in the GGUF plus one
  provenance comment and one patch):
  - `gpt-oss-20b.jinja` (SHA-256 ea5d51949163e3c1023bef7d319622b8396fbe2026cf1d23dc471ced8e1c4aba;
    embedded original b2215de6da8ba369957eece8c5aa18f4af94f6c4d311d85e691373a421d80e89): the
    line `"Current date: " + strftime_now("%Y-%m-%d")` becomes `"Current date: " +
    current_date`, emitted only when the `current_date` kwarg is passed, so no prompt can carry
    the wall-clock date. A missing kwarg cannot raise: llama-server test-renders the template
    without kwargs at startup and rejects one that raises.
  - `olmo-3.1-32b-instruct.jinja` (SHA-256
    bb8b90214eebde6d40cb2b492c32103931a9756c1dc2553aa60b9824dbc25100; embedded original
    49a944c9814e130bd3cc80a2420c55ff22e24a4e4ba97009aa60000909b5eac3, identical to the repo's
    chat_template.jinja): prefixed with `{%- if tools is not defined -%}{%- set tools = none
    -%}{%- endif -%}`. llama-server otherwise refuses the template (`tools | tojson` on an
    undefined value); transformers always passes `tools=None`, so the rendering is unchanged.
    The template contains no date, so `current_date` has no effect on Olmo.
- Checks before each run: `/props` must show the alias, the GGUF file name, `n_ctx` 49,152,
  one slot and the template SHA-256 above; `/apply-template` on the first request must contain
  the system message, for gpt-oss `Current date: <issue date>` and `Reasoning: medium`, and
  never today's date.
- Records (`runs/<block>-<model>/`, UTF-8, LF), in the Message Batches layout that the frozen
  `laf.analysis.llm_samples` reads, so local outputs are scored by the `scoring-v1` code
  unchanged: `requests.jsonl` (written first; custom_id, item_id, arm, info, paraphrase, sample,
  block, model, effort, seed, temperature, params_sha256) and `results.jsonl` (one row per
  custom_id: result `succeeded`/`errored`, model, stop_reason `end_turn`/`max_tokens`, text,
  usage {input_tokens, output_tokens}, latency_s, seed, server_build, machine). Attempts,
  reasoning text, timings and a start line per invocation (git SHA, prompt and item hashes, GGUF
  SHA-256, server settings, OS/GPU/driver; no host names) go to the append-only
  `local_log.jsonl`, which is not committed. A rerun retries only requests without a response;
  results.jsonl keeps the last response, else the last error. The spend ledger skips the local
  model ids (not in the price table).
- Smoke test (dev item us6000rtdt@28d, direct, I1, p1, seed 0): gpt-oss reasoning present,
  valid JSON (`ok`), 6,518 output tokens at 251 tok/s (prompt 4,641 tok/s); Olmo no reasoning,
  valid JSON (`ok`, `notes_too_long`), 747 tokens at 65 tok/s (prompt 2,786 tok/s). Dev check
  through the client (that item, both arms, seeds 0-2): gpt-oss 6/6 `ok`; Olmo 4 `ok`,
  1 `non_monotone`, 1 `out_of_range`. Seed 0 gave byte-identical text after a server restart
  for both models. Constrained decoding keeps gpt-oss reasoning intact, so the unconstrained
  fallback (prereg section 3) is not used.
- Retired/not used: Qwen3.8-27B (cutoff undocumented, released 2026-08-14); gpt-oss-120b
  (about 63 GB; does not fit 48 GB unified memory or the 32 GB GPU without offload; stretch only).

## Adapted models (Adaption AutoScientist, exploratory except E1)
All are LoRA adapters on `openai/gpt-oss-20b` (trained on the bf16 weights), served on the same
MXFP4 GGUF with `--lora` and otherwise the registered gpt-oss settings (`laf.llamacpp` MODELS
`gpt-oss-20b-<run>`, model id `laf/gpt-oss-20b-<run>`). Runs and records: `runs/<run>-adaption/`;
outputs: `runs/extensions/` (registered snapshot) and `runs/e3/extensions/` (E3). Checkpoints
and converted adapters are not committed (`laf adaption download --run <run>` re-fetches a
checkpoint and checks its SHA-256).

| Run | Training data | Iterations | Best win rate | Checkpoint (tar + zstd) SHA-256 | Converted adapter SHA-256 |
|---|---|---|---|---|---|
| e1 (prereg E1) | E1, 3,090 rows | 3 | 0.471 | d06688de19b9c40d319d6f0511ca36b2486a029e9793311b883030799c7ba1ae | not recorded (the reported value had 65 characters) |
| e1a | E1a, 9,030 rows | 1 | 0.505 | 50a9b4c264eb6604aa6e2975b0a25415930484460da851583f2cca69a35b2e7f | not reported |
| e1r1 | E1 | 1 | 0.473 | 7e1b29c647ed60c75e0dc730980031311031398a589faea13fc6c2f8e58f5620 | 33c916fdd70c5c34c5f92ed9ef08d8778645c18797527c0033ff3604bff3689a |
| e1r2 | E1 (re-upload) | 1 | 0.506 | 2b9d845c6d53cadfb0618ca4a27f79faca8e40a43f78f4dd863342d9bb8ca380 | 7ec520aff551b2470a9471cd52e050b1d6f024ef80148fda8ca63839b699645d |
| e1ar2 | E1a | 1 | 0.531 | a010c6efb2701daf5d4eb8ba3e36e1348f23b71671d3b1b6452f8651270cc5e8 | 90e868fed977697936f4da3e02ca28fee75522b9b403a2d2b4fdeba59e6d01d6 |
| e1b | E1b preference pairs, 15,450 rows | 1 (alignment: supervised, then preference) | 0.241 | 5742070f531cc9290a718a191ae5c1d97b84708125d4bd9c7ca67ea72b21c15f | pending |

e1r1, e1r2 and e1ar2 use E1's best hyperparameters (LoRA r 32, alpha 64, q/k/v/o projections,
3 epochs, learning rate 1e-4, cosine schedule). The win rate is AutoScientist's own metric; the
benchmark scores are in `results/e1*.csv` and `results/replicates.csv`.

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
