# Preregistration: calibration of LLM aftershock forecasts against USGS operational forecasts

Status: **v1, frozen at tag `prereg-v1`.** Freezing procedure: section 12. Where this document
and docs/PLAN.md disagree, this document governs.

## 1. Study and estimand
We elicit forecasts of aftershock counts and of the probability of a large aftershock from
general-purpose LLMs, given the information the USGS operational aftershock forecast (OAF) had
at each issue time, and score them against ComCat observations and the official forecast with
proper scoring rules. The estimand is the quality of **a single chatbot answer** to a fixed
prompt (per-sample scores averaged over samples); quantile-averaged ensembles are reported
beside it. This is a **pilot**: with 2-4 sequences per group, results are estimates conditional
on these sequences, not population claims. No significance tests are used for claims.

Information parity: the LLM and the refit baselines see the ComCat catalog as it stood at each
issue time, rebuilt from ComCat's product histories (ADR 0011): the events, magnitudes and
locations USGS's own fetch would have returned. The rebuild reproduces the official products'
own observation counts in 95.1% of 674 checks (V0). Today's revised catalog holds more events (for example
Flores' first version: 56 M>=3 events today vs 19 then); it is used only for outcomes and for
the catalog-effect analysis. Residual differences: deleted events are not reconstructed, and
any shown event without a history falls back to its current origin (`n_hindsight_m4`, required
to be 0 at the freeze). The prompt states the mainshock magnitude USGS used (`magMain`).

## 2. Hypotheses (directional predictions, assessed descriptively)
log-QS: log-scale quantile score for N(M>=5) (ADR 0001). dQS(X, R): mean over cells of log-QS(X)
minus log-QS(R); negative favours X. "OAF cells": scored cells of test-post issue times that
have an official forecast (Colombia, Flores Sea; Panama only in the follow-up, section 4).

