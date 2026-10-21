# Novelty check and literature base

Project: score general-purpose LLMs (Claude, open-weight models) as aftershock forecasters. The models give count quantiles and P(≥1 M≥6) at issue times. Scoring uses WIS, coverage, randomized PIT and Brier, with the USGS operational aftershock forecast (RJ/ETAS) as the reference. Test sequences fall after the June 2026 training cutoff.

Search: Raw API responses, query lists and parsers are saved in the session scratchpad (`scratchpad/agent-novelty/raw/`), which is outside the repo.

---

## A. Novelty search log

The hit count is what the index reported. "Nearest" lists the closest relevant records, not the top-ranked ones. Unless a row says otherwise, arXiv queries were sorted by submission date and filled the `abs:` field.

| # | Channel | Query (abridged) | Hits | Nearest hits / note |
|---|---|---|---|---|
| A1 | arXiv API | (LLM \| "large language model" \| GPT \| Claude \| Gemini) AND aftershock(s) | 0 | none |
| A2 | arXiv API | LLM terms AND "earthquake forecast*" | 0 | arXiv does not support wildcards inside phrases; re-run as A14 |
| A3 | arXiv API | LLM terms AND (ETAS \| Omori \| CSEP) | 38 | All false positives ("ETAS" stems to "ETA") except QuakeGPT 2406.09471 |
| A4 | arXiv API | LLM terms AND seismicity | 30 | TREMORS agentic data acquisition 2609.01777; agentic PSHA interface 2607.16249; SeisMoLLM 2502.19960; QuakeGPT. None forecast seismicity with an LLM |
| A5 | arXiv API | LLM AND earthquake AND (forecast* \| predict*) | 6 | QuakeGPT; LLMs as world models (disaster impact) 2506.06355 |
| A6 | arXiv API | (foundation model \| TSFM \| Chronos \| TimesFM \| Moirai) AND (earthquake \| seismicity \| aftershock) | 46 | Jafari et al. 2408.11990 (TSFMs for earthquake nowcasting); the rest are waveform or imaging FMs |
| A7 | arXiv API | LLM AND forecast* AND (contamination \| cutoff \| leakage) AND benchmark | 33 | ForecastBench 2409.19839; WC2026 2607.17765; WorldCup Arena 2608.04008; OracleProto 2605.03762; Simulated Ignorance 2601.13717 |
| A8 | arXiv API | LLM AND (proper scoring \| interval score \| Brier) AND forecast* | 21 | How proper scoring rules shape LLM forecasting 2608.28482; FinBench 2607.16229; 2607.17765 |
| A9 | arXiv API | LLM AND elicit* AND prior(s) AND (statistical \| Bayesian) | 27 | AutoElicit 2411.17284; LLM-Prior 2508.03766; eliciting LLM priors 2406.01860; quantitative knowledge retrieval from LLMs 2402.07770 |
| A10 | arXiv API | LLM AND "probabilistic forecast*" AND calibrat* | 0 | phrase+wildcard problem (see A19) |
| A11 | arXiv API | aftershock AND forecast* AND (deep learning \| neural \| ML) | 10 | QuakeGen 2607.24109; 2608.18791; EarthquakeNPP 2410.08226; 2603.03079; Dascher-Cousineau NPP 2301.09948 |
| A12 | arXiv API | "aftershock forecast*" | 3 | QuakeGen 2607.24109 |
| A13 | arXiv API | all:aftershock AND (LLM \| language model \| ChatGPT \| GPT) | 1 | SeisLM 2410.15765 (waveforms; not forecasting) |
| A14 | arXiv API | all:earthquake AND all:forecasting AND (LLM \| ChatGPT) | 2 | QuakeGPT; LLM fatality estimation 2312.03755 |
| A15 | arXiv API | all:earthquake AND all:LLM | 11 | Gemini & physical world 2405.18732 (MMI from social media); EEW perception studies |
| A16 | arXiv API | LLM AND (Hawkes \| point process) AND forecast | 0 | — |
| A17 | arXiv API | LLM AND "seismic hazard" | 2 | agentic PSHA/risk interface 2607.16249 |
| A18–A22 | arXiv API | TSFM+catalog; LLM+quantile+calibration; LLM+knowledge cutoff; LLM+natural hazard; ETAS+neural benchmark | 1/2/12/0/7 | "Is capability a liability?" 2605.22672; Memorization problem (econ) 2504.14765; no seismic hits |
| A23 | arXiv API | (earthquake \| aftershock \| seismicity) AND forecast*, **submitted 2026-08-01 → 10-19** | 8 | 2608.18791 (NPP+ETAS); ANADEF 2609.06920; 2608.30861 (physics-AI slow slip). **No LLM forecasters** |
| A24 | arXiv API | LLM terms AND (earthquake \| seismic \| seismology), **2026-08-01 → 10-19** | 5 | TREMORS 2609.01777; SeisEvo 2608.18272. All agentic tooling; none forecast |
| A25 | arXiv API | LLM AND (interval score \| quantile \| prediction interval) AND forecast*, 2026-06 → 10 | 6 | FinBench 2607.16229; ChronoScribe 2610.16345. None seismic |
| O1 | OpenAlex `search` | large language model aftershock forecast (≥2022) | 685 | QuakeGen (arXiv + Research Square 10.21203/rs.3.rs-10587358/v1); DL+ETAS GJI 10.1093/gji/ggae349; Schneider & Guttorp 2024 |
| O2 | OpenAlex `search` | large language model earthquake forecasting (≥2022) | 9 512 | QuakeGPT book chapter 10.1007/978-981-96-2826-1_8; LLM fatality IJDRR 10.1016/j.ijdrr.2024.104680 |
| O3 | OpenAlex `search` | ChatGPT GPT-4 earthquake forecast seismicity | 82 | EMNLP 2025.emnlp-main.153; LLM alert communiqués. No forecaster scoring |
| O4 | OpenAlex `search` | language model ETAS Omori seismicity rate | 36 | Neural TPP for induced seismicity 10.1029/2025jh001052; DL seismicity-rate EPS 10.1186/s40623-025-02241-6 |
| O5 | OpenAlex `search` | LLM probabilistic forecasting calibration benchmark cutoff contamination (≥2024) | 69 | QuantSightBench 2604.15859; Hindcast 2607.14051; Temporal leakage in LLM backtesting 2608.02985; Brier analysis 2609.32885 |
| O6 | OpenAlex `search` | LLM prior elicitation statistical model parameters | 43 231 | AutoElicit; LLM prior elicitation for logistic regression (Edinburgh) |
| O7 | OpenAlex `search` | time series foundation model earthquake catalog | 2 533 | GeoHazards 10.3390/geohazards5040059 (published 2408.11990); QuakeGPT ESSOAr |
| O8 | OpenAlex `search` | aftershock forecasting machine learning, **≥2026-07-01** | 113 | PISAS v1.0 egusphere-2026-4241; Marmara leakage-audited ML vs ETAS 10.31223/x5w78x; EPSL nonstationary-ETAS diagnostic 10.1016/j.epsl.2026.120308. None LLM |
| O9 | OpenAlex `search` | earthquake forecasting, **≥2026-08-01** | 1 675 | Nat. Commun. 10.1038/s41467-026-76243-7; GJI 10.1093/gji/ggag419; SRL AoyuX 10.1785/0220260090. None LLM |
| O10 | OpenAlex `search` | large language model earthquake, **≥2026-08-01** | 1 734 | JGR-MLC 10.1029/2026jh001578 (adapting a pretrained LLM to recover magnitude/location); the rest are post-event mapping/damage |
| O11 | OpenAlex title_and_abstract (bool) | (LLM terms) AND (aftershock \| aftershocks) | 12 | QuakeGPT; Zhou 2026 dissertation (eScholarship W7222770973) on NPPs and LLM anomaly detection, not forecasting |
| O12 | OpenAlex t&a (bool) | (LLM terms) AND (earthquake forecast(ing) \| seismicity rate \| ETAS \| Omori) | 164 | no relevant records (term collisions) |
| O13–O16 | OpenAlex t&a (bool) | LLM+earthquake+forecast ≥2026-06; TSFM+earthquake; LLM+WIS/quantile/PI; LLM+cutoff+contamination ≥2026-06 | 0/135/25/5 | QuantSightBench; CP-LLM conformal intervals; Wisdom of LLM Crowds (ACM TSC); CUSP; AUGUR |
| S1 | Semantic Scholar | large language model aftershock forecasting | 3 382 | top 20 are all LLM time-series work in energy/flu; no seismic hits |
| S9 | Semantic Scholar | LLM earthquake forecasting seismicity ETAS | 196 | ETAS evaluations only, e.g. Earth's Future 2026 10.1029/2025EF007318 and TAO 2026 Taiwan ETAS 10.1007/s44195-026-00153-w. None LLM |
| S2–S8, S10–S12 | Semantic Scholar | Omori/LM; cutoff benchmarks; elicitation; TSFM; GPT scoring; WIS | n/a | HTTP 429 after retries (no API key). These are covered by arXiv/OpenAlex queries |
| R1–R4 | OpenReview API (extra) | aftershock; earthquake forecasting; seismicity; ETAS | 26/10 000/18/98 | EarthquakeNPP (TMLR); "Earthquake AI Scientist" (Agents4Science submission HMCif97Xd4: an LLM agent analysing catalog stationarity, not a scored forecaster) |
| G1 | GitHub `search repos` | llm aftershock | 1 | only this project's own repo |
| G2 | GitHub `search repos` | aftershock forecast | 15 | opensha/opensha-oaf (USGS OAF code); Lsace/global-aftershock-forecast-benchmark (2026-07: ETAS/RJ at 0.01/0.1/1 d issue times, M≥6.5 global); omitakahiro/AftFore |
| G3 | GitHub `search repos` | llm earthquake forecast | 1 | andre-anan-gilbert/llm-earthquake-forecasting (2024 student app: CatBoost forecaster plus an LLM chat agent; the LLM is not scored as a forecaster) |
| G4–G10 | GitHub `search repos` | gpt earthquake forecast; language model seismicity; ETAS llm; aftershock benchmark; earthquake forecasting benchmark; llm forecasting benchmark contamination; repere | 0/0/0/0/1/0/15 | keremalhan/marmara-forecast; mdenolle/repere (see B) |
| G11–G18 | GitHub `search code` | aftershock + anthropic/openai/claude/gpt; Reasenberg Jones llm; ETAS prompt llm; aftershock forecast prompt; omori language model | 0–2 | no relevant code (2 unrelated text-file hits) |
| W1 | WebSearch | large language model aftershock forecasting evaluation 2026 | — | QuakeGPT; EMNLP 2025 world models. No LLM aftershock evaluation |
| W2 | WebSearch | LLM GPT Claude earthquake forecast probability ETAS benchmark | — | EarthquakeNPP, EPBench 2505.15588, DL+ETAS 2310.02574 |
| W3 | WebSearch | "operational aftershock forecast" LLM comparison USGS | — | Edinburgh/BGS ML vs ETAS (EPS 2025); USGS OAF pages |
| W4 | WebSearch | LLM forecasting benchmark post-cutoff quantile PIs proper scoring 2026 | — | OracleProto; Simulated Ignorance (IJCAI 2026); lookahead-bias slides (ABFER 2026); ForecastBench; WC2026 |
| W5 | WebSearch | TSFM Chronos TimesFM earthquake catalog seismicity | — | only Jafari et al. 2024 |
| W6 | WebSearch | LM seismology Omori / productivity elicitation priors | — | Schneider & Guttorp 2024 (human experts) |
| W7 | WebSearch | ChatGPT/Claude aftershock probability study | — | no chatbot evaluations; ML press coverage only |
| W8 | WebSearch | LLM earthquake forecasting SRL/Seismica/AGU 2026 | — | EGU25 LLM magnitude abstract; EMNLP 2025 |

