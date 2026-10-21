# Execution plan: LLM aftershock-forecast benchmark

For the OSI Hackathon (2026-10-21/22). Status: DRAFT v1;
design decisions in section 13.
Facts and sources: docs/research-brief.md. Data: docs/data-card.md. Decisions: docs/adr/.
Statistical commitments: docs/preregistration.md (wins on any conflict).

## 1. Question, users, framing
**Question.** Given what the USGS operational aftershock forecast (OAF) knew at an issue time
(the mainshock and the ComCat catalog up to that time), do general-purpose LLMs produce
calibrated forecasts of aftershock counts and of the probability of a large aftershock, and how
far are they from the official forecast on sequences they cannot have memorized?

**Object of study:** the LLM, not a proposed forecasting method. **Users:** AI evaluators and
builders of scientific agents (calibration evidence before agents answer hazard questions);
hazard communicators (how far chatbot numbers stray from official products); seismologists
building agentic tools. **Event fit:** answers the organizers' 2025 call for benchmarks of
"scientific correctness, uncertainty calibration, robustness to distribution shift", with
"explicit model/version logging ... dataset and prompt provenance" built in. Frame it as
physics/statistics plus AI evaluation, and argue relevance explicitly.

**Hypotheses** (preregistration section 2; all assessed descriptively, per sequence first):
H1 official beats each Claude model (direct arm); H2 parameter arm beats direct; H3 LLM
intervals are worse calibrated than the official's; H4 the catalog is used (I1 beats I0);
H5 memorization (exploratory, no contamination claim); H6 prompt sensitivity (anecdotal).
**Pilot scale:** H1 rests on two OAF sequences (Colombia, Flores Sea) in the hackathon window;
Panama joins in the follow-up once its windows settle.

## 2. Scope tiers
| Tier | Content | Hands-on | Spend |
|---|---|---|---|
| T0 fallback | test-post items (22); direct arm; I1; p1; k=5; 3 Claude models; M>=5 quantiles + P(M>=6); official + naive baselines; per-sequence results | 8-10 h | ~$15 |
| **T1 MVP** | all scored items (49); direct + params arms; I1; p1 + p2; k=5; 3 Claude models; recall probe; official + generic-RJ + RJ-MLE + naive baselines; primary + secondary scores; figures; live Panama hash; write-up; video | 13-15 h | ~$80-100 |
| T2 full | T1 + I0 ablation on test-post items + Sonnet effort=low + two local models (unattended on the RTX 5090) | +2 h | +~$15 |
| T3 stretch | anonymized-prompt arm; NB log score; Mizrahi `etas` spatio-temporal refit (paper stage) | +3-6 h | small |

Decision rule on the day: if the Haiku canary has not returned valid results by 14:00 ET on
Oct 21, drop to T0. If T1 results are scored by 12:00 ET Oct 22, add finished T2 analyses.

## 3. Data specification
Source of truth: `data/processed/<snapshot>/` built by `laf tables` (columns and quality
findings: docs/data-card.md). Unit ("cell"): sequence x issue time x window (1 Day, 1 Week,
1 Month) x target (M>=5 count quantiles; P(M>=6); exploratory M>=4 quantiles).
- Sequences and roles: outcome-blind rules (ADR 0006): test-post Chiapas, Colombia, Flores Sea,
  Panama; ambiguous Sarangani, Venezuela; test-pre Sand Point, Kamchatka, Hubbard Glacier; dev
  Aomori, Sanriku.
- Issue times: ADR 0004 (first valid OAF version or origin + 0.3 d; targets 1/3/7/14/28 d;
  information cutoff = min(creationTime, window start)).
- Regions: ADR 0002. The query circle is centred on the epicentre and covers every scoring
  circle x1.5 (`issue_times.query_covers_x1_5`, all true).
- Mainshock magnitude in prompts: the OAF's `magMain` for OAF issues (what USGS used), the
  ComCat magnitude otherwise.
- Observed count: events in the scoring circle with origin in `[time_start, time_end)` and
  magnitude >= threshold, from the scoring snapshot. **Primary cells closed >= 21 days before
  the snapshot**; 2-day settling is a sensitivity analysis.
- Catalog advantage: `issue_times.comcat_m5_at_cutoff - oaf_obs_m5` per OAF issue
  (data-card table), reported in every comparison with the official forecast.
- Scoring snapshot 20261021T1027Z: 61 issue times (test-post 22, test-pre 16, ambiguous 11,
  dev 12).

