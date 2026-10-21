# ADR 0008: Local model serving

Status: proposed.

## Decision
- llama.cpp `llama-server` (v0.7.0, released 2026-10-15) on both machines: Homebrew on the M3 Max
  Mac (Metal), the `win-cuda-13.4-x64` release zip natively on the Windows RTX 5090 box (it
  includes Blackwell sm_120 kernels; the cuda-12.4 zip does not). No WSL2 needed: the harness is
  pure Python with pathlib and talks HTTP to the server.
- Request: OpenAI-compatible `/v1/chat/completions` with `response_format` json_schema, fixed
  `seed`, fixed `temperature`, `cache_prompt: false`, server started with `--parallel 1` when
  exact reproducibility matters.
- The harness calls local servers through its own small HTTP client, never through an
  OpenAI-compatible shim for Claude.
- gpt-oss chat templates inject the current date by default; we pass a template or system
  content that sets the date to the issue date, so no model sees the real "today".
- Mac and Windows outputs differ even with equal seeds; the machine is logged per run.
