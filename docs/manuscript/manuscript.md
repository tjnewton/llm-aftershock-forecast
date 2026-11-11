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

The mock review's design findings are with the author (primary score, margin, negative control,
invalid-answer rule). Sections 2.5 to 2.8 and 4.1 follow whatever he decides.
-->

## Abstract

[TBD: at most 200 words, no references; written after the registered analysis.]

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
[@Ogata_1988], and USGS now uses it for many of its public forecasts [@van_der_Elst_2022].
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
months after the end of its training data, and a prospective arm forecasts new sequences in
real time, with every forecast sealed and time-stamped before its window opens (Section 2.9).
Every forecaster sees the catalog as it stood when the official forecast was issued, rebuilt
from the catalog's own version history (Section 2.4). The unit of analysis is the sequence,
and the primary test is a single one-sided test with a stated margin (Section 2.8).

The primary hypothesis is that the forecasts of one LLM, queried once with a fixed prompt and
no tools, are non-inferior to the USGS operational forecast: that their mean logarithmic
score for the number of M≥5 aftershocks is worse by less than 0.10 nats per forecast, on the
sequences that follow the model's training cutoff. Non-inferiority within a margin is a weaker
claim than equivalence in skill, and the design says so in two ways. The same test is run for
the generic RJ forecast, which uses nothing about a sequence but its mainshock; if that
forecast also passes, the test cannot tell a forecaster with sequence-specific skill from a
generic default, and I claim none. And the comparisons with simple baselines (a rule of thumb,
generic RJ, an ETAS refit) are reported beside it.

These are probabilistic forecasts of aftershock counts in a stated region and time window.
Nothing in this paper predicts individual earthquakes, and the forecasts published by the
prospective arm are not official forecasts.

## 2 Data and methods

### 2.1 Pre-registration and data splits

The study has two stages. A first analysis of 11 sequences was registered and reported in
October 2026 [TBD: cite the archived write-up]. Those sequences, 39 more that I scored while
developing the methods, and the sequences whose outcomes were used in adaptation experiments
are *development* data: I scored them freely, and every design choice below was made on them.
Every other sequence is *confirmatory*. Outcome exposure, not input exposure, makes a sequence
development data: a sequence whose catalog had appeared in a prompt but whose outcomes I had
not seen stayed confirmatory.

The protocol for the confirmatory stage was frozen as a pre-registration at the commit tagged
`prereg-v2` [TBD: commit hash, date and the public record of its SHA-256]. The frozen material
is the protocol, the prompt templates, the package versions, the analysis code, the candidate
sequences with their forecast items, the data manifest, and the baseline forecasts, which were
computed before any outcome was unsealed. Before the freeze, the work on confirmatory
sequences was limited to steps that use no outcome: fetching data, rebuilding catalogs,
building prompts and computing baseline forecasts. The code enforces the split. Outcome counts
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
subsurface rupture lengths [@Wells_1994] (at least 10 km) of a larger event. That leaves 195
candidates. The foreshock half of this rule uses information from after the event, since a
later, larger earthquake can fall inside the event's own forecast windows; three events were
excluded for that reason alone. The candidate list was kept as built, the three are added back
in a sensitivity analysis, and prospective sequences are subject only to the backward-looking
(aftershock) half of the rule.

The primary set for each model is the candidates with a mainshock of M≥5 in that model's clean
period (Section 2.5). A secondary set holds M4.0–4.9 mainshocks located by United States
regional networks. Magnitudes are those of the frozen data snapshot, or those at first
detection in the prospective arm. A sequence without a valid official forecast or without a
scorable forecast cell drops out; that attrition is reported.

### 2.3 Official forecasts, issue times and cells

Each OAF product version gives, for a circle around the mainshock and for windows of a day, a
week, a month and a year, the distribution of the number of aftershocks at or above M3, 4, 5,
6 and 7. I used the day, week and month windows. A version was rejected if it was filed under
the wrong event: created before the mainshock, centered too far from the epicenter, or stating
a mainshock magnitude that differs from the catalog's.

