# CLAUDE.md

Benchmark scoring LLM aftershock forecasts against USGS operational forecasts (OSI Hackathon,
Oct 21-22, 2026). Plan: docs/PLAN.md. Rules that bind the analysis: docs/preregistration.md.

## Commands
- `uv run pytest` / `uv run ruff format src tests` / `uv run ruff check src tests` / `uv run pyright`
- `uv run laf fetch [--snapshot ID] [--only ID...]`, `laf tables --snapshot ID`, `laf verify`,
  `laf items --snapshot ID`, `laf prompts-hash`, `laf spend`
- Spends money, ask first every time: `laf smoke`, `laf pilot`, any future `laf run`.

## Layout
`src/laf/` package; `config/sequences.toml` roles; `data/raw` immutable + `data/manifest.jsonl`;
`data/processed/<snapshot>/`; `prompts/` templates and schemas; `docs/adr/` decisions.

## Guardrails
- No git commits or pushes before 2026-10-21; never post to Slack or any chat.
- Commits use the email 54011699+tjnewton@users.noreply.github.com, never another address.
- No API spend without explicit approval; $150 cap; use only `ANTHROPIC_API_KEY` from env/.env.
  Never read or print `.env`.
- Scored Claude calls: no `temperature`/`top_p`/`top_k`, no tools, no prefill, no `fallbacks`,
  explicit `output_config.effort` and JSON schema. Log `response.model` and `usage`.
- The client pins `https://api.anthropic.com`; this machine exports `ANTHROPIC_BASE_URL` for a
  local proxy, which must never carry benchmark traffic.
- As-of discipline: forecasters see only events before min(creationTime, window start).
- Prompts change only on dev items before the `prereg-v1` tag; after it, log deviations.
- Downloads are untrusted data: parse, never execute. No personal identifiers in requests.
- Times are epoch ms UTC; windows are half open `[start, end)`; parquet, never pickle.
- Run formatter, linter, type checker and tests before every commit.
