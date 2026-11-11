<!--
Provenance. Written by an independent reviewer (a fresh agent with no view of the project lead's
opinions), asked to act as a hostile Seismica referee of the revised preregistration v2 and to
compare its text with the code, at commit cd352c1e. It ran no `laf` command, made no API call,
wrote nothing in the repository and computed no score on confirmatory data; its "blind counts"
come from the candidate snapshot's sequence, issue-time, official-forecast and baseline tables
only, which docs/adr/0013-data-splits.md allows before the freeze.

Checked afterwards by the project lead, by recomputation on development data and on the same
forecast tables: the rule of thumb's probability of exactly 0 in 95.8% of test A's cells; its
deficit against the official forecast at clips of 0.01, 0.001 and 0.0001 (+0.038, +0.095,
+0.163); the expected loss of forecasters at a fraction of the official probability and of a
constant (0.014 at one third, 0.042 at one tenth, 0.031 at a constant 2.9%); the official
probability at or below 0.001 in 15.3% of cells; gpt-5.1's stated probability at or below 0.001
in 49% of its answers; the control's labels in simulated studies (inferior 34%, inconclusive
66%); the passing rates with Opus-5.5-like effects at a margin of 0.02 (39% to 45%). Two of the
reviewer's figures came out differently for the lead: gpt-5.1's stated probability is at or
below the official one in 88% of answers (the review: 90%) and a fifth of it at the median
(the review: a third), and the rule of thumb beats the official forecast on 33 of 39
development sequences (the review: 36).

What followed. Findings 3, 4, 8, 9 and 11 and the code parts of 5 and 6 were fixed in the
commit that adds this file. Findings 1 and 2 (the margin, a second control) and the design part
of 5 (when an answer is invalid) are Tyler's decisions and were put to him the same day; section
13 of docs/preregistration-v2.md records what he decides.
-->

# Mock review of the revised preregistration v2 (revision of 2026-11-11)

Reviewed at commit cd352c1e (branch confirmatory/v3): docs/preregistration-v2.md, the earlier
mock review, the proposal, `confirmatory.py`, `d2.py`, `sensitivity.py`, `descriptive.py`,
`schemas.py`, `freeze.py`, `runner.py` (BLOCKS), the three confirmatory commands in `cli.py`,
prompts/v3, and the result files of the development rerun.

How the numbers below were obtained. Read-only Python on development data (snapshot
20261021T2300Z, runs/d3 and runs/d2) through `laf.d2.analyze` and `laf.confirmatory`. "Blind
count" means the candidate snapshot's `sequences`, `issue_times` (no observation columns),
`forecast_bins`, `oaf_versions` (model name only) and `baselines_m3.jsonl`: forecasts and
sequence tables, no catalog, no `observed_counts`, no score. No `laf` command, no test run, no
API call, nothing written in the repository. Scripts: check1.py to check6.py beside this file.

## Verdict

1. The revision fixes the score (the earlier review's finding 2) and the invalid-answer rule
   in principle, and almost every number quoted in the text reproduces. As a design it still
   would not carry its headline: the margin was reset after the primary model's development
   result was seen, its anchor is an artifact of the 0.001 clip, and a forecaster that states
   one tenth of the official probability in every cell sits inside it.
2. The likeliest outcome of the registered analysis is three nulls at once: A inconclusive
   (about 80% of simulated studies), the negative control inconclusive (66%), and generic RJ
   non-inferior (the assay clause applies). The text does not say what that outcome licenses.
3. Text and code disagree in places that matter for a freeze: the manifest hashes the v2
   prompt, not v3; verdict columns for B, S1 and S2 survive in four code paths; an
   always-invalid forecaster is labelled "inconclusive". None is hard to fix.

## Findings, by severity

### 1. The margin was reset after the primary model's result, and its anchor is made by the clip
**Design weakness (major).**

What the text says (section 2, lines 106-123): delta = 0.05, "half of the official forecast's
advantage over the rule of thumb" (0.095 on 39 development sequences, 90% interval 0.010 to
0.366); "the usual construction of a non-inferiority margin"; 0.02 was rejected because test A
would be supported in 4% to 12% of studies, "which no result could pass".

