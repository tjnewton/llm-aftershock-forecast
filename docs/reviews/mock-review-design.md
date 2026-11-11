<!--
Provenance. Written by an independent reviewer (a fresh agent with no view of the project lead's
opinions), asked to act as a hostile but fair Seismica referee of the design before the freeze.
It ran no `laf` command, made no API call and computed no score on confirmatory data; its
"blind counts" come from the candidate snapshot's sequence, issue-time, official-forecast and
baseline-forecast tables only, which docs/adr/0013-data-splits.md allows before the freeze.

Checked afterwards by the project lead, by rerunning the reviewer's scripts and the scoring
code: the dry-run rows quoted in findings 1, 4 and 9; the reconstruction for nine zero quantiles
and for a 97.5% quantile of 1 (finding 2); the blind counts in findings 1, 2, 3, 5, 7, 8, 9 and
16. Added by the lead on development data and the dry-run log: a forecaster whose every answer
is invalid scores a mean of +0.0975 nats on the 203 development cells (inconclusive, not
inferior; question 3); 10 of 22 scheduled dry-run issues had their matched window still closed
at detection, and 0 of 3 first issues (question 1); the official forecast expects about 11 of
test A's 89 sequences to have any M>=5 aftershock in the first month (question 5). Not checked:
the reviewer's reading of ADR text in findings 3, 6 and 17, and the references in finding 20
beyond their existence (all twelve resolve on Crossref or arXiv).

The text below is the reviewer's, unchanged.
-->

# Mock review of the study design (preregistration v2, draft)

Reviewed: docs/preregistration-v2.md (draft), ADRs 0001, 0003, 0004, 0006, 0009-0018, the freeze
runbook, data card, model registry, deviations, the literature note, prompts/v2, and the code
behind the registered claims (`confirmatory.py`, `countdist.py`, `d2.py`, `sensitivity.py`,
`splits.py`, `live_scores.py`, `prospective.py`, `live.py`, `tables.py`, `items.py`,
`candidates.py`, `e3.py`, `power.py`, `schemas.py`).

What I looked at beyond text and code, so the authors can judge it:
- The development dry-run tables in `results/confirmatory_dryrun_*_d2_20261021T2300Z.csv` and
  `results/confirmatory_size_d2_20261021T2300Z.csv` (development data, scored by the authors).
- Outcome-blind facts of the candidate snapshot 20261029T2000Z, read with three small scripts
  kept outside the repository: mainshock magnitudes and origins, issue times, the official
  product's model name and M>=5 fractiles, and the baseline forecasts in `baselines_m3.jsonl`.
  I did not open `catalog`, `issue_catalogs` or `observed_counts`, and computed no score.
- `countdist.from_quantiles` evaluated on synthetic quantile sets (no data).

Numbers below marked "blind count" come from the second item.

## 1. Summary for the editor

The study asks whether a general-purpose LLM, given the catalog the USGS operational aftershock
forecast (OAF) had, issues count forecasts that are "non-inferior" to the OAF. The one primary
test (A) is gpt-5.1 on 89 retrospective M>=5 sequences after its documented training cutoff,
with a margin of 0.10 nats per cell on a log score computed from nine quantiles. A prospective
arm (Opus 5.5, gpt-6.1-sol) with sealed, timestamped forecasts supplies a secondary test (B)
where contamination is impossible. The engineering is unusually careful: as-of catalogs
validated against the official products' own counts, a sequence-level studentized bootstrap
with a simulated size, a count-based stopping rule, software gates on outcomes, and a list of
sensitivity analyses fixed in advance.

If the paper were submitted with this design executed exactly as written, I would recommend
**major revision, and I would not accept the headline claim**. Two reasons drive that.
First, the primary test cannot tell the LLM from a mainshock-only generic model: the authors'
own development dry run declares generic Reasenberg-Jones non-inferior to the OAF, and in the
candidate set the generic model and the OAF give the same nine quantiles in two thirds
of test A's cells. A "supported" result would therefore say nothing about forecasting skill,
which the prereg itself concedes in its assay-sensitivity clause. Second, the registered score
is not the forecasts' log score but that of a reconstruction from nine integer quantiles; in
71% of test A's official cells all nine are zero, the reconstruction then assigns every
forecaster the same distribution, and where it does not, the tail that decides the score is
supplied by the scorer. Both problems push toward "no difference", which in a non-inferiority
test is the conclusion the authors want to draw. Both can be fixed before the freeze.

