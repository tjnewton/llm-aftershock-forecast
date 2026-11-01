# Preregistration v2: LLM aftershock forecasts against USGS operational forecasts, retrospective and prospective

Status: **DRAFT, not frozen.** Tyler alone decides the freeze (tag `prereg-v2`). On 2026-10-31
he accepted the recommendations for decisions 1-13 (section 13). Items still marked **OPEN**
need his decision. Items marked **TO BUILD** or **TO
FIX** are work that must be finished before the freeze (section 11). Sources: ADRs 0004, 0006,
0011 and 0013-0018 (decisions of 2026-10-30 and 2026-10-31), the D1 and D2 results, the settings
pilots, and three checks of this draft (2026-10-31: the author's, an independent fact check,
an independent methodology review). Where this document and an ADR disagree after the freeze,
this document governs, and every reference resolves to the tagged commit. Prereg v1 (tag
`prereg-v1`) stays frozen and governs the registered hackathon analysis.

## 1. Study and estimand
We compare probabilistic aftershock forecasts from general-purpose LLMs with the USGS
operational aftershock forecast (OAF) and with statistical baselines.
- **Information parity:** every forecaster sees what the OAF had at each issue time.
  - Retrospectively, the catalog is rebuilt as it stood then from ComCat's product histories
    (ADR 0011). On the candidate set, the rebuilt catalog reproduces the official products'
    own observation counts in 99.05% of 23,264 checks; today's revised catalog would give
    96.85%.
  - The prompt lists at most 800 events, with daily counts beyond that.
  - Prospectively, the catalog is the one fetched at detection.
- **Contamination:** each model is scored only on sequences whose mainshock falls after its
  training cutoff plus a 3-month buffer (section 3). In the prospective arm, contamination is
  impossible.

Per cell (issue time x window x target), dS = S(model) - S(official).
- **S** is the logarithmic score as a loss: S = -log p(y), where p is the forecast probability
  of the observed count y, floored at 1e-6. Lower is better, so negative dS favors the model.
- **Representation-matched:** every forecaster is scored through its nine quantiles with the
  same latent-PCHIP reconstruction and its power-law upper tail (ADR 0015).
- **Primary estimand:** the mean over sequences of the per-sequence mean dS at M>=5.
- **Unit of answer:** a single chatbot answer to a fixed prompt. A model's dS in a cell is the
  mean over its k samples.

## 2. Hypotheses and decision rules
| Id | Hypothesis | Set | Test |
|---|---|---|---|
| **A** (primary) | gpt-5.1 is non-inferior to the official forecast | retrospective: gpt-5.1's clean M>=5 sequences (89 among the current candidates) | one-sided, delta = 0.10 nats per cell |
| B (secondary) | Claude Opus 5.5 is non-inferior to the official forecast | its clean retrospective M>=5 sequences plus prospective sequences (section 5) | one-sided, delta = 0.10, alpha 0.05; reported with its simulated size |
| S1 (secondary) | Opus 4.6 is non-inferior | its clean M>=5 sequences (23); M3/M4 targets on its 76 clean sequences descriptive | one-sided, delta = 0.10, alpha 0.05 |
| S2 (secondary) | gpt-6.1-sol is non-inferior | prospective (ADR 0018 decision 3) | as S1 |
| S3 (secondary) | Opus 5.5, gpt-5.1, Opus 4.6 and gpt-6.1-sol each beat the rule of thumb | each model's A, B, S1 or S2 set | superiority, alpha 0.05 |
| S4 (secondary) | the same models against generic RJ and the legacy-ETAS refit | as S3 | superiority over generic RJ (alpha 0.05); estimate and 95% CI against ETAS |
| S5 (secondary) | Opus 5.5 (and gpt-6.1-sol) against the pipeline's baselines on strict prospective items | prospective strict items | as S3 and S4 |
| D (descriptive) | Sonnet 4.6; M3 and M4 targets; D1 behavioral probes; hindsight effect (ADR 0016) | as stated | no test |

