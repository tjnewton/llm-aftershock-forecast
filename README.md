# Do AI chatbots forecast aftershocks as well as the USGS?

A preregistered, contamination-aware benchmark. Language models get exactly what the US
Geological Survey (USGS) knew when it issued each official aftershock forecast, and both are
scored against what happened, on earthquakes after the models' training cutoff. Entry for the
Open Scientific Intelligence Hackathon, Oct 21-22, 2026.

**[Write-up](docs/writeup.md)** ·
**[Interactive explorer](https://tjnewton.github.io/llm-aftershock-forecast/)** (runs Python in
your browser; about 15 s to load) ·
**[Full analysis](https://tjnewton.github.io/llm-aftershock-forecast/analysis.html)**

![Forecasts for the Flores Sea sequence and every forecaster against USGS](figures/headline.png)

*(a) Forecasts of the number of magnitude 5+ aftershocks in the next week, made at six times
after the M7.8 Flores Sea earthquake: shaded bands are the 50% and 90% ranges, dots what
happened. (b) Average score difference from the USGS forecast on the preregistered test, with
95% intervals; left of zero is better than USGS.*

## What we found
- **Claude Opus 5.5 sits in the top tier with the USGS forecast** and its statistical model
  (ETAS): we found no difference, on the two preregistered sequences or on 18 more recent ones
  (exploratory). Sonnet 5.5 tied on the first and was very slightly worse on the second. Two
  sequences cannot separate the top tier (even a naive baseline ties USGS there), which is why
  the benchmark grows with every new USGS forecast.
- **The benchmark does separate weaker forecasters.** Haiku 5.5 and the small open models
  (gpt-oss-20b, Olmo 3.1 32B) are clearly worse than USGS, and the open models often give
  unusable answers (12% and 54%, against at most 2.7% for Claude). Fine-tuning gpt-oss-20b to
  imitate statistical forecasts for 515 past sequences fixed the format but not the skill.
- **Context matters:** without the list of recent quakes, Sonnet was clearly worse, and asking
  for model parameters instead of direct forecasts made every model worse.
- **No sign of memorization:** Claude did no better on sequences from before its training
  cutoff, and the open models, trained before both sets, kept the same gap on both.
- USGS and Opus both under-predicted the early Flores Sea aftershocks (panel a).

![Every forecaster against USGS, preregistered and exploratory](figures/overview.png)

## Why trust it
- **Preregistered:** hypotheses and analysis frozen (tag `prereg-v1`, SHA-256 posted publicly)
  before any scored call; scoring code frozen (tag `scoring-v1`) before any result was read.
  Later additions are labelled exploratory ([deviations](docs/deviations.md)).
- **No hindsight:** each prompt holds only the earthquake catalog as it stood at the forecast
  time, rebuilt from ComCat's revision histories (it reproduces 95.1% of USGS's own counts).
- **No memorization:** test sequences began after the models' training cutoffs; earlier
  sequences serve as a contamination check.
- **Prospective:** live forecasts for the ongoing M7.7 Panama sequence were hashed and published
  before their windows opened (tags `live-panama-1`, `live-panama-2`).
- **Reproducible:** every download is hashed in `data/manifest.jsonl`, and every result
  regenerates offline (below). Total API cost: $64.

## Why it matters
After a large earthquake, people ask chatbots how many more shocks to expect. To our knowledge
this is the first test of language-model aftershock forecasts against an operational product
([novelty search](docs/research/novelty-and-literature.md)). The design (information-matched
prompts, as-of data, post-cutoff tests, hashed live forecasts) carries over to other operational
science forecasts.

## Built with
Claude Haiku, Sonnet and Opus 5.5 (Anthropic API) as forecasters; gpt-oss-20b and Olmo 3.1 32B
served locally with llama.cpp; **Adaption** AutoScientist for fine-tuning gpt-oss-20b (LoRA);
**Valency** for the fixed literature search and citation checks; **marimo** for the analysis
notebook and the in-browser explorer; USGS ComCat and operational aftershock forecast products
for the data.

## Reproduce (no API calls, no network)
```bash
uv sync && uv run laf verify                                       # re-hash every raw file
uv run marimo export html notebooks/analysis.py -o results/analysis.html   # registered analysis
uv run laf figures --snapshot 20261021T1027Z                       # figures/ and explorer data
uv run laf e3 --snapshot 20261021T2300Z                            # exploratory tables
```

<details>
<summary>Terms, commands and layout</summary>

**Terms.** *Aftershocks* follow a large *mainshock*; *M5+* means magnitude 5 or larger. A
forecast is issued at an *issue time* for the next day, week and month (*windows*). *ETAS* and
*Reasenberg-Jones* are the standard statistical models behind the USGS forecast. Scores are
*log-scale quantile scores* (lower is better); *dQS* is a forecaster's score minus the official
forecast's.

**Commands.** `uv run pytest` (tests use real USGS golden files, no network); data: `laf fetch`,
`laf tables`, `laf asof`, `laf items`, `laf etas`, `laf etas-validate` (each takes
`--snapshot`); scoring: `laf figures`, `laf e1`, `laf e3`, `laf combined`, `laf replicates`,
`laf literature`, `laf live-score`; local models: `python -m laf.llamacpp`. Calls that spend
money (`laf smoke`, `laf pilot`, `laf run`, `laf live`, `laf probe`) need `ANTHROPIC_API_KEY`.

| Path | Contents |
|---|---|
| `src/laf/` | the `laf` package: data, as-of catalog, baselines, prompts, runners, scoring, figures |
| `config/` | sequences and their roles; `sequences_e3.toml` is the exploratory set |
| `data/raw/`, `data/manifest.jsonl` | immutable downloads with URL, time, size and SHA-256 |
| `data/processed/<snapshot>/` | parquet tables, benchmark items, ETAS refit forecasts |
| `prompts/` | templates, JSON schemas, hashes |
| `runs/` | every model request and answer; `runs/e3/`, `runs/extensions/` are exploratory |
| `results/`, `figures/`, `notebooks/` | score tables ([guide](results/README.md)), figures, analysis notebook and explorer |
| `docs/` | [preregistration](docs/preregistration.md), [deviations](docs/deviations.md), [data card](docs/data-card.md), [model registry](docs/model-registry.md), [decisions](docs/adr/) |
| `ops/` | the task queue the two machines shared during the overnight runs |

</details>

## Licence and data
Code: MIT ([LICENSE](LICENSE)). Derived tables and prompts: CC BY 4.0. Raw USGS data are U.S.
public domain; cite the ANSS Comprehensive Earthquake Catalog and the USGS aftershock forecast
products ([data/LICENSE.md](data/LICENSE.md)). Citation: [CITATION.cff](CITATION.cff).