## 2. Findings

### 1. The primary test has no assay sensitivity, and the design already knows it
(a) **Fatal** for the primary claim as written.
(b) Prereg section 2, "Assay sensitivity ... If generic RJ is also non-inferior, A and B are
reported as unable to separate the model from the generic default"; anchors in the same
section: "Generic RJ minus official is -0.013 on E3".
(c) A non-inferiority test is only informative if the reference demonstrably beats a
no-skill comparator on the same cells. Here it does not, and the authors have the evidence:
- Development dry run (`confirmatory_dryrun_secondary_d2`): generic RJ against official, mean
  +0.0009, upper bound 0.020, status `noninferior`, for every tested model's cells.
- Blind count, test A's 89 sequences: the official forecast at the first issue is the product
  "Reasenberg-Jones (Generic)" for 76 of 89 sequences (ETAS for 3). The pipeline's generic RJ
  gives exactly the official's nine M>=5 quantiles in 66.6% of the 1,415 cells, and in 93.4%
  of the cells issued in the first day.
- The same dry run shows what passes: Opus 4.6 is "supported" (mean +0.033, upper 0.061)
  although its lower bound is above zero (0.009), its first-day stratum is not non-inferior
  (mean +0.093, upper 0.196), and the authors' own diagnostic gives it an information gain of
  -2.9 nats per earthquake against the official forecast. Haiku 5.5 passes too.
(d) The expected outcome of the registered primary analysis is "A supported; generic RJ also
non-inferior; no claim of skill". A paper built on that has no primary finding, and readers
will still quote "non-inferior to the USGS forecast".
(e) Make the primary question one the data can answer. Options: a three-arm retention-of-effect
test (model, official, generic RJ as the placebo arm; claim non-inferiority only where the
official beats generic RJ, and require the model to retain a stated share of that advantage);
or restrict the primary cells to versions where the official forecast is sequence-specific
(differs from generic RJ, an outcome-blind rule); or make superiority over generic RJ and the
rule of thumb (now S3 and S4) the primary hypothesis and report the OAF contrast as an
estimate with its interval. Add a registered negative control (finding 13).
(f) CHANGES-THE-DESIGN.

### 2. The registered score does not score the forecasts in the regime that makes up the data
(a) **Major** (close to fatal in combination with finding 1).
(b) Prereg section 1, "every forecaster is scored through its nine quantiles with the same
latent-PCHIP reconstruction and its power-law upper tail"; `countdist.from_quantiles`; ADR 0015
"Representation effect".
(c) Three separate objections.
- **Degenerate cells.** Blind count: in 70.7% of test A's official cells all nine M>=5
  quantiles are 0 (91.3% of cells issued at 7 days or later, 74.1% at 1 to 7 days, 3.7% in the
  first day); the official median is never 1 or more; 10 sequences have no other kind of cell.
  For nine zeros the code returns the same distribution whatever the forecaster believed:
  p(0) = 0.990, p(1) = 0.0102, p(2) = 2.7e-5, p(n >= 3) below the floor. An official
  P(N >= 1) of 0.2% and of 2.4% are scored as 1.02%. Where the model also answers nine zeros,
  dS is exactly 0 whatever happens.
- **A cliff, with a scorer-supplied tail.** Moving only the 97.5% quantile from 0 to 1 changes
  the reconstructed P(N >= 1) from 1.0% to 4.0% and p(3) from the floor to 2.8e-3. Two
  forecasters at 2.4% and 2.6% therefore differ by 7.9 nats if three events occur. The D2
  "rare-event miss" that dominates gpt-5.1's development effects (official about 10%, model
  about 3%) is of this kind. Above the last quantile the score is decided by a power law
  whose exponent comes from the spacing of the last two knots, not by anything either
  forecaster said; ADR 0015 reports that this changes the official score by a quarter of a nat
  on large sequences, "as large as the differences between forecasters".
- **Not proper for the forecaster.** The prompt promises "a proper scoring rule". The log
  score of a reconstruction is not proper with respect to the reported quantiles. Example
  (the registered code, synthetic input): a forecaster whose true distribution has
  P(N >= 1) = 2.4% and a heavy tail (so all nine true quantiles are 0) expects 0.181 nats by
  reporting honestly and 0.144 by reporting a 97.5% quantile of 1. ADR 0015's synthetic check
  ("never beats the truth") tests the reconstruction of a true distribution, not whether
  honest reporting is optimal.
