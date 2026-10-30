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

## Power with the confirmatory models (D2 for the 4.6 models, 2026-10-30)
`laf power --from-d2 --runs runs/d2 --snapshot 20261021T2300Z` uses the D2 items (18 E3
post-cutoff sequences, prompt v2, M3 catalog). Valid answers only; all 594 4.6 answers were
valid. Output: results/power_official_d2_20261021T2300Z.csv. The models ran at their study
settings (ADR 0014 decision 5).

| Model (v2A) | Mean dLS5 per sequence | Between-sequence SD | Equivalence at 0.05, N = 100 | Official better, N = 100 |
|---|---|---|---|---|
| Opus 4.6 (adaptive, medium) | +0.033 | 0.062 | 0.87 | 1.00 |
| Sonnet 4.6 (adaptive, low) | +0.144 | 0.113 | 0.00 | 1.00 |
| Opus 5.5 (registered) | +0.010 | 0.113 | 0.94 | 0.17 |
| Sonnet 5.5 (registered) | +0.008 | 0.020 | 1.00 | 0.97 |

- **How to read the columns:** both take the development estimate as the true difference. "Official better"
  is the power of the one-sided test that the official forecast scores better (95% lower
  bound of mean dLS above 0). The CSV holds the equivalence power at a true difference of 0
  for every margin, as in the table above.
- **Opus 4.6:** likely both within a 0.05 margin and detectably worse than the official
  forecast. The two conclusions are compatible; the paper should report both.
- **Sonnet 4.6:** clearly worse. Equivalence fails at any N, consistent with its weak
  updating in the D1 probes.
- **Caveat:** 18 small sequences. The confirmatory set includes large sequences, where D1
  suggests the 4.6 models' under-updating costs more.

## Confirmatory test design (Tyler, 2026-10-30; the margin is still open)
Clean-period sizes (3-month buffer, ADR 0014; mainshock origin in the clean period;
20261029T2000Z candidates):

| Model | Clean from | M>=5 mainshocks | All candidates |
|---|---|---|---|
| gpt-5.1-2025-11-13 | 2025-01-01 | 88 | 174 |
| claude-opus-4-6 | 2025-12-01 | 22 | 75 |
| claude-sonnet-4-6 | 2026-05-01 | 15 | 40 |
| gpt-6.1-sol | 2026-08-01 | 7 | 20 |
| Claude 5.5 | 2026-10-01 | 7 (plus about 4.3 per month live) | 10 |

1. **Two co-primary tests**, equivalence with the official forecast at M>=5, with a Holm
   correction across the two. The first Holm step tests at 0.025 per side (a 95% interval),
   the second at 0.05. Power is given at both levels: the true Holm power lies between them.
   - **A: gpt-5.1, retrospective**, on its 88 clean M>=5 sequences. If it behaves like Opus
     4.6 or Opus 5.5 did in D2, power at a 0.05 margin is 0.75 to 0.86 at 0.025 (0.83 to 0.91
     at 0.05). It must run before its API removal on 2027-04-01.
   - **B: Claude 5.5 (Opus), prospective plus its clean retrospective sequences.**
     - Prospective items enter only as matched items hashed before their first window opens
       (ADR 0017 decisions 1 and 2). Strict items have other windows than the official
       forecast, so they serve the contrast with the pipeline's baselines instead.
     - A sequence enters if at least one of its matched items is on time. With about 5
       versions per sequence (1,010 issues in 194 candidates) and about 45% of matched items late, almost every sequence
       enters, with roughly half its cells.
     - About 33 M>=5 sequences after the 6-month prospective period. Power at a 0.05 margin:
       0.52 at 0.025, 0.68 at 0.05. Fewer cells per sequence lower it somewhat further.
     - It is the one arm where contamination is impossible, which is the paper's thesis. The
       confirmatory decision uses the prospective stopping rule (ADR 0017), counted in
       eligible sequences; the full sample is reported as it accumulates.
   - Power from `laf.power.power` with `z = Z95` (0.025) or `Z90` (0.05), using each
     model's D2 sequence effects with its D2 mean as the true difference.
2. **Secondary: Opus 4.6** on its 22 M>=5 sequences, preregistered with its power (0.43 at
   0.05 if its D2 gap is real) stated openly. The M3 and M4 targets are added over its 75
   clean-period sequences where the catalog is complete.
3. **Secondary: gpt-6.1-sol, prospective**, as the same-cutoff comparison with Claude 5.5.
4. **Descriptive only: Sonnet 4.6.** It has 15 sequences, its adaptive thinking fails above
   low effort, and it was clearly worse in D2. It stays in the paper through D1, D2 and a
   descriptive table, with no test.

Still needed before the freeze:
- D2 for gpt-5.1, to measure its gap and spread (the power numbers above assume it behaves
  like the Claude models). This needs the OpenAI runner.
- The OpenAI effort level matching Claude's (ADR 0014).
- The margin: this design works at 0.05; at 0.03 only test A has useful power.

## Open decisions (Tyler)
1. The margin anchor and its value (after the development-data numbers exist).
2. Target power and sequence count, which set the prospective stopping rule (ADR 0017).
3. Whether the hierarchical model is confirmatory or a robustness check.

## Changelog
- 2026-10-30: confirmatory test design (co-primary gpt-5.1 retrospective and Claude 5.5
  prospective; Opus 4.6 and gpt-6.1-sol secondary; Sonnet 4.6 descriptive).
- 2026-10-30: power with the 4.6 models from their D2 runs (`laf power --from-d2`).
- 2026-10-30: power simulation (`laf.power`) on E3.
- 2026-10-30: first look at spread and margin anchors on development data.
- 2026-10-29: first version.