## 4. Elicitation design
### 4.1 Factors
| Factor | Levels | Applies to |
|---|---|---|
| Model | claude-opus-5-5, claude-sonnet-5-5, claude-haiku-5-5; gpt-oss-20b, Olmo-3.1-32B-Instruct | all |
| Arm | `direct`, `params` | all |
| Information | `I1` (catalog), `I0` (no catalog) | I0 on test-post items only (T2) |
| Paraphrase | `p1`, `p2` | Claude; local `p1` only |
| Effort | `high` (all Claude); `low` (Sonnet sensitivity, T2) | Claude |
| Sample | k = 5 (Claude), k = 3 seeds (local) | all |

### 4.2 Call counts per Claude model (full T2)
| Block | Items | Arms | Info | Paraphrases | k | Calls |
|---|---|---|---|---|---|---|
| Core | 49 (test-post 22, test-pre 16, ambiguous 11) | 2 | I1 | 2 | 5 | 980 |
| Information ablation | 22 test-post | 2 | I0 | 1 | 5 | 220 |
| Recall probe | 8 sequences (scored, minus Panama) | - | - | 1 | 3 | 24 |
| Live Panama (Oct 21) | 2 (matched, strict) | 2 | I1 | 1 | 5 | 20 |
| Total | | | | | | 1,244 |

Plus Sonnet effort=low: 22 x direct x I1 x p1 x 5 = 110. Local models: 49 x 2 x I1 x p1 x 3 =
294 plus I0 22 x 2 x 3 = 132, so 426 calls each.

### 4.3 Prompts
Drafts in `prompts/` (rationale: prompts/README.md). Same information as USGS at the issue
time; no official numbers; the forecast circle stated; uniform place strings (the origin
product title, "125 km ESE of Petropavlovsk-Kamchatsky, Russia", never ComCat's post-hoc event
names); catalog CSV (M>=4.0, from 7 days before the mainshock, at most 800 most recent rows,
plus daily counts if truncated; `dist_km` from the epicentre). Iterate only on dev items, only
for format compliance; freeze with `prompts/HASHES.json` and `items.jsonl` in the prereg.