(d) The verdict depends on the scorer's reconstruction. In the development dry run Opus 5.5 is
"inconclusive" under the registered score (upper 0.176), and "non-inferior" with the official
forecast's full distribution (0.060); the negative-binomial tail gives 0.111. Loss of
resolution biases dS toward 0, the direction that favors the claim.
(e) Elicit what matters in this regime. The OAF publishes P(at least one) for every magnitude
bin; ask the model for P(N >= 1) at M>=5 (and M>=4, M>=3) beside the quantiles, as it is
already asked at M>=6, and score that probability with the log or Brier score against the
official `probability` field at full resolution. Keep the count score for cells where counts
are expected. Failing that, add upper quantiles (0.99, 0.999) and register the share of
cells with identical quantile vectors and the test on the remaining cells. This is a prompt
change; D2 would have to be repeated on the development items before the freeze.
(f) CHANGES-THE-DESIGN.

### 3. The margin has no seismological meaning and was set with the power table in view
(a) **Major.**
(b) Prereg section 2, "Margin delta = 0.10 nats per cell ... So delta = 0.10 is generous for
small sequences"; ADR 0018, "this design works at 0.05; at 0.03 only test A has useful power",
then the 2026-10-31 table (test A power 0.12 at 0.05, 0.62 at 0.10) and the decision
"delta = 0.10. It lies between the small-sequence and large-sequence factor-of-2 costs".
(c) - The margin is justified as lying between two anchors, 0.063 (small sequences) and 0.30
  (large ones). Blind count: test A has no large sequences (61 of 89 are M5.0-5.4, 22 are
  M5.5-5.9, 6 are M6.0-6.4, none above). Only the small-sequence anchor applies, and the
  margin exceeds it: by the authors' own number, a forecaster wrong by a factor of two in
  rate is inside the margin.
- A mean per cell is diluted by construction. 83% of test A's cells are issued after the
  first day, where three quarters or more are the degenerate cells of finding 2. If a deficit
  sits in the first-day cells, 0.10 per cell allows about 0.6 nats in each. In the units a CSEP reader uses, the
  dry run shows a model at -2.9 nats per earthquake inside the margin.
- The margin doubled the day the gpt-5.1 development run showed that 0.05 gave 12% power.
  That is permitted on development data, but the anchor is then a rationalization and should
  not be presented as the reason.
- I could not tell whether the factor-of-two anchor was scored through nine quantiles. Under
  the registered score, doubling a small rate usually moves no integer quantile and costs
  exactly 0.
- The estimand weights an M5.0 sequence with no aftershock and an M6.4 sequence equally, and
  counts the first day three times (day inside week inside month).
(d) "Non-inferior at 0.10 nats per cell" cannot be translated into a statement about
probabilities or rates that a seismologist would accept as negligible.
(e) State the margin in interpretable units and where information exists: information gain
per earthquake, or nats per first-day cell, or a retained share of the official's advantage
over generic RJ (finding 1). Register the test by issue stratum, with the first day as the
primary stratum. Recompute the anchor under the registered representation.
(f) CHANGES-THE-DESIGN.

### 4. Power and size: the likeliest primary result is "inconclusive", and three secondary tests are not valid tests
(a) **Major.**
(b) Prereg section 2, "A: 0.45 on 89 sequences at 0.05"; section 6, "B at N = 33: 0.14 at
0.05", "S1 ... 0.084 at 0.05", "S2 has no development effects to simulate from"; "one-sided
0.05 ... looser than the usual one-sided 0.025 ... the power available justifies it".
(c) - Test A has 45% power at its own development estimate. The design does not say what an
  inconclusive result supports. It should: nothing, in either direction.
- B, S1 and S2 are labelled "supported / inferior / inconclusive" at nominal 0.05 while their
  simulated size is 0.14, 0.084 and unknown. A test that errs 14% of the time at a nominal 5%
  should not issue a verdict.
- The superiority tests (S3, S4, S5, and superiority after non-inferiority) rest on the same
  small, right-skewed samples. Their size was not simulated.
