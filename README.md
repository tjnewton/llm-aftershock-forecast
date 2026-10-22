# LLM aftershock-forecast benchmark

Do general-purpose LLMs give calibrated aftershock forecasts? This benchmark gives a model the
information the USGS operational aftershock forecast (OAF) had at an issue time (the mainshock
and the ComCat catalog so far) and scores its count quantiles and large-aftershock
probabilities against what happened and against the official forecast, on sequences after the
model's training cutoff. Entry for the Open Scientific Intelligence Hackathon, Oct 21-22, 2026.

**Status:** complete for the hackathon. The design was preregistered
([docs/preregistration.md](docs/preregistration.md), tag `prereg-v1`) and the scoring code frozen
(tag `scoring-v1`) before any result was read. Results:
- Write-up: [docs/writeup.md](docs/writeup.md); figures in [figures/](figures/).
- Frozen analysis notebook, rendered: [results/analysis.html](results/analysis.html)
  (source [notebooks/analysis.py](notebooks/analysis.py)).
- Interactive explorer (marimo, WASM): https://tjnewton.github.io/llm-aftershock-forecast/
  (branch `gh-pages`, source [notebooks/explorer.py](notebooks/explorer.py)).
- Exploratory extensions after the freeze (39 more sequences, adapted open models, a combined
  forecast, a second live round): [docs/deviations.md](docs/deviations.md), tables in
  [results/](results/).
- Live Panama forecasts, hashed before their windows opened: tags `live-panama-1`,
  `live-panama-2`.

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
Scoring and outputs (no API calls): `laf figures`, `laf e1`, `laf e3`, `laf combined`,
`laf literature`, `laf live-score`; `uv run marimo export html notebooks/analysis.py -o
results/analysis.html`. Local models: `python -m laf.llamacpp` (see its docstring).
Calls that spend money (`laf smoke`, `laf pilot`, `laf run`, `laf live`, `laf probe`) need
`ANTHROPIC_API_KEY` in the environment or an untracked `.env` (see `.env.example`).

## Layout
| Path | Contents |
|---|---|
| `src/laf/` | `oaf` (forecast parsing/validation), `catalog`, `usgs` (fetch + manifest), `asof` (catalog as of a past time), `generic_rj` (USGS generic RJ + completeness by regime), `etas` (legacy USGS ETAS port), `etas_validate`, `tables`, `items`, `prompts`, `providers`, `pilot`, `cli` |
| `config/sequences.toml` | sequences and roles (outcome-blind rules); `sequences_e3.toml`: exploratory E3 set |
| `data/raw/`, `data/manifest.jsonl` | immutable downloads with URL, time, size, SHA-256 |
| `data/processed/<snapshot>/` | parquet tables, `items.jsonl`, ETAS refit forecasts |
| `runs/` | batch requests and results per model and block, local-model runs, live rounds, ETAS validation, Adaption records (`runs/e3/`, `runs/extensions/`: exploratory) |
| `prompts/` | templates, JSON schemas, rationale, hashes |
| `docs/` | [plan](docs/PLAN.md), [preregistration](docs/preregistration.md), [research brief](docs/research-brief.md), [data card](docs/data-card.md), [model registry](docs/model-registry.md), [ADRs](docs/adr/), [event checklist](docs/event-checklist.md), [open questions](docs/open-questions.md) |

## Licence and data
Code: MIT ([LICENSE](LICENSE)). Derived tables and prompts: CC BY 4.0. Raw USGS data are U.S.
public domain; cite the ANSS Comprehensive Earthquake Catalog and the USGS aftershock forecast
products ([data/LICENSE.md](data/LICENSE.md)). Citation: [CITATION.cff](CITATION.cff).