What the record and the data say:
- The proposal recommended 0.02 with a stated meaning ("somewhat more than the cost of
  doubling every probability") and said the final value would follow the rerun. The rerun gave
  gpt-5.1 a development mean of +0.019, which is the proposed margin, and power 4%. The margin
  then moved to 0.05 with a new meaning. This is the earlier review's finding 3 again ("the
  margin doubled the day the development run showed that 0.05 gave 12% power"), one step on.
- "Which no result could pass" is false in the registration's own file: with Opus-5.5-like
  effects the test passes at 0.02 in 39% (development mean) to 45% (true mean 0) of studies of
  89 (`results/confirmatory_size_d3_20261021T2300Z.csv`). What cannot pass at 0.02 is a model
  whose own mean is 0.019.
- The rule of thumb states a probability of exactly 0 wherever no M>=5 aftershock has yet
  occurred (`forecast.naive_forecast`: K from the M>=5 count so far). Blind count: that is
  95.8% of test A's 1,415 cells. Its score is therefore the clip: 0.001 nats without an event,
  6.9 with one. On development data it beats the official forecast on 36 of 39 sequences
  (mean -0.016 on those); the whole +0.095 comes from three sequences (+2.29, +1.08, +0.93).
- The anchor moves with the clip, which the same document registers as a sensitivity choice:
  +0.038 at a clip of 0.01 (90% interval -0.004 to +0.227, so no demonstrated advantage at
  all), +0.095 at 0.001, +0.163 at 0.0001 (0.027 to 0.548). "Half the advantage" is 0.019,
  0.048 or 0.081 depending on a constant nobody argues for.
- The usual fixed-margin construction takes a fraction of the conservative bound of the
  reference's effect, not of its point estimate. Here that bound is 0.010, and half of it is
  0.005.
- What 0.05 admits. Blind count, expected dS on test A's cells if the official probability is
  the truth (mean of sequence means): a forecaster at one third of the official probability
  everywhere 0.014; at one fifth 0.025; at one tenth 0.042; three times too high 0.052. One
  constant for every cell, sequence and window is inside the margin for any value from 0.8%
  to 7.4% (best: 2.9%, expected dS 0.031). The margin tolerates a tenfold under-forecast and
  not a threefold over-forecast, the wrong way round for a hazard product.
- gpt-5.1 is that under-forecaster. In the rerun its stated probability is at or below the
  official one in 90% of answer-windows, a third of it at the median, a twentieth at the 10th
  percentile, and at or below the clip in 49%.

Why a referee cares: a margin fixed after seeing where the primary model lands, justified by
an anchor whose interval spans a factor of 37 and whose value is set by the clip, will be read
as chosen to pass. The scale sentence ("four to eight times a factor-of-two error") is honest
and reproduces, and it is the argument against the margin.

Fix: one of (a) register 0.02 as primary, as proposed before the model's result was known,
and accept the power; (b) make superiority over the rule of thumb the primary hypothesis
(power 0.99, size 0.034, reproduced) and report the contrast with the official forecast as an
estimate with its interval; (c) keep 0.05 and say in the text that it was chosen after the
rerun, drop "the usual construction" and "no result could pass", give the anchor at the three
clips, and add a constant-probability forecaster (the development base rate, fixed now) as a
second control with the prediction "not supported".

### 2. The expected result is three nulls, and the negative control cannot fail informatively
**Design weakness (major).**

What the text says: power 22% at the development mean and 56% at a true mean of 0 (section
2); the control C is "predicted: not supported"; the assay clause "will probably apply".

What the data say (development effects resampled to 89 sequences, the registered test):
- A is supported in 22% (CSV; 18% in my 300 studies), inconclusive otherwise, never inferior.
- A forecaster like the rule of thumb is labelled inferior in 34% and inconclusive in 66% (300
  studies). "Not supported" covers both, so the prediction succeeds while the control carries
  the same label as the tested model in two studies out of three. On development data the
  control is already "inconclusive" (dry-run secondary table: +0.095, lower +0.010, upper
  +0.366), and so is gpt-5.1.
- Generic RJ is non-inferior on every model's cells (-0.009; reproduced).
- The simulation understates the tail. Three of 39 development sequences (7.7%) have an M>=5
  aftershock in a scored cell; the official forecast expects 11.1 of test A's 89 (12.5%) in
  the first month alone (blind count, reproduced).
- Two sequences carry gpt-5.1's tail, not one: +0.83 (us7000t0b5) and +0.54 (us7000rrv2).
  Without both the mean is -0.017.

Why a referee cares: a registered primary test that is expected to be inconclusive, with a
control expected to be inconclusive, establishes nothing in either direction, and the text
never says so. The earlier review asked for the interpretation of each outcome of A to be
written in; "inconclusive" still has none.

Fix: state what an inconclusive A licenses (nothing, in either direction); register the
control's prediction as "inferior" or quote its 34% chance of that label beside the
prediction; say in section 2 that the modal joint outcome is A inconclusive, C inconclusive,
generic RJ non-inferior, and what the paper then reports as its finding (S3 is the only
analysis with power).

### 3. The freeze manifest hashes the v2 prompt, not the scored one
**Text/code mismatch (major for the freeze).**

Text (section 11, line 686): the manifest holds "`prompts/v3/HASHES.json` and
`prompts/HASHES.json`". Code: `src/laf/freeze.py:23`,
`PINNED = (Path("prompts/v2/HASHES.json"), Path("prompts/HASHES.json"), Path("uv.lock"))`;
`tests/test_freeze.py:23` asserts the v2 path. Nothing else in the manifest covers
prompts/v3: the scored system text, task text and response schema of v3A and v3B would be in
no hash posted with the tag. (prompts/v3/HASHES.json itself is correct: I recomputed the five
SHA-256 values.)

Fix: add `prompts/v3/HASHES.json` to `PINNED` (keep v2 only if something still renders it) and
update the test.

### 4. Verdicts for B, S1 and S2 survive in the code, and in three sentences of the text
**Text/code mismatch; stale text.**

Text (section 2, line 89; section 6, lines 475 and 522; decision 39): B, S1 and S2 get no
verdict.

Code:
- `confirmatory.py:633-646`, `live_report`: rows "B", "B retrospective part", "B prospective
  part" and "S2" go through `decide` and keep `status`, `noninferior` and `superior`; the
  informative rows at line 682 too. `cli.py:866-870` writes them unchanged.
- `confirmatory.py:544-549`, `secondary`: the informative rows carry `noninferior` for every
  tested model. Dry run: Opus 4.6 True, Opus 5.5 False.
- `confirmatory.py:483-508`, `assay`: the assay and control rows carry a status on B's and
  S1's cells (dry run: "control, claude-opus-5-5, inconclusive" on 18 sequences), at sample
  sizes the text says cannot carry a verdict. The labels are "noninferior / inferior /
  inconclusive", not section 2's four, although the table says C is tested "as A".
- `cli.py:818` (and 993): `hierarchical` runs for every model, descriptive ones included, and
  writes `hier_noninferior`. Dry run: True for Sonnet 4.6 and gpt-6.1-sol, which "get no test
  row" (section 6, line 476).
- `confirmatory.py:237-238`: an unlabeled row keeps `p` and `p_sup` (dry run: Opus 4.6,
  p = 0.0001). A p-value against the margin is a test result.

Stale text:
- Section 6, lines 404-406: "B, S1 and S2 are tested at nominal 0.05 and reported with their
  simulated sizes" (decision 29, replaced by 39).
- Section 2, line 103: "Secondary tests are at 0.05 each and labelled secondary."
- Section 2, lines 124-126: the assay clause still issues a non-inferiority verdict for
  generic RJ on B's cells ("A and B are reported as unable to separate").

Fix: strip verdict columns from every non-primary row in `live_report`, `secondary`, `assay`
and the hierarchical join; drop `p` and `p_sup` for unlabeled rows or say they are reported;
give C section 2's labels; correct the three sentences.

### 5. Invalid answers: validity is judged on fields the primary score never reads
**Design weakness; text/code mismatch; ambiguity.**

Text (section 7): an invalid answer counts a fixed dS of log 2; "each target is scored on its
own numbers" (line 564); two safeguards.

Data and code:
- Validity is per answer (`schemas.py:53-54`, `d2.py:37-45`). All three invalid answers of
  the rerun are `non_monotone` and all three state a usable M>=5 probability. One
  (us6000szt5@28d) fails only on its month M>=3 quantiles.
- Scored on their own probabilities, gpt-5.1's development mean is +0.0166; with log 2 it is
  +0.0191; at the worst case +0.0446. Three answers in 630 move the estimate by half the
  margin under the registered sensitivity rule. Safeguard 1 ("if the verdict differs between
  the two rules...") will therefore trip at almost any invalid rate, which makes it a
  disclaimer and not a safeguard.
- One of the three invalid answers is the first issue of one of the three event sequences
  (us7000s211): the concentration safeguard 2 is meant to reveal is already there.
- A forecaster whose every answer is invalid is labelled **inconclusive**, not inferior:
  identical effects have no spread, so `noninferiority` returns an infinite bound
  (`confirmatory.py:72-73`) and `decide` a lower bound of minus infinity (line 186). I ran
  `decide` and `report` on 89 sequences of log 2. This is the test case the earlier review
  asked for in finding 8.
- Unstated rules: the Brier variant scores an invalid answer at the worst case
  (`sensitivity.py:168`); on strict items (S5) the penalty is an absolute score of log 2,
  not a difference from the official forecast (`live_scores.py:141`, `off = 0.0`).

Fix: for the primary score, call an answer valid when its M>=5 probabilities parse and lie in
[0, 1]; keep whole-answer validity as the sensitivity analysis. When the standard error is 0,
compare the mean with delta directly. State the rule for the Brier variant and for S5.

### 6. The clip decides more than the text admits
**Design weakness.**

Text (section 1): the official forecast contributes its published probability "at full
resolution"; "nothing is reconstructed by the scorer".

Data: the official probability is at or below 0.001 in 15.3% of test A's cells (blind count;
the proposal gave 15%, the registration dropped it). The rule of thumb is at the clip in
95.8%. gpt-5.1's stated probability is at or below it in 49% of development answer-windows
(Opus 4.6 15%, Opus 5.5 17%). In those cells the scorer replaces the forecast. gpt-5.1's
development mean is +0.012, +0.019, +0.024 at clips of 0.01, 0.001, 0.0001, and its upper
bound 0.128, 0.204, 0.265.

Code: the two clip variants carry a verdict at the unchanged margin of 0.05
(`sensitivity.py:200-202`), although the margin's own anchor scales with the clip (finding 1).

Fix: quote the three shares in section 1; argue for 0.001 against the product's resolution or
choose the clip from it; report the clip variants without a verdict, as the Brier row is.

### 7. What is claimed in the predicted case is not defined
**Ambiguity.**

- Lines 96-98 say "supported" means the model matches the operational forecast on moderate
  sequences, "not that it has skill specific to a sequence", then that the assay clause "says
  when no such claim is made at all". Lines 124-128 say that if generic RJ is non-inferior "no
  claim of sequence-specific skill rests on them". The first sentence already withdrew that
  claim unconditionally. Two readers will disagree on whether "A supported, generic RJ
  non-inferior" (the predicted case) permits the sentence "gpt-5.1 is non-inferior to the
  USGS forecast" in the abstract.
- Line 131: if C is supported, "A's result is read accordingly". No rule follows.
- A row whose lower bound is above 0 and whose upper bound is above delta is "inconclusive",
  though the model is measurably worse than the official forecast. The fourth label exists
  only on the supported side.

Fix: a small table of the joint outcomes of A, C and the assay test, each with the one
sentence the paper may write.

### 8. Numbers no command records
**Wrong number (one, wording); untraceable numbers.**

- The column "a forecaster like the rule of thumb is supported" (0%, 0%, 0.3%, 6%) and S3's
  power 0.99 and size 0.034 are in no result file: `laf confirmatory-size` simulates three
  models only (`cli.py:910-912`). I reproduced all six with `confirmatory.size` (0.000,
  0.000, 0.003, 0.063; 0.993; 0.034), so they are right, but this is the earlier review's
  finding 17 again.
- Line 164: "one sequence of 39 contributes +0.83 to gpt-5.1's mean of +0.019". Its effect
  is +0.83; it contributes +0.021 to the mean. The sentence also hides the second sequence
  (+0.54).
- Lines 55-56: "below 2.5% in 71% of those cells" reads as a share of the all-zero cells; it
  is the share of all test A cells (70.7%), and it is the same fact as the 71% above it (nine
  zero quantiles mean a probability of at most 2.5%).

Fix: add the rule of thumb and the S3 contrast to `laf confirmatory-size`; reword the two
sentences.

### 9. Secondary and sensitivity rows that read as verdicts
**Design weakness (minor).**

- The stratum rows and the "margin 0.1" row carry `noninferior` for A (`sensitivity.py:46-56,
  74-75, 96-97`). On development data A is "inconclusive" overall and `noninferior = True` in
  the stratum "7 days or more", where the official median is 0.3% and a factor of two costs
  far less than 0.05. A margin defined per cell over all strata means something else inside
  one stratum.
- S3 and S4 give `superior` for four models at 7 to 33 sequences, with no multiplicity
  control. Checked and not a size problem for S3: with gpt-5.1's effects against the rule of
  thumb the simulated size is 0.019 at N = 23 and 0.029 at N = 33 (power 0.57 and 0.75). The
  registration quotes only N = 89.

Fix: strata as estimates with intervals; quote S3's size at 23 and 33.

### 10. One answer, two forecasts of the same quantity
**Design weakness (minor); text/code mismatch (prompt).**

- Section 7 makes a probability outside the range its own quantiles leave a warning "with
  reported rates". The development rates are not quoted. They are 85% of answers for Opus 4.6
  and Sonnet 4.6, 48% for Opus 5.5, 17% for gpt-5.1, 0% for gpt-6.1-sol (any magnitude). At
  M>=5 alone: Opus 4.6 states less than its quantiles imply in 21% of answer-windows (half
  the bound at the median), Sonnet 4.6 in 21%, gpt-5.1 in 0.1%. The primary and the secondary
  score read different forecasts from the same answer; for S1 that is one cell in five.
- Section 3 says v3A is v2A "plus the three probabilities"; "the context, the catalog and the
  quantile lines are unchanged". The system prompt's scoring sentence changed too
  (prompts/v3/system_A.txt against v2). It now tells the model its quantiles are scored "with
  proper scoring rules", while section 1 says the count score "is not a proper score of the
  reported quantiles".

Fix: quote the rates; mention the system line; in section 1 say which quantile score the
prompt's promise refers to (the log-scale quantile score).

### 11. Smaller mismatches, stale text and gaps
- **Text/code mismatch.** Section 6, line 440: "the non-overlapping subset (one window per
  issue)". `sensitivity.py:16` keeps every day window, the week windows of the first, 7, 14
  and 28-day issues and the month window of the first issue: the first issue keeps three
  nested windows.