USGS updates a forecast many times in the year after a mainshock. From each sequence I took
the first valid version and, for each target time *t* of 1, 3, 7, 14 and 28 days after the
mainshock, the earliest valid version whose information cutoff falls in
[*t*, *t* + max(1 day, *t*/4)). The information cutoff of a version is the earlier of its
creation time and the start of its windows, because in many versions the windows start before
the forecast was created. An *issue* is one such version, and a *cell* is one issue, one
window and one magnitude target. Every forecaster's forecast for a cell refers to the same
circle and the same half-open window [start, end) as the official one.

### 2.4 Information available to the forecasters

Every forecaster is given what the official forecast had: the mainshock and the catalog of
events in the forecast circle with origin time before the information cutoff. In the
retrospective arm that catalog is rebuilt as it stood at the cutoff. ComCat keeps every
version of every origin with the time at which it was indexed; for each event I kept the
versions indexed by the cutoff and took the preferred origin among them. As a check, each
official ETAS and RJ product records how many events above several magnitudes it had fetched.
On 194 of the 195 candidates the rebuilt catalog reproduces those counts exactly in 99.05%
of 23,264 checks, against 96.85% for the catalog as it stands today. The check compares
catalogs and uses no forecast-window outcome. Events that existed at the time and were later
deleted cannot be rebuilt. In the prospective arm the catalog is simply the one fetched when
the official version is detected.

### 2.5 Language models, prompt and answers

[TBD: Table 1. Models: identifier, documented training-data cutoff, first clean date,
settings, role. Content: prereg section 3.]

Five models from two vendors were run (Table 1). A sequence is *clean* for a model when its
mainshock occurred at least three months after the end of the month of the model's documented
training-data cutoff. The primary model, `gpt-5.1-2025-11-13` (OpenAI; cutoff 30 September
2024, clean from 1 January 2025), is clean on almost the whole OAF archive. `claude-opus-5-5`
(Anthropic; cutoff June 2026, clean from 1 October 2026) is the model of the prospective arm,
with `gpt-6.1-sol` (OpenAI; cutoff 30 April 2026). `claude-opus-4-6` and `claude-sonnet-4-6`
(Anthropic) have intermediate cutoffs. Reasoning settings were fixed on development items before the freeze
(Table 1) by pilots; for `gpt-5.1` and `claude-sonnet-4-6` a higher setting used up the
pilot's output limit before giving an answer.

The unit of the study is a single answer to a fixed prompt, as a person would get from a
chatbot. All requests were made without sampling parameters, tools, prefilled answers or
server-side fallbacks, to the vendors' own endpoints, with a JSON schema for the answer. The
model identifier returned with each answer was logged; in the retrospective runs an answer
from a model other than the one requested was invalid.

The prompt states the mainshock, the forecast circle, the issue time and the windows, and
lists the catalog of M≥3 events in the circle from 7 days before the mainshock to the
information cutoff (at most 800 events, with daily counts beyond that). It asks, for each
window, for nine quantiles (2.5, 5, 10, 25, 50, 75, 90, 95 and 97.5%) of the number of
earthquakes of M≥5, M≥4 and M≥3, and for the probability of at least one M≥6 event. The system
prompt tells the model that its quantiles will be scored with a proper scoring rule, that it
has no tools, and that nothing after the issue time is known. The wording was fixed on
development items; a paraphrase of it is run as a robustness check. Each item was sent three
times, and a model's score in a cell is the mean over its three answers.

An answer is invalid if it breaks the schema, is cut off at the output limit (32,000 tokens),
is a refusal, or contains quantiles that decrease or values out of range. An invalid answer is
not dropped: it receives the worst score in its cell among five reference forecasts (the
official forecast and the four baselines of Section 2.6). Invalid rates are reported per
model and arm. Only a failure to deliver any answer counts as a transport error; those were
retried up to ten times and then listed.

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
   from ADR 0010 section 4.]

