---
title: "Can general-purpose language models forecast aftershocks? A pre-registered comparison with the USGS operational aftershock forecast"
author: "Tyler Newton (independent researcher)"
bibliography: references.bib
link-citations: true
---

<!--
DRAFT. Working title. Target: Seismica, Research Article (docs/research/seismica-guidelines.md:
10,000 words and 10 display items in the main text, abstract of at most 200 words).

What is written: the introduction, the methods, the limitations that the design fixes, and the
statements. What waits: the abstract, results, discussion and conclusions, which need the
registered analyses (docs/preregistration-v2.md, both gates). Nothing here uses a confirmatory
outcome. Development numbers appear only where the pre-registration itself cites them to justify
the design (margin, power, size).

Every statement in the methods comes from docs/preregistration-v2.md (cited as "prereg" with its
section) or the ADR it names. If the pre-registration changes before the freeze, this text
follows it. Quantities known only later are marked [TBD: ...].

references.bib is the working reference list: every entry's metadata was fetched from doi.org
or the arXiv API, then corrected by hand where the record was incomplete. Entries not cited
are removed at submission. Render from this folder: pandoc manuscript.md --citeproc -o out.html

To read before the discussion is written (in references.bib, suggested by the mock review of the
design, docs/reviews/mock-review-design.md, finding 20): scoring rare events (Serafini_2022,
Brehmer_2023, Brehmer_2024, Nandan_2019); operational and pseudo-prospective evaluation
(Savran_2020, Mizrahi_2024, Omi_2013); three-arm non-inferiority designs (Pigeot_2003); LLM
forecasting and numerical distributions (Halawi_2024, Schoenegger_2024, Gruver_2023,
Requeima_2024, Paleka_2025). They are cited in the text only once read.

The mock review's design findings were decided by the author (docs/preregistration-v2.md,
decisions 32 to 44: primary score, margin, negative controls, invalid-answer rule). Sections
2.5, 2.7, 2.8, 2.10 and 4.1 follow those decisions; Serafini_2022 and Brehmer_2023 have been
read and are cited; Nandan_2019 is cited from its abstract only and is to be read in full
before submission.

A mock review of this draft (docs/reviews/mock-review-manuscript.md) was answered by decisions
45 to 50 of the protocol, and the text follows them: the reference's own effect, the bound at
0.025, the generic-model check, the depth and region strata, the cluster-block bootstrap, the
release contrast, the sixth gap in information parity, what the on-time rule selects, and
the design history (Table S1 in the supplement, docs/manuscript/supplement.md, with the
full list of prior exposures).
-->

## Abstract

