# Preregistration v2: LLM aftershock forecasts against USGS operational forecasts, retrospective and prospective

Status: **DRAFT, not frozen.** Tyler alone decides the freeze (tag `prereg-v2`). His decisions
are listed in section 13; none is open. The live path on prompt v3 is built, rehearsed and
deployed (2026-11-12, section 11).
Sources: ADRs 0004, 0006,
0011 and 0013-0018 (decisions of 2026-10-30 and 2026-10-31), the D1 and D2 results, the settings
pilots, three checks of this draft (2026-10-31: the author's, an independent fact check,
an independent methodology review), and the revision of 2026-11-11: an independent mock review
of the design (docs/reviews/mock-review-design.md), the proposal that answered it
(docs/proposals/prereg-v2-revision.md) and the development rerun with prompt v3 (`runs/d3`).
Where this document and an ADR disagree after the freeze,
this document governs, and every reference resolves to the tagged commit. Prereg v1 (tag
`prereg-v1`) stays frozen and governs the registered hackathon analysis.

## 1. Study and estimand
We compare probabilistic aftershock forecasts from general-purpose LLMs with the USGS
operational aftershock forecast (OAF) and with statistical baselines.
- **Information parity:** every forecaster is given the catalog the OAF had at each issue
  time, as closely as it can be rebuilt; the known gaps are listed at the end of this item.
  - Retrospectively, the catalog is rebuilt as it stood then from ComCat's product histories
    (ADR 0011). On 194 of the 195 candidates (computed before nn00914068 was restored), the
    rebuilt catalog reproduces the official products'
    own observation counts in 99.05% of 23,264 checks; today's revised catalog would give
    96.85%.
  - The prompt lists at most 800 events, with daily counts beyond that.
  - Prospectively, the catalog is the one fetched at detection.
  - Known gaps, stated and not corrected:
    - events since deleted from ComCat are not rebuilt (ADR 0011);
    - the prompt's mainshock location, depth, magnitude type and place name are those of the
      snapshot's ComCat event; only its magnitude is the official version's (`laf.items`);
    - an official version is matched to its event by today's mainshock magnitude and location
      (ADR 0013; about 1% of issue times);
    - analyst settings inside an official product are not available to any other forecaster;
    - prospectively, the catalog fetched at detection can hold events and revisions indexed
      after the official forecast was computed;
    - the prompt lists the catalog from M3.0 and does not say where it is complete. The
      regional completeness magnitude of the official model is 3.5 for 47 of test A's 89
      sequences, 4.6 for 39 and 3.0 for 3, so for 86 of them the absence of small events in
      the list is not evidence of quiet, and the model is not told (decided 2026-11-12:
      stated, the prompt unchanged).
- **Contamination:** each model is scored only on sequences whose mainshock falls after its
  training cutoff plus a 3-month buffer (section 3). In the prospective arm, contamination is
  impossible.

Per cell (issue time x window), dS = S(model) - S(official).
- **S** is the logarithmic score, as a loss, of the forecast probability p that at least one
  M>=5 earthquake occurs in the window: S = -log p if one occurs and -log(1 - p) if none does,
  with p clipped to [0.001, 0.999] (`scoring.log_score_binary`, the clip prereg v1 set for
  P(M>=6)). Lower is better, so negative dS favors the model.
- **What each forecaster reports:**
  - the model: the probability it states in its answer (section 3);
  - the official forecast: the product's published probability for the M>=5 bin, at full
    resolution;
  - each baseline: the probability from its own count distribution.
  - Nothing is reconstructed by the scorer.
- **The clip decides part of the score**, stated and not corrected:
  - the official probability is at or below 0.001 in 15.3% of test A's cells;
  - the rule of thumb states exactly 0 in 95.8% of them (it counts the M>=5 earthquakes so
    far), so its score is the clip: 0.001 nats without an event, 6.9 with one;
  - in the development rerun the stated probability is at or below 0.001 in 49% of gpt-5.1's
    answers (gpt-6.1-sol 29%, Opus 5.5 17%, Opus 4.6 and Sonnet 4.6 15%; shares of every
    answered window, scored or not).
  - In those cells the scorer uses 0.001 in place of the stated value. Clips of 0.0001 and
    0.01 are sensitivity analyses (section 6), reported without a verdict because the margin
    is set at 0.001: gpt-5.1's development mean is +0.009, +0.017 and +0.022 at clips of 0.01,
    0.001 and 0.0001.
- **Why a probability and not a count** (decided 2026-11-11, after the mock review of the
  design, docs/reviews/mock-review-design.md):
  - In 71% of test A's official cells all nine M>=5 quantiles are zero. The score through nine
    quantiles then gives every forecaster the same distribution, whatever it believed.
  - Nine zero quantiles mean a probability of at most 2.5%. The official probability in
    test A's cells has a median of 0.8%, a range that nine quantiles cannot express.
  - The probability of at least one earthquake is the official product's own headline number.
    Precedent for scoring it: Serafini et al. (2022) and Brehmer et al. (2023)
    (docs/research/novelty-and-literature.md, section E).
  - The count score through nine quantiles (ADR 0015: latent-PCHIP reconstruction, power-law
    upper tail, floor 1e-6) stays as a registered secondary analysis (section 6), because
    counts carry information the probability discards. Its reconstruction is the scorer's, so
    it is not a proper score of the reported quantiles alone.
- **Primary estimand:** the mean over sequences of the per-sequence mean dS.
- **Unit of answer:** a single chatbot answer to a fixed prompt. A model's dS in a cell is the
  mean over its k samples.

## 2. Hypotheses and decision rules
| Id | Hypothesis | Set | Test |
|---|---|---|---|
| **A** (primary) | gpt-5.1 is non-inferior to the official forecast | retrospective: gpt-5.1's clean M>=5 sequences (89 among the current candidates) | one-sided, delta = 0.02 nats per cell |
| C1 (negative control) | the rule of thumb, tested as if it were a model, is non-inferior to the official forecast; predicted result: not supported | test A's cells | as A |
| C2 (negative control) | one constant probability for every cell (0.041), tested the same way; predicted result: not supported | test A's cells | as A |
| B (secondary) | Claude Opus 5.5 against the official forecast | its clean retrospective M>=5 sequences plus prospective sequences (section 5) | estimate with its 90% interval and simulated size; no verdict |
| S1 (secondary) | Opus 4.6 against the official forecast | its clean M>=5 sequences (23); M3/M4 targets on the same sequences, descriptive | as B |
| S2 (secondary) | gpt-6.1-sol against the official forecast | prospective (ADR 0018 decision 3) | as B |
| S3 (secondary) | Opus 5.5, gpt-5.1, Opus 4.6 and gpt-6.1-sol each beat the rule of thumb | each model's A, B, S1 or S2 set | superiority, alpha 0.05 |
| S4 (secondary) | the same models against generic RJ and the legacy-ETAS refit | as S3 | superiority over generic RJ (alpha 0.05); estimate and 95% CI against ETAS |
| S5 (secondary) | Opus 5.5 (and gpt-6.1-sol) against the pipeline's baselines on strict prospective items | prospective strict items | as S3 and S4 |
| D (descriptive) | Sonnet 4.6; retrospective gpt-6.1-sol; M3 and M4 targets; D1 behavioral probes; hindsight effect (ADR 0016) | as stated | no test |