### 4.4 Output validation and failure taxonomy
Each sample gets exactly one status:
| Status | Rule |
|---|---|
| `ok` | parsed and passes all checks |
| `refusal` | `stop_reason == "refusal"` (record `stop_details.category`) |
| `max_tokens` | `stop_reason == "max_tokens"` |
| `schema_invalid` | not valid JSON for the schema (local models; or SDK parse failure) |
| `non_monotone` | any quantile set decreases |
| `out_of_range` | negative count; probability outside [0, 1]; params outside b in [0.3, 2.5], p in [0.3, 2.5], c in [1e-5, 10] d, a in [-6, 2], or a_p05 <= a_p50 <= a_p95 violated |
| `transport_error` | API/HTTP failure after retries (not the model's fault; rerun allowed) |
Warnings (scored anyway, rates reported): `incoherent_windows` (a day quantile above the week
or month quantile at the same level), `incoherent_magnitudes` (M>=5 quantile above M>=4),
`notes_too_long`. Retries: only HTTP 429/5xx/connection errors, at most 4 attempts with
exponential backoff (2, 4, 8 s, honour `retry-after`); the SDK's own retries are off
(`max_retries=0`) so every retry is logged. Primary scoring of invalid samples: worst log-QS of
any forecaster in the cell (prereg section 7).

### 4.5 API settings (Claude), verified against the docs and the claude-api skill
- `client.messages.create(model=<exact id>, max_tokens=..., system=..., messages=[...],
  output_config={"effort": "high", "format": {"type": "json_schema", "schema": <schema>}})`;
  `max_tokens` 32,000 in batches (no HTTP timeout; only used tokens are billed), 16,000 for
  synchronous calls (SDK non-streaming timeout).
- No `thinking` parameter (adaptive default; Opus 5.5 cannot disable it). No
  `temperature`/`top_p`/`top_k` (rejected). No assistant prefill (rejected). No `tools`, so no
  web access. No `fallbacks`/fallback beta (would swap the model under test).
- Bulk runs: `client.messages.batches.create(requests=[{"custom_id": <request key[:64]>,
  "params": {...}}])`; results arrive in any order and are joined by `custom_id`.
- Prompt caching: top-level `cache_control={"type": "ephemeral"}` so the k samples of a prompt
  can share a prefix; report `usage.cache_read_input_tokens`. Optional (input cost is small).
- Log per call: request key, full params, `response.id`, `response.model`, `stop_reason`,
  `stop_details`, `usage`, latency, SDK version, timestamps (implemented in
  `laf.providers.call_anthropic`).
- Credentials: `ANTHROPIC_API_KEY` from the environment or the untracked `.env` only
  (`laf.providers.api_key`); never other credential stores.
- Endpoint pinned to `https://api.anthropic.com` (`laf.providers.API_BASE_URL`): an inherited
  `ANTHROPIC_BASE_URL` (this machine exports one for a local compression proxy) is ignored, and
  `base_url` is logged per call. Found when 3 smoke calls went through the proxy;
  those results are discarded and the key was rotated.

## 5. Forecast construction, baselines and scoring
### 5.1 Converting each forecaster to the common representation
Common representation per cell: nine quantiles of N(M>=5) and N(M>=4) at K = {0.025, 0.05,
0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.975}, plus P(N(M>=6) >= 1); full CDF where available.
- **Direct arm:** as returned.
- **Params arm:** `rj_predictive(params, mag_main, windows)`. Rate 10^(a + b(Mm - M)) (t +
  c)^(-p) per day, t in days after the mainshock, Mm = `mag_main` shown in the prompt; expected
  count lambda(a) = 10^(a + b(Mm - M)) * I(t1, t2) with I = [(t2+c)^(1-p) - (t1+c)^(1-p)]/(1-p),
  or ln((t2+c)/(t1+c)) when |p - 1| < 1e-6. a follows a split normal: median a_p50, lower scale
  (a_p50 - a_p05)/1.645, upper scale (a_p95 - a_p50)/1.645. Predictive pmf = Gauss-Hermite (64
  nodes per half) mixture of Poisson(lambda(a)); quantile = smallest integer n with F(n) >= tau;
  P(M>=6) = 1 - E[exp(-lambda_6(a))]. Deterministic, no sampling. Poisson-mixture dispersion
  only; H2 is read as "format plus RJ structure", shown beside RJ-MLE.
- **Official (OAF):** `fractileValues` at the nine levels (exact grid points) of the selected
  version; `probability` of the M>=6 bin, scored as published (legacy-ETAS products report
  1 - share of catalogs at the smallest count, slightly below 1 when every catalog has an M>=6;
  ADR 0010 section 6). Full fractiles for PIT.
- **Generic RJ (T1; ADR 0009):** USGS's generic model for the sequence's Garcia regime, from
  the operational code (`laf.generic_rj`, values in `sequences.generic_*`): a ~ Normal(
  generic_a_mean, sigma(Mm)) truncated to [generic_a_min, generic_a_max], b, p, c fixed;
  Poisson mixture. Mainshock-only, so it is the information-matched reference for the I0 arm.
- **RJ-MLE refit (all sequences):** at each information cutoff, fit Omori-Utsu (K, c, p) by
  maximum likelihood (Ogata 1983) to events with M >= 4.95 in the scoring circle with
  origin_ms < time < cutoff and t >= t_c, where t_c is when the USGS completeness model
  (`MagComp.complete_after_days(Mm, 4.95)`, ADR 0009) reaches M4.95; c in [1e-4, 2] d, p in
  [0.5, 2.0]; b by Aki-Utsu MLE with binning correction (dM = 0.1), fixed at 1.0 if fewer than
  50 events. Convert to RJ a; uncertainty from the inverse Hessian; same mixture as the params
  arm. With fewer than 10 events: the generic RJ forecast above.
- **Naive (Omori-scaled persistence):** p = 1, c = 0.05 d fixed; K from the number of M>=5
  events with origin_ms < time < cutoff (never the mainshock); Poisson.
- **Legacy-ETAS refit (registered secondary baseline; ADR 0010):** a port of the USGS legacy ETAS code that wrote the published international
  products (Bayesian grid fit with the van der Elst generic prior, 10,000 simulated catalogs),
  refit at every information cutoff on the as-of catalog (ADR 0011): `uv run laf etas --snapshot
  S` writes `etas_forecasts.parquet` (`--catalog hindsight`: `etas_forecasts_hindsight.parquet`).
  On identical inputs it reproduces the USGS Java code exactly (MAP to full precision, forecasts
  within Monte Carlo noise); it reproduces the published Panama MAPs exactly and the Panama and
  Flores forecast distributions within noise (ADR 0010 section 4). The two catalogs split
  refit-vs-official differences into a catalog effect and a code-and-analyst effect.

### 5.2 Scores (ADR 0001)
Primary: log-scale quantile score (log-QS) for N(M>=5) averaged over K. Secondary: natural-
scale QS; coverage of 50/80/90/95% central intervals (with the official's and RJ-MLE's);
randomized PIT (full CDF where available; bin-width-normalized quantile-rank histograms for
the direct arm); Brier and clipped log score for P(M>=6), pooled over all scored roles.
Exploratory: M>=4 log-QS; NB log score.

### 5.3 Aggregation and statistics (prereg sections 1, 6, 7)
- Estimand: a single chatbot answer (mean over the k samples); ensembles reported beside.
- Per-sequence estimates first, with a within-sequence moving-block bootstrap over issue times
  (B = 10,000, seed 20261021); pooled two-stage bootstrap (sequences, then issues) second.
  No significance tests; a hypothesis is "supported" only if every sequence agrees in sign and
  the pooled 95% CI excludes 0.
- Non-overlapping-window subset co-reported; elapsed-time strata (< 1 d, 1-7 d, > 7 d).
- Sensitivity analyses: prereg section 6.

## 6. Contamination and look-ahead controls
- **Cutoffs:** Claude models: Jun 2026 (reliable knowledge and training data, models
  overview). Post-cutoff = origin on or after 2026-07-01; June 2026 = ambiguous.
  gpt-oss-20b (Jun 2024) and Olmo-3.1 (Dec 2024): every candidate is post-cutoff for them.
- **No contamination claim.** Two to three pre-cutoff sequences of very different size cannot
  separate memorization from difficulty, and pre/post score contrasts alone cannot detect
  leakage (arXiv 2608.02985). We report per-sequence values and the recall probe only.
- **Recall probe:** states the circle and 30 days; excludes Panama; scored against a Bath's-law
  baseline; `knows_event = true` on post-cutoff events is reported as a hallucination rate.
- **No tools, no web:** no `tools` in any request; local servers have no tool runtime.
- **As-of discipline:** prompts and baselines see only events with time < information cutoff,
  as ComCat showed them at the cutoff (`issue_catalogs`, ADR 0011; V0 reproduces 95.1% of the official
  products' own counts). Baselines additionally exclude the mainshock (time > origin).
- **Catalog revisions:** today's ComCat is used only for outcomes and for the catalog-effect
  analysis (refit on today's vs as-of catalog); deleted events are not reconstructed.
- **Dates in local chat templates:** gpt-oss injects the real date by default; we set the
  issue date (ADR 0008). Olmo injects its own cutoff text if no system message; we always send
  one.
- **Prompt iteration** on dev sequences only; prompts and items frozen at the tag.

## 7. Risk register
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Runner eats day 1 | Medium | High | Data, items, prompts, provider and pilot already built and tested; strict T0 cut-over at 14:00 ET |
| Thinking tokens blow the budget | Medium | Medium | Pilot measures tokens before the tag; preregistered ladder; workspace spend limit; cost about $15 + $0.020 per mean output token |
| max_tokens truncation at high effort | Medium | Medium | 32k in batches; truncations are a status, scored with the worst-in-cell penalty |
| Batch latency (up to 24 h; 39.5 min for a 3-request smoke batch) | Medium | High | Canary Haiku first, then Sonnet, then Opus by 14:00 ET; if Opus is not back by 08:00 ET Oct 22, drop Opus blocks via the ladder (never pay non-batch 2x) |
| Refusals on hazard questions | Low | Medium | Recorded as outcomes; neutral scientific framing; no fallbacks |
| Structured outputs fail or differ by model | Low | Medium | Smoke test today; schemas use only supported keywords |
| Local model reasoning broken by grammar | Medium | Low | Check on the 5090; unconstrained decoding + parser fallback |
| Live Panama window starts before the hash | Known | Low | Refetch about 11:50 ET; matched + strictly prospective variants |
| ComCat/OAF outage or 5xx on the day | Medium (502/504) | Medium | Resumable deterministic snapshots; snapshots on disk |
| Hindsight catalog biases H1 | Resolved | Low | as-of catalog from ComCat histories (ADR 0011; V0 95.1%); residual: deleted events |
| Judges see geoscience as off-topic | Medium | High | Lead with AI calibration; organizers' own words |
| Write-up not submitted later, so excluded from paper | Medium | High | One-page write-up in the 2025 template submitted with the entry |
| Secrets leak | Low | High | `.env` git-ignored and read-denied for the agent; pre-commit secret check |
| Requests routed via a proxy that rewrites prompts | Seen | High | Base URL pinned in code and tested; `base_url` logged per call |

## 8. Runbook
Times are US Eastern (EDT, UTC-4); the event runs on Central time (CT = ET - 1 h). Kick-off
9:00 CT = 10:00 ET Oct 21. Oct 21 10:00 to Oct 22 16:30 ET. Official deadline Oct 22
19:00 CT (20:00 ET); NC State says 18:00 ET. **Submit by 16:00 ET Oct 22.**

### Preparation
- [x] Data layer, items, prompt rendering, provider, smoke/pilot commands, 45 tests.
- [x] ADRs, prompts v1, data card.
- [x] Participant: new key in a Console workspace with a $150 limit, in `.env` (rotated).
- [x] `uv run laf smoke` ($0.002) and `uv run laf pilot --snapshot 20261021T1027Z` ($0.56):
      24/24 valid JSON; mean output tokens Haiku 7.1k, Sonnet 1.2k, Opus 1.6k
      (docs/model-registry.md).
- [x] Budget rule: projected T2 $54.29, no reduction. No prompt changes needed.
- [x] Smoke batch: 3/3 succeeded with structured outputs, but took 39.5 min for 3 tiny requests.
      Plan for at least 40-60 min per batch on event day.
- [x] Decided: `laf.forecast` and `laf.scoring` are built at the event;
      batch results are not retrieved before they are committed and tagged `scoring-v1`.
- [ ] Windows 5090: llama.cpp `win-cuda-13.4-x64`; gpt-oss-20b (12 GB) and Olmo-3.1-32B Q4_K_M
      (19.5 GB); one dev prompt each: reasoning present, JSON valid, tokens/s.
- [ ] `uv run laf fetch` (new snapshot) to capture Panama versions.

### Day 1: Oct 21
| ET | Task | Done when |
|---|---|---|
| 07:30-08:15 | Morning re-checks (docs/event-checklist.md); `laf fetch`; `laf tables`; `laf verify`; `laf items`; regenerate data card | snapshot S21 verified |
| 08:15-09:00 | First commits (code, data, docs). Fill prereg placeholders (snapshot, manifest, items and prompt hashes, src hash). Commit; tag `prereg-v1`; participant makes the repo public; push with tags; participant posts tag + SHA-256 to Slack | tag visible on GitHub |
| 09:00-11:30 | `schemas` (validation + statuses), `runner` (expand, cache, JSONL log, dry-run estimate, spend guard, batch submit/collect) + tests with a fake provider | dry run prints call count and cost |
| 11:30-11:50 | Submit Haiku core batch (canary) | batch id logged |
| 11:50-12:30 | **Live Panama:** `laf fetch --only us6000u18k`; build items; run matched + strict variants, 3 models, both arms, k=5; SHA-256; commit, tag `live-panama-1`, push; participant posts hash | tag pushed |
| 12:30-13:30 | Check canary statuses and a few rendered prompts; submit Sonnet then Opus batches (core, then T2 blocks); start local runs on the 5090 | batch ids logged |
| 13:30-17:00 | `forecast` and `scoring` with closed-form tests; tag `scoring-v1` before retrieving results | tests green, tag pushed |
| 17:00-19:00 | Collect batches; validate; score; first per-sequence table | scores.parquet |
| 19:00-20:00 | Buffer; deviations log; sleep | |

### Day 2: Oct 22
| ET | Task | Done when |
|---|---|---|
| 07:30-08:00 | Collect remaining batches and local runs; rerun transport errors | all collected |
| 08:00-11:00 | `analysis` + `figures`: per-sequence tables with block-bootstrap CIs, fan charts, coverage vs official, PIT, invalid rates, recall probe | figures from scripts |
| 11:00-13:00 | One-page write-up (2025 template, prose); README results; benchmark card | write-up |
| 13:00-14:30 | Video (<= 4 min; aim for 2 min to also fit the stale 2-min rule) | video exported |
| 14:30-15:30 | Score the live Panama 1-day windows (preliminary, unsettled); final commit; tag `v0.1-submission`; push | tag pushed |
| 15:30-16:00 | Participant submits the social post + write-up per Slack instructions | confirmation |

### Follow-up (after Oct 22)
Score Panama cells after 21-day settling (mid-November); score the live forecasts; add new
forecast-bearing sequences prospectively; Zenodo DOI; collective-paper write-up when invited;
expand toward an independent paper (section 12).

## 9. Compute and API budget
Cost model (batch prices): about $15 fixed (inputs at a mean of about 4.3k
tokens, measured by count_tokens before the run; unbatched pilot/live/probe) plus about $0.020
per mean output token per call (thinking included), for the full T2 design.

| Mean output tokens per call | 2,000 | 4,400 | 6,600 | 10,000 |
|---|---|---|---|---|
| Projected total (T2, batch) | ~$55 | ~$104 | ~$148 | ~$217 |

**Measured (dev pilot):** mean output tokens Haiku 7.1k, Sonnet 1.2k, Opus 1.6k; mean
scored input 4.3k (max 25.6k). Projection with the prereg's 1.25 safety factor: **$54.29**
(Opus $35.25, Sonnet $15.96, Haiku $3.08) plus local models (free). Dev prompts are smaller than
the median scored prompt, so the Haiku canary on Oct 21 re-measures before Sonnet and Opus.

**Cap $150 total**, enforced three ways: (1) a Console workspace spend limit on the new key;
(2) the harness ledger (`runs/spend.jsonl`, actual cost from `usage`) refuses any submission
whose estimate plus spend so far exceeds $140; (3) the preregistered reduction ladder (prereg
section 9), which holds the design under the cap up to about 14k output tokens per call.
Local models: about 1.3 M output tokens each, unattended on the 5090 (throughput measured).

## 10. Module and CLI specifications
Package `laf` (src layout). **Built and tested:** `oaf`, `catalog`, `registry`, `usgs`,
`tables`, `items`, `prompts`, `providers` (Claude call + params + cost), `pilot`, `cli` (`fetch`,
`tables`, `verify`, `smoke`, `pilot`). **To build**:
`schemas`, `runner`, `forecast`, `scoring`, `analysis`, `figures`, the llama.cpp client and the
`items`, `prompts hash`, `run`, `collect`, `score`, `report` commands.

### 10.1 `laf.items`
```python
class CatalogRow(BaseModel): t_days: float; utc_time: str; mag: float; mag_type: str; depth_km: float; dist_km: float
class WindowSpec(BaseModel): key: Literal["day", "week", "month"]; label: WindowLabel; start_ms: int; end_ms: int
class Item(BaseModel):
    item_id: str                  # == issue_id, e.g. "us6000tkt2@3d"
    sequence_id: str; role: Role; issue_ms: int; elapsed_days: float
    mainshock: Mainshock          # origin_ms/utc, place (origin title), lat, lon, depth_km, mag = magMain, mag_type
    region: Region                # scoring circle of the issue
    windows: list[WindowSpec]     # 3, from the OAF version or the schedule
    catalog: list[CatalogRow]     # M>=4.0, from origin - 7 d to issue_ms, <= 800 most recent
    truncated: bool; daily_counts: list[dict] | None
def build_items(tables: dict[str, pd.DataFrame]) -> list[Item]
```
Implemented in `src/laf/items.py`. CLI to add: `laf items --snapshot S` writes
`data/processed/S/items.jsonl` (sorted by item_id; its SHA-256 goes in the prereg).

### 10.2 `laf.prompts`
```python
PROMPT_DIR = Path("prompts")
def render(item: Item, arm: Arm, info: Literal["I0", "I1"], paraphrase: Literal["p1", "p2"]) -> tuple[str, str]  # (system, user)
def schema(arm: Arm | Literal["probe"]) -> dict
def template_hashes() -> dict[str, str]   # sha256 per file in prompts/
```
CLI: `laf prompts render --item ID --arm direct --info I1 --para p1` (print);
`laf prompts hash` writes `prompts/HASHES.json`.

### 10.3 `laf.schemas` (responses and validation)
```python
class Quantiles(BaseModel): q025: int; q050: int; q100: int; q250: int; q500: int; q750: int; q900: int; q950: int; q975: int
class WindowForecast(BaseModel): m5_count_quantiles: Quantiles; m4_count_quantiles: Quantiles; p_m6_at_least_one: float
class DirectForecast(BaseModel): day: WindowForecast; week: WindowForecast; month: WindowForecast; notes: str
class ParamForecast(BaseModel): b: float; p: float; c_days: float; a_p05: float; a_p50: float; a_p95: float; notes: str
Status = Literal["ok", "refusal", "max_tokens", "schema_invalid", "non_monotone", "out_of_range", "transport_error"]
def validate(arm, text: str | None, stop_reason: str | None) -> tuple[Status, BaseModel | None, list[str]]  # warnings
```
The JSON schemas sent to the API equal `prompts/schema_*.json`; a test asserts the pydantic
models and the files agree.

### 10.4 `laf.providers`
```python
class Request(BaseModel):  # canonical, hashed
    provider: Literal["anthropic", "llamacpp"]; model: str; system: str; user: str
    schema_name: str; schema_: dict; effort: str | None; max_tokens: int
    seed: int | None; temperature: float | None; sample_index: int
    meta: dict    # item_id, arm, info, paraphrase, block
    def key(self) -> str: ...   # sha256 of canonical JSON (sorted keys) of all fields except meta
class Response(BaseModel):
    key: str; status_http: int | None; text: str | None; stop_reason: str | None
    stop_details: dict | None; model_reported: str | None; usage: dict | None
    latency_s: float; started_utc: str; error: str | None; raw_id: str | None
def call_anthropic(client, params) -> dict           # implemented (providers.py): settings in 4.5, logged record
def batch_submit(client, reqs) -> str                # returns batch id; custom_id = req.key()[:64]
def batch_collect(client, batch_id) -> list[Response]
def call_llamacpp(base_url, req) -> Response         # POST /v1/chat/completions, response_format json_schema
```
Repeated samples of the same prompt differ only in `sample_index` (part of the key), so the
cache stores each sample separately.

### 10.5 `laf.runner`
```python
class RunConfig(BaseModel):  # runs/<name>.toml, validated
    name: str; snapshot: str; models: list[str]; arms: list[Arm]; infos: list[str]
    paraphrases: list[str]; k: int; effort: str; items: Literal["primary", "secondary", "all", "dev", "live"]
    batch: bool; max_tokens: int = 32000; seed: int = 20261021
def expand(cfg, items) -> list[Request]              # shuffled with cfg.seed (order effects)
def estimate(reqs, client) -> CostEstimate           # count_tokens for each distinct prompt; output tokens from the pilot ledger
def run(cfg, *, dry_run: bool) -> RunManifest
```
Storage: `runs/<name>/requests.jsonl` (append-only), `runs/<name>/responses.jsonl`
(append-only), `cache/<key[:2]>/<key>.json` (content-addressed; a cached key is never re-sent),
`runs/<name>/manifest.json` (git SHA, dirty flag, prompt hashes, schema hashes, data manifest
SHA-256, snapshot id, model ids, effort, SDK and package versions, platform, start/end UTC),
`runs/spend.jsonl` (cost per response from `usage` and the price table in
`config/prices.toml`). Spend guard: refuse if spent + estimate > `LAF_SPEND_CAP_USD` - 10.
CLI: `laf run runs/<name>.toml [--dry-run]`, `laf collect <name>`, `laf spend`.

### 10.6 `laf.forecast`
```python
def rj_expected(a, b, p, c, mag_main, mag, t1_days, t2_days) -> float
def rj_predictive(params: ParamForecast, mag_main: float, windows) -> dict  # split-normal a; quantiles, P(M>=6), cdf
def fit_rj_mle(catalog: pd.DataFrame, origin_ms, cutoff_ms, circle, mc=4.95, t_min_days=0.1) -> RJFit
def naive_forecast(n_m5_so_far, elapsed_days, windows) -> dict
def official_forecast(tables, item_id) -> dict
```

### 10.7 `laf.scoring` (pure functions)
```python
LEVELS = (0.025, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.975)
def pinball(q, y, tau) -> float
def quantile_score(qs: Sequence[float], y: int, *, log: bool = True) -> float
def interval_covered(qs, y, level) -> bool          # central 50/80/90/95 from LEVELS
def pit_rank(qs, y, rng) -> float                    # quantile-resolution randomized PIT
def pit_cdf(cdf, y, rng) -> float                    # randomized PIT with full CDF
def brier(p, event: bool) -> float
def log_score_binary(p, event: bool, eps=1e-3) -> float
```
CLI: `laf score <run>...` writes `results/scores.parquet` (one row per sample x cell x target);
`laf report` writes `results/summary.md` and `figures/*.png` (colour-blind-safe palette).

## 11. Test plan
Existing (46 tests): OAF parsing/validation with real golden files (ETAS, RJ, re-post, wrong
event, mutations), ComCat CSV parsing and count oracles, Wells & Coppersmith radii, haversine
properties (hypothesis), issue-time selection, calendar months, end-to-end tables from a golden
mini snapshot. To add at the event, test-first:
- `prompts` (done: determinism, no unrendered fields, I0 has no catalog, no official-forecast
  vocabulary, hashes; items: as-of guard, mainshock dist_km = 0, uniform place). To add: a
  stored golden rendering; pydantic response models == JSON schema files.
- `schemas.validate`: one test per status and warning using hand-written texts.
- `runner`: `expand` count equals the design table; keys stable across runs and platforms
  (golden hash); cache prevents a second call (fake provider counts calls); spend guard refuses
  over-cap batches; batch results joined by `custom_id` in shuffled order.
- `providers`: request params built for Anthropic contain no `temperature`, `tools`, `thinking`
  or `fallbacks`; contain `output_config.effort` and `format`; transport errors retried, 400
  not retried. No live API in CI.
- `forecast`: `rj_expected` matches the closed-form integral and a numerical quadrature;
  `rj_predictive` with zero a-uncertainty equals Poisson quantiles; split normal with equal
  scales equals the normal mixture; P(M>=6) equals 1 - exp(-lambda); RJ-MLE recovers
  parameters from a synthetic Omori catalog (seeded) within tolerance; naive and RJ-MLE never
  count the mainshock.
- `scoring`: pinball and QS against hand-computed values; QS is minimized in expectation by
  the true quantiles (property test with a known Poisson); coverage boundaries; PIT uniform for
  calibrated synthetic forecasts (KS test, seeded); Brier/log-score closed forms.
- CI: ruff format check, ruff, pyright, pytest (no network), `laf verify`.

## 12. Deliverables, submission and paper path
**Hackathon deliverables:** public repository (MIT code, CC BY 4.0 data); frozen benchmark
(items.jsonl + parquet + manifest); run manifests and JSONL logs; scores; figures; data card;
benchmark card; model registry; preregistration with tag; live Panama hash ledger; video;
one-page write-up.

**Submission checklist:** see docs/event-checklist.md (social post, video <= 4 min, one-page
write-up in the 2025 template: 2-3 line introduction, results with >= 1 figure, 1-2 sentences of
future work, GitHub link, CRediT roles, 4-6 references, prose only).

**Independent paper (SRL, The Seismic Record, Seismica, or a datasets-and-benchmarks track):**
prospective extension (every new OAF-bearing sequence for 6-12 months, preregistered and
hashed); more vendors and open models with documented cutoffs; a tool-using arm (agent may call
`etas`); catalog-based pyCSEP tests with a spatial kernel; power analysis; comparison with
expert elicitation (Schneider & Guttorp 2024); feedback from the USGS forecasting team on the
communication angle; Zenodo DOI and datasheet.

## 13. Design decisions
| Finding | Resolution |
|---|---|
| Holm/bootstrap p invalid with 2-3 clusters | Dropped significance; per-sequence estimates first; "supported" = sign agreement in every sequence + pooled CI |
| Naive replacement rewards failure | Worst log-QS of any forecaster in the cell |
| Outcome-dependent roles | Outcome-blind rules; Colombia joins test-post; Kumamoto (M6.8) dropped; Sand Point, Hubbard to test-pre; Sanriku to dev |
| Hindsight catalog; revised magnitude | as-of catalog for prompts and refit (ADR 0011); magMain in OAF prompts; catalog effect measured by the hindsight refit |
| dist_km from the drifting circle centre | Prompt distances computed from the epicentre (items.py); test: mainshock row is 0 km |
| Notability titles leak recall cues | Origin product title for every event; test |
| H3 ill-posed | Comparative coverage vs official and RJ-MLE; randomized PIT |
| params arm lacks overdispersion | H2 framed as format + RJ structure; RJ-MLE shown beside |
| Freeze order | Items, rendering, provider and pilot pre-tag; items.jsonl and src hashes in the tag; results not retrieved before `scoring-v1` |
| Cost/max_tokens/pilot size | 32k max_tokens in batches; pilot on the largest dev items; cost model and ladder in section 9 |
| 2x non-batch fallback | Removed; ladder instead; Haiku canary gate |
| Live Panama timing | Refetch about 11:50 ET; matched + strict-prospective variants |
| 2-day settling too short | 21-day settling for primary cells; Panama in follow-up |
| Probe confounded by Bath's law | Circle + 30 d stated; Bath baseline; Panama excluded; hallucination rate |
| Contamination claim unsupported | No contamination claim; DiD language removed |
| OAF vs schedule timing | Schedule "first" issue at 0.3 d; elapsed-time strata |
| Further analysis choices | Non-overlap subset co-reported; OAF-only resampling for H1; P(M>=6) pooled only; PIT normalized; ensemble beside single answers; H6 anecdotal |
| Query circle rule | Query centred on the epicentre covering every scoring circle x1.5; tested per issue |
| RJ-MLE Mc and fallback | Mc 4.95 from the USGS completeness model (ADR 0009); USGS generic RJ by Garcia regime as fallback and as a T1 baseline |
| Mainshock in "so far" counts | Baselines use time > origin; test listed |
| Whole-version rejection | Disclosed (affects Kamchatka 7d only); not changed |
| RJ convention | Prompt ties Mm to the stated magnitude and a to b; split normal |
| Local reasoning vs grammar | Check on the 5090; parser fallback |
