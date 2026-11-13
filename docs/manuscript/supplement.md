# Supplement to "Can general-purpose language models forecast aftershocks?"

<!-- Draft. Section and table numbers are cited from docs/manuscript/manuscript.md. The
sensitivity, secondary and descriptive tables of the registered analysis join this file
after the analysis. -->

## S1 Prior exposure to confirmatory data before the freeze

Before the freeze, no confirmatory forecast was scored. The work on confirmatory sequences
was fetching data, rebuilding catalogs, building prompts and computing baseline forecasts,
with the six exceptions below, which the protocol lists as prior exposure.

1. The catalog check of Section 2.4 compared official observation counts across product
   versions, and a later version's count holds part of the outcome of an earlier window.
2. A dry run of the prospective detector tracked new official versions of some October 2026
   candidates; only its timing logs were read.
3. Two paid end-to-end checks of the prospective pipeline, on 2 and 12 November 2026, each
   produced 12 answers from the two live models for a dry-run version of one candidate: the
   first a candidate of test B's retrospective part, the second one of the primary test's set
   as well. Neither version is in the frozen data, and the answers were checked for form and
   never scored.
4. Of the foreshock and aftershock exclusions I viewed aggregate counts and, on 1 November
   2026, the identities of the three events excluded by the forward-looking half of the rule
   (Section 2.2): I know that a larger event followed each within a year, inside its circle,
   and nothing else about their outcomes.
5. The revision of the protocol on 11 November 2026 used counts on the candidates' forecast and
   sequence tables that involve no catalog, observed count or score: the distribution of the
   official probabilities and quantiles, the baselines' probabilities, the expected loss of
   simple forecasters if the official probability were the truth, the official model type by
   issue time, the median circle radius and how many mainshocks precede the primary model's
   release. These counts set the choice of the primary score, the meaning of the margin and the
   informative-sequence threshold, and are quoted where they are used.
6. On 12 November 2026 a review of a draft of this paper, and my check of it, counted on the
   same tables the primary test's sequences by region, depth, network, magnitude type and
   completeness magnitude, the spread of the circle radii and of the first version's delay, and
   how many of its mainshocks have another within 20 to 100 km and 30 days. The reviewer's
   script loaded a table that also carries the official products' observation counts and
   reports that those columns were neither printed nor used.

## S2 Design decisions made after a development result

**Table S1.** Design decisions made after a development result, in order; all dates are in
2026. No confirmatory outcome was used for any of them (Section 2.1 lists what was seen of
the confirmatory data). Estimates are the primary model's mean $dS$ in development, in nats
per cell. Power is the share of simulated studies in which the primary hypothesis (A) is
supported.

| Date | Decision | Known at the time | Effect on the development estimate or power |
|---|------|------|-----|
| 30 Oct to 1 Nov | Reasoning settings (Table 1): the highest that answered reliably in a pilot. | Three pilot calls per setting on development items: validity, output tokens and cost. `gpt-5.1` at `high` was cut off in 3 of 3 at a limit of 16,000 output tokens, half the study's, and runs at `medium`. | Not measured. |
| 31 Oct | One-sided non-inferiority instead of two-sided equivalence. | The primary model's first development run (18 sequences, count score): at M≥4 it beat the official forecast by 0.062 nats per cell, which fails a two-sided test. | A model better than the official forecast no longer fails. |
| 31 Oct | A margin of 0.10 on the count score. | The same run. A factor-of-two error in the expected count cost 0.063 nats per cell on 39 development sequences and 0.30 on the registered ones. | Power for (A) at a level of 0.025, by a normal approximation: 0.12 at a margin of 0.05, 0.62 at 0.10, 0.95 at 0.15. |
| 31 Oct | The mean of sequence effects stays the estimand. | The same run: mean +0.042 per sequence, 10% trimmed mean −0.014. | The trimmed mean, which favored the model, is reported beside the mean. |
| 31 Oct | The bootstrap-*t* bound instead of the percentile bound. | A simulation from the same effects (one sequence in 18 at +1 nat), at a nominal 0.025: the percentile bound erred 0.15 of the time at 33 sequences and 0.05 at 88; the bootstrap-*t*, 0.15 and 0.02. | Power for (A) at 0.05: 0.42. |
| 31 Oct | Test (A) alone is primary, at one-sided 0.05. Test B, until then co-primary under a Holm correction (first step at 0.025) and described as the paper's thesis, becomes secondary. | The development effects of both models, and the size simulation: 0.14 at 33 sequences for any test. | Power 0.42 for (A) and 0.64 for B; a first 0.45 for (A) came from a run that no command recorded. |
| 11 Nov | Primary score: the stated probability, not the count through nine quantiles. The final prompt adds the probabilities. | A review of the design, and counts that use no outcome: all nine official quantiles are zero in 71% of cells. The development rerun (39 sequences) preceded the decision. | +0.017 on the new score. On the count score the new prompt moved three models by at most 0.005 and `claude-sonnet-4-6` by 0.14. |
| 11 Nov | Margin: 0.02 proposed, 0.05 adopted, 0.02 restored the same day. | The proposal came before any answer to the final prompt [TBD: whether the proposal made 0.02 conditional on the rerun; the protocol does not record its wording]. The other two steps came after the rerun, with +0.017 known. | (A) is supported in 23% to 55% of simulated studies at 0.05 and in 4% to 11% at 0.02 (95% to 99% at 0.10). Under the count score and a margin of 0.10 the power had been 0.42. |
| 11 Nov | Invalid answers: a fixed $\log 2$ instead of the worst baseline score in the cell; then, in the same sitting as the margin's restoration, invalid only without a usable M≥5 probability. | Under the first rule a forecaster that never answers scored +0.0975 in development. The rerun's three invalid answers, all the primary model's, each held a usable probability. | +0.019 to +0.017, against a margin of 0.02. |
| 11 Nov | Negative controls: `claude-sonnet-4-6` dropped; the rule of thumb, then a constant 0.041. | With the final prompt the first control's development result was no longer worse than the official forecast. The rule of thumb can hardly be supported. The constant is the development base rate (22 of 536 cells) and scores +0.021 (−0.030 to +0.099). | None on (A). The constant is supported in 8% of simulated studies. |
| 11 Nov | Informative sequences: selected by the generic RJ probability (at least 0.10), not by the official mean count (at least 0.5). | Counts that use no outcome: the earlier rule kept 5 of 89 sequences; the new one keeps 49. | None on (A). |
| 11 Nov | B, S1 and S2 are reported without a verdict. | Simulated sizes of 0.14 to 0.17 at 23 and 33 sequences. | None. |
| 12 Nov | After a review of this paper's draft the primary test stays. Added: the report on the reference's own effect, the bound at 0.025, the depth and region strata, the cluster-block bootstrap and the release contrast. | The development results above, and counts on mainshock metadata. | None. |