All four were computed and their hashes frozen before any outcome was unsealed.

### 2.7 Outcomes and scores

The outcome of a cell is the number of ComCat events at or above the target magnitude inside
the official circle and window, counted on one snapshot of the catalog taken after the
prospective arm ended (Section 2.9). A cell is scored once its window closed at least 21 days
before that snapshot, because M≥5 counts are still revised for weeks.

The primary score is the logarithmic score [@Gneiting_2007] of the observed count *y*,
$S = -\log p(y)$ in nats, with $p(y)$ floored at $10^{-6}$; lower is better. An LLM gives nine
quantiles, not a distribution, so a distribution has to be built from them: I interpolate the
cumulative distribution of a continuous latent count monotonically [@Fritsch_1980] through the
quantiles on a logarithmic scale, with a power-law upper tail set by the last segment, and
read off the probability of each integer. On development data the score of a forecast depends
on how it is represented by about as much as forecasters differ from each other where counts
are large. So in the primary comparison every forecaster, the official forecast included, is
reduced to the same nine quantiles and rebuilt the same way. Scoring the official and ETAS
forecasts from their full distributions is a sensitivity analysis.

For a model and a cell, $dS = S_\mathrm{model} - S_\mathrm{official}$, so negative values
favor the model. The primary target is M≥5. The M≥4 and M≥3 targets are descriptive, the
latter only where the catalog is complete at M3 for the whole window, and the probability of
an M≥6 event is reported with its Brier score [@Brier_1950].

### 2.8 Hypotheses and tests

The estimand is the mean over sequences of each sequence's mean $dS$ at M≥5. Cells of one
sequence are dependent (nested windows, successive issues sharing aftershocks), so the
sequence is the unit, and uncertainty comes from a bootstrap that resamples whole sequences
(10,000 resamples, fixed seed).

**Primary hypothesis (A).** `gpt-5.1` is non-inferior to the official forecast on its clean
M≥5 sequences ([TBD: N; 89 expected at the freeze]): the upper bound of mean $dS$ is below
$\delta = 0.10$ nats per cell, in a one-sided test at 0.05. Each tested hypothesis is labeled
*supported* (upper bound below $\delta$), *inferior* (lower bound above $\delta$) or
*inconclusive*. Superiority over the official forecast (upper bound below 0) is tested only if
non-inferiority is supported. One primary test means no correction for multiplicity; every
other test is labeled secondary, and none can overturn the primary result.

**The margin.** A margin has to be fixed in advance and to mean something. On development
data, doubling the expected count of the official forecast costs 0.063 nats per cell on 39
mostly moderate sequences and 0.300 on six large ones, and the generic RJ forecast differs
from the official one by −0.013 and +0.184 on the same sets. A margin of 0.10 nats is therefore
strict for large, productive sequences and generous for small ones, where most cells have a
count of zero and carry little information. Two registered analyses address this. The
*assay-sensitivity* test [@Piaggio_2012] runs the same non-inferiority test for the generic RJ
forecast on the same cells; if generic RJ also passes, the result is reported as unable to
separate the model from a generic default. The *informative-sequence* estimand repeats the
primary analysis on the sequences whose first official forecast expects at least 0.5 M≥5
aftershocks in the month, a criterion that uses no outcome.

**The bound.** The sequence effects are heavy-tailed: in development one sequence in 18 held
a rare large aftershock that a model had judged very unlikely. A percentile bootstrap bound
then claims non-inferiority too often, so the registered bound is studentized (bootstrap-*t*)
[@Efron_1994]. Its size was simulated before the freeze from development effects shifted so
that the true mean equals $\delta$: 0.018 to 0.029 at a nominal 0.05 with 89 sequences. Its
power, taking the development estimate as the truth, is 0.45. An inconclusive result is
therefore a likely outcome even if the model is in truth non-inferior, and it would not be
evidence of inferiority.