- **Stale text.** Decision 21 (line 748) still names "v2A" for the unbuffered batch; the
  code sends v3A (`cli.py:730`).
- **Stale text, acknowledged.** The live path is still on prompt v2A and the count score
  (`prospective.py:31`, `live_scores.py:136-163`). With today's code `confirmatory_cells`
  keeps only `variant == "v3A"`, so B's prospective part and S2 would be empty. Section 11
  lists it as TO BUILD; section 6's "Built: the prospective inputs" paragraph does not say
  which score it describes.
- **Design weakness.** Section 9's prior-exposure list omits the blind counts on the candidate
  snapshot's forecast tables that shaped this revision (71%, 15%, 49 of 89). The informative
  threshold (0.10) sits just under the median of generic RJ's month probability (0.1016),
  with 8 sequences within 0.005 above the threshold and 2 within 0.005 below; the text
  discloses the seven.
- **Design weakness.** "The five baselines" are four on these data: RJ-MLE falls back to
  generic RJ with fewer than 10 M>=4.95 events (`analysis.py:129-132`) and is identical to it
  in every development cell (same mean and interval).
- **Design weakness.** Decision 41: no outside protocol review; a mock review by an agent of
  the same project "stands in its place". A referee will not count it as independent.
- **Ambiguity.** Section 8 compares 8,383 output tokens per answer (630 answers, 39
  sequences) with 7,543 (297 answers, 18 sequences): different item sets, so "about 11%" is
  not the prompt's effect alone.

