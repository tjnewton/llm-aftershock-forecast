# CLAUDE.md

Benchmark scoring LLM aftershock forecasts against USGS operational forecasts (OSI Hackathon,
Oct 21-22, 2026). Plan: docs/PLAN.md. Rules that bind the analysis: docs/preregistration.md.

## Commands
- `uv run pytest` / `uv run ruff format src tests` / `uv run ruff check src tests` / `uv run pyright`
- Data: `uv run laf fetch|asof|tables|items --snapshot ID` (`--config config/sequences_e3.toml`
  for E3), `laf verify`, `laf prompts-hash`, `laf spend`
- Scoring (no API): `laf figures`, `laf e1 --model M`, `laf e3`, `laf combined`, `laf replicates`,
  `laf literature`, `laf live-score`; local models: `python -m laf.llamacpp` (docstring)
- Spends money, ask first every time: `laf smoke`, `laf pilot`, `laf run`, `laf live`, `laf probe`.
  Adaption launches (`laf adaption launch`) also need a yes.

## Layout
`src/laf/` package; `config/sequences.toml` roles; `data/raw` immutable + `data/manifest.jsonl`;
`data/processed/<snapshot>/`; `prompts/` templates and schemas; `docs/adr/` decisions;
`results/` score tables; exploratory runs in `runs/e3/` and `runs/extensions/`, outside the frozen
analysis's `runs/*/` glob; changes after `prereg-v1` go in `docs/deviations.md`.

## Guardrails
- Never post to Slack or any chat.
- Commits use the email 54011699+tjnewton@users.noreply.github.com, never another address.
- No API spend without explicit approval; ~$200 total cap (guard $195); use only `ANTHROPIC_API_KEY` from env/.env.
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
