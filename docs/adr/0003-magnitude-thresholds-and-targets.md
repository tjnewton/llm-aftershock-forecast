# ADR 0003: Magnitude thresholds and forecast targets

Status: proposed. Changes the original design (drops M>=4.5).

## Decision
- **Primary target:** quantiles of N(M>=5.0) in each window (1 Day, 1 Week, 1 Month).
- **Secondary target:** P(N(M>=6.0) >= 1) in each window.
- **Exploratory:** quantiles of N(M>=4.0), reported with an explicit incompleteness caveat.
- Counting rule: an event counts if its ComCat preferred magnitude >= threshold - 1e-6. Mixed
  magnitude types (mb, Mww) are used as ComCat reports them, as USGS does.

## Why not M>=4.5
The original plan had M>=4.5 as secondary. The official forecast has no M>=4.5 bin (bins are
M>=3, 4, 5, 6, 7, 8), so M>=4.5 would have no official baseline, and it sits below the USGS ETAS
completeness (Mc 4.75-5.25) where ComCat is incomplete early in sequences. M>=5 is at or above
the USGS Mc for every candidate except Kamchatka (Mc 5.15-5.25), where it is 0.15-0.25 below;
pooled results are therefore also reported without Kamchatka. M>=4 keeps an official
comparison for exploratory use.

## Evidence
International ComCat completeness on the 30-day catalogs is about M4.4-4.7 (MAXC+0.2); USGS ETAS
Mc in the valid archived international versions ranges 4.15-5.25 (Flores 4.85-4.95, Panama 4.75-4.95, Kamchatka 5.15-5.25; docs/data-card.md).
