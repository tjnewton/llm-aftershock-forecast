# ADR 0016: Hindsight bias from catalog revisions (B1)

Status: **living document.** Method proposed; first exploratory numbers on development data are
below.

## Question
Retrospective forecast tests usually run on today's catalog. Today's ComCat holds events and
magnitudes that were added or revised after each issue time. How much does that inflate
retrospective scores, for which forecasters, and for which sequences? ADR 0011 rebuilds the
catalog as it stood at each issue time (V0 reproduces 95.1% of the official products' own
observation counts), so I can answer this directly.

## Method
- **Forecasters:** every forecaster that reads the catalog is run twice, on the as-of catalog
  and on today's catalog (origin time before the information cutoff, same selection rules):
  - ETAS refit (`laf etas --catalog asof|hindsight`);
  - RJ-MLE;
  - the simple rule of thumb (`naive`);
  - an LLM subset (direct arm, one model, I1). The LLM subset costs API money, so it waits for
    approval.
- **Catalog differences** (outcome-blind, every sequence): events visible at the cutoff that
  exist only in today's catalog (late additions), events whose magnitude changed across a
  target threshold, location changes across the circle edge, and deleted events (not
  reconstructable, ADR 0011 Limitations).
- **Forecast differences** (outcome-blind, allowed on confirmatory data): the log ratio of
  median counts and the change in P(M>=6), hindsight minus as-of.
- **Score inflation** (development data only): per cell, dS = S(hindsight) - S(as-of), for the
  log-scale quantile score and the log score (ADR 0015) at M>=3, 4 and 5. Report the mean by
  sequence, with a bootstrap over sequences (ADR 0018), and by elapsed-time stratum.
- Only issue times with a full as-of history (`catalog_source == "asof"`) enter. Eight E3
  sequences lack histories (below), so they are refetched first.

## First look (2026-10-29, exploratory, ETAS refit only, M>=5 log-QS, primary cells)
- **Data:** registered and E3 snapshots, 557 cells in 39 sequences.
- **Mean change:** dQS = -0.004 (hindsight looks better). 10.6% of cells improve, 5.7% get
  worse, and 83.7% are unchanged; most of those are small sequences with zero-count forecasts
  at M>=5.
- **By sequence:** the effect sits in the large sequences: Kamchatka -0.040, Sarangani -0.033,
  Flores Sea -0.031, offshore Chiapas -0.015. Venezuela goes the other way (+0.005).
- **Against the official forecast** (521 cells): ETAS on the as-of catalog is 0.005 better and
  ETAS on today's catalog 0.007 better. So hindsight inflates the refit's apparent advantage by
  about half.
- **Reading:** small on average, concentrated where it matters (the large sequences that drive
  pooled results). M>=4 and M>=3 targets should show larger effects. This is exploratory and
  has no uncertainty yet.

## Results on development data (`laf hindsight`, 2026-10-30)
**Catalog backfill (outcome-blind).** Count the M>=4 events visible before each issue time, in
the issue's circle, summed over issue times with full histories:

| Set or sequence | Available then (as-of) | In today's catalog | Ratio |
|---|---|---|---|
| Registered snapshot, all | 4,557 | 9,761 | 2.1 |
| Kamchatka | 1,495 | 4,505 | 3.0 |
| Sarangani | 605 | 1,307 | 2.2 |
| Flores Sea | 840 | 1,480 | 1.8 |
| Offshore Chiapas | 515 | 869 | 1.7 |
| E3 snapshot, all | 561 | 655 | 1.2 |

98.7% of the events available then still exist today. The difference is events ComCat added
later, not deletions. V0 (ADR 0011) confirms that the as-of catalogs match what USGS used.

**Score inflation** (dS = S(today) - S(as-of); negative means hindsight looks better; primary
cells with full histories; two-stage bootstrap over sequences and issue times, 10,000
replicates):

| Set | Forecaster | Cells (sequences) | dLS M>=5 [95% CI] | dQS M>=5 [95% CI] |
|---|---|---|---|---|
| Registered | ETAS refit | 132 (8) | -0.094 [-0.177, +0.009] | -0.015 [-0.025, -0.002] |
| Registered | RJ-MLE | 132 (8) | +0.043 [-0.111, +0.351] | +0.003 [-0.017, +0.036] |
| Registered | rule of thumb | 132 (8) | -0.152 [-0.566, +0.525] | -0.001 [-0.037, +0.059] |
| E3 | ETAS refit | 425 (31) | -0.001 [-0.013, +0.008] | -0.000 [-0.002, +0.000] |
| E3 | RJ-MLE | 425 (31) | 0 (the generic fallback in small sequences) | 0 |
| E3 | rule of thumb | 425 (31) | +0.006 [0.000, +0.025] | +0.001 [-0.001, +0.005] |

The values are from a 2,000-replicate run. The 10,000-replicate run of `laf hindsight` moves the interval ends by at most 0.003 and writes
results/hindsight_summary_<snapshot>.csv.

**Reading.** Revisions matter where catalogs are revised most: the large international
sequences. On them, the ETAS refit scores about 0.09 nats better on today's catalog than on
the one it would have had. That is as large as the representation effect of ADR 0015 and as
the differences between forecasters, so a retrospective test on today's catalog flatters
catalog-driven forecasters. The two simple baselines do not show a consistent sign. The LLM
subset (I1 prompts rebuilt from today's catalog) needs API spend and waits for approval.

## Data gaps
- E3 snapshot `20261021T2300Z`: 44 of its 210 issue times were built without histories. Five of
  the eight sequences involved have no event in ComCat besides the mainshock, so they have
  nothing to fetch. Before the fix below, `laf tables` labeled such sequences "hindsight" and
  took the mainshock from today's catalog. Fixed on 2026-10-30: the mainshock's own history (its
  event document) is now used whenever the catalog holds no other event. The committed E3 tables
  stay as built, because the E3 prompts were made from them. A rebuild would change only those
  mainshock rows (for example M5.2 today, M5.1 as it was at the issue time). The other three
  sequences (us6000s7qf, us6000sr43, us7000thwt) need their histories fetched before B1 covers
  them.

## Changelog
- 2026-10-30: mainshock-only sequences get an as-of catalog (`laf tables` fix); E3 data-gap
  note corrected.
- 2026-10-30: `laf.hindsight` (RJ-MLE and the rule of thumb added; M>=4 log score) and the
  results above; catalog backfill measured.
- 2026-10-29: first version; E3 hindsight refit written
  (`data/processed/20261021T2300Z/etas_forecasts_hindsight.parquet`); first look above.
