# Preregistration v2: LLM aftershock forecasts against USGS operational forecasts, retrospective and prospective

Status: **DRAFT, not frozen.** Tyler alone decides the freeze (tag `prereg-v2`). Items marked
**OPEN** still need his decision. Sources: ADRs 0013-0018 (decisions of 2026-10-30 and
2026-10-31) and the D1, D2 and settings-pilot results. Where this document and an ADR disagree
after the freeze, this document governs. Prereg v1 (tag `prereg-v1`) stays frozen and governs
the registered hackathon analysis.

## 1. Study and estimand
We compare probabilistic aftershock forecasts from general-purpose LLMs with the USGS
operational aftershock forecast (OAF) and with statistical baselines.
- **Information parity:** every forecaster sees the information the OAF had at each issue time.
  The as-of catalog rebuild reproduces the official products' observation counts in 99.05% of
  23,264 checks on the candidate set (ADR 0013).
- **Contamination:** each model is scored only on sequences whose mainshock falls after its
  training cutoff plus a 3-month buffer (section 3). In the prospective arm, contamination is
  impossible.

Per cell (issue time x window x target), dS = S(model) - S(official), where S is the log score
of the count distribution. Every forecaster is scored through its nine quantiles with the same
latent-PCHIP reconstruction (ADR 0015). Negative dS favors the model.
- **Primary estimand:** the mean over sequences of the per-sequence mean dS at M>=5.
- **Estimand of an answer:** one chatbot answer to a fixed prompt. The per-sample scores are
  averaged within a cell.

## 2. Hypotheses
| Id | Hypothesis | Set | Test |
|---|---|---|---|
| **A** (co-primary) | gpt-5.1 is non-inferior to the official forecast | retrospective, gpt-5.1's 88 clean M>=5 sequences | one-sided, delta = 0.10 nats per cell |
| **B** (co-primary) | Claude Opus 5.5 is non-inferior to the official forecast | prospective (on-time matched items) plus its clean retrospective M>=5 sequences | one-sided, delta = 0.10 |
| S1 (secondary) | Opus 4.6 is non-inferior | its 22 clean M>=5 sequences (M3/M4 targets on its 75 where complete) | one-sided, delta = 0.10, alpha 0.05 |
| S2 (secondary) | gpt-6.1-sol is non-inferior | prospective plus clean retrospective | as S1 |
| S3 (secondary) | each model beats the rule of thumb | as its primary or secondary set | superiority |
| S4 (secondary) | each model against the legacy-ETAS refit | as above | estimate and 95% CI |
| D (descriptive) | Sonnet 4.6; D1 behavioral probes; hindsight effect (ADR 0016) | as stated | no test |

- **Multiplicity:** a Holm correction across A and B. The first step tests at 0.025, the
  second at 0.05. Secondary tests are at 0.05 each and are labelled secondary.
- **Superiority** is reported whenever the one-sided interval lies below 0.

## 3. Models and settings
| Model | Training cutoff | Clean from | Settings | Role |
|---|---|---|---|---|
| `gpt-5.1-2025-11-13` | 2024-09-30 | 2025-01-01 | reasoning effort `medium` (ADR 0014 decision 6) | A |
| `claude-opus-5-5` | Jun 2026 | 2026-10-01 | registered request: no `thinking` field (adaptive by default), effort `high` | B |
| `claude-opus-4-6` | Aug 2025 | 2025-12-01 | `thinking: {"type": "adaptive"}`, effort `medium` (ADR 0014 decision 5) | S1 |
| `gpt-6.1-sol` | 2026-04-30 | 2026-08-01 | **OPEN**: effort from a pilot, as for gpt-5.1 | S2 |
| `claude-sonnet-4-6` | Jan 2026 | 2026-05-01 | `thinking: {"type": "adaptive"}`, effort `low` | D |

- **Requests (all models):**
  - No sampling parameters, no tools, no prefill, no server-side fallbacks.
  - A strict JSON schema (`prompts/v2/schema_direct.json`) and an explicit effort.
  - Base URLs pinned to the official APIs. `response.model` and `usage` are logged.
- **Prompt:** `v2A` (`prompts/v2/HASHES.json`). It asks for nine quantiles of N(M>=5),
  N(M>=4) and N(M>=3) and P(M>=6) per window, and shows the catalog from M3.0. `v2B` is a
  preregistered robustness check (ADR 0015 decision 4).
- **Samples:** **OPEN**, k samples per item (D2 used 3).
- **Unbuffered sensitivity:** the clean rule without the 3-month buffer.

## 4. Data, sequences and cells
- **Retrospective candidates:** every ComCat event with an OAF product from 2024-11-14 (the
  archive start) to 2026-10-29: 194 candidates (config/sequences_confirmatory.toml, snapshot
  20261029T2000Z).
  - Development sequences are excluded (registered, E3 and the E1 pool; config/splits.toml).
  - So are foreshocks and aftershocks of a larger event: inside its Wells-Coppersmith circle
    within 365 days (ADR 0006 rule; 10 of 254 OAF events).
  - Outcome exposure makes a sequence development; input exposure does not (ADR 0013).
