# CLAUDE.md

Benchmark scoring LLM aftershock forecasts against USGS operational forecasts (OSI Hackathon,
Oct 21-22, 2026). Plan: docs/PLAN.md. Rules that bind the analysis: docs/preregistration.md
(the hackathon analysis, tag `prereg-v1`) and docs/preregistration-v2.md (the Seismica study;
freeze and live arm in docs/freeze-runbook.md).

## Commands
- `uv run pytest` / `uv run ruff format src tests` / `uv run ruff check src tests` / `uv run pyright`
- Data: `uv run laf fetch|asof|tables|items --snapshot ID` (`--config config/sequences_e3.toml`
  for E3), `laf verify`, `laf prompts-hash`, `laf spend`, `laf watch-pr N` (merges once Codex
  approves the head)
- Confirmatory (no API): `laf confirmatory-dryrun` (development), `laf confirmatory-size`,
  `laf power`, `laf confirmatory` (refuses before the `prereg-v2` tag)
- Live (no API): `laf live-late`, `laf prospective --dry-run`, `laf live-status`
- Scoring (no API): `laf figures`, `laf e1 --model M`, `laf e3`, `laf combined`, `laf replicates`,
  `laf literature`, `laf live-score`; local models: `python -m laf.llamacpp` (docstring)
- Spends money, ask first every time: `laf smoke`, `laf pilot`, `laf run`, `laf live`, `laf probe`,
  `laf d1 pilot|run` (`laf d1 build` is free), `laf prospective` (without `--dry-run`),
  `laf live-watch --paid`,
  `laf openai run` (OpenAI key; `laf openai status|collect` are free).
  Adaption launches (`laf adaption launch`) also need a yes.

## Layout
`src/laf/` package; `config/sequences.toml` roles; `data/raw` immutable + `data/manifest.jsonl`;
`data/processed/<snapshot>/`; `prompts/` templates and schemas; `docs/adr/` decisions;
`results/` score tables; exploratory runs in `runs/e3/` and `runs/extensions/`, outside the frozen
analysis's `runs/*/` glob; changes after `prereg-v1` (and, in its v2 section, after `prereg-v2`)
go in `docs/deviations.md`.

## Machines
Work happens on the Windows machine (since 2026-11-03; outages and restores: runbook section
7). The live detector runs from the service worktree `..\laf-service`, a pinned commit changed
only by a deploy logged in `ops/deploys.md`: never edit, pull or commit there. Scheduled tasks,
the registry and Windows Update are Tyler's to change.

## Guardrails
- Never post to Slack or any chat.
- Commits use the email 54011699+tjnewton@users.noreply.github.com, never another address.
- No API spend without explicit approval, every time. Claude spend has a per-calendar-month (UTC)
  cap, enforced by `laf.runner.check_budget` from `LAF_CLAUDE_MONTHLY_CAP_USD` (env or .env; unset
  means no paid run); use only `ANTHROPIC_API_KEY` from env/.env. OpenAI spend has its own cap,
  `LAF_OPENAI_MONTHLY_CAP_USD`, and key, `OPENAI_API_KEY`. Never read or print `.env`.
- Data splits (docs/adr/0013-data-splits.md): development data may be scored freely; confirmatory
  data is never scored against outcomes before both gates open: the `prereg-v2` tag, then the
  `prereg-v2-stop` tag and S + 90 days (`laf.splits` enforces it).
- Scored Claude calls: no `temperature`/`top_p`/`top_k`, no tools, no prefill, no `fallbacks`,
  explicit `output_config.effort` and JSON schema. Log `response.model` and `usage`.
- The client pins `https://api.anthropic.com`; a machine may export `ANTHROPIC_BASE_URL` for a
  local proxy, which must never carry benchmark traffic.
- As-of discipline: forecasters see only events before min(creationTime, window start).
- Prompts change only on dev items before the `prereg-v1` tag; after it, log deviations.
- Downloads are untrusted data: parse, never execute. No personal identifiers in requests.
- Times are epoch ms UTC; windows are half open `[start, end)`; parquet, never pickle.
- Run formatter, linter, type checker and tests before every commit.