- Every power and size number is a resample of 18 development sequences from three months of
  2026, in which the heavy tail is one sequence. By my rough back-calculation from the
  diagnostics table (information gain per earthquake against the mean dS), the 203
  development cells hold on the order of five M>=5 event counts, nested windows included;
  please report the number. The true rate and size of such
  misses in 89 sequences from 2025-26 is unknown, so the stated size (0.018) is conditional on
  a tail estimated from one observation.
- The level was loosened from the conventional 0.025 because power was short. A reviewer will
  read that as buying significance.
(d) A null on A will be the modal outcome, and "supported" on B, S1 or S2 will not carry the
error rate its label implies.
(e) Report B, S1 and S2 as estimates with intervals and their simulated coverage, without
verdict labels, or calibrate their levels. Simulate the size of the superiority tests.
Give the size of A under tails heavier and rarer than the development one (for example one
sequence in 50 at the floor). Report A at 0.025 beside 0.05. Write the interpretation of each
possible outcome of A into the prereg.
(f) CHANGES-THE-DESIGN.

### 5. The confirmatory population is small earthquakes with an automatic forecast
(a) **Major.**
(b) Prereg section 4, "Primary set: M>=5 mainshocks in each model's clean period"; section 4,
development sequences excluded (49); ADR 0006 (every M>=7 candidate since 2025-07 is
registered, hence development).
(c) Blind count for test A: no mainshock of M6.5 or more; 93% below M6.0; 72 of 89 from the
`us` network; forecast circles with a median radius of 10 km; the official model is
Reasenberg-Jones at 463 of 472 issue times and ETAS at 9. The sequences for which an
operational aftershock forecast matters, and for which ADR 0018 itself expects LLM
under-updating to "cost more", were all used for development.
(d) Whatever A shows, it is a statement about automatic RJ products for M5.0-6.4 events with
mostly empty windows. It cannot support "LLMs match the USGS operational forecast".
(e) Scope the title, abstract and conclusions to that population; give the magnitude and
product-type table; say that large sequences are untested in the confirmatory arm (the
prospective arm will add whatever occurs). A magnitude-stratified estimate is worth
registering even if underpowered.
(f) MANUSCRIPT.

### 6. Test B's prospective part selects against the only cells that carry information
(a) **Major.**
(b) Prereg section 5, "a matched item enters test B only if its answer record's hash reached
the GitHub push receipt before the item's first window opened"; ADR 0017, "the first window
opens a median 12 minutes after the version is published. In 30.4% of versions it opens before
publication", polling every 10 minutes, first live detection "would have been 12 minutes
late"; ADR 0018, "almost every sequence enters, with roughly half its cells".
(c) Information sits in the first issue (3.7% degenerate cells in the first day against
74-91% later, blind count). The first issue is also the item least likely to be on time:
publication lag, a 10-minute poll, ComCat index lag and one to several minutes of model time
all precede a window that opens minutes after publication. A sequence then enters B through
its later issues, where dS is zero by construction, and counts as one sequence with an effect
near zero. The late-share table in ADR 0017 is over all versions, not by scheduled slot. The
registered timeliness table compares medians; it does not protect the test.
A second asymmetry: live, the catalog is "the one fetched at detection" (`live.live_tables`
cuts today's catalog at the cutoff by origin time). The model sees events and revisions
indexed after the official forecast was computed. In the first hour that is not negligible
(ADR 0016 measures the backfill).
(d) The one arm that cannot be contaminated is biased toward non-inferiority by its inclusion
rule, and its two parts estimate different things.
(e) Before the freeze, report the on-time share by slot from the dry run. Register B's
prospective estimate by stratum and require a stated number of on-time first-day items for
any verdict; consider faster polling for the first version of a new sequence. State the
detection-lag information advantage and bound it (for example by rerunning the baselines on
the catalog cut at the official creation time).
(f) CHANGES-THE-DESIGN.

### 7. Test A's contamination control rests on a vendor's statement
(a) **Major.**
(b) Prereg section 1, "each model is scored only on sequences whose mainshock falls after its
training cutoff plus a 3-month buffer"; section 3 table (gpt-5.1 cutoff 2024-09-30, clean from
2025-01-01); section 6 release date 2025-11-10; sensitivity "a release-date clean rule".
(c) Blind count: 62 of test A's 89 sequences (70%) occurred before gpt-5.1 was released. They
are clean only if OpenAI's documented cutoff is exact and nothing later entered the model.
The one bound that needs no trust, the release date, leaves 27 sequences, a sample at which
the authors' own simulation says the test is not controlled. The 3-month buffer is asserted,
not argued. The prompts give place names and dates, so recall is possible; the v1 recall
probe (`prompts/probe_recall.txt`) is not in the v2 design, and the D1 probes run on
development items only. The authors' own literature note lists a paper arguing that pre/post
comparisons cannot detect leakage.
(d) A skeptical reader can attribute any good result on A to leakage and cannot be refuted
from the registered analyses.
(e) Register a closed-book recall probe on the confirmatory mainshocks for every tested model
(no outcomes needed to run it; scored after the gates), and an anonymized-prompt variant
(relative dates, no place) on a subset. Report A split at the release date as a registered
contrast with its interval. Cite evidence on effective versus stated cutoffs to justify the
buffer.
(f) CHANGES-THE-DESIGN.