### Conclusion (Part A)

- **No study in the searched indexes scores a general-purpose LLM as an aftershock or seismicity-rate forecaster with proper scoring rules (WIS, PIT, Brier, CSEP likelihood tests) against an ETAS or Reasenberg–Jones reference.** That includes everything posted Aug–Oct 2026.
- The closest prior work falls into four groups, and none combines all the elements:
  - **Trained ML vs. USGS/ETAS:** QuakeGen 2607.24109 claims to beat the operational USGS RJ forecast, 2608.18791 beats ETAS on Amatrice–Norcia timing, plus EarthquakeNPP and PISAS. These are task-specific models, not prompted LLMs.
  - **LLMs in seismology:** shaking intensity (Mousavi et al. 2024 GJI, EMNLP 2025), magnitude/location (JGR-MLC 2026), and agentic tooling (TREMORS, Repère). None of it forecasts.
  - **Contamination-controlled LLM forecasting benchmarks:** ForecastBench, WC2026, WorldCup Arena, OracleProto, Wisdom of LLM Crowds, QuantSightBench (LLM prediction intervals). None is in the geoscience domain.
  - **Human expert elicitation of ETAS priors** (Schneider & Guttorp 2024), the methodological analog of eliciting from an LLM.
- **Caveat:** not finding something in these indexes does not prove it doesn't exist. Possible gaps:
  - Semantic Scholar was mostly rate-limited (2 of 12 queries returned).
  - arXiv phrase+wildcard queries returned 0, and some of them were rewritten.
  - Conference abstracts (AGU Fall 2026, SSA, EGU), non-English venues, workshop papers outside OpenReview, and unindexed preprints were not searched exhaustively.
  - Re-check AGU 2026 session listings and arXiv physics.geo-ph before submission.

