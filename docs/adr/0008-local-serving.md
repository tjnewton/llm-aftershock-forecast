# ADR 0008: Local model serving

Status: proposed.

## Decision
- llama.cpp `llama-server` (v0.7.0, released 2026-10-15) on both machines: Homebrew on the M3 Max
  Mac (Metal), the `win-cuda-13.4-x64` release zip natively on the Windows RTX 5090 box (it
  includes Blackwell sm_120 kernels; the cuda-12.4 zip does not). No WSL2 needed: the harness is
  pure Python with pathlib and talks HTTP to the server.
- Windows build used: b11739 (commit 0ce8cd114) with the cudart 13.4 DLLs; its CUDA archs
  include 1200 (sm_120) and it runs on driver 610.88 (CUDA 13.3).
- Server, one model at a time: `-c 49152 -ngl all -fit off -np 1 --no-cache-prompt --cache-ram 0
  --host 127.0.0.1 --port 9931 --no-webui --jinja --alias <model id> --chat-template-file
  config/llamacpp/<model>.jinja` (9931 is the v0.7.0 default port).
- Request: OpenAI-compatible `/v1/chat/completions` with `response_format` json_schema (the
  arm's schema from `prompts/`), `seed` = sample index 0/1/2, `max_tokens` 16,000,
  `cache_prompt: false`, `chat_template_kwargs.current_date` = UTC date of the issue time.
- Sampling, explicit on every request: gpt-oss-20b temperature 1.0, top_p 1.0, top_k 0, min_p 0
  (openai/gpt-oss README); Olmo-3.1-32B-Instruct temperature 0.6, top_p 0.95 (its
  generation_config.json), top_k 50 (its card's example), min_p 0. top_k 0 and min_p 0 switch
  off llama.cpp defaults no card asks for; all other samplers stay at their neutral defaults.
  gpt-oss reasoning effort stays at the template default (`medium`).
- The harness calls local servers through its own small HTTP client (`laf.llamacpp`), never
  through an OpenAI-compatible shim for Claude.
- Chat templates are the ones embedded in the GGUFs with one patch each
  (`config/llamacpp/`): gpt-oss's `Current date: strftime_now(...)` becomes `Current date:
  current_date`, emitted only when the kwarg is passed, so no model sees the real "today"
  (llama-server test-renders templates without kwargs at startup, so a missing kwarg omits the
  line instead of raising); Olmo's gets `tools` defaulting to `none`, which llama-server needs to
  accept it and which renders as transformers does. Olmo's template has no date line.
- Each run checks the server's `/props` (alias, GGUF, context, one slot, template SHA-256) and
  renders the first request through `/apply-template` (issue date and `Reasoning: medium`
  present for gpt-oss, today's date absent).
- Local runs write `runs/<block>-<model>/requests.jsonl` and `results.jsonl` in the Message
  Batches layout, so the frozen `scoring-v1` code loads and scores them unchanged (effort
  `medium` for gpt-oss, `none` for Olmo); attempts go to an uncommitted `local_log.jsonl`.
- Mac and Windows outputs differ even with equal seeds; the machine is logged per run.
  Exact values, hashes and smoke results: docs/model-registry.md, "Local serving".

Update (2026-10-21/22): adapted models are served on the same registered gpt-oss settings plus
`--lora <adapter>.gguf` and their own alias; `laf.llamacpp` refuses unless `/lora-adapters`
shows exactly the registered adapter at scale 1. Their runs, and every E3 run, are written one
level down (`runs/extensions/`, `runs/e3/`), outside the frozen analysis's `runs/*/` glob and so
outside the registered forecasters' invalid-answer penalty pool.