- **Decision rule** for each tested hypothesis, at its level:
  - **supported** if the upper bound of mean dS is below delta;
  - **inferior** if the lower bound is above delta;
  - **inconclusive** otherwise.
  - **Superiority** over the official forecast is tested for A at 0.05 only after its
    non-inferiority is supported (a fixed sequence on one hypothesis, so no extra alpha). For
    secondary models, superiority is tested at 0.05 after non-inferiority and labelled
    secondary.
  - No secondary target, secondary set or sensitivity analysis overturns a primary result.
- **One primary hypothesis** (Tyler, 2026-10-31): A, at one-sided 0.05.
  - B was co-primary with a Holm correction. It became secondary when the size simulation
    showed that no test controls its error at about 33 sequences (section 6).
  - Secondary tests are at 0.05 each and labelled secondary.
  - A and B are still computed together on the final outcome snapshot (section 5), because
    computing A early would reveal outcomes of October sequences that A and B share.
- **Margin delta = 0.10 nats per cell** (ADR 0018). Anchors on development data, as the mean
  per cell:
  - Doubling the official expected count costs 0.063 on the E3 sequences (mostly M5-6, mostly
    zero counts) and 0.300 on the six large registered sequences.
  - Generic RJ minus official is -0.013 on E3 and +0.184 on the registered sequences.
  - So delta = 0.10 is generous for small sequences. Most cells carry little information,
    which pulls the mean toward 0.
  - **Assay sensitivity** (decided 2026-10-31): the same non-inferiority test is run for generic RJ
    against the official forecast on each test's cells. If generic RJ is also non-inferior, A
    and B are reported as unable to separate the model from the generic default, and no claim
    of sequence-specific skill rests on them.
  - **Informative-sequence secondary estimand** (decided 2026-10-31): the primary estimand on the sequences
    whose official forecast at the first issue has a mean N(M>=5) of at least 0.5 in the month
    window. This is outcome-blind.
- **Power, with the registered bootstrap-t:**
  - It is computed from each model's development (D2) sequence effects, with its D2 mean as
    the true difference (1,000 simulations).
  - A: 0.45 on 89 sequences at 0.05. On all 175 clean candidates it is 0.84, which overstates,
    because the extra sequences are resampled from M>=5 effects.
  - B: 0.64 on 33 at 0.05.
  - The normal approximation used earlier (`laf.power`) gave higher numbers: A 0.62, B 0.96. It
    ignores the heavy tail.
  - A's development effects come from 18 sequences, one of which (a rare-event miss) dominates
    them, so these powers are uncertain in both directions.

## 3. Models and settings
| Model | Training cutoff | Clean from | Settings | Role |
|---|---|---|---|---|
| `gpt-5.1-2025-11-13` | 2024-09-30 | 2025-01-01 | reasoning effort `medium` (ADR 0014 decision 6) | A |
| `claude-opus-5-5` | Jun 2026 | 2026-10-01 | registered request: no `thinking` field (adaptive by default), effort `high` | B |
| `claude-opus-4-6` | Aug 2025 | 2025-12-01 | `thinking: {"type": "adaptive"}`, effort `medium` (ADR 0014 decision 5) | S1 |
| `gpt-6.1-sol` | 2026-04-30 | 2026-08-01 | reasoning effort `high` (ADR 0014 decision 7); no dated snapshot, so each response's reported model is logged | S2 |
| `claude-sonnet-4-6` | Jan 2026 | 2026-05-01 | `thinking: {"type": "adaptive"}`, effort `low` | D |

- **Requests (all models):**
  - No sampling parameters, no tools, no prefill, no server-side fallbacks.
  - The JSON schema `prompts/v2/schema_direct.json`, strict where the API supports it, and an
    explicit effort.
  - Base URLs pinned to the official APIs. `response.model` and `usage` are logged for every
    call. An answer whose `response.model` differs from the requested ID is invalid.
- **Prompt:** `v2A` (hashes in `prompts/v2/HASHES.json`).
  - It asks, per window, for nine quantiles of N(M>=5), N(M>=4) and N(M>=3) and for P(M>=6),
    and shows the catalog from M3.0.
  - `v2B` is a preregistered robustness check (ADR 0015 decision 4), run by the A and B
    models only.
