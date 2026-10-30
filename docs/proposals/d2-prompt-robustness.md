# Proposal: prompt and effort robustness study (D2)

Status: **approved by Tyler (2026-10-30) and run; results below.** It covers the prompt wording (a science decision)
and a paid batch on development items. No prompt file changes until it is approved. After
approval the changes go through a pull request with `frozen-override` (`prompts/` is frozen)
and a `docs/deviations.md` entry.

## Why
The registered study used one prompt (two paraphrases) and one effort level. A referee will ask
whether the results depend on wording, catalog presentation or effort. ADR 0015 also adds M>=3
targets, so the forecasters must be asked for M3 quantiles. D2 settles these on development
items, and prereg v2 then freezes 2-3 variants.

## Changes common to every variant
1. **Ask for M3 quantiles.** Task text adds: "the same nine quantiles for magnitude 3.0 or
   larger". `schema_direct.json` adds `m3_count_quantiles` (same nine fields). The validator
   adds an `incoherent_magnitudes` check (M3 >= M4 >= M5).
2. **Catalog shown from M3.0** (was M4.0), so the forecaster sees the same events it is asked
   to forecast. The existing 800-row cap with the daily-count table stays.
   - Effect on prompt length: median rows rise. Large sequences (Kamchatka) hit the cap
     earlier and get the daily-count table.

## Variants
| Variant | Wording | Catalog presentation |
|---|---|---|
| A | current `p1` wording + M3 | event list (as now) |
| B | current `p2` paraphrase + M3 | event list |
| C | `p1` wording + M3 | **summary**: daily counts at M3/M4/M5/M6 since the mainshock and the 20 largest events (no full list) |

Effort: every variant at `high` (registered setting). Sonnet 5.5 also runs variant A at
`medium` to measure effort sensitivity.

C tests whether the answer depends on how the catalog is presented. It is information-poorer
(no individual small events), which is the point: a robust forecaster should not move much.

## Design and cost (development items only)
- **Items:** E3 post-cutoff, 99 items in 18 sequences. Direct arm, I1.
- **Calls:** k = 3 samples per item and variant; Claude Opus 5.5 and Sonnet 5.5 for all three
  variants, plus Sonnet at medium on A; Haiku 5.5 optional.
- **Cost estimate:**
  - Basis: mean tokens of the E3 runs (input 1,847; output Opus 1,123, Sonnet 947), batch
    price, plus 15% for the extra M3 field.
  - Per model: Opus 891 calls, about $15.3; Sonnet 891 + 297 calls, about $8.9; Haiku 891
    calls, about $0.9.
  - **Total about $25**. October so far: $64.32 of $200.
- **Analysis** (exploratory, development data):
  - Per variant: representation-matched log score vs official, and the between-variant spread
    per cell (SD across variants) compared with the between-sample spread within a variant.
  - Invalid-answer rates.
  - Coherence: M3 >= M4 >= M5, and the M3:M4 ratio against b-value scaling (about 10 per unit).

## Decisions requested
1. Add M3 quantiles to the direct arm, and show the catalog from M3.0. (Recommended: yes.)
2. Variants A, B and C as above. (Recommended: yes. An alternative to C is a plain-language
   framing, but the plan keeps naturalistic queries to an appendix.)
3. Approve the paid D2 batch: about $25 (Opus + Sonnet + Haiku, E3 post items).

## Results (2026-10-30, development data; `laf d2`, results/d2_*_20261021T2300Z.csv)
Runs: 2,970 requests, all succeeded; cost $25.24. Items: E3 post-cutoff (99 items, 203 primary
cells with an official forecast). dLS = representation-matched log score (ADR 0015) minus the
official forecast's, mean over samples and cells; negative is better than official.

| Model, effort | Variant | Invalid | dLS M>=5 | dLS M>=4 |
|---|---|---|---|---|
| Opus 5.5, high | A / B / C | 0 / 0 / 0 | +0.003 / +0.000 / +0.009 | -0.038 / -0.047 / -0.032 |
| Sonnet 5.5, high | A / B / C | 0 / 0 / 0 | +0.011 / +0.026 / +0.045 | +0.062 / +0.092 / +0.113 |
| Sonnet 5.5, medium | A | 0 | +0.068 | +0.376 |
| Haiku 5.5, high | A / B / C | 2.5% / 0 / 1.8% | +0.015 / +0.027 / +0.029 | +0.088 / +0.136 / +0.141 |

Robustness (M>=5, cells where every variant answered validly):

| Model | Between-variant SD per cell | Within-variant (sample) SD |
|---|---|---|
| Opus 5.5 | 0.013 | 0.018 |
| Sonnet 5.5 | 0.033 | 0.031 |
| Haiku 5.5 | 0.021 | 0.028 |

**Reading.**
- Wording (A against B) and catalog presentation (C) move answers no more than resampling the
  same prompt does. The summary catalog (C) costs Sonnet the most: +0.045 against +0.011 for
  A at M>=5.
- Opus 5.5 matches the official forecast at M>=5 and beats it at M>=4.
- Effort matters for Sonnet: medium is clearly worse, most of all at M>=4. That supports the
  registered `high` setting.
- M3 answers are coherent: M3 >= M4 >= M5 holds in all but at most 0.5% of samples.
- M3 scoring could not be tested. No E3 post-cutoff sequence is in a region whose catalog is
  complete at M3 (Alaska and the generic US region have Mcat 3.5, Guam 4.6). In the
  confirmatory candidates, 35 of 194 sequences (the California regions, Mcat 3.0) can carry M3
  targets.

**Implications for prereg v2 (Tyler's decision).**
- Variants A and B are equivalent within noise. Pre-registering A as primary and B as a
  robustness variant is enough. C is informative but not needed as a confirmatory arm.
- Effort `high` stays.
- M3 targets are a secondary analysis on the California candidates.

### The 4.6 models (2026-10-30)
D2 items, prompt v2A, 3 samples each, at the study settings of ADR 0014 decision 5 (block
`d2-46`, runs/d2/d2-46-*). All 594 answers were valid; cost $11.12. Mean dLS against the
official forecast (positive = worse), as in the summary table:

| Model | Effort | d5 | d4 |
|---|---|---|---|
| Opus 4.6 | adaptive, medium | +0.043 | +0.086 |
| Sonnet 4.6 | adaptive, low | +0.151 | +0.326 |
| Opus 5.5 (for comparison) | high | +0.003 | -0.038 |

Both 4.6 models forecast worse than Opus 5.5, Sonnet 4.6 by a wide margin. This matches their
weaker response to the observed aftershock count in the D1 probes. Power: ADR 0018.