---

## B. Prior-work verification

All rows were checked through arXiv API metadata, Crossref, OpenAlex, OpenReview or the GitHub API.

| Work | Verified? | Link | Venue / status | Relevance (1–2 sentences) |
|---|---|---|---|---|
| Zhu, "Earthquake Aftershock Forecasting using Conditional Generative Models" (QuakeGen) | Yes | https://arxiv.org/abs/2607.24109 ; also https://doi.org/10.21203/rs.3.rs-10587358/v1 | arXiv v1 2026-07-27; Research Square preprint 2026-08-18 (not peer-reviewed yet) | A diffusion model generates aftershock-rate and max-magnitude fields. It is reported to beat the USGS RJ forecast on global sequences and to match ETAS on daily regional forecasts. It is the closest "beats USGS operational" claim, but it is a trained model, not an LLM. |
| Stockman, Lawson & Werner, EarthquakeNPP | Yes | https://arxiv.org/abs/2410.08226 ; https://openreview.net/forum?id=dIcNAg6ZuZ | **Accepted to TMLR (2026)** per arXiv v3 comment and OpenReview; an earlier version was rejected at ICLR 2025 | Benchmarks five neural point processes against ETAS on California catalogs, and none beats ETAS. Strong evidence that ETAS is a hard baseline, and a template for the evaluation protocol. |
| Xiong et al., "Scaling-law-informed neural point processes for earthquake sequence forecasting" | Yes | https://arxiv.org/abs/2608.18791 | arXiv preprint 2026-08-19 | The "Fusion" NPP adds ETAS temporal features and Gutenberg–Richter magnitudes. It beats ETAS on target-event temporal likelihood for Amatrice–Visso–Norcia when smaller events are kept as input, with no gain on magnitudes. This is the newest hybrid-vs-ETAS result. |
| Mousavi et al. 2024, "Gemini and physical world: LLMs can estimate the intensity of earthquake shaking…" | Yes | https://doi.org/10.1093/gji/ggae436 (arXiv 2405.18732) | Geophys. J. Int. 240(2):1281–1294 (Dec 2024) | Gemini estimates MMI from multimodal social-media posts. It is the main peer-reviewed "LLM knows seismology" paper, but the task is post-event intensity, not forecasting. |
| Schneider & Guttorp 2024, "What do we know without the catalog? Eliciting prior beliefs from experts for aftershock models" | Yes | https://doi.org/10.1785/0320240008 | The Seismic Record 4(4):259–267 | Elicits ETAS-parameter priors for the Pacific Northwest from human experts, via seismological quantities. It is the direct analog of "LLM as elicited expert" and supports the parameter-elicitation arm of the project. |
| Li et al., "LLMs as World Models: Data-Driven and Human-Centered Simulation for Disaster Impact Assessment" | Yes | https://doi.org/10.18653/v1/2025.emnlp-main.153 (arXiv 2506.06355) | EMNLP 2025 main, pp. 3078–3096 | LLMs simulate MMI at zip/county scale for Napa 2014 and Ridgecrest 2019, scored against DYFI. It is evidence that LLMs encode quantitative earthquake knowledge, but it is not aftershock forecasting. |
| Gao, Jiang & Yan, "Detecting Lookahead Bias in LLM Forecasts" | Yes | https://arxiv.org/abs/2512.23847 | arXiv preprint (v2 2026-06-12); presented at the ABFER 2026 conference (slides found) | Introduces the "Lookahead Propensity" recall probe, which collapses after the training cutoff. It is a template for a contamination diagnostic: ask models to recall the actual sequence before forecasting it. |
| Ding, Guo & Xu, "FIFA World Cup 2026 as a Contamination-Free Benchmark for LLM Forecasting Agents" | Yes | https://arxiv.org/abs/2607.17765 | arXiv preprint 2026-07-20 | Four frontier agents (incl. Claude Opus 4.8) forecast 104 post-cutoff matches; none beats the bookmaker's Brier score. It is the same design idea as this project (post-cutoff events, a market or operational reference) in a different domain. |
| Douven, "Wisdom of LLM Crowds: Aggregation and Contamination in Language Model Ensembles" | Yes | https://arxiv.org/abs/2607.18269 ; https://doi.org/10.1145/3839337 | **Published**: ACM Trans. Social Computing 9 (2026) | 15 LLMs on 254 binary market questions. The frontier-vs-local gap shrinks from 35.8% to 8.9% on post-cutoff questions. This quantifies why the evaluation has to be restricted to events after the cutoff. |
| Karger et al., ForecastBench | Yes | https://arxiv.org/abs/2409.19839 ; https://openreview.net/forum?id=lfPkGWXLLf | ICLR 2025 (poster) | A dynamic benchmark that asks only about unresolved future events, scored by Brier score. It is the standard reference for LLM forecasting evaluation that is leakage-free by construction. |
| mdenolle/repere (Repère) | Yes (public, MIT; created 2026-05-08, last push 2026-10-17, v0.5.2) | https://github.com/mdenolle/repere | Software (InspectAI-based), no paper found | An open evaluation framework for geoscience AI agents, with STA/LTA, pipeline-regression, dv/v, literature-RAG and orchestration suites. The README and file tree have **no forecasting or aftershock suite**, so it is the nearest geoscience-LLM eval harness and a possible host for this benchmark. |