## Checked and found correct
- The score: `d2.analyze(score="probability")` takes the answer's own `p_m5`, the product's
  published M>=5 probability and each baseline's `1 - cdf_m5[0]`, all through
  `scoring.log_score_binary` with `P_CLIP = 0.001`.
- The margin and sensitivity margins (`DELTA = 0.05`, `SENSITIVITY_MARGINS = (0.02, 0.10)`),
  the four labels for A (`_status`), superiority only after non-inferiority, the bootstrap-t
  with B = 10,000 and a fixed seed.
- The log 2 rule and the worst-case rule in `confirmatory_cells`; invalid rates by stratum
  and event (`sensitivity.invalid_by_cell`).
- The informative rule (`confirmatory.informative`): generic RJ, month window of the first
  issue that has one, threshold 0.10, no count read.
- Section 6's sensitivity list against `sensitivity.sensitivity`, `SCORE_VARIANTS` and
  `diagnostics`: every listed analysis has a row, and no row is unlisted (exceptions:
  findings 5, 6, 9 and 11).
- prompts/v3: task text as approved in the proposal; schema requires the four probabilities;
  HASHES.json matches the files; BLOCKS `confirmatory`, `-sens`, `-v3b` send v3A or v3B at
  k = 3 and study effort.
- The manifest's other contents (document, uv.lock, items, baselines with `p_m5`, src tree,
  data manifest, snapshot tables, configs).