[TBD: at most 200 words, no references; written after the registered analysis, with the
deficit in nats per cell. The protocol fixes in advance what the abstract may say, by the
outcome of the primary test (A). If A is supported, the generic model is inferior or
inconclusive and neither control is supported: the primary model is non-inferior to the
official forecast at the margin, on moderate sequences. If A is supported, the generic model
is also non-inferior and neither control is supported: the model is within the margin of the
official forecast and so is the generic model, a forecaster as good as a calibrated generic
model, with no claim of skill specific to a sequence; the abstract carries that clause in the
same sentence. If A is supported and either control is supported: the test did not tell
forecasters apart, and there is no claim. If A is inconclusive, under either label: nothing
in either direction; the estimate and its interval are reported, and the abstract says the
comparison with the official forecast was inconclusive. If A is inferior: the model is worse
than the official forecast by more than the margin. If A is supported but the official
forecast is not shown to beat the constant control on the same cells (the lower bound of
that control's difference is not above 0): no claim rests on "supported", and the abstract
says so in the same sentence. The protocol has no pre-written sentence for superiority over
the official forecast or for a stratum or secondary interval below 0, and no headline claim
is made from either.]

## Non-technical summary

[TBD: about 200 words; encouraged by the journal, not required.]

## 1 Introduction

After a large earthquake, the question that matters most to the people nearby is what comes
next. The United States Geological Survey (USGS) answers it with an operational aftershock
forecast (OAF): for a region around the mainshock, the probability of at least one aftershock
above each of several magnitudes, and the range of the number of aftershocks to expect, over
the next day, week, month and year [@Michael_2020; @Hardebeck_2024]. These forecasts rest on
two families of statistical models. The Reasenberg–Jones (RJ) model combines the Omori–Utsu
decay of aftershock rate with time and the Gutenberg–Richter distribution of magnitudes
[@Reasenberg_1989; @Reasenberg_1994; @Utsu_1995], with generic parameters by tectonic region
that are updated as a sequence unfolds [@Page_2016; @Hardebeck_2019]. The epidemic-type
aftershock sequence (ETAS) model lets every earthquake trigger its own aftershocks
[@Ogata_1988], and USGS also issues ETAS-based forecasts [@van_der_Elst_2022]; for the
sequences of this study the official forecast is almost always an RJ product (Section 4.1).
Both are simple, well understood and hard to beat. In a benchmark of neural point processes on
California catalogs none beat ETAS [@Stockman_2024], a well-known deep-learning result on
aftershock locations was reproduced by a model with a single neuron
[@DeVries_2018; @Mignan_2019], and gains over ETAS or the operational forecast are only now
being reported for models trained for the task [@Xiong_2026; @Zhu_2026].

General-purpose large language models (LLMs) are a different kind of forecaster. They are not
trained on earthquake catalogs for this task, yet they have read much of the seismological
literature, and they can be given a catalog and asked for a forecast in plain language. There
is evidence that they hold quantitative knowledge about earthquakes: they estimate shaking
intensity from reports and descriptions of an event [@Mousavi_2024; @Li_2025]. Outside
seismology, LLMs are now scored as probabilistic forecasters against human forecasters and
betting markets [@Karger_2024; @Ding_2026]. They are also what a member of the public can consult within
minutes of an earthquake, whether or not an official forecast exists for it. To my knowledge,
no study has scored the aftershock forecasts of a general-purpose LLM with proper scoring
rules against an operational forecast (the search is logged in the project repository).

A fair test of that kind has to solve four problems, and each has undone evaluations before.

The first is contamination. An LLM asked about an earthquake that occurred before its training
data ended may recall what happened instead of forecasting it. The advantage of frontier
models shrinks on questions that resolve after their training cutoff [@Douven_2026], recall
can be detected directly [@Gao_2025], and comparing scores before and after the cutoff cannot
by itself detect the leak [@Zhang_2026]. The only complete remedy is to forecast events that had not happened when the
model was trained, and best of all events that have not happened yet.

The second is hindsight in the data. Earthquake catalogs are revised for weeks after a large
event: events are added, magnitudes change. A retrospective test that shows a forecaster
today's catalog gives it information the operational forecast did not have when it was issued.

The third is statistical. Aftershock productivity varies widely between sequences
[@Page_2016], most moderate mainshocks have no large aftershock at all, and the
forecasts for one sequence at successive times and over nested windows are strongly dependent.
A few large sequences can therefore drive any pooled score, in either direction.

The fourth is the freedom of the analyst. With many models, prompts, magnitude thresholds,
windows and scores to choose from, some comparison will favor any conclusion. Earthquake
forecasting answered this problem with prospective testing under rules fixed in advance
[@Schorlemmer_2007; @Schorlemmer_2018; @Jordan_2011], and other fields with pre-registration
[@Nosek_2018].

This study is built around those four problems. I froze the protocol, the prompts, the code
and the list of candidate sequences before scoring any forecast in the confirmatory data
(Section 2.1). Each model is scored only on sequences whose mainshock came at least three
months after the cutoff that its vendor documents, and a prospective arm forecasts new
sequences in real time, with every forecast sealed and its seal time-stamped, so that a
forecast made after its window opened is identified and left out (Section 2.9).
Every forecaster is given the catalog that the official forecast had, as closely as it can be
rebuilt from the catalog's own version history; six known gaps remain (Section 2.4). The unit
of analysis is the sequence, and the primary test is a single one-sided test with a stated
margin (Section 2.8).

The primary hypothesis is that the forecasts of one LLM, queried once with a fixed prompt and
no tools, are non-inferior to the USGS operational forecast: that the mean logarithmic score
of the probability the model states for at least one M≥5 aftershock is worse than that of the
official probability by less than 0.02 nats per cell (one forecast window at one issue time;
the mean is taken over sequences, of each sequence's mean), on the sequences whose mainshock
came at least three months after the knowledge cutoff that the model's vendor documents.
Non-inferiority within a margin is a weaker claim than equivalence in skill, and the design
says so in four ways. The same test is run for the generic RJ forecast, which uses nothing
about a sequence but its mainshock; if that forecast also passes, as I expect it to, the test
cannot tell a forecaster with sequence-specific skill from a generic default, and I claim
none. Two forecasters that should not pass, a rule of thumb and one constant probability, are
run through the test as negative controls and are predicted not to be supported. I report
whether the official forecast itself is shown to beat that constant probability on the same
cells, and I claim nothing from a supported result if it is not. And the test is expected to
be inconclusive at this sample size, in which case the finding is the estimate with its
interval (Section 2.8).

These are probabilistic forecasts of aftershock counts in a stated region and time window.
Nothing in this paper predicts individual earthquakes, and the forecasts published by the
prospective arm are not official forecasts.

## 2 Data and methods

### 2.1 Pre-registration and data splits

The study has two stages. A first analysis of 11 sequences was registered and reported in
October 2026 [TBD: cite the archived write-up]. Those sequences, 39 more that I scored while
developing the methods, and the sequences whose outcomes were used in adaptation experiments
are *development* data: I scored them freely, and every design choice below that needed an
outcome was made on them. Forty-nine of them are among the events with an official forecast
and are excluded from the candidates in Section 2.2: 7 of the 11 registered sequences, the 39
and 3 from the adaptation experiments. Every other sequence is *confirmatory*. Outcome
exposure, not input exposure, makes a sequence development data: a sequence whose catalog had
appeared in a prompt but whose outcomes I had not seen stayed confirmatory.

The protocol for the confirmatory stage was frozen as a pre-registration at the commit tagged
`prereg-v2` [TBD: commit hash, date and the public record of its SHA-256]. The frozen material
is the protocol, the prompt templates, the package versions, the analysis code, the candidate
sequences with their forecast items, the data manifest, and the baseline forecasts, which were
computed before any outcome was unsealed. Before the freeze, no confirmatory forecast was
scored. The work on confirmatory sequences was fetching data, rebuilding catalogs, building
prompts and computing baseline forecasts, with six exceptions that the protocol lists as
prior exposure and Supplement Section S1 gives in full: a catalog check whose observation
counts hold part of the outcome of earlier windows (Section 2.4); the timing logs of a dry
run of the prospective detector; two paid end-to-end checks, whose answers were checked for
form and never scored; the identities of the three events excluded by the forward-looking
half of the exclusion rule (Section 2.2); and two sets of counts on the candidates' forecast
and sequence tables, made on 11 and 12 November 2026 without any catalog, observed count or
score. The first set fixed the choice of the primary score, the meaning of the margin and
the informative-sequence threshold; both are quoted where they are used. The code enforces the split. Outcome counts
of confirmatory sequences are written as nulls until two conditions hold: the freeze tag
exists, and a second tag records the end of the prospective arm and 90 days have passed since
then (Section 2.9). No confirmatory score or test was computed before that date, so no interim
result could shape the analysis. Changes after the freeze are listed with their time, reason
and expected effect in [TBD: Supplemental Section / deviations log].

### 2.2 Sequences

The retrospective candidates are all events in the USGS Comprehensive Earthquake Catalog
(ComCat) that carry an OAF product, from the start of that archive (14 November 2024) to 29
October 2026: 254 events. I excluded the 49 development sequences and 10 events that are
foreshocks or aftershocks of a larger event, defined as lying within 365 days and within 1.5
subsurface rupture lengths [@Wells_1994] (at least 10 km) of a larger event. The larger
events considered are those with an OAF product and all ComCat events of M≥6 since 1 November
2023, so an aftershock of a smaller event without an OAF product stays in as a mainshock.
That leaves 195 candidates. The foreshock half of this rule uses information from after the
event, since a later, larger earthquake can fall inside the event's own forecast windows;
three events were excluded for that reason alone. The candidate list was kept as built, and
prospective sequences are subject only to the backward-looking (aftershock) half of the rule.
The three are added back in a sensitivity analysis, which adds one sequence to the primary
test: only one of them (M5.5) is an M≥5 mainshock in a tested model's clean period.

The candidate list ends before the prospective arm starts. Sequences with a mainshock between
29 October 2026 and the start of the prospective arm (*L*, Section 2.9) were fetched once, at
least 7 days after *L*, into a supplementary snapshot built by the same outcome-blind
procedure with the backward-looking half of the rule; its items and baselines were hashed and
time-stamped before any model saw them. They belong to the retrospective part of test B
(Section 2.8).

The primary set for each model is the candidates with a mainshock of M≥5 in that model's clean
period (Section 2.5). A secondary set holds M4.0–4.9 mainshocks located by United States
regional networks. Magnitudes are those of the frozen data snapshot, or those at first
detection in the prospective arm. A sequence without a valid official forecast or without a
scorable forecast cell drops out; that attrition is reported. The primary model's set is
narrow in region, depth and magnitude; Section 4.1 describes it.

### 2.3 Official forecasts, issue times and cells

Each OAF product version gives, for a circle around the mainshock and for windows of a day, a
week, a month and a year, the distribution of the number of aftershocks at or above M3, 4, 5,
6 and 7. I used the day, week and month windows. A version was rejected if it was filed under
the wrong event: created before the mainshock, centered too far from the epicenter, or stating
a mainshock magnitude more than 0.25 from the one the catalog gives today (Section 2.4).

USGS updates a forecast many times in the year after a mainshock. From each sequence I took
the first valid version and, for each target time *t* of 1, 3, 7, 14 and 28 days after the
mainshock, the earliest valid version whose information cutoff falls in
[*t*, *t* + max(1 day, *t*/4)). The information cutoff of a version is the earlier of its
creation time and the start of its windows, because in many versions the windows start before
the forecast was created. An *issue* is one such version, and a *cell* is one issue and one
window; each magnitude target is scored on those cells separately. Every forecaster's forecast for a cell refers to the same
circle and the same half-open window [start, end) as the official one.

### 2.4 Information available to the forecasters

Every forecaster is given what the official forecast had, as closely as it can be rebuilt:
the mainshock and the catalog of events in the forecast circle with origin time before the
information cutoff. In the
retrospective arm that catalog is rebuilt as it stood at the cutoff. ComCat keeps every
version of every origin with the time at which it was indexed; for each event I kept the
versions indexed by the cutoff and took the preferred origin among them. As a check, each
official ETAS and RJ product records how many events above several magnitudes it had fetched.
On 194 of the 195 candidates the rebuilt catalog reproduces those counts exactly in 99.05%
of 23,264 checks, against 96.85% for the catalog as it stands today. The observation counts
of a later version hold part of the outcome of an earlier version's windows, so this check
is listed among the prior exposures (Section 2.1). In the prospective arm the catalog is the
one fetched when the official version is detected.

Six gaps remain and are not corrected. Events that existed at the time and were later
deleted cannot be rebuilt. The mainshock's location, depth, magnitude type and place name in
the prompt are those of the catalog snapshot; only its magnitude is the official version's.
An official version is matched to its event by today's mainshock magnitude and location,
which matters at about 1% of issue times. Settings that an analyst chose inside an official
product are not available to any other forecaster. In the prospective arm the catalog
fetched at detection can hold events and revisions indexed after the official forecast was
computed. And the prompt lists the catalog from M3 without saying where it is complete: the
regional completeness magnitude of the official model is 3.5 for 47 of the primary set's 89
sequences, 4.6 for 39 and 3.0 for 3, so for 86 of them the absence of small events from the
list is not evidence of quiet, and the model is not told.

### 2.5 Language models, prompt and answers

[TBD: Table 1. Models: identifier, documented cutoff under the vendor's own term for it,
first clean date, settings, role. Content: prereg section 3.]

Five models from two vendors were run (Table 1). A sequence is *clean* for a model when its
mainshock occurred at least three months after the end of the month of the cutoff that the
model's vendor documents. I use each vendor's own term for that date: the "training data
cutoff" of the Anthropic models and the "knowledge cutoff" of the OpenAI models. The primary
model, `gpt-5.1-2025-11-13` (OpenAI; knowledge cutoff 30 September 2024, clean from 1 January
2025), is clean on almost the whole OAF archive. `claude-opus-5-5` (Anthropic; training data
cutoff June 2026, clean from 1 October 2026) is the model of the prospective arm, with
`gpt-6.1-sol` (OpenAI; knowledge cutoff 30 April 2026). `claude-opus-4-6` and
`claude-sonnet-4-6` (Anthropic) have intermediate cutoffs. `claude-sonnet-4-6`, and
`gpt-6.1-sol` on the retrospective sequences, are descriptive: their results are reported
without a test. Reasoning settings were fixed on development items before the freeze
(Table 1) by pilots; for `gpt-5.1` and `claude-sonnet-4-6` a higher setting used up the
pilot's output limit before giving an answer. For `gpt-5.1` that limit was 16,000 tokens,
half the study's (Table S1).

The unit of the study is a single answer to a fixed request. The request is a call to the
vendor's programming interface with a system prompt that casts the model as a statistical
seismologist, a JSON schema for the answer, a fixed reasoning setting and the catalog of
Section 2.4; it is not a conversation in a consumer chatbot. All requests were made without
sampling parameters, tools, prefilled answers or server-side fallbacks, to the vendors' own
endpoints. The model identifier returned with each answer was logged; in the retrospective
runs an answer from a model other than the one requested was invalid.

The prompt states the mainshock, the forecast circle, the issue time and the windows, and
lists the catalog of M≥3 events in the circle from 7 days before the mainshock to the
information cutoff (at most 800 events, with daily counts beyond that). It asks, for each
window, for nine quantiles (2.5, 5, 10, 25, 50, 75, 90, 95 and 97.5%) of the number of
earthquakes of M≥5, M≥4 and M≥3, and for the probability of at least one earthquake of M≥3,
M≥4, M≥5 and M≥6. The system prompt tells the model that its probabilities and quantiles will
be scored with proper scoring rules, that it has no tools, and that nothing after the issue
time is known. For the quantiles that statement refers to the log-scale quantile score
registered for the first stage, a sensitivity analysis here; the count score of Section 2.7
is not a proper score of the reported quantiles alone. The model is told neither where the
catalog is complete (Section 2.4) nor that probabilities are clipped before scoring (Section
2.7). The wording was fixed on development items; a paraphrase of it is run as a robustness
check. Each item was sent three times, and a model's score in a cell is the mean over its
three answers, which estimates the expected score of a single answer.

For the primary score an answer is invalid in a window when it gives no usable probability
of an M≥5 earthquake there: a refusal, an answer cut off at the output limit (32,000 tokens),
text that cannot be parsed, or a probability that is missing or outside [0, 1]. An invalid
answer is not dropped. It counts as a score difference of $\log 2$ (0.69 nats), the loss of
a coin flip against a certain outcome; an invalid rate of 3% would alone use up the margin of
Section 2.8. No fixed penalty is both mild and unable to help a
model, so two registered analyses bracket it: the worst possible score in place of $\log 2$,
and a stricter rule under which a defect anywhere in the answer makes it invalid. That
stricter rule was the registered one until the development run with this prompt; the change
and its effect are stated in Section 4.1. If the verdict differs between $\log 2$ and the
worst possible score, I report the result as depending on how invalid answers are handled.
For every other target the whole answer must be valid. In the Brier-score analysis an
invalid answer takes the worst Brier score, 1, and on the strict items of Section 2.9, which
have no official forecast, it scores $\log 2$ itself. Invalid rates are reported per model
and arm, by time since the mainshock and by whether an M≥5 earthquake occurred in the cell.
Only a failure to deliver any answer counts as a transport error. Such a request was sent up
to ten times in all; persistent failures are listed and left out of the estimate, so a cell
with no delivered answer drops out.

### 2.6 Baselines

Four statistical forecasts were computed for every cell from the same catalog the LLMs saw.

1. *Rule of thumb.* The number of M≥5 events so far, extended with an Omori decay with
   *p* = 1 and *c* = 0.05 days, Poisson counts, and a Gutenberg–Richter *b* of 1 for the other
   magnitudes.
2. *Generic RJ.* The RJ model with the USGS generic parameters for the tectonic regime of the
   epicenter [@Page_2016; @Garcia_2012], taken from the operational code, including the
   between-sequence spread of productivity. It uses nothing about the sequence but the
   mainshock.
3. *RJ refit.* Maximum-likelihood Omori–Utsu parameters from the M≥4.95 events of the
   sequence, starting when the catalog is complete at that magnitude under the time-dependent
   completeness model of @Page_2016, with the generic forecast as the fallback below 10
   events.
4. *ETAS refit.* A reimplementation of the Bayesian ETAS model in the USGS operational code
   [@van_der_Elst_2022], refitted at each issue on the as-of catalog and forecast with 10,000
   simulated catalogs. [TBD: one sentence on its validation against the published products,
   from ADR 0010 section 4.] [TBD: cite the methods source of the operational ETAS model;
   the paper cited here evaluates the public forecast.]

All four were computed and their hashes frozen before any outcome was unsealed. The RJ refit
is seldom a forecast of its own. It falls back to generic RJ where the as-of catalog holds
fewer than 10 events of M≥4.95, and it equaled generic RJ in every development cell; where
that holds, the four forecasts are three distinct ones.

### 2.7 Outcomes and scores

The outcome of a cell is whether at least one ComCat event of M≥5 occurred inside the
official circle and window, counted on one snapshot of the catalog taken after the
prospective arm ended (Section 2.9). A cell is scored once its window closed at least 21 days
before that snapshot, because M≥5 counts are still revised for weeks. For a mainshock below
M5.5, as 61 of the primary set's 89 are, such an event is about as large as the mainshock:
the target is then a doublet or foreshock probability more than an aftershock one.

The primary score is the logarithmic score [@Gneiting_2007] of the probability $p$ a
forecaster gives to that event: $S = -\log p$ if it occurred and $S = -\log(1 - p)$ if it
did not, in nats, with $p$ clipped to [0.001, 0.999]; lower is better. The probability of at
least one aftershock is the headline number of the official product, and scoring binary
events with small probabilities by a proper score is established in earthquake forecasting
[@Serafini_2022; @Brehmer_2023]. The LLM's $p$ is the probability stated in its answer, the
official forecast's is the published probability for the M≥5 bin, and each baseline's comes
from its own count distribution, so the scorer reconstructs nothing; it does clip (below).

The count of aftershocks was the primary target in an earlier draft of the protocol and is
now a secondary one. An LLM gives nine quantiles of the count, not a distribution, so a
distribution has to be built from them: I interpolate the cumulative distribution of a
continuous latent count monotonically [@Fritsch_1980] through the quantiles on a logarithmic
scale, with a power-law upper tail, and every forecaster, the official forecast included, is
reduced to the same nine quantiles and rebuilt the same way. The reconstruction is the
scorer's, so this is not a proper score of the reported quantiles alone. A review of the
design before the freeze, by an LLM agent instructed to act as a hostile referee (Section
4.1), showed what it costs on moderate sequences: in 71% of the primary test's cells all
nine M≥5 quantiles of the official forecast are zero, and the reconstruction then gives
every forecaster the same distribution, whatever it believed. Nine zero quantiles can say no
more than that the probability is at most 2.5%, and the official probability in the primary
test's cells has a median of 0.8%. The count score is still reported, because counts carry
information that the probability of at least one event discards [@Nandan_2019].

For a model and a cell, $dS = S_\mathrm{model} - S_\mathrm{official}$, so negative values
favor the model. The M≥4 and M≥3 targets are descriptive, the latter only where the catalog
is complete at M3 for the whole window, and the probability of an M≥6 event is reported with
its Brier score [@Brier_1950].

The clip decides part of the score, and I state how much. The official probability is at or
below 0.001 in 15% of the primary test's cells. In development the probability stated by the
primary model was at or below 0.001 in 49% of its answers. In those cells the scorer uses
0.001, and the models are not told that it does. Clips of 0.0001 and 0.01 are registered
sensitivity analyses, without a verdict because the margin is set for a clip of 0.001. The
primary model's development mean is +0.009, +0.017 and +0.022 nats per cell at clips of 0.01,
0.001 and 0.0001: it moves with the clip and exceeds the margin of Section 2.8 at the
smallest.

### 2.8 Hypotheses and tests

The estimand is the mean over sequences of each sequence's mean $dS$, in nats per cell. It
gives a sequence with one cell the weight of a sequence with many, and it counts the first
day after an issue in each of that issue's three nested windows. Cells of one sequence
are dependent (nested windows, successive issues sharing aftershocks), so the sequence is the
unit, and uncertainty comes from a bootstrap that resamples whole sequences (10,000
resamples, fixed seed). Sequences are resampled as independent, which some are not: by a
reviewer's count from locations and times alone, 23 of the primary set's 89 mainshocks have
another within 20 to 100 km and 30 days. A registered sensitivity analysis resamples
clusters instead (mainshocks of a model's set within 100 km and 30 days of each other, and
their neighbors' neighbors); if its verdict differs, I report the primary result as
depending on the independence of neighboring sequences.

**Primary hypothesis (A).** `gpt-5.1` is non-inferior to the official forecast on its clean
M≥5 sequences ([TBD: N; 89 expected at the freeze]): the upper bound of mean $dS$ is below
$\delta = 0.02$ nats per cell, in a one-sided non-inferiority test [@Piaggio_2012] at 0.05.
That level matches the 90% interval of equivalence testing and is looser than the one-sided
0.025 usual for non-inferiority; the power available is the reason. The bound at 0.025 is
reported beside it and changes no verdict. The result is labeled *supported*
(upper bound below $\delta$), *inferior* (lower bound above $\delta$) or *inconclusive*,
and a result whose lower bound is above 0 says so on either side of the margin: the model is
then measurably worse than the official forecast. Superiority over the official forecast
(upper bound below 0) is tested only if non-inferiority is supported, and is reported with
the generic model's and the constant control's results beside it. One primary test means
no correction for multiplicity, and no other analysis can overturn it. The kind of test, the
choice of this model as the only primary one and the level were all settled after
development results (Table S1).

**The margin.** A margin has to be fixed in advance and to mean something. Its meaning here
comes from the forecasts alone. If the official probability were the truth, a forecaster
stating half of it in every cell would lose 0.006 nats per cell on the primary test's cells,
one stating double 0.012, one stating a third 0.014, one stating three times it 0.052, one
stating a tenth 0.042, and one stating a single constant probability in every cell, sequence
and window at least 0.031. A margin of 0.02 therefore lets through a forecaster that is wrong
by a factor of two everywhere and keeps out a forecaster that knows nothing about the
sequence. It is not symmetric: it admits a threefold under-forecast and rejects a threefold
over-forecast. And it is about two thirds of the official forecast's expected advantage over
that constant, so a forecaster just inside the margin has kept about a third of that
advantage. I report how the margin was reached, because part of it happened after
development results were known: 0.02 was proposed before any model had answered the final
prompt; after a development run a margin of 0.05 was adopted for a few hours, anchored on the
deficit of the rule of thumb; a second review of the same kind showed that anchor to be an
artifact of the clip and that 0.05 would admit the constant forecaster; and 0.02 was
restored, with the primary model's development estimate (+0.017) known. It replaced a margin
of 0.10 on the count score (Table S1). Margins of 0.05 and 0.10 are registered sensitivity
analyses.

**Controls.** Four registered analyses say what a result on (A) can mean. The
*generic-model check* runs the same non-inferiority test for the generic RJ forecast on the
same cells; if generic RJ is also non-inferior, the result is reported as unable to separate
the model from a generic default. I expect that clause to apply: on development data the
generic RJ forecast's mean $dS$ is −0.009 (90% interval −0.155 to +0.014), and it is
supported in 99% of simulated studies of 89 sequences if that is its true difference and in
70% if the true difference is 0. Earlier drafts called this check assay sensitivity, which
it is not: in the trial literature that term means a trial's ability to tell an effective
treatment from an ineffective one [TBD: cite ICH E10]. Two *negative controls*
are tested exactly as a model would be and are predicted not to be supported, which an
inconclusive result also fulfills: the rule of thumb, and a constant probability of
0.041 in every cell (the share of scored development cells with an M≥5 earthquake). If
either is supported, the test could not tell forecasters apart and no claim rests on (A).
*The reference's own effect*: a non-inferiority result means something only if the reference
is itself better than a forecaster that knows nothing, and on development data that is not
shown: the constant control's mean $dS$ is +0.021 (90% interval −0.030 to +0.099). Whatever
the result of (A), I therefore report whether the lower bound of that difference is above 0;
if it is not, no claim rests on a supported (A).
The *informative-sequence* estimand repeats the primary analysis on the sequences for which
the generic RJ forecast gives at least a 10% chance of an M≥5 aftershock in the first month,
a criterion that uses no outcome and neither of the two forecasts under comparison. Of the
primary set's 89 sequences 49 qualify, and seven lie between 0.101 and 0.103, so the set is
sensitive to the threshold.

**The bound and its power.** The sequence effects are heavy-tailed: in development two of
39 sequences, each with an M≥5 aftershock that the primary model had judged unlikely,
carried its mean. A percentile bootstrap bound then claims non-inferiority too often, so the
registered bound is studentized (bootstrap-*t*) [@Efron_1994]. Its size was simulated before
the freeze in 1,000 studies of 89 sequences, drawn from development effects shifted so that
the true mean equals $\delta$. At a nominal 0.05 it is 0.034 with effects like the primary
model's, 0.047 with effects like `claude-opus-5-5`'s and 0.083, above the nominal level, with
effects like the constant control's. Its power is low: with the primary model's development
effects, (A) is supported in 4% of simulated studies if the true mean is the development
estimate (+0.017) and in 11% if it is 0. The protocol therefore states in advance that the
primary test is expected to be inconclusive, that an inconclusive result is evidence in
neither direction, and that the finding is then the estimate with its 90% interval, read
against the scale given under "The margin" above. In simulation from development effects
the most likely joint outcome is an inconclusive (A), controls that are not supported and a
non-inferior generic model; I then report the estimate with its interval, the contrast with
the rule of thumb and the descriptive results, and do not present (A) as support.

**Secondary analyses.** (B) `claude-opus-5-5` against the official forecast on its clean
retrospective M≥5 sequences (mainshocks from 1 October 2026 to *L*, from the candidate list
and the supplementary snapshot of Section 2.2) together with the prospective ones, the two
parts resampled separately; B is also reported for each part alone. (S1, S2) The same for
`claude-opus-4-6` on its clean sequences and for `gpt-6.1-sol` on the prospective items.
These three are reported as estimates with 90% intervals and no verdict. For B, at about 33
sequences, the simulated size of the bound at a nominal 0.05 is 0.14 to 0.17 (0.144 with
effects like `claude-opus-5-5`'s and 0.165 with effects like the primary model's; B was
simulated as one sample, not as its two parts), and for S1, at 23, it is 0.14, because a
sample that small can miss the rare event altogether; for S2 it was not simulated,
because that model's development sequences held no M≥5 aftershock. (S3, S4) Superiority of
each of the four tested models over the rule of thumb and over generic RJ, each test at 0.05
with no correction across models or baselines, and each model's difference from the ETAS
refit with a 95% interval. The contrast with the rule of thumb is the one analysis with
power, and its meaning is limited, because the rule of thumb states a probability of zero in
almost every cell. (S5) The prospective models against the baselines on the on-time strict
items of Section 2.9, at the same level.

Beside the mean I report the 10% trimmed mean and the median of the sequence effects with
bootstrap intervals, the influence of each sequence on the result, and a hierarchical model
with random effects for sequence and issue and fixed effects for window and time since the
mainshock. The trimmed mean and the median discount the rare sequences with a large
aftershock, which are what matters for hazard: in development the primary model's median
(−0.013) favors it and its mean (+0.017) does not. The hierarchical model is a robustness
check that estimates an unweighted mean over windows and strata, not the mean of sequence
means.

### 2.9 Prospective arm

The prospective arm started at a time *L* [TBD], when the detector was started after the
freeze; it committed that time to a public branch of the repository before its first poll and
admitted only sequences with a mainshock at or after *L*. The detector polled ComCat every
10 minutes for new OAF versions of new M≥5 events (and of the secondary M4.0–4.9 events),
applied the aftershock exclusion and the issue schedule of Section 2.3 in real time, and for
each scheduled version built two forecast items: a *matched* item on the official version's
own windows, and a *strict* item whose windows open at the next full hour at least 30 minutes
after detection. The matched item allows a comparison with the official forecast. The strict
item's windows open after detection by design; it is compared with the baselines, and the
on-time rule below is applied to it as well.

For each issue the answers of the live models (`claude-opus-5-5` and `gpt-6.1-sol`, three
answers each) were written to one record and the baseline forecasts to a second. The SHA-256
hash of each record was pushed to the public branch at once, the push time recorded by
GitHub was saved beside it, and an OpenTimestamps proof was requested for each record. A
matched item counts as *on time*, and enters test B, only if that recorded push preceded the
opening of the item's first window. Late, failed and missed
items (a scheduled version that was never forecast, for instance during an outage) are listed
with their reasons and were never forecast after the fact. On-time and late versions are
compared on covariates that use no outcome: magnitude, network or region, time since the
mainshock and official model type. The full forecasts were published after their windows
closed, with a notice that they are not official forecasts.

The on-time rule selects. With polling every 10 minutes, many first versions are detected
after their first window has opened. In a dry run of the detector from 1 to 12 November 2026
(24 issued versions on 14 sequences, 13 of the versions on secondary sequences), 11 versions
were on time: none of 3 first versions, none of 3 at one day, 2 of 3 at three days, 3 of 5 at
seven, 3 of 4 at fourteen and 3 of 6 at twenty-eight. The prospective part of test B
therefore holds few first-day cells, where the official probability is largest (Section
2.10), and I report the on-time share by slot [TBD: the study's shares].

The evidence of timeliness is the push time. The OpenTimestamps proofs show that a record
existed, not when to within the 30-minute margin. The push time was read from GitHub's
activity record by the machine that ran the detector and committed beside the seal, because
GitHub's own record may lapse. After that the claim rests on a file that I archived, bounded
from outside only by the OpenTimestamps proof, to within hours. No third-party time stamp
with finer resolution was taken.

The live models spent only a fixed monthly reserve per vendor. A group of three answers ran
only if its worst-case cost fit what was left of that vendor's reserve, in a registered
order: `claude-opus-5-5` on the matched item, then on the strict item, then `gpt-6.1-sol`.
Answers not made for that reason are listed as missed for budget. Secondary sequences
(M4.0–4.9) could use only the first half of each reserve, so that many small events could
not exhaust a month's reserve before an M≥5 sequence arrived.

Sequences stopped entering at a time *S* [TBD]: the latest origin among the first 26 eligible
M≥5 sequences, or *L* + 182 days if earlier. The rule was fixed in advance and there was no
early stopping. One snapshot of outcomes for the whole study was taken at *S* + 90 days, which
covers the last 28-day issue, a month window and the settling time, and all confirmatory
scores were computed once, on that snapshot.

Two constraints on the calendar came from the models. `gpt-5.1` is withdrawn by its vendor on
1 April 2027, and the protocol required all forecasts of the primary test to be generated by
1 March 2027 [TBD: dates of the batches]. If a live model had been withdrawn or changed, its accrual would
have stopped at the first answer reporting a different model [TBD: whether this occurred].

### 2.10 Sensitivity and descriptive analyses

All of the following were registered and are reported in one table whatever their result
[TBD: Supplemental Table]; anything else in this paper is labeled exploratory. Sequences: all
of the primary model's clean candidates including M<5 mainshocks; the three forward-excluded
events; a clean period without the three-month buffer; a clean period that starts at the
model's release date; and the mean $dS$ on a model's sequences before its release minus that
on the sequences after it, with a 90% interval (for the primary model, 62 sequences before
and 27 after). No recall probe was run on confirmatory mainshocks. Strata, from none of
which a headline claim is made: time since the mainshock (under 1 day, 1–7 days, later; the
official probability has a median of 8.4% in the first day and 0.3% after day 7); and, as
estimates without a verdict, mainshock depth (under 70 km; 70 km or more) and region (Alaska;
the Marianas region; elsewhere). Dependence: the cluster-block bootstrap of Section 2.8.
Cells: a subset of windows that do not overlap; the cells where the rebuilt catalog matches
the official event count exactly; settling of 2 days instead of 21; forecast circles of half
and 1.5 times the radius. Answers: the paraphrased prompt; valid answers only; an invalid
answer at the worst possible score; an answer invalid when anything in it is defective.
Margins and level: 0.05 and 0.10; the bound at one-sided 0.025. Scores: the probability
clipped at 0.0001 and at 0.01; its Brier score; and the
count score through nine quantiles (Section 2.7) with its own variants, namely the log-scale
quantile score registered for the first stage [@Bracher_2021; @Bosse_2023], full
distributions for the official and ETAS forecasts, a negative-binomial upper tail, and score
floors of $10^{-4}$ and $10^{-8}$ with the rate at which each binds. Only analyses on the
primary score at its registered clip carry a verdict; the others give an estimate and a
bound. Diagnostics per
forecaster: the number test of the Collaboratory for the Study of Earthquake Predictability
(CSEP) [@Zechar_2010; @Savran_2022], probability integral transform histograms for counts
[@Czado_2009], and the information gain per earthquake [@Rhoades_2011]. Registered as
descriptive, without a test: `claude-sonnet-4-6`, the retrospective `gpt-6.1-sol`, the M≥4
and M≥3 targets, behavioral probes of the models and the effect of hindsight in the catalog
on the forecasts [TBD: one sentence on each of the last two, from the D1 results and ADR
0016].

### 2.11 Use of AI tools

[Draft for the author's approval; the journal asks for this in the Methods when AI contributed
code.] The software for this study (data retrieval, catalog reconstruction, baselines, scoring
and analysis) was written with an LLM coding assistant ([TBD: tool and versions]) under my
direction, and changes to it were checked by automated tests and [TBD: the review process the
author wants to state]. The same assistant helped draft this manuscript. I am responsible for
all of its content. [TBD: N; three if the assistant is Anthropic's, two if OpenAI's] of the
five models evaluated here come from the vendor of that assistant. Freezing the protocol, the
prompts and the code, and sealing the forecasts, fixed the analysis before any confirmatory
score existed and lets others repeat the scoring from the archived answers. It does not show
that the code is correct, and it does not make the evaluation independent of the tool that
built it: the reviews of the protocol and of this paper's draft were also made by LLM agents
(Section 4.1). What I verified myself: [TBD: what the author personally checked, for example
a sample of cells scored by hand against the code].

## 3 Results

[TBD: after the registered analysis. Planned display items within the limit of 10: Table 1
(models); Figure 1 (design: timeline of cutoffs, clean periods, retrospective and prospective
arms); Figure 2 (map and magnitude–time plot of the sequences); Table 2 (primary and secondary
tests); Figure 3 (sequence effects with the bound and the margin); Figure 4 (scores against
baselines by time since the mainshock); Figure 5 (calibration: PIT and number test); Figure 6
(prospective arm: timeliness and results). The sensitivity table and the descriptive tables go
in the supplement.]

## 4 Discussion

[TBD after the results.]

### 4.1 Limitations fixed by the design

These hold whatever the results are.

- **Power.** The primary test is expected to be inconclusive. Its simulated power is 4% to
  11% with the primary model's development effects, and 39% to 45% with effects shaped like
  another model's. The size of the study is set by the archive of official forecasts, not by
  the margin. The registered finding is then the estimate with its interval.
- **What non-inferiority means.** A supported primary hypothesis says that the model's stated
  probabilities cost less than 0.02 nats per cell against the official ones on this
  population: more than the cost of stating double the official probability everywhere
  (0.012) or a third of it (0.014), and less than the cost of using one constant probability
  (0.031) or of stating three times the official probability (0.052). The margin is thus
  more lenient to under-forecasting than to over-forecasting, it gives away about two thirds
  of the official forecast's expected advantage over that constant, and its level is looser
  than the usual one-sided 0.025 (Section 2.8). On these sequences the generic model is
  expected to pass the same test, so support would show a forecaster as good as a calibrated
  generic model, not skill specific to a sequence.
- **The reference's own effect.** On development data the official forecast is not shown to
  beat one constant probability (Section 2.8). Unless the confirmatory data show it, being
  within the margin of the official forecast says nothing about skill, and I claim nothing
  from a supported result.
- **The margin's history.** The margin was fixed before the freeze and before any
  confirmatory score, but after development results. A value of 0.02 was proposed first, 0.05
  was adopted for a few hours after a development run, and 0.02 was restored when a review
  showed that 0.05 would admit a forecaster with no information. The primary model's
  development estimate (+0.017) was known when 0.02 was restored. Results at 0.05 and 0.10
  are in the sensitivity table. The kind of test, the primary model, the level, the score
  and the controls were also settled after development results; Table S1 lists each change.
- **The invalid-answer rule's history.** The rule that an answer is invalid for the primary
  score only when it gives no usable probability of an M≥5 earthquake was also chosen after
  the development run. Under the earlier rule, a defect anywhere in an answer made it invalid.
  In development that rule touched three answers of the primary model, each with quantiles
  out of order and a usable probability, and the model's mean was +0.019 nats per cell; under
  the adopted rule all three are scored and the mean is +0.017. The earlier rule is a
  registered sensitivity analysis.
- **A few sequences decide.** The result turns on the sequences with M≥5 aftershocks. In
  development two of 39 sequences carried the primary model's mean, and without them it was
  negative.
- **Small samples and rare events.** The secondary comparisons on about 33 and 23 sequences
  are reported as estimates without a verdict: there the bound's simulated size is 0.14 to
  0.17 at a nominal 0.05, and a sample that small cannot rule out a deficit that shows only
  when a rare large aftershock occurs.
- **Neighboring sequences.** The primary analysis resamples sequences as independent, and
  some are neighbors in space and time (Section 2.8); the exclusion rule can leave an
  aftershock of an event below M6 without an OAF product in the set as a mainshock. The
  cluster-block bootstrap is a sensitivity analysis and cannot overturn the primary result.
- **The controls.** The rule of thumb states a probability of zero in 96% of the primary
  test's cells, so its score is set by the clip and its predicted result can hardly not
  happen: in simulation it is never supported at this margin, inferior in about 63% of
  studies and inconclusive in about 37%, the label the primary model is also expected to
  get. The constant-probability control is supported in about 8% of simulated studies.
- **Population.** The sequences are those for which USGS published a forecast between November
  2024 and the end of the study, less the ones used for development, and the largest recent
  sequences were all used for development. In the primary set as it stood at the freeze, no
  mainshock is M6.5 or larger and 61 of 89 are below M5.5; 36 are in Alaska, 35 in the
  Marianas region (place names with Guam, Mariana or Micronesia) and 18 elsewhere, 6 of them
  in or off Oregon; 20 are at 70 km or deeper (35 at 35 km or deeper, the deepest at 247 km);
  72 were located by the global network (`us`) and 19 have a body-wave magnitude (mb); the
  official forecast is a Reasenberg–Jones product at 463 of 472 issue times and the generic
  one at the first issue of 76 sequences; and the official forecast itself expects only
  about 11 of the 89 sequences to have any M≥5 aftershock in the first month. For the 61
  mainshocks below M5.5 the target is an event about as large as the mainshock, a doublet or
  foreshock more than an aftershock. The primary test therefore speaks to automatic
  forecasts for moderate mainshocks with mostly empty windows, 71 of the 89 in two regions,
  not to the large sequences for which an aftershock forecast matters most. Results by depth
  and by region are registered as estimates without a verdict (Section 2.10). Results need
  not carry over to other regions, other catalogs or mainshocks without an operational
  forecast. [TBD: these counts use no outcome; recompute them if the design changes before
  the freeze.]
- **Contamination.** In the retrospective arm, cleanliness rests on the cutoffs that the
  vendors document (for the primary model a "knowledge cutoff") and a three-month buffer,
  and a model's effective cutoff can differ from the documented one [@Cheng_2024]. No recall
  probe was run on the confirmatory mainshocks. Of the primary model's 89 sequences, 62
  predate its public release, and only those can have been in material published before the
  model existed. The difference between the two groups is reported with its 90% interval,
  and the analysis restricted to the 27 after the release is in the sensitivity table, at a
  sample size where the bound's size is not controlled (compare 0.14 to 0.17 at 23 and 33
  sequences). Contamination would favor the model, the direction that a non-inferiority
  test rewards. Only the prospective arm excludes contamination by construction.
- **Late detection.** The on-time rule removes most early versions from the prospective
  comparison with the official forecast (Section 2.9), so the prospective part of test B
  holds few first-day cells, where the official probability is largest. The evidence of
  timeliness is a push time that my own machine read from GitHub and archived; no third
  party stamps it more finely than hours.
- **What the pre-registration covers.** The outcomes of the retrospective arm existed, and
  were public, when the protocol was frozen. For that arm the pre-registration is an analysis
  plan fixed before any confirmatory score was computed, backed by a software lock and a list
  of prior exposures; it is not proof that no outcome could have been seen. The prospective
  arm is blind by construction.
- **Different sequences for different models.** Each model is tested on its own clean period,
  so the models are compared with the official forecast, not with each other.
- **One prompt, one answer.** The result describes a single answer to a fixed prompt without
  tools. It bounds neither what a model could do with tools, fine-tuning or a better prompt,
  nor what a user would get with a different question.
- **Counts in a circle.** The targets are numbers of events in the official circle. The study
  does not test spatial forecasts or magnitudes beyond the thresholds. Almost all circles in
  the primary set have a radius of 10 km, which is also the median [TBD: the share of
  circles at exactly 10 km and the largest radius, from the frozen forecast tables], the
  order of the location uncertainty of events located teleseismically, and M5.0 is a
  threshold across mixed magnitude types, so whether an
  aftershock counts can turn on a small difference in location or magnitude. Every forecaster
  is scored on the same outcome, so this adds noise, which the radius analyses bound.
- **The clip.** Probabilities are clipped to [0.001, 0.999] before scoring. That replaces the
  official probability in 15% of the primary test's cells and replaced the primary model's
  stated probability in 49% of its development answers. The models are not told of the
  clip, and the primary model's development mean lies on either side of the margin
  according to it (Section 2.7). Clips of 0.0001 and 0.01 are in the sensitivity table.
- **Two forecasts in one answer.** An answer holds a probability of at least one M≥5 event
  and nine quantiles of the same count, and the two can disagree: in development the stated
  probability lay outside the range its own quantiles allow, at some magnitude, in 17% of the
  primary model's answers and in 85% of two other models'. The primary score reads the
  probability and the secondary score the quantiles.
- **Wording.** Adding the probabilities to the prompt changed the count forecasts of one of
  the four models run with both prompts in development by 0.14 nats per cell and left the
  other three unchanged. The
  paraphrase check runs for two models only.
- **Review of the protocol.** No outside review of the protocol took place before the freeze.
  Two reviews of the protocol and one of a draft of this paper, by LLM agents instructed to
  act as hostile referees, were made and are in the repository; they are not independent of
  the project.
- **The catalog as it stood.** The rebuilt catalog matches the official event counts in 99% of
  checks, not all; deleted events are missing, and event identities are those of today's
  catalog. USGS analysts may also have had information that never reached ComCat. The prompt
  lists events from M3 and does not say where the catalog is complete, so for 86 of the
  primary set's 89 sequences a model may read missing small events as quiet (Section 2.4).
- **Selection by the future.** Three events were excluded by a rule that looks forward in
  time. For sequences added after the candidate list was built, only the backward-looking half
  of the rule applies, so a sequence later followed by a larger event nearby stays in.
- **Reproducibility of the models.** The primary model is withdrawn by its vendor in April
  2027. Its answers are archived, but they cannot be regenerated. Only the primary model's
  identifier carries a date. For the others the model name returned with each answer was
  logged: it shows a redirect to another model, not a silent update under the same name. Reasoning settings differ between models.
- **One host.** The prospective arm ran on a single machine. Forecasts missed during outages
  are listed and were not backfilled, and when a monthly budget reserve was exhausted the
  second live model was dropped first, so its missing forecasts cluster in busy months [TBD: the count and the comparison of missed with issued
  versions].

## 5 Conclusions

[TBD after the results.]

## Data and code availability

[TBD at submission: Zenodo DOI of the archived repository snapshot (code, frozen protocol,
prompts, forecast items, sealed records and their time stamps, model answers, scores) beside
the repository URL and the tagged version; license. Earthquake data are from the USGS ComCat
and its OAF products, retrieved through the public FDSN event service; the data manifest lists
every file with its hash. The journal does not accept GitHub alone.]

## Author contributions

[TBD: CRediT roles.]

## Competing interests

[TBD: the author's statement, including any vendor credits or funding.]

## Acknowledgments

[TBD.]

## References