Other close prior work found during the search:
- **QuantSightBench** (arXiv 2604.15859): LLM prediction-interval forecasting, scored on coverage and sharpness.
- **"How Proper Scoring Rules Shape LLM Forecasting"** (arXiv 2608.28482, Tetlock group).
- **"Temporal Leakage in LLM Backtesting"** (arXiv 2608.02985): argues that comparing scores before and after the cutoff cannot detect leakage on its own.
- **Lsace/global-aftershock-forecast-benchmark** (GitHub, 2026-07): a global ETAS/RJ benchmark with issue times of 0.01, 0.1 and 1 days, close to this project's baseline design.

---

## C. Methods references

All DOIs were checked through `api.crossref.org/works/<doi>` and returned HTTP 200, except the two rows marked otherwise.

| Citation | DOI | Crossref? | Used for |
|---|---|---|---|
| Reasenberg & Jones 1989, Science 243:1173–1176 | 10.1126/science.243.4895.1173 | Yes | RJ generic model; P(≥1 M≥Mx) and expected counts |
| Reasenberg & Jones 1994, Science 265:1251–1252 | 10.1126/science.265.5176.1251 | Yes | Updated RJ formulation |
| Page et al. 2016, BSSA 106:2290–2301 | 10.1785/0120160073 | Yes | Global generic RJ parameters by tectonic region; time-dependent incompleteness; inter-sequence variability |
| Hardebeck et al. 2019, SRL 90:262–270 | 10.1785/0220180240 | Yes | Updated California RJ parameters |
| Michael et al. 2020, SRL 91:153–173 | 10.1785/0220190196 | Yes | USGS OAF practice and communication (2018 Anchorage) |
| van der Elst et al. 2022, SRL 93:620–640 | 10.1785/0220210222 | Yes | Evaluation of the USGS public forecast incl. ETAS (2019–21 Puerto Rico). A separate "ETAS for OAF" methods paper was **not located** |
| Hardebeck et al. 2024, Annu. Rev. Earth Planet. Sci. 52:61–84 | 10.1146/annurev-earth-040522-102129 | Yes | Review of aftershock forecasting and the state of USGS OAF |
| Ogata 1988, JASA 83:9–27 | 10.1080/01621459.1988.10478560 | Yes | ETAS model |
| Utsu, Ogata & Matsu'ura 1995, J. Phys. Earth 43:1–33 | 10.4294/jpe1952.43.1 | Yes | Omori–Utsu law review |
| Wells & Coppersmith 1994, BSSA 84:974–1002 | 10.1785/BSSA0840040974 | Yes | Rupture length scaling for the aftershock spatial window |
| Gneiting & Raftery 2007, JASA 102:359–378 | 10.1198/016214506000001437 | Yes | Proper scoring rules (log score, CRPS, interval/quantile scores) |
| Bracher et al. 2021, PLoS Comput. Biol. 17:e1008618 | 10.1371/journal.pcbi.1008618 | Yes | Weighted interval score for quantile forecasts |
| Bosse et al. 2023, PLoS Comput. Biol. 19:e1011393 | 10.1371/journal.pcbi.1011393 | Yes | Scoring on log-transformed counts (heavy-tailed aftershock counts) |
| Czado, Gneiting & Held 2009, Biometrics 65:1254–1261 | 10.1111/j.1541-0420.2009.01191.x | Yes | Randomized/non-randomized PIT for count data |
| Brier 1950, Mon. Weather Rev. 78:1–3 | 10.1175/1520-0493(1950)078<0001:VOFEIT>2.0.CO;2 | Yes | Brier score for P(≥1 M≥6) |
| Savran et al. 2022, SRL 93:2858–2870 | 10.1785/0220220033 | Yes | pyCSEP (N-test and catalog-based evaluations) |
| Schorlemmer et al. 2007, SRL 78:17–29 | 10.1785/gssrl.78.1.17 | Yes | CSEP likelihood (N/L) tests |
| Schorlemmer et al. 2018, SRL 89:1305–1313 | 10.1785/0220180053 | Yes | CSEP achievements and prospective-testing principles |
| Aki 1965, Bull. Earthq. Res. Inst. Tokyo 43:237–239 | none | No DOI (Crossref bibliographic search: no match) | b-value MLE. Cite by journal/volume |
| Woessner & Wiemer 2005, BSSA 95:684–698 | 10.1785/0120040007 | Yes | Mc estimation and uncertainty |
| Mignan & Woessner 2012, CORSSA | 10.5078/corssa-00180805 | **Crossref 404**; registered with **DataCite** (verified via api.datacite.org); doi.org resolves | MAXC completeness method and +0.2 correction |
| Helmstetter, Kagan & Jackson 2006, BSSA 96:90–106 | 10.1785/0120050067 | Yes | Short-term aftershock incompleteness Mc(t) after the mainshock |
| Hainzl 2016, SRL 87:337–344 | 10.1785/0220150211 | Yes | Rate-dependent incompleteness |
| Hainzl 2016, JGR Solid Earth 121:6499–6509 | 10.1002/2016JB013319 | Yes | Apparent Omori c-value from rate-dependent incompleteness |
| Mizrahi, Nandan & Wiemer 2021, JGR Solid Earth 126:e2021JB022379 | 10.1029/2021JB022379 | Yes | ETAS inversion with time-varying Mc; `etas` package (github.com/lmizrahi/etas, verified to exist) |