| Id | Prediction | Quantity | "Supported" if |
|---|---|---|---|
| H1 | The official forecast beats each Claude model (direct arm, I1) | dQS(model, official) on OAF cells, per sequence and pooled | dQS > 0 in every OAF sequence and the pooled 95% CI excludes 0 |
| H2 | The parameter arm (RJ structure + elicited parameters) beats the direct arm | dQS(params, direct), same model, test-post cells | < 0 in every test-post sequence, pooled CI excludes 0 |
| H3 | Direct-arm intervals are less well calibrated than the official's | coverage of central 50/90% intervals and randomized-PIT KS distance, minus the official's (and minus RJ-MLE's) | LLM coverage error larger than official's in every OAF sequence |
| H4 | The catalog is used | dQS(I1, I0), direct arm, test-post cells | < 0 in every test-post sequence, pooled CI excludes 0 |
| H5 | (exploratory) Memorization | recall-probe accuracy above the Bath's-law baseline, pre vs post; rate of `knows_event = true` on post-cutoff events (hallucination) | descriptive only; no contamination claim is made |
| H6 | (exploratory) Prompt sensitivity | paraphrase effect vs sample spread | anecdotal (two paraphrases) |

H2 compares "elicitation format plus Reasenberg-Jones structure" with direct elicitation; the
RJ-MLE refit, which shares the structure, is always shown beside the parameter arm.

## 3. Models and settings
- Claude: `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5`; `output_config.effort =
  "high"`; adaptive thinking (parameter omitted); no sampling parameters; no tools; no
  server-side refusal fallbacks; structured output via `output_config.format` with the schemas
  in `prompts/`; `max_tokens = 32000` in batches (16000 for synchronous calls); Message Batches
  API for bulk runs; `response.model`, `usage`, `stop_reason`, `stop_details` logged.
- Sensitivity: `claude-sonnet-5-5` at effort `low` (test-post, direct, I1, p1).
- Local (secondary): `openai/gpt-oss-20b` (cutoff Jun 2024) and
  `allenai/Olmo-3.1-32B-Instruct` (cutoff Dec 2024, open data), llama.cpp `llama-server` with
  JSON-schema constrained decoding (unconstrained decoding plus the same parser if the
  check shows constrained decoding breaks reasoning), temperature from the model
  card, seeds 0/1/2, system message always present, template date set to the issue date.
- Samples: k = 5 per prompt (Claude), k = 3 (local), subject to the budget rule (section 9).

## 4. Data, sequences and cells
- Scoring snapshot: 20261021T1027Z (taken 2026-10-21), data manifest SHA-256
  9e70d0f8ed43b74807aa7a31df102627bcdd1b734f4a999a3840c52bed7672a4, `items.jsonl` SHA-256
  fc7825e23421be618677fe2924a48a523b68d7084ac5f2629355b4ebd44b628f (every rendered prompt is
  reproducible from it and `prompts/HASHES.json`).
- Code: `src/laf` SHA-256 1275e16b2dfb683067a71d117180c43162aebc393edbfd978eefdf74e91484d4
  (`find src/laf -name '*.py' | sort | xargs shasum -a 256 | shasum -a 256`).
- **Sequences and roles (outcome-blind rules, ADR 0006)** from ComCat M>=7.0 mainshocks with
  origin 2025-07-01 to 2026-10-14, excluding foreshocks/aftershocks of a larger listed event:
  test-post = every such event from 2026-07-01 (offshore Chiapas, Colombia, Flores Sea, Panama);
  ambiguous = every such event in June 2026 (Sarangani, Venezuela); test-pre = every such
  event before June 2026 with an OAF product (Sand Point, Kamchatka, Hubbard Glacier);
  dev = Aomori and Sanriku (pre-cutoff, no OAF; prompt iteration only, never scored).
- Issue times: ADR 0004 (first valid OAF version, or origin + 0.3 d without OAF; plus targets
  1/3/7/14/28 d; information cutoff min(creationTime, window start)). OAF versions failing
  schema validation or the event-match check are never used.
- **Primary cells:** windows 1 Day, 1 Week, 1 Month that closed at least 21 days before the
  scoring snapshot (ComCat M>=5 counts keep changing for weeks). Cells closing later
  (including all Panama cells) are scored in a follow-up with a later snapshot and reported
  separately; a 2-day-settling version is a sensitivity analysis.
- Exclusions: none beyond these rules. No sequence, issue or cell is dropped after seeing
  results. Every run, including failed ones, is reported. New sequences after the tag go to a
  separate prospective set only.

## 5. Outcomes
- Primary: log-QS for N(M>=5) over K = {0.025, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.975}.
- Co-primary: invalid-output rate by model, arm and status.
- Secondary: natural-scale QS; coverage of 50/80/90/95% central intervals (reported with the
  official's and RJ-MLE's coverage); randomized PIT (full-CDF where available; bin-width-
  normalized quantile-rank histograms otherwise); Brier and clipped log score for P(M>=6),
  pooled over all scored roles only (0 positive test-post cells under the primary rule).
- Exploratory: M>=4 log-QS (incompleteness caveat); NB log score; ensembles; recall probe.
- Observed counts: ComCat events in the cell's scoring circle with origin in [start, end) and
  magnitude >= threshold - 1e-6, from the scoring snapshot.

## 6. Analysis
- References: the official forecast (its fractiles at K) on OAF cells; the USGS generic RJ
  forecast for the sequence's Garcia regime (ADR 0009; reference for the I0 arm), the RJ-MLE
  refit and the naive forecast (PLAN 5.1) on all cells; the legacy-ETAS refit (ADR 0010,
  secondary), `etas_forecasts.parquet` SHA-256
  ff6c3c6423c1240d71bfa963b64a7dc8eaeb03c08b68001e872d91bfebee60aa, computed on the scoring
  snapshot before any LLM run.
- Catalog effect: dQS(refit on today's catalog, refit on the as-of catalog) on all cells
  (`etas_forecasts_hindsight.parquet` vs `etas_forecasts.parquet`): how much a forecaster gains
  from ComCat's later revisions. Code-and-analyst effect: dQS(as-of refit, official) on OAF
  cells, reported with each sequence's V3 emulation result (ADR 0010 section 4). Both beside H1.
- The refit stays a registered baseline if `uv run laf etas --snapshot S --validate` (seed
  offset 0) exits 0; otherwise it is reported as exploratory. Other seed offsets are reported
  only.
- Sensitivity variant (labelled, not a baseline): the refit with analyst settings inferred from
  the official Colombia and Venezuela products (`etas_forecasts_analyst.parquet`,
  `config/analyst_settings.toml`; ADR 0010 section 4.1), reported beside the registered refit on
  those sequences' cells.
- Official P(M>=6) is the published `probability` of the M>=6 bin, scored as published. For
  legacy-ETAS products it is 1 - (share of simulated catalogs at the smallest count), slightly
  below 1 when every catalog has an M>=6 (negligible under the clipped log and Brier scores).
- Parameter-arm forecasts: `laf.forecast.rj_predictive` exactly as specified in PLAN 5.1
  (split-normal over a from the three elicited quantiles; Gauss-Hermite mixture of Poisson).
- Uncertainty: per-sequence estimates with a within-sequence moving-block bootstrap over
  issue times (B = 10,000, seed 20261021), shown first; pooled estimates with a two-stage
  bootstrap (sequences, then issue times) as secondary. H1 resamples only OAF-bearing
  sequences.
- Overlap: primary uses all primary cells; the non-overlapping subset (all 1-Day; 1-Week at
  first/7d/14d/28d; 1-Month at first only) is co-reported.
- Stratification: every pooled table is also shown by elapsed-time bin (< 1 d, 1-7 d, > 7 d).
- Sensitivity analyses: valid-only; region radius x0.5 and x1.5; issues later than 1 day only;
  without Kamchatka; without Chiapas (17 days after the cutoff month); issues where
  |comcat_m5_at_cutoff - oaf_obs_m5| <= 1; 2-day settling; 1-Day windows only; Sonnet effort low.

## 7. Invalid outputs and refusals
Statuses (PLAN 4.4): ok, refusal, max_tokens, schema_invalid, non_monotone, out_of_range,
transport_error. **Primary analysis: an invalid sample (every status except transport_error)
receives the worst log-QS of any forecaster (any model's valid sample or any baseline) in that
cell.** Valid-only scoring is a sensitivity analysis; invalid rates are a co-primary outcome.
transport_error samples are retried (at most 4 attempts, HTTP 429/5xx/connection only); if
still failing at analysis time they are excluded and counted. Refusals are never re-asked or
routed to another model. Warnings (incoherent windows or magnitudes) do not invalidate a sample.

## 8. Recall probe
One closed-book question per scored sequence except Panama (too recent for a 30-day answer),
k = 3 per Claude model. Scored deterministically: largest aftershock within the stated circle
and 30 days within 0.2 magnitude units; N(M>=5, circle, 30 d) within a factor of 2. Baseline:
Bath's law (Mm - 1.2) and the USGS generic-RJ median 30-day count (ADR 0009); we report accuracy above that baseline and the share
of `knows_event = true` on post-cutoff events (a hallucination indicator).

## 9. Budget rule (applied once, before scored runs, from the pilot)
Projected cost = sum over planned calls of (count_tokens input x price) + (pilot mean output
tokens per model x 1.25 x price), batch discount applied. If above $135, apply in order until it
is not: (a) Opus k 5 to 3; (b) drop the Opus I0 block; (c) Opus p2 only on test-post items;
(d) drop Sonnet effort low; (e) Sonnet k 5 to 3. Applied steps are recorded in the run
manifest and the deviations log. Runs start with a Haiku canary (core block), checked for
status rates and rendered prompts, before Sonnet and then Opus are submitted.

## 10. Prospective element (demonstration, not evidence)
On 2026-10-21, after refetching Panama at about 12:00 ET (versions appear about 15:52 UTC
daily), two forecasts are issued with all three Claude models, both arms, I1, p1, k = 5:
(a) matched to the newest official version (its windows; information cutoff as ADR 0004);
(b) strictly prospective, with windows starting at the next full hour after the outputs are
hashed. The SHA-256 of the outputs JSONL is committed, tagged `live-panama-1` and pushed; the
participant posts the hash publicly. Both are scored when their windows close and settle, and
reported separately from the analyses above.

## 11. Exploratory extensions (sponsor platforms)
These never enter H1-H6 and change no registered arm, prompt, item or baseline. They are
reported in a separate section of the results. No Anthropic spend.

- **E1, adapted open model (Adaption AutoScientist).** `openai/gpt-oss-20b` fine-tuned with
  LoRA by supervised learning. Training rows are prompts rendered with the registered template
  (direct arm, I1, p1) at schedule issue times (origin + 0.3 d, 1/3/7/14/28 d), with today's
  ComCat catalog. The rows cover ComCat M>=6.5 mainshocks with origin 2010-01-01 to
  2025-06-30, excluding foreshocks and aftershocks of a larger listed event (ADR 0006 rule).
  No benchmark sequence falls in this range. If fewer than 1,000 rows result (the platform
  minimum), the start date moves back in whole years until there are 1,000. Each completion is
  the legacy-ETAS refit forecast (ADR 0010, code defaults) for that issue time, written in the
  direct-arm schema. No observed count enters training. The training data are used as built:
  no prompt rephrasing, no web search ("hallucination mitigation" off). The checkpoint is the
  one AutoScientist reports as best. Dev items serve only as a format check (valid-JSON rate),
  with no score-based selection on any benchmark item. Evaluation runs the adapted model and
  base `gpt-oss-20b` under the section 3 local settings (direct arm, I1, p1, k = 3) on all
  scored items. Reported: dQS(adapted, base) and dQS(adapted, legacy-ETAS refit) on all
  primary cells, dQS(adapted, official) on OAF cells, and invalid rates; descriptive only.
- **E2, literature exposure (Valency MCP Bond).** For each benchmark sequence, the number of
  distinct papers (deduplicated by DOI or arXiv id) about that mainshock. Fixed queries:
  "<name> earthquake <year>" and "<year> M<magnitude> <name> aftershocks". Each paper is
  screened by title and abstract for the specific mainshock. Counts are split by first
  publication date: before each model's documented cutoff (docs/model-registry.md) and before
  each issue time. Query results are stored as raw files with manifest lines. The counts are a
  descriptive contamination covariate shown beside H5; no claim rests on them.
- **Analysis notebook (marimo).** `notebooks/analysis.py` renders every table and figure of
  sections 5-8 from `laf.scoring`. It is committed and tagged with the scoring code
  (`scoring-v1`, section 12) before batch results are retrieved. An interactive results
  explorer (marimo, exported as static HTML) is presentation only.

## 12. Freezing procedure
Before any scored call: 
(1) fill every [placeholder]; (2) write `prompts/HASHES.json` and `items.jsonl`;
(3) record the SHA-256 of `src/laf/` at the tag; (4) commit; (5) compute
`shasum -a 256 docs/preregistration.md`; (6) `git tag -a prereg-v1` with that SHA-256 in the
message; (7) make the repository public and push commit and tag; (8) the participant posts the
tag, commit SHA and file SHA-256 in the hackathon Slack. Batch results are not retrieved until
the scoring code (`laf.forecast`, `laf.scoring`) is committed and tagged `scoring-v1`, unless it
was already frozen at `prereg-v1`. Record after freezing:
- Commit: 1c15325b25204dca48066eff1a22fb9d4f332f83  - File SHA-256: 1d8d3722d5a963a24efbd4f03f00437e9e13a8bcf74daed086eb17a0e75281b1  - Tag: prereg-v1  - Pushed (UTC): 2026-10-21T14:08:44Z

## 13. Deviations
Any change after the tag is logged in `docs/deviations.md` with UTC time, reason and expected
effect, and reported in the write-up.