- **Decision rule** for A and for the controls C1 and C2, at one-sided 0.05:
  - **supported** if the upper bound of mean dS is below delta;
  - **supported, worse inside the margin** if, in addition, the lower bound is above 0: the
    model is non-inferior at this margin and measurably worse than the official forecast;
  - **inferior** if the lower bound is above delta;
  - **inconclusive** otherwise; **inconclusive, worse than the official forecast** if the
    lower bound is above 0 while the upper bound is above delta.
  - **Superiority** over the official forecast is tested for A at 0.05 only after its
    non-inferiority is supported (a fixed sequence on one hypothesis, so no extra alpha).
  - **B, S1 and S2 get no verdict** (decided 2026-11-11): each is reported as its estimate
    with a 90% interval, beside the simulated size of the same bound (section 6). At their
    numbers of sequences the test's size is not controlled (about 0.14 at a nominal 0.05 for
    B and S1; not simulated for S2), so a label would claim more than the data can carry.
  - **Scope of the claim** (decided 2026-11-11): test A's sequences are mainshocks of M5.0 to
    6.4 (61 of 89 are M5.0 to 5.4, none is M6.5 or larger) with automatic forecasts, for
    which the official forecast is close to the generic model: it is the generic RJ product
    at the first issue of 76 of the 89. "Supported" therefore means that the model matches
    the operational forecast on moderate sequences, not that it has skill specific to a
    sequence.
  - **What each outcome licenses**, written before any confirmatory outcome is seen:

    | A | Generic RJ (generic-model check) | Controls C1 and C2 | The paper may say |
    |---|---|---|---|
    | supported | inferior or inconclusive | neither supported | gpt-5.1 is non-inferior to the official forecast at the margin, on moderate sequences. |
    | supported | non-inferior | neither supported | gpt-5.1 is within the margin of the official forecast, and so is the generic model: a forecaster as good as a calibrated generic model, with no claim of skill specific to a sequence. The abstract carries that clause whenever it carries the first. |
    | supported | any | either supported | The test did not tell forecasters apart. No claim. |
    | inconclusive (either label) | any | any | Nothing in either direction. The estimate and its interval are reported, and the abstract says the comparison with the official forecast was inconclusive. |
    | inferior | any | any | gpt-5.1 is worse than the official forecast by more than the margin. |
    | supported | any | C2's lower bound not above 0 | The official forecast is not shown to beat one constant probability on these cells, so being within the margin of it shows nothing about skill. No claim rests on "supported"; the paper says so in the same sentence. |

    - **The reference's own effect** (decided 2026-11-12, after the mock review of the
      manuscript, docs/reviews/mock-review-manuscript.md). A non-inferiority result means
      something only if the reference is itself better than a forecaster that knows nothing.
      On development data that is not shown: the constant control is +0.021 against the
      official forecast with a 90% interval from -0.030 to +0.099. The paper therefore
      reports, beside test A, whether the lower bound of the constant control's difference is
      above 0 (`official_beats_constant` in the `control` row), whatever A's result, and the
      last row of the table applies when it is not.
    - The paper has no pre-written sentence for superiority over the official forecast or for
      a stratum or secondary interval below 0, and makes no headline claim from either: a
      stratum is an estimate without a verdict (section 6), and superiority is reported as
      tested (above) with the generic model's and the constant's results beside it.

  - **The most likely joint outcome**, by simulation from development effects: A
    inconclusive, the control not supported, generic RJ non-inferior. The paper then reports
    the estimate with its interval, the contrast S3 (the one analysis with power; its meaning
    is limited, because the rule of thumb states a probability of 0 almost everywhere) and
    the descriptive results. It does not present an inconclusive A as support.
  - No secondary target, secondary set or sensitivity analysis overturns a primary result.
- **One primary hypothesis** (Tyler, 2026-10-31): A, at one-sided 0.05.
  - B was co-primary with a Holm correction. It became secondary when the size simulation
    showed that no test controls its error at about 33 sequences (section 6).
  - The secondary superiority tests (S3, S4, S5) are at 0.05 each and labelled secondary.
    B, S1 and S2 carry no test against the official forecast (decision 39).
  - A and B are still computed together on the final outcome snapshot (section 5), because
    computing A early would reveal outcomes of October sequences that A and B share.
