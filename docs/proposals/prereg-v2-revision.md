# Proposal: revising preregistration v2 before the freeze

Status: **proposed; nothing here is decided.** Tyler chose to revise before freezing after the
mock review of the design (docs/reviews/mock-review-design.md). This document gives the
concrete wording, cost and power figures for the decisions that are still his. It changes no
prompt file, no code and no line of docs/preregistration-v2.md. After his decisions the changes
go through pull requests (`prompts/` needs `frozen-override`), and the paid rerun needs his
approval with the runner's own estimate.

Every number below comes from development data, from forecasts and sequence tables of the
candidate snapshot (no catalog, no outcome), or from the records of past runs. No confirmatory
outcome was used.

## 1. What has to be fixed
The review's two main findings, both reproduced:
- **Finding 2, the score.** In 71% of test A's official cells all nine M>=5 quantiles are zero,
  and the reconstruction then gives every forecaster the same distribution. The official
  forecast's own probability of at least one M>=5 aftershock is below 2.5% in 71% of cells
  (median 0.8%), which nine quantiles cannot express.
- **Finding 1, the comparison.** On these moderate sequences the official forecast is close to
  the generic model: it is the generic RJ product at the first issue of 76 of 89 sequences, and
  on development data generic RJ scores as well as the official forecast under any score
  (section 4). A pass on "non-inferior to the official forecast" therefore shows a forecaster
  as good as a calibrated generic model, not one with skill specific to a sequence.

Finding 2 can be fixed. Finding 1 is a fact about the population; the design can only be
honest about it and show that the test fails a forecaster that should fail.

## 2. Proposed changes

### P1. Ask for the probability of at least one aftershock (prompt v3)
The official product's headline number is the chance of at least one aftershock above each
magnitude. The models are already asked for it at M>=6. Ask for it at M>=5, M>=4 and M>=3 too.

`task_direct_A.txt`, proposed (the last four lines replace the current last line):

```text
## Task
For each window (day, week, month) give:
- the 2.5, 5, 10, 25, 50, 75, 90, 95 and 97.5 percent quantiles of the number of earthquakes with
  magnitude 5.0 or larger (whole numbers, non-decreasing);
- the same nine quantiles for magnitude 4.0 or larger;
- the same nine quantiles for magnitude 3.0 or larger;
- the probability (0 to 1) of at least one earthquake with magnitude 3.0 or larger;
- the probability (0 to 1) of at least one earthquake with magnitude 4.0 or larger;
- the probability (0 to 1) of at least one earthquake with magnitude 5.0 or larger;
- the probability (0 to 1) of at least one earthquake with magnitude 6.0 or larger.
```

`task_direct_B.txt` (the paraphrase), item 4 becomes:

```text
4. four probabilities, each between 0 and 1: that at least one M>=3.0 earthquake occurs, at
   least one M>=4.0, at least one M>=5.0, and at least one M>=6.0.
```

`system_A.txt`, the scoring rule line becomes:

```text
- Express uncertainty honestly. Your probabilities and quantiles are scored with proper scoring
  rules, so overconfident and underconfident answers both lose points.
```

`system_B.txt`, rule 4 becomes:

```text
4. Your forecast is scored by proper scoring rules: both overconfident and underconfident
   probabilities and ranges are penalized.
```

`schema_direct.json`: each window gains `p_m3_at_least_one`, `p_m4_at_least_one` and
`p_m5_at_least_one` (numbers, required), beside `p_m6_at_least_one`.

Validity: a probability outside [0, 1] is invalid, as now. Probabilities that decrease with
falling magnitude (P at M>=5 above P at M>=4), or that contradict the same answer's quantiles
(a 10% quantile of 1 or more with a probability below 0.9), are warnings with reported rates,
not invalid; each target is scored on its own numbers.