- **Samples:** k = 3 per item (decided 2026-10-31), as in D2.
- **Output cap:** 32,000 tokens for every scored call, batch or live (live calls stream).
- **Model changes** (decided 2026-10-31):
  - gpt-5.1 is removed from the API on 2027-04-01, so all test A forecasts are generated by
    2027-03-01.
  - If a model is withdrawn or changes (shown by `response.model`), its accrual stops then, and
    its tests use what accrued.

## 4. Data, sequences and cells
- **Retrospective candidates** (config/sequences_confirmatory.toml, snapshot 20261029T2000Z;
  195 candidates): every ComCat event with an OAF product from 2024-11-14 (the archive start)
  to 2026-10-29, 254 in all. Excluded:
  - development sequences: 49 (registered, E3, the E1 outcome pool; config/splits.toml);
    outcome exposure makes a sequence development, input exposure does not (ADR 0013);
  - foreshocks and aftershocks of a larger event: 10. That is an event inside the
    1.5 x Wells-Coppersmith circle (at least 10 km) of a larger event within 365 days. The
    context is the OAF events plus ComCat M>=6 from 2023-11-01 (ADR 0006 rule, `laf.e3.claimed`).
  - Nothing else. nn00914068 (M5.7, 2026-04-14, Silver Springs NV) had been dropped for E3
    because ComCat would not return it in full. It was retrieved on 2026-10-31 and restored,
    making 195 candidates; its outcomes stay sealed.
  - **The foreshock half of the exclusion rule uses future information** (decided 2026-10-31). 3 of the 10
    excluded events were excluded only because a larger event followed within a year. That
    event can fall inside their own forecast windows, so the exclusion selects on outcomes. The
    3 were counted without looking at their identities.
    - The candidate list stays as built, since the primary set must not change after this
      partial exposure.
    - Prospective sequences get only the backward-looking (aftershock) half.
    - Tests A, B and S1 are also reported with the 3 included, as a sensitivity analysis.
- **Primary set:** M>=5 mainshocks in each model's clean period.
  - Mainshock magnitudes are those of the frozen snapshot (retrospective) or at first
    detection (prospective).
  - The counts quoted (89, 23, 7) are expected sizes. A sequence with no valid official version
    or no primary cell drops out, and that attrition is reported.
  - Secondary set: M4.0-4.9 mainshocks from US regional networks (`laf.prospective.US_REGIONAL`:
    ak, ci, hv, mb, nc, nm, nn, pr, se, tx, uu, uw).
  - Test A's sensitivity analysis uses all of gpt-5.1's 175 clean candidates; test B stays on
    M>=5.
- **Issue times (both arms):**
  - The first valid official version, plus for each target t in {1, 3, 7, 14, 28} days the
    earliest valid version whose information cutoff falls in
    [origin + t, origin + t + max(1 d, t/4)) (ADR 0004).
  - Prospectively, the same schedule is applied in real time, and only the scheduled versions
    get forecasts (decided 2026-10-31). Other versions are not forecast; forecasting every one
    would mean about 60 versions per sequence, mostly months later.
- **Windows:** day, week and month, taken from each official version; the year window is not
  used. Windows are half-open [start, end).
- **Strata:** under 1 day, 1 to 7 days, and 7 days or more after the mainshock.
- **Targets:**
  - M>=5 is primary. M>=4 is descriptive (decided 2026-10-31): no completeness rule exists at M4, and 9 of
    Opus 4.6's 76 clean sequences have catalog completeness 4.6.
  - M>=3 is descriptive and counts only where the catalog is complete at M3 for the whole
    window: the official product's own Mc (ETAS `Mc` or RJ `Mcat`) is at most 3.0, and the
    time-dependent completeness after the mainshock (`MagComp`, ADR 0009) reaches 3.0 before
    the window opens (ADR 0015). In practice these are 35 California candidates.
  - P(M>=6) is reported with its Brier score.