- **Margin delta = 0.02 nats per cell** (decided 2026-11-11; it replaces 0.10 on the count
  score).
  - **Meaning, from forecasts alone.** If the official probability were the truth, the
    expected loss on test A's 1,415 cells (mean of sequence means) would be:
    - 0.006 for a forecaster at half the official probability in every cell, 0.012 at double;
    - 0.014 at one third, 0.025 at one fifth, 0.042 at one tenth, 0.052 at three times;
    - at least 0.031 for any one constant probability used in every cell, sequence and window
      (the best constant is 2.9%).
    - So 0.02 lets a factor-of-two error through and keeps out a forecaster that knows
      nothing about the sequence. It is about two thirds of the official forecast's expected
      advantage over that constant.
  - **How the margin was reached**, in order, all on 2026-11-11 and all on development data
    and forecast tables (no confirmatory outcome was seen):
    - 0.02 was proposed before any model had answered prompt v3
      (docs/proposals/prereg-v2-revision.md, P3), as somewhat more than the cost of doubling
      every probability.
    - After the development rerun, 0.05 was set for a few hours as "half the official
      forecast's advantage over the rule of thumb" (decision 34). An independent review
      (docs/reviews/mock-review-revision.md) showed that anchor to be made by the clip (the
      rule of thumb's deficit is +0.038, +0.095 or +0.162 at clips of 0.01, 0.001 and 0.0001)
      and that 0.05 would admit the tenfold under-forecast and the constant above.
    - 0.02 was restored (decision 42). gpt-5.1's development result (+0.017) was known when
      it was restored; of the margins considered it is the one test A is least likely to pass.
  - **Sensitivity margins, named in advance:** 0.05 and 0.10. The same estimate and bound are
    read at both and reported beside the primary result. Neither changes it.
  - **The primary test is expected to be inconclusive.** Simulated from gpt-5.1's development
    effects on 89 sequences (below), test A is supported in 4% to 11% of studies. The paper's
    finding is then the estimate with its 90% interval, read against the scale above, and not
    a verdict.
  - **Generic-model check** (decided 2026-10-31; called "assay sensitivity" in earlier
    drafts and still in the code's row names. Renamed 2026-11-12: in the trial literature
    (ICH E10) that term means a trial's ability to tell an effective treatment from an
    ineffective one, which this check does not show): the same non-inferiority test is run for generic RJ
    against the official forecast on test A's cells. If generic RJ is also non-inferior, A is
    reported as unable to separate the model from the generic default, and no claim of
    sequence-specific skill rests on it. On development data generic RJ minus official is
    -0.009 (90% interval -0.155 to +0.014). Simulated at 89 sequences, generic RJ is
    supported in 99% of studies if its true difference is that development mean and in 70%
    if it is 0 (in every study at margins of 0.03 and above with the development mean), so
    the clause is expected to apply. On B's and S1's cells the same contrast is an estimate
    with its interval, without a label.
  - **Negative controls** (decided 2026-11-11): two forecasters that should not pass, each
    tested against the official forecast on test A's cells exactly as a model would be, each
    predicted "not supported".
    - **C1, the rule of thumb.** It states exactly 0 in 95.8% of test A's cells, so its score
      is set by the clip. Simulated: supported in 0.3% of studies of 89 sequences at the
      margin of 0.05 and in none at 0.02; labelled inferior in about 63% and inconclusive in
      about 37%. Its prediction can hardly fail, which makes it a weak control.
    - **C2, one constant probability for every cell:** 0.041, the share of scored development
      cells with an M>=5 earthquake (22 of 536), fixed now (`d2.CONTROL_P`). It is the
      forecaster the margin is set to keep out. On development data it is +0.021 (90%
      interval -0.030 to +0.099). Simulated: supported in 8% of studies at 0.02 (33% at 0.05,
      83% at 0.10). So this prediction can fail, about one time in twelve, and the bound's
      simulated size for effects like these is 0.08, above its nominal 0.05.
    - If either control is supported, the paper says that the test could not tell forecasters
      apart, and no claim rests on A (the table above).
    - Sonnet 4.6 was first chosen as a control ("inferior", from its development result with
      prompt v2A). It is not one: with prompt v3A its development result is no worse than the
      official forecast (section 3). It stays descriptive.
  - **Informative-sequence secondary estimand** (revised 2026-11-11): the primary estimand on
    the sequences where generic RJ's probability of at least one M>=5 earthquake is at least
    0.10 in the month window of the sequence's first issue that has a month window (one first
    issue among test A's published day and week windows only).
    - It is outcome-blind and blind to both contestants; the earlier rule selected on the
      official forecast's mean count and kept 5 of 89.
    - For a prospective sequence the same probability is read from the sealed baselines
      record of its first released issue that has a month window, on its matched item
      (`live_scores.live_informative`).
    - 49 of test A's 89 sequences qualify. Seven lie between 0.101 and 0.103, so the set is
      sensitive to the threshold's value; it is fixed by the frozen forecasts
      (`confirmatory.informative`).
- **Power, with the registered bootstrap-t:**
  - It is simulated from each model's own sequence effects in the development rerun with
    prompt v3 (39 sequences for gpt-5.1, 1,000 simulations):
    `laf confirmatory-size --snapshot 20261021T2300Z --v3 --delta 0.02 0.03 0.05 0.10`,
    `results/confirmatory_size_d3_20261021T2300Z.csv`.
  - A, 89 sequences, one-sided 0.05, margin 0.02: supported in 4% of studies if gpt-5.1's
    true mean is its development mean (+0.017), and in 11% if it is 0. The share of simulated
    studies in which each forecaster is supported:

    | Margin | gpt-5.1, true mean +0.017 | gpt-5.1, true mean 0 | C1, like the rule of thumb | C2, like the constant |
    |---|---|---|---|---|
    | **0.02** | 4% | 11% | 0% | 8% |
    | 0.03 | 8% | 20% | 0% | 15% |
    | 0.05 | 23% | 55% | 0.3% | 33% |
    | 0.10 | 95% | 99% | 6% | 83% |

  - The power depends on the tail of the model's effects, which development data cannot
    settle. With effects shaped like Opus 5.5's the same test at 0.02 is supported in 39% to
    45% of studies of 89 sequences; with gpt-5.1's, in 4% to 11%.
  - The result will turn on the few sequences with M>=5 aftershocks. The official forecast
    itself expects about 11 of test A's 89 sequences to have one in the first month. In
    development, two sequences of 39 carry gpt-5.1's mean of +0.017: their effects are +0.83
    and +0.54. Without the first the mean is -0.005, without both -0.020. gpt-5.1 is better
    than the official forecast on the typical sequence (median -0.013) and much worse where
    M>=5 aftershocks occurred: its stated probability is at or below the official one in 88%
    of answers and a fifth of it at the median (both before the clip).
  - Superiority over the rule of thumb (S3) has simulated power 0.996 for gpt-5.1 at 89
    sequences (development mean -0.079, size 0.032). At the secondary models' numbers of
    sequences, with gpt-5.1's effects: power 0.64 and size 0.022 at 23, power 0.80 and size
    0.031 at 33. Its meaning is limited: the rule of thumb states 0 almost everywhere.
  - The controls' columns in the table above and these S3 figures are the rows `rule of thumb
    (control C1)`, `constant probability (control C2)` and `... minus the rule of thumb (S3)`
    of the same file; generic RJ's share under "Assay sensitivity" is its row `generic RJ
    (assay sensitivity)`.
  - Under the earlier draft (count score, margin 0.10, prompt v2A) the power from the D2
    effects was 0.42 for A and 0.64 for B (`results/confirmatory_size_d2_20261021T2300Z.csv`;
    a first quoted 0.45 for A came from a run that no command recorded). The normal
    approximation used before that (`laf.power`) ignored the heavy tail.

## 3. Models and settings
| Model | Cutoff (see the note below the table) | Clean from | Settings | Role |
|---|---|---|---|---|
| `gpt-5.1-2025-11-13` | 2024-09-30 | 2025-01-01 | reasoning effort `medium` (ADR 0014 decision 6) | A |
| `claude-opus-5-5` | Jun 2026 | 2026-10-01 | registered request: no `thinking` field (adaptive by default), effort `high` | B |
| `claude-opus-4-6` | Aug 2025 | 2025-12-01 | `thinking: {"type": "adaptive"}`, effort `medium` (ADR 0014 decision 5) | S1 |
| `gpt-6.1-sol` | 2026-04-30 | 2026-08-01 | reasoning effort `high` (ADR 0014 decision 7); no dated snapshot, so each response's reported model is logged | S2 |
| `claude-sonnet-4-6` | Jan 2026 | 2026-05-01 | `thinking: {"type": "adaptive"}`, effort `low` | D |

- **The cutoff column** holds each vendor's documented date under the vendor's own name
  for it: "training data cutoff" for the Anthropic models, "knowledge cutoff" for the OpenAI
  models (ADR 0014). The paper uses the vendor's term for each (decided 2026-11-12).
- **Requests (all models):**
  - No sampling parameters, no tools, no prefill, no server-side fallbacks.
  - The JSON schema `prompts/v3/schema_direct.json`, strict where the API supports it, and an
    explicit effort.
  - Base URLs pinned to the official APIs. `response.model` and `usage` are logged for every
    call. In the batches, an answer whose `response.model` differs from the requested ID is
    invalid (`d2.samples`). Live, such an answer stops that model's accrual (model changes,
    below).
- **Prompt:** `v3A` (hashes in `prompts/v3/HASHES.json`; decided 2026-11-11, wording approved
  by Tyler).
  - It asks, per window, for nine quantiles of N(M>=5), N(M>=4) and N(M>=3) and for the
    probability of at least one earthquake at M>=3, M>=4, M>=5 and M>=6, and shows the catalog
    from M3.0. It is prompt `v2A` of the earlier draft plus the three probabilities below M6;
    the context, the catalog and the quantile lines are unchanged. One line of the system
    prompt changed with it: the models are told that their "probabilities and quantiles are
    scored with proper scoring rules". For the quantiles that promise refers to the log-scale
    quantile score (ADR 0001), a sensitivity analysis here; the count score through nine
    quantiles is not proper for the reported quantiles alone (section 1).
  - `v3B`, the same change to the paraphrase `v2B`, is a preregistered robustness check (ADR
    0015 decision 4), run by the A and B models only.
  - Development rerun with `v3A` (`runs/d3`, 2,094 answers; 3 invalid by the whole answer,
    none for the primary score, section 7): on the same 18
    sequences and the same count score, gpt-5.1, Opus 4.6 and Opus 5.5 score as with `v2A`
    (differences -0.002, -0.005, -0.001 nats per cell), and Sonnet 4.6 scores 0.14 better
    (+0.144 with `v2A`, -0.0004 with `v3A`; 95% interval of the difference -0.21 to -0.10).
    So the wording can matter for one model, which is what `v3B` is run to show for A and B.
  - One answer now holds two forecasts of the same quantity, and they can disagree. In the
    rerun the stated probability lies outside the range the same answer's nine quantiles
    leave for it, at some magnitude, in 85% of Opus 4.6's and Sonnet 4.6's answers, 48% of
    Opus 5.5's, 17% of gpt-5.1's and none of gpt-6.1-sol's. At M>=5 alone it is below that
    range in 21% of Opus 4.6's and Sonnet 4.6's answer-windows and in 0.1% of gpt-5.1's. The
    primary score reads the probability and the secondary score the quantiles (section 7).
- **Samples:** k = 3 per item (decided 2026-10-31), as in D2.
- **Output cap:** 32,000 tokens for every scored call, batch or live (live Claude calls stream; OpenAI calls do not).
- **Model changes** (decided 2026-10-31):
  - gpt-5.1 is removed from the API on 2027-04-01, so all test A forecasts are generated by
    2027-03-01.
  - If a model is withdrawn or changes (shown by `response.model`), its accrual stops then, and
    its tests use what accrued (decision 28). Live, the first answer whose `response.model` is
    set and differs from the requested ID marks the change: that model's answers from that
    issue on (in the order of the answers seals) are excluded from scoring and listed as
    "after a model change"; earlier answers stand. A batch is one point in time, so there a
    mismatched answer is invalid.

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
    3 were counted on 2026-10-31 without looking at their identities. They were identified
    on 2026-11-01, with Tyler's approval, to build the sensitivity analysis that adds them
    back (section 6 names them): from then on it is known that a larger event followed each
    of the three within a year, inside its circle. Nothing else about their outcomes was
    viewed (corrected 2026-11-12: this bullet and section 9 said that only counts were seen).
    - The candidate list stays as built, since the primary set must not change after this
      partial exposure.
    - Prospective sequences get only the backward-looking (aftershock) half.
    - Tests A, B and S1 are also reported with the 3 included, as a sensitivity analysis.
- **Primary set:** M>=5 mainshocks in each model's clean period.
  - Mainshock magnitudes are those of the frozen snapshot (retrospective) or at first
    detection (prospective). Test B therefore uses both definitions, one in each of its
    parts.
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
    window: the official product's own Mc (ETAS `Mc` or RJ `Mcat`) is at most 3.0, the
    regional completeness magnitude (`magcomp_mcat`) is at most 3.0, and the
    time-dependent completeness after the mainshock (`MagComp`, ADR 0009) reaches 3.0 before
    the window opens (ADR 0015). In practice these are 35 California candidates.
  - P(M>=6) is reported with its Brier score.
- **Outcomes:**
  - ComCat counts of events at or above the threshold (tolerance 1e-6) in the official
    forecast's region circle and window.
  - A cell is primary once its window closed at least 21 days before the outcome snapshot;
    2 days is a sensitivity analysis.
- **Prospective inclusion:** a new event with origin at or after L (section 5) qualifies by
  the same magnitude rules.
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
  - Revised 2026-11-11: the live models answer prompt `v3A` (section 3), and the second record
    seals each baseline's probability of at least one M>=5 earthquake beside its quantiles,
    so the probability score (section 1) needs nothing computed after the outcome. Built
    (`laf.prospective`); the detector runs it once that code is deployed (section 11).
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
  - Host (decided 2026-11-01): the Windows machine, for the whole live arm (ADR 0017 decision
    14): the full records must stay private until their windows close, which a GitHub Actions
    run cannot ensure.
- **On time:** a matched item enters test B only if its answer record's hash reached the
  GitHub push receipt before the item's first window opened (decision 22). The OpenTimestamps
  proofs witness that the record existed, not when to within the 30-minute margin.
  - **What the rule selects** (stated 2026-11-12, the detector unchanged). At 10-minute
    polling many first versions are detected after their first window has opened. In the dry
    run from 2026-11-01 to 2026-11-12 (24 issued versions on 14 sequences, 13 of the versions
    on secondary sequences) 11 were on time: none of 3 first versions, none of 3 at one day,
    2 of 3 at three days, 3 of 5 at seven, 3 of 4 at fourteen and 3 of 6 at twenty-eight
    (the log at ae0d8cb7 on `live-dryrun`: `detection` records with a slot, on time when the
    `receipt` record's `matched_receipt_margin_s` is above 0). Test B's prospective part will
    therefore hold few first-day cells, where the official probability is largest, and the
    paper says so and reports the on-time share by slot.
  - **What the evidence is.** The push time is read from GitHub's activity record by this
    machine and committed beside the seal; GitHub's own record may lapse. After that the
    30-minute claim rests on a file the author archived, bounded from outside only by the
    OpenTimestamps proof (hours). No third-party time stamp with finer resolution is taken.
  - Late, missed and failed items are listed with reasons and never backfilled. Missed
    includes every scheduled version of an included prospective sequence that was never
    issued (an outage, a ComCat delay): `live_scores.unissued`, from the outcome snapshot's
    versions, written as `live_missed_*.csv`.
  - "Failed" means a pipeline or transport failure: no answer was delivered (an error, or no
    reported model). A delivered invalid answer, even one without text, is scored under
    section 7, never excluded.
  - On-time and late versions are compared on outcome-blind covariates: magnitude, network or
    region, time since the mainshock, official model type. Built: `live_scores.timeliness`
    (the network is the event ID's prefix), written as `confirmatory_timeliness_*.csv`.
- **Arms of test B:**
  - L is the UTC time at which the paid detector starts (decision 26). Before its first poll it
    commits `start.json` (`start_ms`, and the deployed commit) to the `live` branch, and from
    then on it admits only sequences with origin at or after L ("before the start" in its log
    otherwise). Defining L by the first sealed record instead would put that record's own
    sequence, which began before it, outside the prospective part.
  - The retrospective part is the Opus-5.5-clean qualifying M>=5 sequences with origin in
    [2026-10-01, L). Those after the candidate snapshot are fetched once, by the same
    outcome-blind procedure, into a supplementary snapshot, at least 7 days after L so that a
    sequence that began shortly before L has its first OAF product: `laf candidates --since
    2026-10-29 --until <the day after L>` lists the OAF events that are not development and
    not aftershocks (the backward half of the rule, section 4; on the candidate window this
    procedure gives the 195 candidates plus the 3 forward-excluded ones; decision 19).
  - Prospective sequences have origin at L or later. A sequence belongs to exactly one part.
  - Test B is also reported for each part alone.
  - (This definition of the parts and the supplementary snapshot was decided 2026-10-31.)
- **Stopping rule:** sequences stop entering at S = min(L + 182 days, the latest origin among
  the first 26 eligible prospective M>=5 sequences in order of first detection); eligible
  means included as primary at its first detection (`inclusion.json` on the `live` branch,
  which records the detection time). Normally the latest origin is the 26th's own; taking the
  latest keeps all 26 in [L, S] when one is detected late. Prospective sequences have origin
  in [L, S] (decisions 23 and 27). `laf live-status` reports L, the eligible sequences in
  order and S, so the stop can be committed promptly.
  - In software: once config/live_stop.toml (S) is in the detector's checkout, a new sequence
    whose origin is after S is not admitted; admitted sequences keep their scheduled
    issues to the 28-day slot, and releases continue (`laf.live_watch`).
  - The 6-month clock does not pause for outages.
  - One outcome snapshot for A and B is taken at S + 90 days. That covers the last 28-day
    issue, its tolerance, a month window and 21 days of settling.
  - Built: `laf outcome-config` (the fetch's config: the frozen configs and every live item's
    sequence) and `laf outcome-snapshot` (`laf.outcome`). Forecast-time inputs stay as frozen
    in each sequence's own snapshot, checked against its manifest (the freeze manifest; for
    the snapshot at L, its own, written and timestamped when taken; a snapshot in no manifest
    is refused): items, issue times
    and catalogs, official forecasts, the ETAS refit. The fresh fetch gives only outcomes: each
    frozen issue's counts in its own circle and windows, and the catalog end that decides
    settling. Sequences with origin at L or later come from the fresh fetch alone.
  - There is no early stopping.
- **No interim looks** (decided 2026-10-31): no confirmatory score or test is computed before S + 90 days.
  Computing A early would reveal outcomes of October sequences that A and B share.
  - Built: the second software gate (`laf.splits`). At S, a commit records S (epoch ms) in
    config/live_stop.toml and Tyler tags it `prereg-v2-stop`. Outcomes of every confirmatory
    sequence, live records included, stay sealed until that tag exists and S + 90 days have
    passed; `laf live-score` refuses v2 records until then.
- **Budget priority** (decided 2026-10-31): a fixed live reserve. If the cap binds, the order is Opus 5.5 matched,
  then Opus 5.5 strict, then gpt-6.1-sol. Misses are listed as "missed: budget".
  - Each provider has its own reserve, so the order binds within a provider. Each item and
    model (k answers) runs if its worst case fits what is left, in that order
    (`prospective.plan_calls`).
  - Secondary sequences (M4.0-4.9, section 4) get model calls only while each call's worst
    case fits within the first half of the provider's monthly reserve; the second half is kept
    for primary sequences, so a swarm of small events cannot use up a month's reserve before
    an M>=5 sequence arrives (decision 31).
- **Live models:** Opus 5.5 and gpt-6.1-sol (decided 2026-10-31), gpt-6.1-sol at effort
  `high` (ADR 0014 decision 7).
- **Live start** (decided 2026-11-01): the live arm starts right after the `prereg-v2` tag,
  once one paid end-to-end check has passed (on a version the study does not use, published
  nowhere). L is then the paid detector's start (decision 26, replacing the first sealed live
  record); no calendar date is set.

## 6. Analysis (ADR 0018; `laf.confirmatory`)
- **Primary:** a sequence block bootstrap (B = 10,000, fixed seed) over the per-sequence mean
  dS. Test B resamples its retrospective and prospective parts separately.
  - **The bound** (decided 2026-10-31): a studentized (bootstrap-t) upper bound. Under heavy tails, the
    percentile bound drafted earlier claims
    non-inferiority too often. In an earlier simulation (ADR 0018 decision 8), with the true
    mean at delta and a nominal 0.025:
    - With effects like gpt-5.1's in D2 (one sequence in 18 at +1 nat), it errs 0.15 of the
      time at N = 33 and 0.05 at N = 88.
    - A studentized (bootstrap-t) bound errs 0.15 at N = 33 and 0.02 at N = 88.
    - At N = 33 no bootstrap can recover a rare event the sample misses.
    - Before the freeze, the registered test's size is simulated from the development
      effects shifted to delta. For test A, a size above 0.03 would have meant registering a
      calibrated nominal level as a number (decision 8 set that threshold when the level was
      0.025); it is not needed (below). B, S1 and S2 are reported as estimates with
      intervals and their simulated sizes, without a verdict (decision 39): no level can
      repair a size that comes from samples that miss a rare event.
    - Test B at about 33 sequences cannot rule out a rare-event deficit, and the paper says
      so.
  - **The level** (decided 2026-10-31): one-sided 0.05 for the single primary test, A. It
    matches the 90% interval of equivalence testing but is looser than the usual one-sided
    0.025 for non-inferiority; the power available justifies it. The bound at one-sided
    0.025 is reported beside it (the row `one-sided 0.025` of the sensitivity table, decided
    2026-11-12); it changes no verdict.
  - **Simulated size** of the bootstrap-t, from the development rerun's effects (prompt v3,
    probability score) shifted to delta (`laf confirmatory-size --v3`,
    `results/confirmatory_size_d3_20261021T2300Z.csv`):
    - At the registered level, 0.05, and N = 89: 0.034 (gpt-5.1-like effects) and 0.047
      (Opus-5.5-like effects). Both are below the nominal level, so no calibration is needed
      for A. (At nominal 0.025: 0.031 and 0.030.) For effects like the constant control's it
      is 0.083 (section 2).
    - The percentile bound drafted first would err 0.12 and 0.09 of the time at 0.05.
    - At N = 33: 0.165 and 0.144 at 0.05. S1 (Opus 4.6-like effects, N = 23): 0.142 at 0.05
      (0.093 at 0.025). These are why B and S1 carry no verdict (section 2). B is simulated
      as one sample of 33 sequences that all contribute cells, not as the two parts the test
      resamples separately. S2 is not simulated: gpt-6.1-sol's development effects come from
      11 sequences, none with an M>=5 aftershock.
    - Under the earlier draft (count score, D2 effects) the sizes at 0.05 were 0.018 and
      0.029 at N = 89, 0.14 at N = 33 and 0.084 for S1
      (`results/confirmatory_size_d2_20261021T2300Z.csv`).
- **Beside the mean:**
  - The 10% trimmed mean and the median of the sequence effects, with bootstrap intervals.
  - Leave-one-sequence-out influence on A and B (`confirmatory.influence`: each sequence's
    effect and the mean and bound without it; B with its two parts).
  - The hierarchical model dS_ijk = mu + u_i + v_ij + e_ijk, with window and stratum as fixed
    effects in sum coding. It is a robustness check that estimates an unweighted mean over
    windows and strata, not the mean of sequence means. If it fails to converge or cannot be
    fitted (too few sequences), that is reported in its row and the analysis goes on.
- **Sensitivity analyses**, all reported in one table whatever their result; anything not
  listed is exploratory:
  - the margins 0.05 and 0.10 (section 2);
  - test A on all clean candidates;
  - with the 3 forward-excluded candidates;
  - the non-overlapping subset (`sensitivity.NON_OVERLAP`: every day window, the week
    windows of the first, 7-day, 14-day and 28-day issues, and the month window of the first
    issue; the first issue keeps its three nested windows);
  - v3B;
  - valid answers only, invalid answers at the worst case, and invalid by the whole answer
    (section 7);
  - the probability clipped at 0.0001 and at 0.01 instead of 0.001;
  - the Brier score of the probability (estimate and bound only: delta is defined for the log
    score);
  - the count score through nine quantiles, the earlier draft's primary score (estimate and
    bound only), with its own variants:
    - the registered log-scale quantile score (ADR 0015 decision 1);
    - full-distribution scores of the official and ETAS forecasts;
    - the negative-binomial tail instead of the power-law tail;
    - log floors of 1e-4 and 1e-8, with the floor-binding rate per forecaster and the number
      of cells above each forecaster's 97.5% quantile;
  - the unbuffered clean rule (gpt-5.1's 13 M>=5 sequences that only it admits get their own
    batch, `confirmatory-unbuffered`, decision 21);
  - a release-date clean rule (for gpt-5.1 a subset of the buffered set);
  - the 2-day settling rule;
  - the subset where the as-of catalog matches the official observation counts exactly
    (the issue's M>=5 count in its as-of catalog, counted as the V0 check counts: the
    mainshock excluded, magnitudes within 0.01 of the threshold, equals the official
    product's own count);
  - region radius x0.5 and x1.5;
  - results by stratum, named in advance: under 1 day, 1 to 7 days, 7 days or more after the
    mainshock. The first day is where the official probability is largest (median 8.4%,
    against 0.3% after day 7);
  - results by who the sequences are (decided 2026-11-12), as estimates without a verdict:
    mainshock depth under 70 km and 70 km or more, and region (Alaska; the Marianas region,
    which is place names with Guam, Mariana or Micronesia; other). Of test A's 89 sequences
    36 are in Alaska, 35 in the Marianas region and 18 elsewhere (6 of them in or off
    Oregon); 20 are at 70 km or deeper (35 at 35 km or deeper, the deepest at 247 km); 72
    were located by the global network `us`; 19 have a body-wave magnitude (mb). For the 61
    mainshocks below M5.5, "at least one M>=5" is an event about as large as the mainshock:
    a doublet or foreshock probability more than an aftershock one;
  - dependence between sequences (decided 2026-11-12): the primary analysis resamples
    sequences as independent. The row `cluster-block bootstrap` resamples clusters instead:
    mainshocks of a model's set within 100 km and 30 days of each other are joined, and
    their neighbors' neighbors with them (`confirmatory.sequence_clusters`; locations and
    times only). The estimand and the bootstrap-t are unchanged, with the linearized
    standard error of a ratio of cluster totals. It is a sensitivity analysis, so it does
    not overturn the primary result (section 2); if its verdict differs, the paper reports
    the primary result as depending on the independence of neighboring sequences;
  - contamination (decided 2026-11-12): the mean dS on a model's sequences before its
    release minus that on the sequences after it, with a 90% interval (`before minus after
    the model's release`; for gpt-5.1, 62 sequences before and 27 after). Only the earlier
    group can have been in material published before the model existed. No recall probe
    is run on confirmatory mainshocks;
  - CSEP-style N-test, PIT and information gain per earthquake (ADR 0015);
  - invalid rates by arm, and by stratum and by whether an M>=5 earthquake occurred in the
    cell, so that invalid answers concentrated in hard cells are visible (section 7).
- **Software:** `laf confirmatory --snapshot S --runs DIR` refuses to run until both gates are
  open (the tag `prereg-v2`; the tag `prereg-v2-stop` and S + 90 days).
  - It computes A, B and S1 against the official forecast on the probability score
    (`d2.analyze(score="probability")`), with the trimmed mean, median and hierarchical model.
  - The registered decision for A is its `noninferior` column at 0.05. The `status` column
    applies section 2's rule to A: supported, supported and worse inside the margin, inferior
    (the lower bound at the same one-sided level above delta; `confirmatory.decide`, decision
    25) or inconclusive. B and S1 keep their estimate and bounds, with no status.
  - Built: the registered bound and its size simulation (`laf confirmatory-size`); models
    outside the primary and secondary lists (Sonnet 4.6 among them) get no test row.
  - Built: the secondary table (`laf.confirmatory.secondary`, written beside the tests): the
    contrasts S3 and S4 (dS against each pipeline baseline on the model's own test cells), the
    assay-sensitivity test, the negative controls C1 and C2 (`control` rows: the rule of
    thumb's and the constant probability's own tests against the official forecast on the
    model's cells), and the informative-sequence
    estimand (`confirmatory.informative`: generic RJ's month-window probability, computed
    from the frozen forecast-time tables with no count read).
  - Built: the descriptive table (`laf.descriptive`, `confirmatory_descriptive_*.csv`;
    decision 30). For every model with answers, Sonnet 4.6 and the retrospective gpt-6.1-sol
    included, on its own clean M>=5 set: the mean dS against the official forecast at M>=4
    and at M>=3, for the count quantiles and for the probability of at least one earthquake
    (against the product's published probability; M3 only where the completeness rule of
    section 4 holds), over sequences of per-sequence means, from valid answers only (the
    invalid-answer penalty is registered at M>=5); and the Brier score of P(M>=6) for the model, the official forecast (its published
    M>=6 probability) and the pipeline baselines on the same cells, each beside its difference
    from the official one. No test. It covers the retrospective batches; the live items are
    scored at M>=5 only.
  - Built: the prospective inputs (`laf confirmatory --live <worktree of live>`;
    `laf.live_scores`). Every released issue is scored on the outcome snapshot: whether an
    M>=5 earthquake occurred in the item's own circle and windows, from its own sequence's
    catalog, once settled 21 days. On matched items the answer's stated probability is scored
    against the matched official version's published probability. Strict items have no
    official forecast: the stated probability's score stands by itself there, beside the
    scores of the pipeline's baselines' sealed probabilities. Answers to prompt v2A (the dry
    run before the deploy of section 11) state no M>=5 probability and are never scored. Test B joins its retrospective part (origin before L) and its prospective
    part (sequences included as primary at first detection, `<sequence>/inclusion.json`;
    origin in [L, S]; on-time matched items) in the two-part bootstrap
    (`noninferiority(..., strata=...)`: each part resampled at its own size, with the
    stratified standard error; a part with fewer than two sequences has no spread, and then
    all sequences are resampled together), and is reported for each part alone. S2 is
    gpt-6.1-sol on the same prospective items; its retrospective batch is descriptive, with no
    test row (decision 24). S3 and S4 use each model's full set (B's two parts, S2's items).
    S5 contrasts the on-time strict items with each baseline. Every live item is listed with
    its on-time, failed and missed answers.
  - Built (`laf.sensitivity`): region radius x0.5 and x1.5 (outcomes recounted from each
    sequence's own catalog, x1.5 only where the catalog query covered it); in one table, the
    margins 0.05 and 0.10, test A on all clean candidates, the unbuffered and release-date
    clean rules, the non-overlapping subset, v3B, valid answers only, invalid answers at the
    worst case, invalid by the whole answer, the exact-match subset, the 2-day settling rule and the strata, with invalid
    rates by arm written beside it (`confirmatory_invalid_*.csv`) and, by stratum and by
    whether an M>=5 earthquake occurred in the cell, in `confirmatory_invalid_cells_*.csv`;
    the scoring variants (the probability clipped at 0.0001 and 0.01; its Brier score; the
    count score through nine quantiles with log floors 1e-4 and 1e-8, the negative-binomial
    tail, full distributions of the official forecast (its published fractile grid of 197 or
    399 points) and the ETAS refit (its simulated histogram), and the log-scale quantile
    score; every variant in another score than the probability's log score reports its
    estimate and bound without delta); and per forecaster's count quantiles the floor-binding
    rates, cells above its 97.5% quantile, N-test failures, the PIT's KS distance and
    information gain per earthquake. In every row of these tables a secondary model keeps its
    estimate and bound and carries no verdict.
    Release dates are the Models API creation dates, checked 2026-11-01: gpt-5.1 2025-11-10,
    Opus 4.6 2026-02-04, Sonnet 4.6 2026-02-17, gpt-6.1-sol 2026-09-27, Opus 5.5 2026-09-21.
  - Built: tests A, B and S1 with the 3 forward-excluded candidates (`laf.sensitivity`; they
    are in config/sequences_forward_excluded.toml and never enter a main analysis). They were
    identified on 2026-11-01 with Tyler's approval: nc75094976 (M4.23, 2024-12-04), us7000q8wx
    (M4.40, 2025-06-26) and us7000s2bn (M5.50, 2026-03-05), each followed within a year by a
    larger event whose circle holds it. Only us7000s2bn is in a tested model's clean M>=5 set
    (gpt-5.1 for A, Opus 4.6 for S1); nc75094976 predates gpt-5.1's clean period and is
    secondary, and us7000q8wx is an M4 on the global network. Their data are in the
    forward-excluded snapshot 20261101T2202Z (outcomes sealed), and their forecasts (gpt-5.1
    and Opus 4.6, v3A, k = 3, about $1.76 by the runners' estimates, approved) run after the
    tag with the other confirmatory
    batches. The outcome snapshot at S + 90 days fetches this config with the candidates.

## 7. Invalid outputs
- An invalid answer counts a fixed dS of log 2 (0.69 nats, a coin flip against a certain
  outcome; decided 2026-11-11).
  - **For the primary score an answer is invalid when it gives no usable M>=5 probability**
    for the window (`schemas.stated_p5`): a refusal, an answer cut off at the output cap,
    text that does not parse, a probability that is missing or outside [0, 1], or, in the
    batches, a mismatched `response.model` (section 3). A delivered answer without text (cut
    off while reasoning, or a refusal with no text) is invalid too, batch or live; only a
    failure to deliver an answer is a transport error. A defect elsewhere in the answer
    (non-monotone quantiles, another value out of range) does not make the M>=5 probability
    invalid.
  - **This rule changed after the development rerun, and the change is disclosed.** The draft
    judged the whole answer. All three invalid answers of the rerun (gpt-5.1) state a usable
    M>=5 probability; one fails only on its M>=3 quantiles for the month. Under the whole-answer
    rule they counted log 2 for a number the primary score never reads, and gpt-5.1's
    development mean was +0.019; under this rule it is +0.017. The whole-answer rule is
    a registered sensitivity analysis ("invalid by the whole answer").
  - For every other target (the count score, the descriptive M>=4 and M>=3 results) the whole
    answer must be valid: a schema violation, an answer cut off at the output cap, a refusal,
    non-monotone quantiles, a value out of range, or a mismatched `response.model`.
  - The penalty does not depend on k, on the cell or on which other runs exist.
    `laf.confirmatory` applies it.
  - No fixed penalty can be both mild and unable to help a model. With probabilities clipped
    to [0.001, 0.999] a valid answer can lose up to 6.9 nats, so log 2 is better than a valid
    answer that was badly wrong. Two registered safeguards:
    - the worst-case rule (an invalid answer scored as the clipped probability on the wrong
      side, 6.9 nats) is a sensitivity analysis, and if the verdict differs between the two
      rules the paper reports the result as depending on how invalid answers are handled;
    - invalid rates are reported by stratum and by whether an M>=5 earthquake occurred in the
      cell (section 6).
  - For scale: an invalid rate of 3% alone uses up the margin of 0.02. In the development
    rerun no answer of any model is invalid for the primary score; by the whole answer
    gpt-5.1 has 3 invalid answers in 630 (0.5%) and the other four models none. Two of the
    nine answer-windows those three cover lie in first-day cells where an M>=5 earthquake
    occurred, the concentration the second safeguard is there to show.
  - The earlier draft's rule, the worst score in the cell among the five baselines (official,
    generic RJ, RJ-MLE, the rule of thumb, the legacy-ETAS refit), costs exactly zero where
    the baselines agree (47% of test A's cells): a forecaster that never answers scored +0.0975
    on development data. It is kept for the count score, the secondary analysis.
- A probability at a larger magnitude above the one at a smaller magnitude, and a probability
  outside the range the same answer's nine quantiles leave for it, are warnings with reported
  rates, not invalid: each target is scored on its own numbers. The development rates are in
  section 3.
- The Brier variant of section 6 scores an invalid answer at its worst case (a Brier score of
  1): log 2 is a quantity in nats and has no meaning there.
- On strict live items there is no official forecast, so scores are not differences: an
  invalid answer there scores log 2 itself, the score of a probability of one half
  (`live_scores.live_samples`).
- "The five baselines" can be four: RJ-MLE falls back to generic RJ where the as-of catalog
  holds fewer than 10 events of M>=4.95, and it equals generic RJ in every development cell.
- Magnitudes that disagree across targets (an M3 count below an M4 count) are a warning, not
  invalid at M5.
- Retrospective transport errors are retried, up to 10 attempts. Persistent failures are listed
  and left out.
  - Built: `laf run --retry` and `laf openai run --retry` resend the latest attempt's
    errored, expired, cancelled or missing requests, unchanged (each checked against its ledger
    hash), as `<run>-retry2` up to `-retry10`; an answer, valid or not, is never resent. A
    retried error that a later attempt answered drops out (`d2.samples`); the rest are listed
    (`confirmatory_failures_*.csv`).
- Invalid rates are reported per model and arm (retrospective batches, prospective answers).

## 8. Budget
- Claude spend is capped per calendar month (`LAF_CLAUDE_MONTHLY_CAP_USD`) and OpenAI spend
  separately (`LAF_OPENAI_MONTHLY_CAP_USD`).
- Every retrospective batch is approved by Tyler with its cost estimate.
- Live calls spend only a fixed live reserve per provider (ADR 0017, "The paid path").
- **Cost plan** (decided 2026-11-01). Estimates use the token counts measured in D2 and the
  gpt-6.1-sol pilot at current prices; each batch's own estimate, with a 25% margin, is what
  Tyler approves.
  - Retrospective batches (k = 3, Batch API): A, gpt-5.1 on v3A for all 175 clean candidates
    (the 89 M>=5 and test A's sensitivity set), about $109, and on v3B for the 89, about $55;
    B, Opus 5.5 on v3A and v3B for its retrospective part, about $4; S1, Opus 4.6, about $9;
    gpt-6.1-sol (descriptive: S2 is prospective), about $3; Sonnet 4.6 (descriptive), about $3. In all, about $16 Claude
    and $167 OpenAI.
  - Live: about $0.21 Claude and $0.41 OpenAI per issue (two items, k = 3, both live models;
    worst case $3.89 and $1.94); at about 42 issues a month (8 sequences, 5.2 issues each),
    about $9 Claude and $17 OpenAI a month.
  - Caps and reserves: Claude $200 a month with a $20 live reserve; OpenAI $150 a month from
    November 2026 to January 2027, $100 in February and $50 after, with a $25 live reserve
    (decision 20).
  - Order: test A's batches first, two half-parts a month (v3A on the 89, then the sensitivity
    set, then v3B, then the unbuffered extras), planned by the end of January 2027 and no later
    than 2027-03-01 (section 3; the freeze moved from November to December): gpt-5.1 shuts
    down on 2027-04-01. The Claude batches on the candidate snapshot run right after the tag
    (Opus 4.6 retires no sooner than 2027-02-05, Sonnet 4.6 no sooner than 2027-02-17); B's
    batches on the supplementary snapshot after L.
  - Commands (runs under `runs/confirmatory/`): `laf openai run --block confirmatory`,
    `confirmatory-sens` (gpt-5.1 below M5), `confirmatory-v3b` or `confirmatory-unbuffered`
    (gpt-5.1's unbuffered extras), and `laf run --block
    confirmatory` or `confirmatory-v3b` for Claude; each sends only the model's own clean set
    at its study settings (`confirmatory.batch_items`). `--chunk K/N` splits a batch whose
    estimate exceeds the month's room; `--forward-excluded` runs the forward-excluded
    snapshot. The runners' estimates (pilot output tokens, plus 25%) are above the plan's:
    $86.52 for gpt-5.1's primary prompt on the 89, $84.49 for the sensitivity set and $86.60
    for the robustness prompt, about $258 against the plan's $164 (about $13 more for the
    unbuffered extras). Each goes in two parts of about $43.
  - **Prompt v3** (2026-11-11): the estimates above were computed with prompt v2. Prompt v3
    adds three lines to the input. In the development rerun gpt-5.1 used 8,383 output tokens
    per answer on 39 sequences, against 7,543 with prompt v2 on 18 of them (different item
    sets, so the difference is not the prompt's alone). The rerun's actual cost was below the runners'
    estimates: $26.92 against $38.71 for gpt-5.1 and $31.79 against $42.15 for the three
    Claude models. So the runners' estimates above still bound the plan; each batch's own
    estimate is recomputed and approved before it is sent.
  - The development rerun with prompt v3 (`runs/d3`, approved 2026-11-11) cost $31.79 (Claude)
    and $31.80 (OpenAI).

## 9. Availability and timeline
- All items, sealed records, answers, scores and code are released with a DOI at
  publication.
- Dates: the freeze; L; S; the outcome snapshot at S + 90 days; test A's runs by 2027-03-01.
- **Prior exposure:**
  - The V0 check compared official observation counts in later versions, which hold partial
    outcomes of earlier windows (allowed by ADR 0013).
  - Since 2026-10-30, the live dry run has tracked new official versions of some October
    candidates; only its timing logs were viewed.
  - On 2026-11-02 the paid end-to-end check (one issue, published nowhere) produced 12
    answers from Opus 5.5 and gpt-6.1-sol for a dry-run version of us6000tzna (2026-10-05), a
    candidate in test B's retrospective part. That version is not in the frozen snapshot, and
    only the answers' format and validity were checked.
  - On 2026-11-12 the check was repeated on prompt v3 and the deployed live path (one issue,
    published nowhere): 12 answers from Opus 5.5 and gpt-6.1-sol for the dry run's 28-day
    version of aka2026ukynnb (2026-10-15), a candidate in test A's set and in test B's
    retrospective part. That version is not in the frozen snapshot. Only the answers' format
    and validity were checked; the items' catalog was not viewed and nothing was scored.
  - Of the fore/aftershock exclusions, aggregate counts were viewed, and on 2026-11-01 the
    identities of the 3 forward-excluded events (section 4): a larger event is known to have
    followed each within a year, inside its circle.
  - On 2026-11-12 the mock review of the manuscript and the lead's check of it counted, on
    the candidate snapshot's `sequences`, `issue_times` and `forecast_bins` tables (mainshock
    metadata and forecasts; no catalog, no observed count, no score): test A's sequences by
    region, depth, network, magnitude type and completeness magnitude (section 6), the
    spread of the circle radii and of the first version's delay, and how many of test A's
    mainshocks have another within 20 to 100 km and 30 days (23 of 89, the reviewer's count).
    The reviewer's script loaded `issue_times`, which carries the official product's own
    observation counts; it reports that those columns were neither printed nor used.
  - The revision of 2026-11-11 used outcome-blind counts on the candidate snapshot's forecast
    and sequence tables (no catalog, no observed count, no score): the share of test A's
    cells with nine zero quantiles (71%), the official probability's distribution (median
    0.8%; at or below 0.001 in 15.3% of cells), how often the baselines' quantiles equal the
    official ones, the rule of thumb's probability (exactly 0 in 95.8% of cells), generic
    RJ's month-window probability per sequence (49 of 89 at or above 0.10), and the expected
    loss of simple forecasters if the official probability were the truth (section 2). The
    two mock reviews that made or prompted these counts are in docs/reviews/. The first of
    them also counted, on the same tables, the official model type by issue time
    (Reasenberg-Jones at 463 of 472), the median radius of the forecast circle (10 km),
    how many of test A's sequences precede gpt-5.1's release (62 of 89), and the mainshock
    magnitudes of test A's sequences (61 of 89 are M5.0 to 5.4, none is M6.5 or larger),
    which section 2 quotes under "Scope of the claim" (added 2026-11-13).

## 10. Changes from prereg v1
- **Data:** 195 confirmatory candidates instead of the registered sequences; prospective
  sequences counted toward a test.
- **Contamination:** the 3-month buffer now applies to the Claude 5.5 models too.
- **Scoring:** the log score of the stated probability of at least one M>=5 earthquake as the
  primary score instead of the log-scale quantile score; the log score of the count
  distribution, representation-matched through nine quantiles, is secondary.
- **Tests:** formal non-inferiority tests with a margin and decision rules, instead of
  descriptive hypotheses (one primary hypothesis since decision 14, so no multiplicity
  correction).
- **Models:** older-cutoff and other-vendor models with study settings fixed by pilots.
- **Prompts:** v3 with M3 targets and the probability of at least one earthquake at M>=3,
  M>=4 and M>=5 beside the one at M>=6.
- **Invalid answers:** a fixed penalty of log 2 instead of the worst valid score in the cell,
  with the worst case as a sensitivity analysis. Invalid rates are reported, where v1 made
  them an outcome.
- **Prospective arm:** strict and matched items with a stopping rule instead of the v1
  demonstration.

## 11. Freezing procedure
The freeze needs all of the following:
- No item marked OPEN, TO BUILD or TO FIX remains.
- `laf confirmatory` has run end to end on a development snapshot, including the prospective
  inputs and the size simulation.
  - Done 2026-11-01 on 20261021T2300Z: `laf confirmatory-dryrun` (the tests, the secondary
    table, the sensitivity analyses, the scoring variants, the diagnostics) with `--live` on a
    `laf live-rehearsal` issue (us7000ti1p: the real prospective pipeline, items, seals,
    spend file and baselines, with synthetic answers from stub clients and the settling check
    overridden, `--assume-settled`: a rehearsal of the code path, not a result), and
    `laf confirmatory-size`, which reproduces the sizes quoted in section 6.
  - Done 2026-11-02 for the outcome snapshot (`laf.outcome`): the 39 development sequences
    fetched again (20261102T1247Z, a scratch data folder), assembled with the frozen
    20261021T2300Z (210 items and their issue tables, official forecasts and ETAS refit kept;
    3,780 counts recounted, 5 changed by catalog revisions, 114 more windows closed), then
    `laf confirmatory-dryrun` on the assembled directory, every output written. `laf
    confirmatory` itself refuses before the tag; the dry run shares its secondary, sensitivity,
    scoring, live and listing functions, while its main table takes development cells
    (`power.d2_cell_differences`) where `laf confirmatory` takes `confirmatory_cells`, which
    tests cover.
  - Redone in part after the revision of 2026-11-11: `laf confirmatory-dryrun` on the
    development rerun (`runs/d3`, prompt v3, the probability score; its main table now takes
    `confirmatory_cells` too) and `laf confirmatory-size --v3`, which reproduces the sizes
    and powers quoted in sections 2 and 6.
  - Built 2026-11-11: the live path on prompt v3 and the probability score
    (`laf.prospective` sends v3A and seals each baseline's probability; `laf.live_scores`
    scores the stated probability against the matched official version's). Rehearsed the
    same day: `laf live-rehearsal` on us7000ti1p (the real prospective pipeline with
    synthetic answers to prompt v3A; the sealed baselines carry their probabilities), then
    `laf confirmatory-dryrun --live` on it with `--assume-settled`, every output written.
  - Done 2026-11-11 for the outcome snapshot, again, with the probability score: the 39
    development sequences fetched afresh (20261111T2239Z, a scratch data folder), assembled
    with the frozen 20261021T2300Z by `laf.outcome.assemble` (210 items and their forecast
    tables kept; 3,780 counts recounted, 17 changed by catalog revisions, 144 more windows
    closed), then `laf confirmatory-dryrun` on the assembled directory, every output written
    (gpt-5.1 +0.018 there, against +0.017 on the frozen snapshot's outcomes).
  - Done 2026-11-12: the detector deploy of the live path (Tyler's; runbook section 0.4,
    commit fe904a0b, logged in ops/deploys.md). The dry run continues on prompt v3: its first
    scheduled version on this code was sealed the same day with the baselines' M>=5
    probability in every row, and the paid end-to-end check was repeated on it (section 9).
    Nothing is listed as open before the tag.
- Tyler tags `prereg-v2` (an annotated tag) on a commit that holds this document and the
  manifest below. The SHA-256 of these is posted publicly with the tag's commit hash:
  - this document;
  - `prompts/v3/HASHES.json` and `prompts/HASHES.json` (the shared templates every v3 prompt
    also renders);
  - `uv.lock` (the exact package versions);
  - the items files;
  - the `src/laf` tree (its tracked files);
  - the data manifest;
  - the candidate snapshot tables;
  - `config/splits.toml` and the sequence configs;
  - the baseline forecasts (ETAS refit with seeds), computed before any outcome is unsealed.
- The tag opens the first software gate (`laf.splits`); every confirmatory outcome stays sealed
  behind the second gate until S + 90 days (section 5, no interim looks).
- `laf freeze-manifest --snapshot 20261029T2000Z 20261101T2202Z` writes, for the candidate and
  the forward-excluded snapshots, the items (`items_m3.jsonl`) and the baseline forecasts
  (`baselines_m3.jsonl`, with the ETAS refit of `laf etas`; each row carries the baseline's
  probability of at least one M>=5 earthquake beside its quantiles) without any outcome, and the SHA-256
  of every artifact above with one hash over the whole manifest (`results/freeze_manifest.json`).
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

Decided on 2026-11-02:
19. The supplementary snapshot at L selects by the backward half of the exclusion rule only
    (section 5), as the live arm does: the forward half needs up to 365 days after the origin,
    and the later event can fall in the sequence's own windows. A supplementary sequence later
    followed by a larger event stays in B, as a live one would; the paper notes it as a
    limitation.
20. The OpenAI cap is $150 a month from November 2026 to January 2027, $100 in February and
    $50 after (replacing decision 18's $100 to February): test A's batches cost about $258 by
    the runners' estimates, and gpt-5.1 shuts down on 2027-04-01.
21. The unbuffered clean-rule sensitivity analysis gets its own batch: gpt-5.1 on the 13 M>=5
    sequences that only the unbuffered rule admits (v2A then, now v3A; k = 3, about $13); without it, that
    row would repeat the main analysis.
22. On time means GitHub's push receipt before the first window; the OpenTimestamps clause is
    dropped, since a proof does not time a record to within the 30-minute margin.
23. S is the origin of the 26th eligible prospective sequence (or L + 182 days), eligible
    meaning included as primary at first detection; prospective origins are in [L, S], and
    the detector refuses origins after S.
24. S2 is prospective only, as registered; the retrospective gpt-6.1-sol batch is descriptive.
25. The decision rule's lower bound is computed at the same one-sided level, so each tested
    row is labelled supported, inferior or inconclusive.

Decided on 2026-11-04, after a pre-freeze review of the code and this document:
26. L is the time the paid detector starts, published as `start.json` on the `live` branch
    before its first poll; the detector admits only sequences with origin at or after L; the
    supplementary snapshot is taken at least 7 days after L (section 5).
27. Eligible prospective sequences are counted in order of first detection, and S is the
    latest origin among the first 26 (or L + 182 days, if earlier), replacing decision 23's S
    rule; `laf live-status` reports them (section 5).
28. A model change stops that model's live accrual at its first mismatched `response.model`;
    in the batches a mismatched answer stays invalid (section 3).
29. A calibrated level applies to test A only; B, S1 and S2 are tested at nominal 0.05 and
    reported with their simulated sizes (section 6).
30. S1 stays on Opus 4.6's 23 clean M>=5 sequences, with M3 and M4 targets descriptive on the
    same sequences; the descriptive table and the Brier score of P(M>=6) are reported (section 6).
31. Secondary live sequences use only the first half of each provider's monthly live reserve
    (section 5).

Decided on 2026-11-11, after an independent mock review of the design
(docs/reviews/mock-review-design.md), the proposal that answered it
(docs/proposals/prereg-v2-revision.md) and a development rerun with prompt v3 (`runs/d3`):
32. The primary score is the log score of the stated probability of at least one M>=5
    earthquake, clipped to [0.001, 0.999], against the official product's published
    probability; the count score through nine quantiles is secondary (sections 1 and 6).
33. Prompt v3: `v3A` is scored and `v3B` is the robustness prompt; they are `v2A` and `v2B`
    plus the probability of at least one earthquake at M>=3, M>=4 and M>=5 (section 3).
34. The margin is 0.05 nats per cell, half of the official forecast's advantage over the rule
    of thumb on development data, replacing 0.10. The registration states that this anchor
    is uncertain and names 0.02 and 0.10 as sensitivity margins (section 2). Replaced the
    same day by decision 42.
35. A stays a non-inferiority test against the official forecast, with the claim scoped to
    moderate sequences where that forecast is close to the generic model (section 2).
36. The rule of thumb is the registered negative control C. Sonnet 4.6 is not a control: its
    development result changed with prompt v3. It stays descriptive (sections 2 and 3).
37. An invalid answer counts a fixed dS of log 2, with the worst case as a sensitivity
    analysis and invalid rates by stratum and by event, replacing decision 9 for the primary
    score (section 7).
38. The informative-sequence estimand selects on generic RJ's month-window probability, at
    least 0.10, replacing the rule of decision 5 (section 2).
39. B, S1 and S2 are estimates with intervals and simulated sizes, without a verdict,
    replacing the nominal tests of decisions 14 and 29 (sections 2 and 6).
40. Results by stratum are named in advance, and a supported row whose lower bound is above 0
    is labelled as worse inside the margin (sections 2 and 6).
41. No outside protocol review is invited before the freeze (Tyler, 2026-11-11). Two mock
    reviews by fresh agents of this project are in the repository (docs/reviews/); they are
    not an independent outside review, and the paper says so.

Decided on 2026-11-11, later the same day, after an independent review of the revised text
(docs/reviews/mock-review-revision.md) showed that decision 34's anchor does not hold:
42. The margin is 0.02 nats per cell, the value proposed before any model had answered
    prompt v3, replacing decision 34. 0.05 and 0.10 are the sensitivity margins. The
    registration says that the primary test is expected to be inconclusive and that the
    paper's finding is the estimate with its interval (section 2).
43. For the primary score an answer is invalid only when it gives no usable M>=5 probability;
    the whole-answer rule is a sensitivity analysis, and the text discloses that the rule
    changed after the rerun and by how much (section 7; it amends decision 37).
44. A second negative control: one constant probability for every cell, predicted not
    supported (section 2; it adds to decision 36).

Decided on 2026-11-12, after the mock review of the manuscript draft
(docs/reviews/mock-review-manuscript.md), whose verdict on the design was "major revision".
The primary analysis, the margin, the prompt and the detector do not change:
45. The primary test stays as registered. The paper reports whether the official forecast
    is shown to beat the constant control on test A's cells and claims nothing from
    "supported" when it is not; the bound is also reported at one-sided 0.025; "assay
    sensitivity" is renamed the generic-model check (section 2). The reviewer's alternatives
    (the estimate alone as primary, or a three-arm retention-of-effect design) are not taken:
    a third change of the primary analysis after development results is not made.
46. Results by mainshock depth and by region are registered as estimates without a
    verdict; the catalog's completeness is stated as a sixth gap in information parity, the
    prompt unchanged; the population counts are in section 6 and in the prior-exposure list.
47. A cluster-block bootstrap is a registered sensitivity analysis for dependence between
    neighboring sequences (section 6); the primary resampling unit stays the sequence.
48. The detector is unchanged. The text states that the on-time rule leaves few first-day
    cells in test B's prospective part, with the dry run's on-time share by slot, and what
    the evidence of timeliness is; no third-party time stamp is built (section 5).
49. No recall probe on confirmatory mainshocks. The contrast between sequences before and
    after a model's release is registered with its interval, and the paper uses each
    vendor's own term for its cutoff (sections 3 and 6).
50. The prior-exposure list is corrected: the 3 forward-excluded events were identified on
    2026-11-01 (sections 4 and 9).

No decision is open.