### P2. Primary score: the log score of that probability
For a cell, with E the event "at least one M>=5 aftershock in the window" and p the forecast
probability clipped to [0.001, 0.999] (ADR 0001's clip for the M>=6 probability):
S = -log p if E occurs, -log(1 - p) otherwise; dS = S(model) - S(official).
- The official probability is the product's published `probability` for the M>=5 bin, at full
  resolution. The baselines' probabilities come from their own distributions.
- It is a proper score of what the forecaster reports, with nothing reconstructed by the scorer.
- Precedent: Serafini et al. (2022) for binary events with small probabilities; Brehmer et al.
  (2023) (docs/research/novelty-and-literature.md, section E).
- The count score through nine quantiles stays as a registered secondary analysis, because
  counts carry information the probability discards (Nandan et al. 2019). Its text should stop
  calling it proper for the reported quantiles: the reconstruction is not.
- Sensitivity: clips of 0.0001 and 0.01; the Brier score. 15% of test A's official cells are
  at or below the 0.001 clip.

### P3. Margin: 0.02 nats per cell, with its meaning stated
- On test A's cells a forecaster wrong by a factor of two in the official probability loses
  0.006 to 0.013 nats per cell in expectation (0.02 to 0.05 in first-day cells). The registered
  0.10 is about ten times a factor-of-two error.
- At 0.02 the test separates the forecasters it should (section 4): a forecaster like generic
  RJ is declared non-inferior in 73% to 99% of simulated studies, one like the rule of thumb in
  none. At 0.10 with the registered count score, a forecaster like the rule of thumb passes in
  19%.
- 0.02 is somewhat more than the cost of doubling every probability (0.013). The final value
  should be set after the development rerun gives the models' own effects (section 3).

### P4. The primary hypothesis and what it claims
Two ways to state it; the rest of the design is the same under both.
- **(a) Keep non-inferiority to the official forecast as primary** (recommended), on the P2
  score with the P3 margin, and scope the claim in the registration itself: for mainshocks of
  M5.0 to 6.4 with automatic forecasts, where the official forecast is statistically close to
  the generic model. The assay-sensitivity clause stays and will probably apply.
- **(b) Make superiority over the rule of thumb primary**, with the comparison to the official
  forecast as an estimate with its interval. Power for a competent forecaster is about 0.8 to
  0.9 (section 4). It answers a smaller question ("better than a naive rule") more surely.

### P5. Negative controls, registered with their predicted result
- The rule of thumb, tested as if it were a model against the official forecast: predicted
  "not supported". It costs nothing.
- Sonnet 4.6 (already in the plan as descriptive, about $3 in the confirmatory batches) gets a
  test row with the prediction "inferior", as in the development dry run (+0.144).
- If a control passes, the paper says the test could not tell forecasters apart.

### P6. Invalid answers
The worst-of-five-baselines penalty costs exactly zero where the baselines agree (47% of test
A's cells), and on development data a forecaster that never answers scores a mean of +0.0975.
Proposed: an invalid answer counts as dS = +log 2 (0.69 nats, the loss of a coin flip against a
certain outcome) in its cell, whatever happened and whatever the other forecasters said. It can
never help a model, and an invalid rate of 3% alone uses up a margin of 0.02. (Scoring it as
the probability 0.5 instead would reward an invalid answer in the cells where the event
occurs.) Valid answers only stays as a sensitivity analysis.

### P7. Smaller changes
- **Informative sequences:** select on generic RJ's probability of at least one M>=5
  aftershock in the first month (a threshold fixed blind so that a usable number of sequences
  qualify), not on the official forecast, which is one of the two contestants. The current rule
  keeps 5 of 89.
- **B, S1 and S2** are reported as estimates with intervals and their simulated coverage,
  without "supported / inferior" labels: their simulated sizes are 0.14, 0.084 and unknown.
- **By issue stratum:** test A's estimate is also reported for the first day, 1 to 7 days and
  later, named in advance; the first day is where the official probability is largest (median
  8.4% against 0.3% after day 7).
- **Status for "worse but inside the margin":** when the lower bound is above 0 and the upper
  bound below the margin, the row says so, instead of "supported" alone.

### Not proposed here, to decide separately
- Test B's on-time rule (finding 6). In the dry run 0 of 3 first issues and 10 of 22 scheduled
  issues had their matched window still closed at detection. Faster polling for the first
  version of a new sequence would need a detector deploy. Reporting B by slot needs none.
- A closed-book recall probe and an anonymized-prompt variant (finding 7); a mainshock-only arm
  and a local open model as a rerunnable anchor (finding 13); resampling overlapping sequences
  as one block (finding 16). Each adds cost or code; I bring them one at a time if wanted.

## 3. The development rerun (paid; needs approval with the runner's estimate)
Prompt v3A on development items, k = 3, each model at its study setting. Costs are the actual
cost per answer of the same model on the same items in the earlier prompt study (runs/d2),
times the number of answers; the new fields add a few output tokens.

| Model | Role | Minimal: the 99 items of the earlier study | Recommended: every development item clean for the model |
|---|---|---|---|
| gpt-5.1 (medium) | A | 297 answers, $11.42 | 39 sequences, 630 answers, about $24.3 |
| Opus 5.5 (high) | B | 297 answers, $5.14 | the same 297 (none of the development sequences is clean under the buffer) |
| Opus 4.6 (adaptive, medium) | S1 | 297 answers, $6.87 | 39 sequences, 630 answers, about $14.6 |
| Sonnet 4.6 (adaptive, low) | control | 297 answers, $4.25 | 22 sequences, 351 answers, about $5.0 |
| gpt-6.1-sol (high) | S2 | not run before | 11 sequences, 186 answers, about $6 (from 6 pilot answers: uncertain) |
| **Total** | | **OpenAI $11.4, Claude $16.3** | **OpenAI about $30, Claude about $25** |

With the runners' 25% margin the recommended set is about $37 (OpenAI) and $31 (Claude), inside
this month's caps. The recommended set doubles the sequences behind test A's power and size
(39 instead of 18), which answers the review's point that the heavy tail was estimated from one
sequence in 18, and it gives S2 the development effects it never had. Variant v3B (the
paraphrase) is not rerun: the earlier study found wording effects no larger than sampling
noise, and v3B changes the same lines as v3A.

Order after approval: prompt files and schema (pull request with `frozen-override`), a
`confirmatory`-style block for the rerun, the batches, then the size and power simulation on
the models' own effects with `laf confirmatory-size`, then the final margin and the text of
preregistration v2.

## 4. Size and power from development data
39 development sequences with an official forecast (536 cells; an M>=5 aftershock in 22 cells
of 3 sequences). No model has answered the new question yet, so these use the baselines as
stand-ins: generic RJ for a competent forecaster, the rule of thumb for a poor one.

Baseline minus official, mean over sequences, 90% interval (bootstrap-t):

| Baseline | Probability score (P2) | Registered count score | Cells with exactly equal scores |
|---|---|---|---|
| Generic RJ | -0.009 [-0.155, +0.014] | -0.008 [-0.046, +0.011] | 3% (probability), 68% (count) |
| Rule of thumb | +0.095 [+0.010, +0.366] | +0.049 [-0.004, +0.399] | 16%, 69% |

Share of simulated studies of 89 sequences that declare non-inferiority to the official
forecast (one-sided 0.05, 400 simulations, effects resampled from the development ones):

| Effects shaped like | Score | Margin | True mean at the margin (size) | True mean 0 | True mean as in development |
|---|---|---|---|---|---|
| Generic RJ | probability | 0.01 | 0.03 | 0.21 | 0.64 |
| Generic RJ | probability | 0.02 | 0.03 | 0.73 | 0.99 |
| Generic RJ | probability | 0.05 | 0.03 | 1.00 | 1.00 |
| Generic RJ | probability | 0.10 | 0.03 | 1.00 | 1.00 |
| Generic RJ | count | 0.02 | 0.04 | 0.85 | 1.00 |
| Generic RJ | count | 0.10 | 0.04 | 1.00 | 1.00 |
| Rule of thumb | probability | 0.02 | 0.06 | 0.11 | 0.00 |
| Rule of thumb | probability | 0.10 | 0.06 | 0.35 | 0.08 |
| Rule of thumb | count | 0.02 | 0.02 | 0.08 | 0.02 |
| Rule of thumb | count | 0.10 | 0.02 | 0.77 | 0.19 |

Superiority over the rule of thumb at 89 sequences (P4, option b): power 0.79 (a forecaster
like generic RJ) and 0.87 (like the official forecast) under the probability score, 0.64 and
0.67 under the count score; size 0.03 to 0.04.

Limits of these figures: the stand-ins are statistical models, not language models, whose
answers add sampling noise (k = 3) and may be shaped differently; three sequences with events
carry the tails; 400 simulations give about two digits. The rerun of section 3 replaces them
with the models' own effects.

## 5. Decisions for Tyler
1. P1: the wording above, yes or with changes.
2. P2: the probability log score as the primary score, the count score secondary.
3. P3: a margin near 0.02, fixed after the rerun.
4. P4: (a) non-inferiority to the official forecast with the claim scoped, or (b) superiority
   over the rule of thumb.
5. P5: the two negative controls.
6. P6: the invalid-answer rule (a fixed +0.69 nats per invalid answer).
7. P7: the four smaller changes, each yes or no.
8. Section 3: minimal or recommended set, and whether gpt-6.1-sol is included.

My recommendation: yes to P1, P2, P3, P5, P6 and P7; (a) for P4; the recommended set with
gpt-6.1-sol for the rerun.

## 6. Time
Test A's batches cost about $271 by the runners' estimates. The OpenAI cap less the live
reserve leaves $125 in December, $125 in January and $75 in February, and the forecasts must
exist by 2027-03-01. Prompt files, the rerun and the simulation are days of work once approved;
a tag in the first half of December keeps test A inside the caps.