Software for the baselines (verified via the GitHub API): `opensha/opensha-oaf` (USGS OAF code), `lmizrahi/etas`, and `pyCSEP`.

---

## D. Suggested reference sets

**One-page hackathon write-up (6):**
1. Reasenberg & Jones 1989 (baseline model)
2. Page et al. 2016 (generic parameters; this is what the USGS product uses outside California)
3. Gneiting & Raftery 2007 (proper scoring)
4. Bracher et al. 2021 (WIS)
5. Karger et al. 2025, ForecastBench (contamination-free LLM forecasting)
6. Zhu 2026, QuakeGen (closest "beats USGS RJ" claim; it shows the reference is beatable by trained models)

**Full paper (~20):**
- *Aftershock models and the operational forecast:*
  - Reasenberg & Jones 1989, 1994
  - Ogata 1988
  - Utsu, Ogata & Matsu'ura 1995
  - Page et al. 2016
  - Hardebeck et al. 2019
  - Michael et al. 2020
  - van der Elst et al. 2022
  - Hardebeck et al. 2024 (review)
- *Catalog processing:*
  - Aki 1965
  - Woessner & Wiemer 2005 or Mignan & Woessner 2012
  - Helmstetter, Kagan & Jackson 2006
  - Hainzl 2016 (SRL)
  - Mizrahi et al. 2021
  - Wells & Coppersmith 1994
- *Scoring:*
  - Gneiting & Raftery 2007
  - Bracher et al. 2021
  - Bosse et al. 2023
  - Czado, Gneiting & Held 2009
  - Brier 1950
  - Schorlemmer et al. 2007
  - Savran et al. 2022
- *ML/LLM context:*
  - Stockman et al. (EarthquakeNPP, TMLR 2026)
  - Zhu 2026 (QuakeGen)
  - Xiong et al. 2026 (2608.18791)
  - Mousavi et al. 2024 (GJI)
  - Schneider & Guttorp 2024
  - Karger et al. 2025 (ForecastBench)
  - Douven 2026 (ACM TSC)
  - Gao, Jiang & Yan (lookahead bias)
  - optionally QuantSightBench (2604.15859) for LLM prediction intervals

The full list runs to about 30. Trim to 20 by dropping Reasenberg & Jones 1994, Hainzl 2016, Wells & Coppersmith 1994, Brier 1950, Schorlemmer et al. 2007, Michael et al. 2020, Gao et al. and QuantSightBench, if the venue limits references.