- **Outcomes:**
  - ComCat counts of events at or above the threshold (tolerance 1e-6) in the official
    forecast's region circle and window.
  - A cell is primary once its window closed at least 21 days before the outcome snapshot;
    2 days is a sensitivity analysis.
- **Prospective inclusion:** a new event qualifies by the same magnitude rules.
  - An event inside the circle of a larger event from the previous 365 days is excluded as an
    aftershock, using the same context catalogs (decided 2026-10-31).
  - A sequence once included is never removed.
  - Event identities are matched through ComCat's associated IDs.

## 5. Prospective protocol
This replaces ADR 0017 decisions 1-2: ADR 0018's test B, decided later, uses on-time matched
items against the official forecast. ADR 0017 records this (2026-10-31).
- **Detection:** ComCat is polled every 10 minutes. Each scheduled official version (section 4)
  gets two items:
  - a **matched** item, on the version's own windows;
  - a **strict** item, whose windows open at the next full hour at least 30 minutes after
    detection (kept, decided 2026-11-01: on live data the items and baselines took about 21 s
    before any model time, the 30-minute lead leaves the answers room either way, and rounding
    to 10 minutes would shrink the offset from the official windows by under 50 minutes on
    windows of a day or more).
- **Per issue:**
  - The live models' answers (k samples) are sealed first, in one record with its SHA-256.
  - The baselines on the same items (generic RJ, RJ-MLE, the rule of thumb, the legacy-ETAS
    refit) are sealed in a second record. This keeps a slow ETAS refit from making answers
    late.
  - Each record gets an OpenTimestamps proof and is committed to the `live` branch in real
    time. Full forecasts are published after their windows close, with a note that they are
    not official forecasts.
  - Built: the two-record seal (`laf.prospective`); the detector-to-issue wiring as a dry run
    (`laf live-watch`: inclusion rule, schedule, both records, no model calls); publishing
    (`laf.publish`): each seal file is pushed at once, then its OpenTimestamps proofs from
    three public calendars, and GitHub's push receipt is read from the repository activity
    API. The dry run publishes to the branch `live-test`, the study to `live`.
  - Each push receipt is committed beside its seal (`receipt.json`), so the on-time evidence
    stays on the branch whatever GitHub's activity retention.
  - Built: the release. Each poll, the detector releases every issue whose forecast windows
    have all closed: the files named in its seals' manifests, each checked against the hash
    published on the branch (a mismatch is never released), with a NOTICE that they are not
    official forecasts (`laf.publish.release`).
  - Built: the paid path (`laf live-watch --paid`; ADR 0017 "The paid path"): the live models
    spend only a fixed live reserve per provider, counted on spend files published with each
    answers seal, in the budget priority below.
  - Host (decided 2026-11-01): the Windows machine from L until hackathon judging ends, then
    the scheduled GitHub Actions workflow (ADR 0017 decision 13).
- **On time:** a matched item enters test B only if its answer record's hash reached the
  GitHub push receipt (or an OpenTimestamps calendar) before the item's first window opened.
  - Late, missed and failed items are listed with reasons and never backfilled.
  - "Failed" means a pipeline or transport failure. A delivered invalid answer is scored under
    section 7, never excluded.
  - On-time and late versions are compared on outcome-blind covariates: magnitude, network or
    region, time since the mainshock, official model type.
- **Arms of test B:**
  - Let L be the UTC time of the first sealed live record.
  - The retrospective part is the Opus-5.5-clean qualifying M>=5 sequences with origin in
    [2026-10-01, L). Those after the candidate snapshot are fetched once at L, by the same
    outcome-blind procedure, into a supplementary snapshot.
  - Prospective sequences have origin at L or later. A sequence belongs to exactly one part.
  - Test B is also reported for each part alone.
  - (This definition of the parts and the supplementary snapshot was decided 2026-10-31.)
- **Stopping rule:** sequences stop entering at S = min(L + 182 days, the time of the 26th
  eligible prospective M>=5 sequence).
  - The 6-month clock does not pause for outages.
  - One outcome snapshot for A and B is taken at S + 90 days. That covers the last 28-day
    issue, its tolerance, a month window and 21 days of settling.
  - There is no early stopping.
