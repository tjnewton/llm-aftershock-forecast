# ADR 0018: Confirmatory analysis and power (B3, A3)

Status: **living document, proposed.** Margins and thresholds are Tyler's decisions before prereg
v2; this records the method and what the development data says.

## Estimands
Per cell, dS = S(model) - S(reference), with S the primary score (ADR 0015). The reference is
the official USGS forecast where one exists. Main contrasts:
- **Equivalence with the official forecast:** is the mean dS inside (-delta, +delta)?
- **Superiority over the rule of thumb** (the aftershock count so far, extended with the usual
  Omori decay; `naive`): is the mean dS < 0?
- **Against the ETAS refit** on the as-of catalog: a contrast with a seismology reference that
  has no analyst in the loop.

## Dependence
Cells are not independent. Windows of one issue time are nested (day within week within month).
Issue times of one sequence share aftershocks, and the 1-week and 1-month windows of
consecutive issues overlap. Hence:
- **Primary: block bootstrap over sequences** (resample sequences with replacement, keep all
  their cells; B = 10,000, fixed seed), giving a 90% CI for a TOST equivalence test and a 95% CI
  for superiority.
- **Confirmatory model:** a hierarchical model, dS_ijk = mu + u_i + v_ij + e_ijk (sequence i,
  issue time j, window k), with window and elapsed-time stratum as fixed effects. This is a
  check that the bootstrap conclusion holds with partial pooling.
- **Reported beside:** the non-overlapping subset (one window per issue, as in prereg v1), and
  results by elapsed-time stratum.

## Equivalence margin
The margin must have a physical meaning, fixed before any confirmatory score is seen. Candidate
anchors, computed on development data only:
1. The score gap between USGS's own two operational models: Reasenberg-Jones products against
   the ETAS-based products, or the published product against the generic-RJ forecast for the
   same sequence. If two forecasts USGS considers acceptable differ by X, a gap smaller than X is
   operationally irrelevant.
2. The score change from a factor-of-2 error in the expected count (a 0.3 shift of log10 rate),
   computed by perturbing the official forecast.

## Power (A3)
From development data: the spread of the per-sequence mean dS (between-sequence SD) and the
within-sequence spread, both by forecaster pair. Then simulate the bootstrap TOST at candidate
sequence counts (20, 40, 80, 120) and margins, and report the sequence count needed for 80%
power at a true difference of 0. E3 (39 sequences, all with an official forecast) is the main
input. E3 uses M>=5 targets only, so a power analysis for M>=3 targets also needs the E3
sequences rescored at M3 (development data, allowed).

## First look on development data (2026-10-30, exploratory)
**Spread.** E3 post-cutoff sequences (18 sequences, 203 primary cells with an official forecast).
dLS = LS(Claude direct answer, the mean over its samples) - LS(official), both scored through
nine quantiles (ADR 0015):

| Model | Mean dLS | Between-sequence SD | Within-sequence SD |
|---|---|---|---|
| Opus 5.5 | +0.011 | 0.106 | 0.071 |
| Sonnet 5.5 | +0.038 | 0.034 | 0.069 |
| Haiku 5.5 | +0.029 | 0.058 | 0.075 |

With the standard error of the mean about SD_between / sqrt(N), 80% TOST power at a true
difference of 0 needs a margin of about 2.9 SD_between / sqrt(N). Taking SD_between = 0.1 gives
about 0.05 nats at N = 40, 0.03 at N = 100 and 0.02 at N = 194. These numbers are rough: E3 cells
are mostly small sequences with zero counts.

**Margin anchors** (mean per cell, primary cells with an official forecast):

| Anchor | Registered (6 seq., 96 cells) | E3 (39 seq., 536 cells) |
|---|---|---|
| Expected count x2 (NB fitted to the official quantiles, mean doubled) | +0.300 | +0.063 |
| Expected count x0.5 | +0.202 | -0.021 |
| Generic RJ - official | +0.184 | -0.013 |
| ETAS refit - official | -0.044 | -0.018 |

**Reading.** The anchors scale with how much a cell can tell apart: large sequences give
tenths of a nat, small ones hundredths. A single margin in nats would be loose for small
sequences and tight for large ones. Options to settle with Tyler, after a proper simulation
(bootstrap of sequence effects, the candidate set's size mix, M3 targets):
1. margins by mainshock-magnitude stratum;
2. a relative margin, dS divided by the cell's factor-of-2 penalty;
3. the primary test on the stratum where cells carry information (M>=6 or M3 targets), with
   the rest descriptive.

## Power simulation (`laf power`, development data, 2026-10-30)
Inputs: E3 sequence effects, from direct-arm answers given the catalog (I1), scored through
nine quantiles. A simulated study draws N sequence effects with replacement (centred and
shifted to the true difference) and uses the normal-approximation 90% interval of the
sequence-level mean. Output: results/power_<reference>_<snapshot>.csv.

**Equivalence with the official forecast** (true difference 0; between-sequence SD over 39
sequences: Opus 0.131, Sonnet 0.163):

| N sequences | Opus, margin 0.03 | Opus, 0.05 | Sonnet, 0.03 | Sonnet, 0.05 |
|---|---|---|---|---|
| 60 | 0.28 | 0.80 | 0.00 | 0.68 |
| 100 | 0.54 | 0.95 | 0.19 | 0.87 |
| 194 | 0.87 | 1.00 | 0.69 | 0.98 |

**Superiority over the rule of thumb**, at the development estimate (Opus -0.061 nats,
Sonnet -0.039):

| N sequences | 60 | 100 | 150 | 194 |
|---|---|---|---|---|
| Opus | 0.38 | 0.68 | 0.88 | 0.95 |
| Sonnet | 0.12 | 0.20 | 0.31 | 0.39 |

Invalid samples get the worst score of any valid forecast in the cell (prereg section 7);
`--valid-only` is the sensitivity variant. Opus and Sonnet rarely answer invalidly, so their
numbers barely move. Haiku goes from +0.029 (valid only) to +0.066. The open models are far
from the official forecast on E3: gpt-oss-20b +0.35 nats, and Olmo-3.1-32B +0.94 (+0.66 valid
only; 277 of its 630 answers are non-monotone).

**Reading.**
- Equivalence at a margin of 0.05 nats needs about 100 sequences.
- At 0.03 nats it needs all 194 candidates, and more for Sonnet.
- Superiority over the rule of thumb is within reach only for Opus, with most of the candidate set.
- The prospective arm adds sequences slowly. The retrospective older-cutoff arm is clean on
  all 194 candidates only for gpt-5.1, and on 26 for Opus 4.6.

**Caveats.**
- The effects are heavy-tailed, so with few sequences the normal approximation is optimistic,
  and power is not monotone in N below about 40.
- These numbers are for M>=5 targets. M3 targets add information per cell.

## Open decisions (Tyler)
1. The margin anchor and its value (after the development-data numbers exist).
2. Target power and sequence count, which set the prospective stopping rule (ADR 0017).
3. Whether the hierarchical model is confirmatory or a robustness check.

## Changelog
- 2026-10-30: power simulation (`laf.power`) on E3.
- 2026-10-30: first look at spread and margin anchors on development data.
- 2026-10-29: first version.