- The "exact-match" sensitivity row equals the main row on development data because all 210
  issues match, not because the filter is inert.
- All 195 candidates have role `test-post`, so `laf confirmatory`'s default role filter drops
  nothing.

## Numbers checked

| Quoted (section) | Quoted value | My value | Source | Result |
|---|---|---|---|---|
| gpt-5.1 development mean, median (2) | +0.019, -0.011 | +0.0191, -0.0111 | runs/d3, probability score | reproduced |
| Largest sequence effect; mean without it (2) | +0.83; -0.002 | +0.831; -0.0023 | same | reproduced; "contributes" is wrong wording |
| Rule of thumb minus official, 90% interval (2) | 0.095; 0.010 to 0.366 | +0.0953; +0.0098 to +0.3659 | same, 39 sequences | reproduced |
| Sequences with M>=5 aftershocks (2) | 3 | 3 (22 event cells of 536) | same | reproduced |
| Generic RJ minus official (2) | -0.009; -0.155 to +0.014 | -0.0088; -0.1545 to +0.0135 | same | reproduced |
| Power of A at 0.05: development mean, zero (2) | 22%, 56% | 0.215, 0.562 | size CSV and my rerun of `size` | reproduced |
| Power table at 0.02, 0.03, 0.10 (2) | 4/12, 7/21, 94/99 | 0.036/0.121, 0.070/0.205, 0.940/0.992 | size CSV | reproduced |
| Rule of thumb supported at 0.02 to 0.10 (2) | 0, 0, 0.3%, 6% | 0.000, 0.000, 0.003, 0.063 | my run of `size` | reproduced; in no file |
| S3 power and size, gpt-5.1 (2) | 0.99; 0.034 | 0.993; 0.034 | my run of `size` | reproduced; in no file |
| S3 mean and interval (2) | -0.076; -0.383 to -0.019 | -0.0762; -0.3829 to -0.0191 | runs/d3 | reproduced |
| Earlier-draft power A, B (2) | 0.42, 0.64 | 0.423, 0.639 | d2 size CSV | reproduced |
| Size at N = 89, 0.05 (6) | 0.035, 0.047 | 0.035, 0.047 | size CSV | reproduced |
| Size at nominal 0.025 (6) | 0.032, 0.030 | 0.032, 0.030 | size CSV | reproduced |
| Percentile bound (6) | 0.12, 0.09 | 0.120, 0.091 | size CSV | reproduced |
| Size at N = 33; S1 at 23 (6) | 0.165, 0.144; 0.142 (0.093) | same | size CSV | reproduced |
| Answers and invalid answers of the rerun (3, 7) | 2,094; 3; gpt-5.1 3 of 630 | 2,094; 3; 3 of 630, all non-monotone | runs/d3 raw | reproduced |
| Sonnet 4.6 count score v2A, v3A, interval (3) | +0.144, -0.0004; -0.21 to -0.10 | +0.1441, -0.0004; -0.210 to -0.101 | runs/d2, runs/d3, 18 sequences | reproduced |
| Other models' v3A minus v2A (3) | -0.002, -0.005, -0.001 | -0.0021, -0.0045, -0.0006 | same | reproduced |
| Invalid rates that use up the margin (7) | 3% for 0.02, about 7% for 0.05 | 2.9%, 7.2% | arithmetic | reproduced |
| Test A set and magnitudes (2) | 89; 61 M5.0-5.4; none M6.5+ | 89; 61; none (largest 6.2) | blind count | reproduced |
| Generic RJ product at the first issue (2) | 76 of 89 | 76 | blind count | reproduced |
| Official probability below 2.5%; median (1) | 71%; 0.8% | 70.7%; 0.78% | blind count, 1,415 cells | reproduced |
| Official median, first day and after day 7 (6) | 8.4%; 0.3% | 8.36%; 0.28% | blind count | reproduced |
| Factor-of-two loss per cell; first day (2) | 0.006 to 0.013; 0.02 to 0.05 | 0.0064, 0.0127; 0.022, 0.045 | blind count | reproduced |
| Expected sequences with an M>=5 in a month (2) | about 11 | 11.13 | blind count | reproduced |
| Informative sequences; near the threshold (2) | 49 of 89; seven at 0.101-0.103 | 49; 7 | blind count | reproduced |
| First issue without a month window (2) | one | one (88 of 89 have it) | blind count | reproduced |
| Clean sets (4, 6) | 175; 13; 23; 7; 76 | 175; 13; 23; 7; 76 | blind count | reproduced |
| Output tokens per answer, estimates (8) | 8,383 against 7,543; $38.71; $42.15 | 8,382.6; 7,543.2; 38.71; 42.15 | runs/d3, runs/d2, batch.json | reproduced |
| Baselines agree in 47% of cells; never-answering +0.0975 (7) | | | | not rechecked |
| Actual costs of the rerun (8) | $26.92, $31.79, $31.80 | | | not rechecked |