- **No interim looks** (decided 2026-10-31): no confirmatory score or test is computed before S + 90 days.
  Computing A early would reveal outcomes of October sequences that A and B share.
  - Built: the second software gate (`laf.splits`). At S, a commit records S (epoch ms) in
    config/live_stop.toml and Tyler tags it `prereg-v2-stop`. Outcomes of every confirmatory
    sequence, live records included, stay sealed until that tag exists and S + 90 days have
    passed; `laf live-score` refuses v2 records until then.
- **Budget priority** (decided 2026-10-31): a fixed live reserve. If the cap binds, the order is Opus 5.5 matched,
  then Opus 5.5 strict, then gpt-6.1-sol. Misses are listed as "missed: budget".
- **Live models:** Opus 5.5 and gpt-6.1-sol (decided 2026-10-31), gpt-6.1-sol at effort
  `high` (ADR 0014 decision 7).
- **Live start** (decided 2026-11-01): the live arm starts right after the `prereg-v2` tag,
  once one paid end-to-end check has passed (on a version the study does not use, published
  nowhere). L is then the time of the first sealed live record; no calendar date is set.

## 6. Analysis (ADR 0018; `laf.confirmatory`)
- **Primary:** a sequence block bootstrap (B = 10,000, fixed seed) over the per-sequence mean
  dS. Test B resamples its retrospective and prospective parts separately.
  - **The bound** (decided 2026-10-31): a studentized (bootstrap-t) upper bound. Under heavy tails, the
    percentile bound drafted earlier claims
    non-inferiority too often. In simulation with the true mean at delta and a nominal 0.025:
    - With effects like gpt-5.1's in D2 (one sequence in 18 at +1 nat), it errs 0.15 of the
      time at N = 33 and 0.05 at N = 88.
    - A studentized (bootstrap-t) bound errs 0.15 at N = 33 and 0.02 at N = 88.
    - At N = 33 no bootstrap can recover a rare event the sample misses.
    - Before the freeze, the registered test's size is simulated at N = 33 and 89 from the
      development effects shifted to delta. Wherever it exceeds 0.03, a calibrated nominal
      level is registered as a number.
    - Test B at about 33 sequences cannot rule out a rare-event deficit, and the paper says
      so.
  - **The level** (decided 2026-10-31): one-sided 0.05 for the single primary test, A. It
    matches the 90% interval of equivalence testing but is looser than the usual one-sided
    0.025 for non-inferiority; the power available justifies it.
  - **Simulated size** of the bootstrap-t at nominal 0.025, from D2 effects shifted to delta
    (`laf confirmatory-size`):
    - 0.007 (gpt-5.1-like effects) and 0.025 (Opus-5.5-like effects) at N = 89;
    - 0.14 for both at N = 33.
    - The size at 0.05 and N = 89 is 0.018 and 0.030, within the 0.03 threshold, so no
      calibration is needed for A.
- **Beside the mean:**
  - The 10% trimmed mean and the median of the sequence effects, with bootstrap intervals.
  - Leave-one-sequence-out influence on A and B.
  - The hierarchical model dS_ijk = mu + u_i + v_ij + e_ijk, with window and stratum as fixed
    effects in sum coding. It is a robustness check that estimates an unweighted mean over
    windows and strata, not the mean of sequence means. If it fails to converge, that is
    reported.
- **Sensitivity analyses**, all reported in one table whatever their result; anything not
  listed is exploratory:
  - test A on all clean candidates;
  - with the 3 forward-excluded candidates;
  - the non-overlapping subset (one window per issue);
  - v2B;
  - valid answers only;
  - the registered log-scale quantile score (ADR 0015 decision 1);
  - full-distribution scores of the official and ETAS forecasts;
  - the negative-binomial tail instead of the power-law tail;
  - log floors of 1e-4 and 1e-8, with the floor-binding rate per forecaster and the number of
    cells above each forecaster's 97.5% quantile;
  - the unbuffered clean rule;
  - a release-date clean rule;
  - the 2-day settling rule;
  - the subset where the as-of catalog matches the official observation counts exactly;
  - region radius x0.5 and x1.5;
  - results by stratum;
  - CSEP-style N-test, PIT and information gain per earthquake (ADR 0015);
  - invalid rates by arm.
