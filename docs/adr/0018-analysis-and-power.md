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

## Open decisions (Tyler)
1. The margin anchor and its value (after the development-data numbers exist).
2. Target power and sequence count, which set the prospective stopping rule (ADR 0017).
3. Whether the hierarchical model is confirmatory or a robustness check.

## Changelog
- 2026-10-29: first version.