No quoted figure is wrong; one sentence misdescribes a figure (finding 8).

## The earlier review's 20 findings after the revision

| # | Earlier finding | Status | Note |
|---|---|---|---|
| 1 | No assay sensitivity | Answered in part | Claim scoped; control C added. The official forecast still has no advantage over generic RJ, the clause is still expected to apply, and the control is weak (findings 1, 2). |
| 2 | Score does not score the forecasts | Answered | Probability score primary; count score secondary and no longer called proper. Residue: the clip (finding 6). |
| 3 | Margin without meaning, set with power in view | Answered in part | Meaning stated in probability terms and recomputed under the registered score. Set with the power table in view a second time (finding 1). First day not made primary. |
| 4 | Power and size | Answered in part | B, S1, S2 lose their verdict in the text (not fully in code, finding 4); power is now printed by a command. Power fell from 0.45 to 0.22; no interpretation of "inconclusive"; no size under a heavier tail; level still 0.05. |
| 5 | Population is small earthquakes | Answered | Scope clause with counts in section 2. No magnitude-stratified estimate. |
| 6 | Test B's on-time rule selects against informative cells | Open | The catalog gap is now stated in section 1; nothing else changed. B carries no verdict, which lowers the stakes. |
| 7 | Contamination control rests on the vendor | Open | No recall probe, no anonymized prompt, no registered split at the release date. |
| 8 | A model that never answers would pass | Answered in part | Fixed log 2 and two safeguards. An always-invalid forecaster is still not "inferior" in code; validity is per answer (finding 5). |
| 9 | Informative estimand empty, selects on the comparator | Answered | Generic RJ at 0.10, 49 of 89, reproduced. Verdict column for secondary models (finding 4). |
| 10 | Many secondary tests with labels | Answered in part | B, S1, S2 unlabeled; "worse inside the margin" added. S3 to S5 unchanged, no multiplicity control. |
| 11 | Hindsight in the prompt and in version matching | Answered by disclosure | Listed as known gaps, "stated and not corrected"; frequency not shown. |
| 12 | Information parity overstated | Answered | Reworded with the gaps listed. |
| 13 | No negative control, ablation or empirical baseline | Answered in part | Rule of thumb as control. No open-weights anchor, no mainshock-only arm, no empirical baseline. |
| 14 | Model identity and reproducibility | Open | Unchanged (manuscript). |
| 15 | Retrospective arm is a plan for public data | Open | Unchanged; this revision adds design choices made after the candidate fetch (finding 11). |
| 16 | Independence between sequences | Open | Overlapping pairs still resampled separately. |
| 17 | Text and code that disagree | Answered in part | The 0.03 threshold, the two magnitude definitions and B's unstratified simulation are now stated; power has a command. New untraceable numbers and new mismatches (findings 3, 4, 8, 11). |
| 18 | Outcome measurement | Open | Unchanged. A binary event at M5.0 makes one borderline event worth several nats. |
| 19 | Operations of the live arm | Open | Unchanged (manuscript). |
| 20 | Prior work | Answered for the registration | Serafini and Brehmer cited for the score. The non-inferiority literature is invoked ("the usual construction") without the conservative-bound method it prescribes. |