- **Software:** `laf confirmatory --snapshot S --runs DIR` refuses to run until the tag
  `prereg-v2` exists.
  - It computes A, B and S1 against the official forecast at M>=5, with the trimmed mean,
    median and hierarchical model.
  - The registered decision for A is its `noninferior` column at 0.05.
  - Built: the registered bound and its size simulation (`laf confirmatory-size`); models
    outside the primary and secondary lists (Sonnet 4.6 among them) get no test row.
  - Built: the secondary table (`laf.confirmatory.secondary`, written beside the tests): the
    contrasts S3 and S4 (dS against each pipeline baseline on the model's own test cells), the
    assay-sensitivity test, and the informative-sequence estimand, whose official mean is the
    integral of the official quantile function over its published fractile grid.
  - **TO BUILD:**
    - S5 (with the prospective inputs);
    - the prospective inputs to test B (its two-part bootstrap is built: `noninferiority(...,
      strata=...)` resamples each part at its own size, with the stratified standard error);
    - S2;
    - the listed sensitivity analyses.

## 7. Invalid outputs
- An invalid answer gets the worst score in its cell from a fixed pool (decided 2026-10-31). Invalid means a schema
  violation, an answer cut off at the output cap, a refusal, non-monotone quantiles, a value out
  of range, or a mismatched `response.model`.
  - The pool is the five baselines (official, generic RJ, RJ-MLE, the rule of thumb, the
    legacy-ETAS refit), scored through nine quantiles at M>=5. It therefore does not depend on k
    or on which other runs exist.
  - This is the prereg v1 rule with its pool fixed. `laf.confirmatory` applies it.
- Magnitudes that disagree across targets (an M3 count below an M4 count) are a warning, not
  invalid at M5.
- Retrospective transport errors are retried, up to 10 attempts. Persistent failures are listed
  and left out.
- Invalid rates are reported per model and arm.

## 8. Budget
- Claude spend is capped per calendar month (`LAF_CLAUDE_MONTHLY_CAP_USD`) and OpenAI spend
  separately (`LAF_OPENAI_MONTHLY_CAP_USD`).
- Every retrospective batch is approved by Tyler with its cost estimate.
- Live calls spend only a fixed live reserve per provider (ADR 0017, "The paid path").
- **Cost plan** (decided 2026-11-01). Estimates use the token counts measured in D2 and the
  gpt-6.1-sol pilot at current prices; each batch's own estimate, with a 25% margin, is what
  Tyler approves.
  - Retrospective batches (k = 3, Batch API): A, gpt-5.1 on v2A for all 175 clean candidates
    (the 89 M>=5 and test A's sensitivity set), about $109, and on v2B for the 89, about $55;
    B, Opus 5.5 on v2A and v2B for its retrospective part, about $4; S1, Opus 4.6, about $9;
    S2, gpt-6.1-sol, about $3; Sonnet 4.6 (descriptive), about $3. In all, about $16 Claude
    and $167 OpenAI.
  - Live: about $0.21 Claude and $0.41 OpenAI per issue (two items, k = 3, both live models;
    worst case $3.89 and $1.94); at about 42 issues a month (8 sequences, 5.2 issues each),
    about $9 Claude and $17 OpenAI a month.
  - Caps and reserves: Claude $200 a month with a $20 live reserve; OpenAI $100 a month from
    November 2026 to February 2027 and $50 after, with a $25 live reserve.
  - Order: test A's batches first, about $55 a month (v2A on the 89, then the sensitivity set,
    then v2B), all by 2027-03-01; the other retrospective batches after L, since B's
    retrospective part needs the supplementary snapshot taken at L.

## 9. Availability and timeline
- All items, sealed records, answers, scores and code are released with a DOI at
  publication.
- Dates: the freeze; L; S; the outcome snapshot at S + 90 days; test A's runs by 2027-03-01.
- **Prior exposure:**
  - The V0 check compared official observation counts in later versions, which hold partial
    outcomes of earlier windows (allowed by ADR 0013).
  - Since 2026-10-30, the live dry run has tracked new official versions of some October
    candidates; only its timing logs were viewed.
  - Only aggregate counts of the fore/aftershock exclusions were viewed.

## 10. Changes from prereg v1
- **Data:** 195 confirmatory candidates instead of the registered sequences; prospective
  sequences counted toward a test.
- **Contamination:** the 3-month buffer now applies to the Claude 5.5 models too.
- **Scoring:** the log score of the count distribution as the primary score instead of the
  log-scale quantile score, with representation-matched scoring.
- **Tests:** formal non-inferiority tests with a margin, a multiplicity correction and decision
  rules, instead of descriptive hypotheses.
- **Models:** older-cutoff and other-vendor models with study settings fixed by pilots.
- **Prompts:** v2 with M3 targets.
- **Invalid answers:** the penalty pool is fixed to the baselines. Invalid rates are reported,
  where v1 made them an outcome.
- **Prospective arm:** strict and matched items with a stopping rule instead of the v1
  demonstration.

## 11. Freezing procedure
The freeze needs all of the following:
- No item marked OPEN, TO BUILD or TO FIX remains.
- `laf confirmatory` has run end to end on a development snapshot, including the prospective
  inputs and the size simulation.
- Tyler tags `prereg-v2` on a commit that holds this document. The SHA-256 of these is posted
  publicly with the tag's commit hash:
  - this document;
  - `prompts/v2/HASHES.json`;
  - the items files;
  - the `src/laf` tree;
  - the data manifest;
  - the candidate snapshot tables;
  - `config/splits.toml` and the sequence configs;
  - the baseline forecasts (ETAS refit with seeds), computed before any outcome is unsealed.
- The tag unseals confirmatory outcomes in the software (`laf.splits`) except those behind the
  second gate (section 5).
- Confirmatory runs and live forecasting start after the tag.

## 12. Deviations
Changes after the freeze go in a dedicated v2 section of docs/deviations.md, each with its
UTC time, reason and expected effect. A change made after outcomes are unsealed is exploratory,
and the registered analysis is still reported.

## 13. Decisions
Decided on 2026-10-31 (Tyler accepted the recommendations):
1. the bootstrap-t bound, with a simulated size check and a calibrated level where needed;
2. one-sided 0.05 (Holm while A and B were co-primary);
3. the ADR 0004 schedule applied in real time, forecasting only scheduled versions;
4. the candidate list kept as built, the backward half of the exclusion rule applied
   prospectively, and a sensitivity analysis with the 3 forward-excluded candidates;
5. the assay-sensitivity test and the informative-sequence secondary estimand;
6. S5 on strict items, with ADR 0018's test B replacing ADR 0017 decisions 1-2;
7. A and B computed together on one snapshot at S + 90 days, behind a second software gate;
8. the two parts of test B, the supplementary snapshot at L, and a stratified bootstrap;
9. a penalty pool of the five baselines only;
10. S1 on M5; M3 and M4 descriptive;
11. superiority over generic RJ in S4;
12. the model-change and budget-priority rules;
13. k = 3.

Decided on 2026-10-31, after the size simulation:
14. A is the sole primary hypothesis at one-sided 0.05; B is secondary and reported with its
    simulated size. The 6-month live window stays.

Decided on 2026-11-01:
15. The strict window rule stays: the next full hour at least 30 minutes after detection.
16. The live arm starts right after the `prereg-v2` tag, once one paid end-to-end check has
    passed; no calendar date.
17. gpt-6.1-sol runs at effort `high`, from its pilot (ADR 0014 decision 7).
18. The cost plan of section 8: the OpenAI cap is $100 a month until test A's batches are
    done (February 2027), and the live reserves are $20 (Claude) and $25 (OpenAI) a month.

No decision is OPEN.
