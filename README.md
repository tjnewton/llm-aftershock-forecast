# LLM aftershock-forecast benchmark

Do general-purpose LLMs give calibrated aftershock forecasts? This benchmark gives a model the
information the USGS operational aftershock forecast (OAF) had at an issue time (the mainshock
and the ComCat catalog so far) and scores its count quantiles and large-aftershock
probabilities against what happened and against the official forecast, on sequences after the
model's training cutoff. Entry for the Open Scientific Intelligence Hackathon, Oct 21-22, 2026.

**Status:** Data layer, as-of catalogs, item building,
prompt rendering and the legacy-ETAS baseline (validated against the USGS Java code) are built
and tested; no LLM forecasts have been elicited yet. The design is preregistered
in [docs/preregistration.md](docs/preregistration.md) (frozen at tag `prereg-v1` on Oct 21).

## Quick start
```bash
uv sync                                   # Python 3.12, locked dependencies
uv run pytest                             # tests use real USGS golden files, no network
uv run laf fetch                          # new raw snapshot from ComCat + every OAF version
uv run laf tables --snapshot <SNAPSHOT>   # tidy parquet tables in data/processed/<SNAPSHOT>/
uv run laf verify                         # re-hash every raw file, re-validate every forecast
uv run laf asof --snapshot <SNAPSHOT>     # ComCat product histories -> catalog as of each issue time
uv run laf items --snapshot <SNAPSHOT>    # benchmark items (what each forecaster may see)
uv run laf etas --snapshot <SNAPSHOT>     # legacy-ETAS refit baseline (docs/adr/0010-etas-refit.md)
uv run laf etas-validate --snapshot <SNAPSHOT>  # validation vs official products, USGS Java, synthetic truth
```
Calls that spend money (`laf smoke`, `laf pilot`, later `laf run`) need `ANTHROPIC_API_KEY` in
the environment or an untracked `.env` (see `.env.example`).

## Layout
| Path | Contents |
|---|---|
| `src/laf/` | `oaf` (forecast parsing/validation), `catalog`, `usgs` (fetch + manifest), `asof` (catalog as of a past time), `generic_rj` (USGS generic RJ + completeness by regime), `etas` (legacy USGS ETAS port), `etas_validate`, `tables`, `items`, `prompts`, `providers`, `pilot`, `cli` |
| `config/sequences.toml` | sequences and roles (outcome-blind rules) |
| `data/raw/`, `data/manifest.jsonl` | immutable downloads with URL, time, size, SHA-256 |
| `data/processed/<snapshot>/` | parquet tables, `items.jsonl`, ETAS refit forecasts |
| `runs/` | API call logs, ETAS validation reports, archived USGS Java runs |
| `prompts/` | templates, JSON schemas, rationale, hashes |
| `docs/` | [plan](docs/PLAN.md), [preregistration](docs/preregistration.md), [research brief](docs/research-brief.md), [data card](docs/data-card.md), [model registry](docs/model-registry.md), [ADRs](docs/adr/), [event checklist](docs/event-checklist.md), [open questions](docs/open-questions.md) |

## Licence and data
Code: MIT ([LICENSE](LICENSE)). Derived tables and prompts: CC BY 4.0. Raw USGS data are U.S.
public domain; cite the ANSS Comprehensive Earthquake Catalog and the USGS aftershock forecast
products ([data/LICENSE.md](data/LICENSE.md)). Citation: [CITATION.cff](CITATION.cff).
