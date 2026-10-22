# Research brief: verified fact base

> Historical: the pre-event fact base (Oct 19-20). Later facts are in the ADRs, the model
> registry and docs/deviations.md.

Every claim has a source and access time (UTC). Longer ledgers with every query: 
docs/research/event.md, data-availability.md, models-and-tooling.md,
novelty-and-literature.md, plus this session's own checks.

## Changes
1. **OAF windows often start before `creationTime`** (Flores up to -6 h, Venezuela -9 h,
   Kamchatka -7 d on a re-post); USGS's own data cutoff is the window start (Kamchatka v72 to
   v73: +6 M>=5 observations between two versions created 6 min apart). Issue time must be
   min(creationTime, timeStart), not creationTime. [data-availability.md sec. 6; this session,
   `oaf_versions.window_offset_min`, snapshot 20261021T1027Z]
2. **Wrong-event products:** Kamchatka's first `oaf` product is a Myanmar forecast created
   before the Kamchatka mainshock; Flores' first is byte-identical to Colombia's v2. [this
   session; data-availability.md item 4]
3. **Malformed products:** two Kamchatka versions have trailing commas (invalid JSON); seven have
   non-monotone fractiles; 2025 products round `median`/`p95*` to 2 significant figures. [this
   session, tests/golden]
4. **Catalog revisions continue:** Panama day-1 M>=5 count in the OAF circle 14 (notes) to 16;
   Panama v1's `observations` (22/11/1 at M3/5/6) vs ComCat now
   (36/14/1); Flores v2 saw 19 M>=3, ComCat now 56. [data-availability.md item 8; V0,
   snapshot 20261021T1027Z]
5. **FDSN `starttime` ignores fractions of a second**, so "mainshock + 1 ms" still returns the
   mainshock; counts in the old notes used +1 s and are consistent. [this session]
6. **The OAF has no M>=4.5 bin** (bins M>=3, 4, 5, 6, 7, 8), so the planned M>=4.5 secondary
   target has no official baseline. [forecast.json, all versions]
7. **gpt-oss-20b has a documented cutoff of June 2024; Qwen3.8-27B has none** (released
   2026-08-14). Olmo-3.1-32B-Instruct documents Dec 2024 with open training data. [models-and-
   tooling.md A]
8. **Prompt sizes are about 3k tokens, not 11k**: median 39 catalog rows at M>=4 per issue,
   maximum 759 (Kamchatka 14 d). [this session, `issue_catalogs`]
9. **Closest new work** (non-LLM): GitHub `Lsace/global-aftershock-forecast-benchmark` (2026-07,
   ETAS/RJ at 0.01/0.1/1-day issue times for global M>=6.5); PISAS v1.0
   (egusphere-2026-4241). LLM forecasting methods: QuantSightBench (arXiv 2604.15859), "How
   proper scoring rules shape LLM forecasting" (2608.28482), "Temporal leakage in LLM
   backtesting" (2608.02985: pre/post-cutoff score comparison alone cannot detect leakage).
   [novelty-and-literature.md]
10. **Design:** outcome-blind roles
    (Colombia and Sand Point added, Kumamoto dropped), no significance tests (pilot scale),
    worst-in-cell penalty for invalid outputs, 21-day settling (Panama scored in follow-up),
    `magMain` in prompts, uniform place strings, epicentre distances. Details: PLAN
    section 13.