**Secondary hypotheses.** (B) `claude-opus-5-5` is non-inferior to the official forecast on
its clean retrospective M≥5 sequences together with the prospective ones, the two parts
resampled separately; with about 33 sequences the simulated size of this test is 0.14 at a
nominal 0.05, because a sample that small can miss the rare event altogether, and the test is
reported with that size. (S1, S2) The same test for `claude-opus-4-6` on its clean sequences
and for `gpt-6.1-sol` on the prospective items. (S3, S4) Superiority of each model over the
rule of thumb and over generic RJ, and its difference from the ETAS refit with a 95% interval.
(S5) The prospective models against the baselines on the strict items of Section 2.9.

Beside the mean I report the 10% trimmed mean and the median of the sequence effects, the
influence of each sequence on the result, and a hierarchical model with random effects for
sequence and issue.

### 2.9 Prospective arm

The prospective arm started at a time *L* [TBD], when the detector was started after the
freeze; it committed that time to a public branch of the repository before its first poll and
admitted only sequences with a mainshock at or after *L*. The detector polled ComCat every
10 minutes for new OAF versions of new M≥5 events (and of the secondary M4.0–4.9 events),
applied the aftershock exclusion and the issue schedule of Section 2.3 in real time, and for
each scheduled version built two forecast items: a *matched* item on the official version's
own windows, and a *strict* item whose windows open at the next full hour at least 30 minutes
after detection. The matched item allows a comparison with the official forecast; the strict
item guarantees that every forecast precedes its window, and is compared with the baselines.

For each issue the answers of the live models (`claude-opus-5-5` and `gpt-6.1-sol`, three
answers each) were written to one record and the baseline forecasts to a second. The SHA-256
hash of each record was pushed to the public branch at once, the push time recorded by
GitHub was saved beside it, and an OpenTimestamps proof was requested for each record. A matched item counts as *on time*, and enters test B, only if
that recorded push preceded the opening of the item's first window. Late, failed and missed
items (a scheduled version that was never forecast, for instance during an outage) are listed
with their reasons and were never forecast after the fact. On-time and late versions are
compared on covariates that use no outcome. The full forecasts were published after their
windows closed, with a notice that they are not official forecasts.

Sequences stopped entering at a time *S* [TBD]: the latest origin among the first 26 eligible
M≥5 sequences, or *L* + 182 days if earlier. The rule was fixed in advance and there was no
early stopping. One snapshot of outcomes for the whole study was taken at *S* + 90 days, which
covers the last 28-day issue, a month window and the settling time, and all confirmatory
scores were computed once, on that snapshot.

Two constraints on the calendar came from the models. `gpt-5.1` is withdrawn by its vendor on
1 April 2027, so all forecasts of the primary test were generated before then
[TBD: dates of the batches]. If a live model had been withdrawn or changed, its accrual would
have stopped at the first answer reporting a different model [TBD: whether this occurred].

### 2.10 Sensitivity and descriptive analyses

All of the following were registered and are reported in one table whatever their result
[TBD: Supplemental Table]; anything else in this paper is labeled exploratory. Sequences: all
of the primary model's clean candidates including M<5 mainshocks; the three forward-excluded
events; a clean period without the three-month buffer; a clean period that starts at the
model's release date. Cells: one window per issue (no overlap); the cells where the rebuilt
catalog matches the official event count exactly; settling of 2 days instead of 21; forecast
circles of half and 1.5 times the radius; results by time since the mainshock (under 1 day,
1–7 days, later). Answers: the paraphrased prompt; valid answers only. Scores: the
log-scale quantile score registered for the first stage [@Bracher_2021; @Bosse_2023]; full
distributions for the official and ETAS forecasts; a negative-binomial upper tail; score
floors of $10^{-4}$ and $10^{-8}$ with the rate at which each binds. Diagnostics per
forecaster: the number test of the Collaboratory for the Study of Earthquake Predictability
(CSEP) [@Zechar_2010; @Savran_2022], probability integral transform histograms for counts
[@Czado_2009], and the information gain per earthquake [@Rhoades_2011].

