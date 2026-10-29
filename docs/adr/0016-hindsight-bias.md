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

## Data gaps to fix
- E3 snapshot `20261021T2300Z`: 44 of its 210 issue times have no histories. They come from
  eight sequences (aka2026nyxoap, tx2026ojlaky, us6000s7qf, us6000sr43, us7000rrjh, us7000s0nl,
  us7000thsx, us7000thwt). `n_hindsight_m4`, which counts events with M >= 4 that forecasters
  were shown without a history, sums to 40 over the snapshot's issue times. Prompts for those issues showed today's catalog. Refetching their
  histories (`laf asof --only ...`, one fetcher) closes the gap for B1. The E3 LLM results stay
  as run and get a footnote.

## Changelog
- 2026-10-29: first version; E3 hindsight refit written
  (`data/processed/20261021T2300Z/etas_forecasts_hindsight.parquet`); first look above.