11. **The published international forecasts come from the USGS legacy ETAS code**
    (`etas/GraphicalForecast.java`, van der Elst generic priors), not the newer `oetas`; the
    minimum simulated magnitude (minMag) rule changed four times in 2025-26, which matters
    when b > 1 (about 3x for Kamchatka). The 2025 Kamchatka products came from a Feb-2025 build
    (minMag 5.8, read from their own fractiles) while the 2026 sequences used minMag 3.0; with
    each product's revealed minMag our port reproduces all five ETAS sequences (V2 72/75;
    ADR 0010 section 3.5; docs/research/legacy-etas-formulas.md). On identical inputs the port
    equals the USGS Java code (MAP to full precision, forecasts within Monte Carlo noise), and with
    the catalog rebuilt as of each issue time (ADR 0011) it reproduces the Panama, Flores and
    Kamchatka forecast distributions within noise. Colombia and Venezuela were issued with
    analyst settings visible only in the published MAPs (a regime override to SZ-GENERIC for
    Venezuela's first month; c pinned at 0.003 and 0.1 and changing regimes for Colombia); with
    them, all five ETAS sequences are emulated within noise.
12. **The catalog USGS saw can be rebuilt** from ComCat's product histories: it reproduces the
    official products' own observation counts in 95% of 674 checks (today's catalog: 69%), so
    the LLM prompts use it and the hindsight-catalog caveat no longer applies (ADR 0011).

## Event (event.md)
| Fact | Source |
|---|---|
| Scope: "the physical sciences and mathematics"; "LLMs, autonomous agents, datasets, benchmarks, models, and scientific software are all fair game"; no page names Earth science | https://llmhackathon.github.io/about/ |
| Deadline Oct 22, 7:00 PM CT (8 PM ET); NC State "6 PM ET (tentative)"; Luma ends 6 PM CT | https://llmhackathon.github.io/agenda/ ; https://ncsu-osi-hackathon-materials-2026.github.io/ ; https://luma.com/ku88xh92 |
| Submission: social media post, optional video up to 4 min, write-up up to 1 page; /submission/ and FAQ still show 2025 rules (2-min video, materials/chemistry relevance) | agenda; https://llmhackathon.github.io/submission/ |
| No 2026 rubric, tracks, prizes, credits or prior-work rules published; updates "in Slack first" | agenda; event.md |
| 2025 paper: 120 submissions, 88 included; "not included ... due to incomplete documentation submission by the teams"; calls for benchmarks of "uncertainty calibration, robustness to distribution shift"; reproducibility via "explicit model/version logging, ... dataset and prompt provenance" | https://arxiv.org/html/2605.03205v1 |
| 2025 write-up template (commit ff496d2): intro 2-3 lines; results with >= 1 figure/table; 1-2 sentences future work; GitHub/demo links; CRediT; 4-6 references; prose only | https://github.com/llmhackathon/2025-arXiv-paper/blob/ff496d2/template.tex |
| Luma open, free, no approval (1,848 registered, 1,152 spots left) | https://luma.com/ku88xh92 |

## USGS data
| Fact | Source |
|---|---|
| forecast.json keys: creationTime, expireTime, advisoryTimeFrame, template, injectableText, observations, model{name, parameters incl. regionType/regionCenterLat/regionCenterLon/regionRadius, Mc or Mcat}, fractileProbabilities, barLabels, forecast[4 windows x bins], nextForecastTime | https://earthquake.usgs.gov/product/oaf/us6000u18k/us/1791593712688/forecast.json |
| ETAS: 399 fractiles 0.0025-0.9975; RJ: 197 fractiles 0.01-0.99; windows 1 Day / 1 Week / 1 Month (calendar, 30-31 d) / 1 Year | golden files in tests/golden |
| All versions via `includesuperseded=true`; product URL contains updateTime | https://earthquake.usgs.gov/fdsnws/event/1/query?eventid=us6000u18k&format=geojson&includesuperseded=true |
| 254 events carry OAF, 252 since 2024-11-01; 7 of 23 M>=7 events since 2025-06-01 have OAF | data-availability.md sec. 1 |
| Scoring snapshot 20261021T1027Z (11 sequences, 374 files; the fetch was resumed after truncated USGS responses); Panama: 13 versions (12 valid, distinct cutoffs) as of 10:27 UTC; first created 2026-10-10 00:51 (6.9 h after the mainshock), ETAS Mc 4.95; 1-week M>=5 median 12 (95% 3-38) | this session |
| Version counts (valid / all): Flores 30/34, Kamchatka 61/80, Venezuela 36/45, Colombia 21/24, Hubbard Glacier 68/68 (RJ) | docs/data-card.md |
| Query limit 20,000 rows; CSV includes magType and updated; international magnitudes one decimal | data-availability.md sec. 11 |
| USGS data are U.S. public domain (works of the U.S. Government, 17 U.S.C. 105) | **Not re-verified:** www.usgs.gov copyright pages returned HTTP 403 from this machine ; the claim rests on the earlier notes and the statute |