### 2.11 Use of AI tools

[Draft for the author's approval; the journal asks for this in the Methods when AI contributed
code.] The software for this study (data retrieval, catalog reconstruction, baselines, scoring
and analysis) was written with an LLM coding assistant ([TBD: tool and versions]) under my
direction, and changes to it were checked by automated tests and [TBD: the review process the
author wants to state]. The same assistant helped draft this manuscript. I am responsible for
all of its content. Two of the five models evaluated here come from the vendor of that
assistant; the frozen protocol, the fixed prompts and the sealed forecasts are what keep the
evaluation independent of the tool used to build it.

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

- **Power.** The primary test has an estimated power of 0.45. The study can support
  non-inferiority or inferiority, and it may do neither.
- **What non-inferiority means.** The margin is generous for moderate sequences, where most
  forecasts are for zero events. A supported primary hypothesis says that the model's forecasts
  cost less than 0.10 nats per forecast against the official ones on this population; whether
  that reflects skill specific to a sequence is what the assay-sensitivity test and the
  baseline comparisons show.
- **Small samples and rare events.** The secondary tests on about 33 and 23 sequences do not
  control their error rate at the nominal level and cannot rule out a deficit that shows only
  when a rare large aftershock occurs.
- **Population.** The sequences are those for which USGS published a forecast between November
  2024 and the end of the study, less the ones used for development, and the largest recent
  sequences were all used for development. In the primary set as it stood at the freeze, no
  mainshock is M6.5 or larger and 61 of 89 are below M5.5; the official forecast is a
  Reasenberg–Jones product at 463 of 472 issue times and the generic one at the first issue of
  76 sequences; and the official forecast itself expects only about 11 of the 89 sequences to
  have any M≥5 aftershock in the first month. The primary test therefore speaks to automatic
  forecasts for moderate mainshocks with mostly empty windows, not to the large sequences for
  which an aftershock forecast matters most. Results need not carry over to other regions,
  other catalogs or mainshocks without an operational forecast. [TBD: these counts use no
  outcome; recompute them if the design changes before the freeze.]
- **Contamination.** In the retrospective arm, cleanliness rests on the vendors' documented
  training cutoffs and a three-month buffer, and a model's effective cutoff can differ from
  the documented one [@Cheng_2024]. Of the primary model's 89 sequences, 62 predate its public
  release; the analysis restricted to the 27 after it is in the sensitivity table. Only the
  prospective arm excludes contamination by construction.
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
  does not test spatial forecasts or magnitudes beyond the thresholds. The median circle in
  the primary set has a radius of 10 km, the order of the location uncertainty of events
  located teleseismically, and M5.0 is a threshold across mixed magnitude types, so whether an
  aftershock counts can turn on a small difference in location or magnitude. Every forecaster
  is scored on the same outcome, so this adds noise, which the radius analyses bound.
- **Representation.** Scoring every forecaster through nine quantiles discards part of the
  official forecast's distribution; the full-distribution scores are in the sensitivity table.
- **The catalog as it stood.** The rebuilt catalog matches the official event counts in 99% of
  checks, not all; deleted events are missing, and event identities are those of today's
  catalog. USGS analysts may also have had information that never reached ComCat.
- **Selection by the future.** Three events were excluded by a rule that looks forward in
  time. For sequences added after the candidate list was built, only the backward-looking half
  of the rule applies, so a sequence later followed by a larger event nearby stays in.
- **Reproducibility of the models.** The primary model is withdrawn by its vendor in April
  2027. Its answers are archived, but they cannot be regenerated. Two models are served under
  undated identifiers: the model name logged with each answer shows a redirect to another
  model, not a silent update. Reasoning settings differ between models.
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