- **Primary set:** M>=5 mainshocks in each model's clean period. US-regional-network
  M4.0-4.9 mainshocks are secondary. Test A's sensitivity analysis uses all of gpt-5.1's 174
  clean candidates (test B stays on M>=5).
- **Targets:** M>=5 (primary), M>=4, and M>=3 where the catalog is complete at M3 for the whole
  window (official Mc <= 3.0 and time-dependent completeness, ADR 0015; in practice the 35
  California candidates). P(M>=6) is reported.
- **Issue times and windows:** as ADR 0004, with day, week and month windows from each
  official version. Strata: under 1 day, 1 to 7 days, 7 days or more after the mainshock.
- **Outcomes:** ComCat counts in the official forecast's region circle and window. A cell is
  primary once its window closed at least 21 days before the outcome snapshot; 2 days is a
  sensitivity analysis.
- **Prospective inclusion:** every new valid OAF version of a sequence that qualifies by the
  same rules (`laf.prospective.qualifies`).

## 5. Prospective protocol (ADR 0017)
- **Detection:** ComCat is polled every 10 minutes. Each new OAF version gets two items:
  - a **matched** item, on the version's own windows;
  - a **strict** item, whose windows open at the next full hour at least 30 minutes after
    detection.
- **Per issue:**
  - the live models' answers (k samples) and the baselines on the same items (generic RJ,
    RJ-MLE, the rule of thumb, the legacy-ETAS refit);
  - one sealed record (`laf.prospective.seal`) with its SHA-256 and an OpenTimestamps proof,
    committed in real time to the `live` branch.
  - Full forecasts are published after their windows close, with a note that they are not
    official forecasts.
- **Eligibility:** a matched item enters test B only if its record was sealed before its first
  window opened. Late, missed and failed items are listed and never backfilled. Strict items
  serve the contrast with the baselines on identical windows.
- **Stopping rule:** new sequences stop entering at whichever comes first: 6 months after live
  forecasting starts, or 26 eligible prospective M>=5 sequences (33 for test B with the clean
  retrospective ones). There is one analysis, after the last windows close, and no early
  stopping.
- **No interim looks:** no one computes confirmatory scores or tests before the stop.
- **OPEN:**
  - the strict window rounding (next full hour or next 10 minutes), after the forecast
    latency is measured;
  - the live start date;
  - which models run live (proposed: Opus 5.5 and gpt-6.1-sol).

## 6. Analysis (ADR 0018; `laf.confirmatory`)
- **Primary:** the sequence block bootstrap (B = 10,000, fixed seed) over per-sequence mean dS.
  The upper bound is the (1 - alpha) percentile; non-inferior if it lies below 0.10.
- **Beside the mean:**
  - the 10% trimmed mean and the median of the sequence effects, with bootstrap intervals;
  - the hierarchical model dS_ijk = mu + u_i + v_ij + e_ijk, with window and stratum as fixed
    effects (a robustness check, not confirmatory).
- **Sensitivity analyses:**
  - test A on all clean candidates;
  - v2B;
  - full-distribution scores of the official and ETAS forecasts;
  - the unbuffered clean rule;
  - the 2-day settling rule;
  - results by stratum.
- **Software:** `laf confirmatory --snapshot S --runs DIR` refuses to run until the tag
  `prereg-v2` exists.

## 7. Invalid outputs
- An invalid answer (schema violation, cut off at the output cap, refusal, non-monotone or out
  of range) gets the worst score of any valid forecast in its cell: every valid answer and
  every baseline (prereg v1 rule).
- Transport errors are left out.
- Invalid rates are reported per model.

## 8. Budget
Claude spend is capped per calendar month (`LAF_CLAUDE_MONTHLY_CAP_USD`) and OpenAI spend
separately (`LAF_OPENAI_MONTHLY_CAP_USD`). Every paid batch is approved by Tyler with its cost
estimate. A run the budget cannot cover is reported, not silently dropped. **OPEN:** the cost
plan for the confirmatory runs (models x sequences x issues x k), spread across months.

## 9. Freezing procedure
Tyler tags `prereg-v2` on a commit that holds this document. The tag's commit hash, and the
SHA-256 of this document, `prompts/v2/HASHES.json` and the items files, are posted publicly.
The tag unseals confirmatory outcomes in the software (`laf.splits`). Confirmatory runs and
live forecasting start after the tag.

## 10. Changes from prereg v1
- **Data:** 194 confirmatory candidates instead of the registered sequences; prospective
  sequences counted toward a test.
- **Scoring:** log score of the count distribution as the primary score instead of the
  log-scale quantile score, with representation-matched scoring.
- **Tests:** formal non-inferiority tests with a margin and a multiplicity correction instead
  of descriptive hypotheses.
- **Models:** older-cutoff and other-vendor models with study settings fixed by pilots.
- **Prompts:** v2 with M3 targets.
- **Prospective arm:** strict and matched items with a stopping rule instead of the v1
  demonstration.

## 11. Deviations
Changes after the freeze go in docs/deviations.md with their reasons.