## Models and API
| Fact | Source |
|---|---|
| Opus 5.5, Sonnet 5.5, Haiku 5.5, Fable 5.1: reliable knowledge cutoff and training data cutoff Jun 2026 | https://platform.claude.com/docs/en/about-claude/models/overview.md |
| Prices $/MTok in/out: Opus 5.5 4/20 (cache read 0.20), Sonnet 5.5 2/10 (0.10), Haiku 5.5 0.10/0.50 (0.01, prompts <= 100K); batch 50% off | https://platform.claude.com/docs/en/about-claude/pricing.md |
| Opus 5.5 default effort medium, thinking cannot be disabled; Sonnet 5.5 default high, `disabled` is a 400; Haiku 5.5 default medium; non-default sampling params rejected; no prefill; forced tool_choice rejected | models overview; claude-api skill (cached 2026-10-06) |
| Structured outputs: `output_config.format = {type: json_schema, schema}`; `minItems` only 0/1; numeric bounds unsupported | https://platform.claude.com/docs/en/build-with-claude/structured-outputs.md |
| Minimum cacheable prefix 512 tokens on Opus/Sonnet 5.5 | https://platform.claude.com/docs/en/build-with-claude/prompt-caching.md |
| Batches: results in any order, keyed by custom_id; most finish within 1 h, max 24 h | claude-api skill, python/batches.md |
| anthropic Python SDK 1.15.0 (uses httpx2); `messages.create` and `count_tokens` accept `output_config` | PyPI; local introspection |
| gpt-oss-20b cutoff Jun 2024; Olmo-3.1-32B-Instruct Dec 2024; Gemma 4 Jan 2025; Qwen3.8-27B undocumented | models-and-tooling.md A (18:44-18:54 UTC) |
| llama.cpp v0.7.0 (2026-10-15): `response_format` json_schema, `seed`, `--parallel`; Windows `win-cuda-13.4-x64` zip has sm_120 | models-and-tooling.md B |
| Python 3.12 is the only minor version all needed packages support (floatcsep < 3.13; numpy 2.5 >= 3.12); pycsep 0.8.0 has a Brier score since 0.7.0; `etas` MIT, GitHub only | models-and-tooling.md C |

## Novelty (novelty-and-literature.md)
25 arXiv, 16 OpenAlex, 12 Semantic Scholar (10 rate-limited), 4 OpenReview, 18 GitHub and 8
web queries found **no study that scores a general-purpose LLM as an aftershock or seismicity
forecaster with proper scoring rules**. Absence in these indexes is not proof. Closest work:
QuakeGen (arXiv 2607.24109; trained ML beating USGS RJ), EarthquakeNPP (TMLR), arXiv 2608.18791,
Mousavi et al. 2024 GJI (10.1093/gji/ggae436), Schneider & Guttorp 2024 (10.1785/0320240008),
EMNLP 2025 main.153, ForecastBench (ICLR 2025), the GitHub benchmark above.

## Unverified or open
- 2026 submission route, rubric and paper policy (not published).
- Local-model throughput on the RTX 5090 (not measured; Windows box not accessible here).
- ~~Batches with structured outputs~~ Verified: 3/3 succeeded, 39.5 min turnaround for a
  3-request batch.
- ~~Generic RJ parameters~~ Resolved: taken from the USGS operational code `opensha/opensha-oaf`
  (CC0, commit 08a274bd) and validated against the first USGS RJ
  products for Sand Point and Hubbard Glacier (ADR 0009).