### 8. A model that never answers would pass the primary test
(a) **Major** in principle; probably small in effect at the invalid rates seen so far.
(b) Prereg section 7, "An invalid answer gets the worst score in its cell from a fixed pool
... the five baselines".
(c) The penalty is the worst of official, generic RJ, RJ-MLE, the rule of thumb and the ETAS
refit. Blind count: in 46.9% of test A's cells all five give identical nine quantiles, so an
invalid answer there costs exactly 0, and in 87.7% no baseline has a 97.5% quantile above 1.
A forecaster that returned nothing but invalid answers would be scored as the cell-wise worst
baseline, and finding 1 shows that baselines pass. The dry run is consistent with this:
gpt-5.1's "valid answers only" row equals its main row to every printed digit although one
of its answers was invalid.
Invalidity is also unlikely to be random: long catalogs and long reasoning hit the output cap.
(d) The rule does not do what a penalty must do in a non-inferiority design: make failure to
forecast count against the claim.
(e) Compute on development data the test result of the "always invalid" pseudo-forecaster; if
it is not "inferior", change the rule. Simple alternatives: a registered ceiling on the
invalid rate above which no non-inferiority verdict is issued, or a fixed ignorance forecast
that is strictly worse than every baseline.
(f) CHANGES-THE-DESIGN.

### 9. The informative-sequence estimand is empty and selects on the comparator
(a) Minor (but it is the design's stated remedy for finding 1).
(b) Prereg section 2, "the sequences whose official forecast at the first issue has a mean
N(M>=5) of at least 0.5 in the month window".
(c) Blind count with the registered function's rule: 5 of test A's 89 sequences qualify. In
the dry run 2 of 18 did and the bound was infinite. Selecting on a high official forecast also
selects official over-forecasts (regression to the mean), which favors the challenger.
(d) The secondary estimand meant to show sequence-specific skill cannot return a result.
(e) Select on something independent of both contestants (generic RJ's expected count, or
mainshock magnitude), at a threshold that keeps a usable number of sequences, chosen blind.
(f) CHANGES-THE-DESIGN.

### 10. About twenty secondary tests at 0.05 each, all with verdict labels
(a) Minor.
(b) Prereg section 2, "Secondary tests are at 0.05 each and labelled secondary"; section 6,
"The `status` column applies section 2's rule to every tested row".
(c) B, S1, S2, S3 and S4 for four models, S5 for two models and two baselines, the assay and
informative rows, and superiority after each non-inferiority: the label "secondary" is not an
error-rate control. Separately, the rule has no status for "worse than the official forecast
but inside the margin" (Opus 4.6 in the dry run); the paper will be tempted to print
"non-inferior" for a model that is detectably worse.
(d) Some secondary "supported" or "superior" will appear by chance and be quoted.
(e) Holm within each secondary family, or estimates and intervals without labels. Add the
status "worse, within the margin" when the lower bound is above 0, and headline the two-sided
90% interval.
(f) CHANGES-THE-DESIGN.

### 11. Hindsight reaches the prompt and the choice of versions
(a) Minor.
(b) `tables.py` lines 237-242 and `items.py` lines 120-128: the prompt's mainshock latitude,
longitude, depth, magnitude type and place come from the snapshot's current ComCat event; only
the magnitude is the version's `magMain`. ADR 0013, "Known limitation: event matching uses
today's mainshock".
(c) The model is shown a revised hypocenter and magnitude type that the OAF did not have at
the issue time, next to a magnitude it did have. And versions are declared invalid by
comparing their `magMain` with today's magnitude, which removes the versions built on a wrong
early magnitude: selection on later information, in the official forecast's favor (about 1%
of issue times, by the ADR's count).
(d) Small, but each contradicts the parity claim, and a reviewer will find them in the code.
(e) Build the mainshock block from the as-of preferred origin (the histories are already
fetched), or state the leak and show how often the fields differ.
(f) CHANGES-THE-DESIGN.

### 12. "Information parity" is stated more strongly than the design delivers
(a) Minor.
(b) Prereg section 1, "every forecaster sees what the OAF had at each issue time".
(c) Exceptions the documents themselves record: deleted events are not reconstructed (ADR
0011); the prompt keeps the 800 most recent events where the legacy ETAS code keeps the 1,000
largest; the
OAF may include analyst settings (ADR 0010 section 4.1); the prompt gives the model the
official region and windows; finding 11; and the live catalog is fetched after the official
forecast was made (finding 6). The evidence that the USGS data cutoff equals the window start
when the window opens before `creationTime` is one Kamchatka example (ADR 0004).
(d) An absolute claim invites a single counterexample.
(e) Replace with what is guaranteed: the as-of catalog reproduces the official products' own
observation counts in 99.05% of checks (99.98% at M5), with the listed exceptions.
(f) WORDING.

### 13. No negative control, no ablation and no climatological baseline on confirmatory data
(a) Minor (major if finding 1 is not fixed another way).
(b) Prereg section 2 (hypothesis table) and section 7 (the five baselines).
(c) - No forecaster known to be bad is registered. ADR 0018 records gpt-oss-20b at +0.35 nats
  and Olmo at +0.94 on E3; either, run locally at no cost, would show whether the test can
  fail a bad forecaster, and would give the study one arm that anyone can rerun after the
  API models retire.
- No mainshock-only (I0) arm on confirmatory data, so "the model uses the sequence" cannot be
  shown; the D1 probes are on development items.
- No empirical baseline: the distribution of aftershock counts by mainshock magnitude from
  the historical catalog (the 515 outcome catalogs already on disk would do).
(d) Without them a pass cannot be distinguished from a test that passes everything.
(e) Register gpt-oss-20b as a negative control and reproducibility anchor; add the I0 arm for
the A model; add the empirical baseline to S3/S4.
(f) CHANGES-THE-DESIGN.

### 14. Model identity and reproducibility
(a) Minor.
(b) Prereg section 3, "no dated snapshot, so each response's reported model is logged";
"If a model is withdrawn or changes (shown by `response.model`)"; "gpt-5.1 is removed from
the API on 2027-04-01".
(c) `response.model` detects a redirect to another ID, not a silent update behind an undated
ID (`gpt-6.1-sol`, `claude-opus-5-5`), nor changes in server-side reasoning behavior. S2's
"model" is whatever the alias served over six months. The primary model will be gone before
the paper appears, so test A cannot be rerun by anyone. Settings were chosen as "the highest
effort that reliably answers" on three development items under 12k-16k caps, while the
registered cap is 32k, and efforts differ across models.
(d) Limits what "gpt-5.1" and "Opus 5.5" mean in the conclusions and rules out cross-model
statements.
(e) Say so; archive every request and response (planned); avoid cross-model comparisons;
see finding 13 for an open-weights anchor.
(f) MANUSCRIPT.

### 15. The retrospective arm is a plan for existing, public data, and the seal is porous
(a) Minor.
(b) ADR 0013, "The guard is a brake against accidents, not a proof: the raw catalogs on disk
still contain the outcomes"; prereg section 9, "Prior exposure".
(c) The candidate data were fetched on 2026-10-29; the margin, the primary model, the level
and the exclusion handling were decided afterwards. Outcomes are public (ComCat). Later
issues' prompts and the stored `oaf_obs_m5` contain the outcomes of earlier windows. One
author and automated agents work in the repository that holds the catalogs. B's retrospective
part grows with every week the freeze is delayed.
(d) "Preregistered" will be read as "designed blind". For the retrospective arm it is a
pre-analysis plan with a software brake.
(e) Use that wording; give the dates; make the OSF registration mandatory rather than
optional; keep the list of prior exposures complete.
(f) MANUSCRIPT.

### 16. Independence between sequences
(a) Minor.
(b) Prereg section 6, "a sequence block bootstrap"; section 4 exclusion rule (context: "the
OAF events plus ComCat M>=6").
(c) The rule removes an event only inside the circle of a larger event that has an OAF product
or is M>=6; neighbors of similar size, and aftershocks of an M5.5-5.9 parent without an OAF
product, stay. Blind count: 4 pairs (8 of test A's 89 sequences) have overlapping forecast
circles and origins within 58 days; none in S1. S1's 23 sequences come from three calendar
months plus one event. The OAF code changed four times in the period (ADR 0010), so the reference is not one
system.
(d) Small for A. Worth closing because it is cheap.
(e) Resample the overlapping pairs as one block, by an outcome-blind rule; report results by
OAF code period.
(f) CHANGES-THE-DESIGN.

### 17. Text and code that disagree or cannot be traced
(a) Minor.
(b), (c) - Section 6: the 0.03 threshold was defined for nominal 0.025 (ADR 0018 decision 8)
  and is then applied to the sizes at nominal 0.05 ("0.018 and 0.029, within the 0.03
  threshold"). Say which level the calibration rule refers to.
- Section 2: the bootstrap-t powers (0.45, 0.64) are not produced by any command I could
  find; `laf.power.power` is the normal approximation and `confirmatory.size` returns size.
- B's size was simulated at N = 33 without its two strata and assuming all 26 prospective
  sequences contribute cells.
- `confirmatory.report` and its docstring still implement Holm across co-primary models;
  harmless with one primary model, but the text says there is no correction.
- prompts/README.md is headed "Prompts v0 (DRAFT, not yet run)" and describes the v1
  templates; ADR 0015 is "proposed". Both are cited as sources of the frozen design.
- Inclusion magnitude is "the frozen snapshot" for B's retrospective part and "first
  detection" for its prospective part: two definitions of M>=5 inside one test.
(d) Each is small; together they give a reviewer reason to doubt the rest.
(e) Fix the text; add the power simulation as a command with its output file.
(f) WORDING.

### 18. Outcome measurement
(a) Minor.
(b) Prereg section 4, "ComCat counts of events at or above the threshold ... in the official
forecast's region circle"; sensitivity "region radius x0.5 and x1.5".
(c) Blind count: the median forecast circle in test A is 10 km, the same order as teleseismic
location uncertainty for the 72 `us` events, and M5.0 is a threshold across mixed magnitude
types. Whether an aftershock counts can turn on a location or an mb/Mw difference. Both
forecasters are scored on the same outcome, so this adds noise rather than bias, unless one of
them forecasts the sequence and the other the circle. The x1.5 check runs "only where the
catalog query covered it".
(d) Noise in a handful of events decides a test whose information is a handful of events.
(e) Report how many M>=5 outcome events lie within one radius outside the circle or within
0.1 of the threshold, and the x1.5 coverage share.
(f) MANUSCRIPT.

### 19. Operations of the live arm
(a) Minor.
(b) Prereg section 5, "The 6-month clock does not pause for outages"; "Misses are listed as
'missed: budget'"; runbook section 7.
(c) One host; missed issues are never backfilled; under a binding budget gpt-6.1-sol is
dropped first, so S2's missing items cluster in busy months. None of this depends on outcomes
as far as I can see, but it thins the first-day cells further (finding 6).
(d) Affects power and representativeness of B and S2, not validity.
(e) Report issued, late, missed and failed counts by slot and month (planned), and the
realized number of first-day cells.
(f) MANUSCRIPT.

### 20. Prior work a Seismica referee will expect
(a) Minor.
(b) docs/research/novelty-and-literature.md, sections B-D.
(c) The list covers CSEP basics and LLM benchmarks but misses work that bears directly on the
weak points above (please verify each reference; I cite from memory):
- scoring forecasts when events are rare: Serafini et al. (2022, GJI) on proper scores for
  binary events in a low-probability environment; Brehmer et al. (2024) on comparative
  evaluation of point-process forecasts; Nandan et al. (2019, SRL) on forecasting full count
  distributions; Rhoades et al. (2011) for information gain per earthquake and its tests;
- operational and early aftershock forecasting: Omi et al. (2013) and later papers on
  forecasting from incomplete early catalogs; Savran et al. (2020) on the pseudo-prospective
  Ridgecrest evaluation; Mizrahi et al. (2024, Reviews of Geophysics) on current practice;
- non-inferiority methodology: ICH E10 on assay sensitivity and the three-arm
  retention-of-effect design (for example Pigeot et al. 2003);
- LLM forecasting and cutoffs: Halawi et al. (2024), Schoenegger et al. (2024), Gruver et al.
  (2023) and Requeima et al. (2024) on numerical predictive distributions from LLMs, Paleka
  et al. (2025) on pitfalls in evaluating LLM forecasters, Cheng et al. (2024) on effective
  versus stated knowledge cutoffs.
(d) The first group anticipates finding 2; the third, finding 1.
(e) Read and cite; use them to motivate the changes.
(f) MANUSCRIPT.

## 3. Checked and found sound

- **Bootstrap.** `confirmatory.noninferiority`, `_stratified` and `decide` implement what
  section 6 says: resampling of per-sequence means, the studentized bound, an order-statistic
  quantile, fixed seed and B, the stratified standard error for B, the fallback when a part has
  fewer than two sequences. The simulated sizes in the prereg match
  `results/confirmatory_size_d2_*.csv`.
- **One primary hypothesis**, superiority only after non-inferiority, sensitivity analyses
  listed in advance and reported whatever their result, "no sensitivity analysis overturns a
  primary result".
- **Demoting B** after the size simulation, and saying in the text that B "cannot rule out a
  rare-event deficit", is the honest call.
- **Stopping rule.** S depends on calendar time and a count of detected mainshocks, not on any
  score; no interim look; one snapshot at S + 90 days. `splits.py` enforces annotated tags,
  descent from `prereg-v2`, and S in epoch ms within bounds.
- **As-of catalogs.** The validation against the official products' own observation counts
  (99.05% of 23,264 checks, 99.98% at M5) is the right check, and the information cutoff
  min(creationTime, window start) is the conservative choice. ADR 0016's measurement of the
  hindsight-catalog effect is a contribution in itself.
- **Forward-looking exclusion.** Found by the authors, kept out of the main set, reported as a
  sensitivity analysis; the prospective and supplementary rules use the backward half only
  (`prospective.is_aftershock`, `candidates.is_aftershock`).
- **Clean sets.** `eligible` and `batch_items` apply one rule, so what is sent is what is
  analyzed; development sequences can never enter.
- **Sealing.** Answers are sealed and pushed before the baselines run; on time is decided by
  the push receipt (`receipt_ms < first_window_ms`), with OpenTimestamps as a witness; a
  model change stops accrual from the first mismatched answer.
- **Invalid versus transport.** The distinction is clear and coded the same way for batches
  and live answers; the penalty pool does not depend on k or on which runs are loaded (its
  leniency is finding 8).
- **Sequence overlap** in test A is limited to 4 pairs (finding 16).

## 4. Questions for the authors

1. In the live dry run, what share of first-version matched items would have been on time,
   by scheduled slot, with the registered models' measured latency?
2. Was the factor-of-two anchor (0.063, 0.300) scored through nine quantiles and the
   registered reconstruction, or through the fitted negative binomial?
3. On the development cells, what does the registered test return for a forecaster whose
   every answer is invalid?
4. Which code and seed produced the bootstrap-t power values 0.45 and 0.64?
5. How many M>=5 aftershocks does the official forecast itself expect in test A's cells
   (an outcome-blind sum)? That is the study's effective sample size.
6. Why is the "region radius x0.5" row in the dry run identical to the main row for all
   three models?
7. For official versions whose windows open before `creationTime`, what evidence beyond the
   Kamchatka example shows that the product used no data after the window start?
8. Which events receive an OAF product (72 of test A's 89 are `us` network events), and has
   that policy changed during the archive?
9. Is there a latest date for L? Each week before the freeze moves sequences from the
   prospective part of B to the retrospective part.
10. Section 2 lists "hindsight effect (ADR 0016)" as descriptive: on which data, with which
    forecasters, and does the LLM subset on the hindsight catalog run on confirmatory items?
