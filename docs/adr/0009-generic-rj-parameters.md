# ADR 0009: Generic Reasenberg-Jones parameters by tectonic regime

Status: Implemented in `src/laf/generic_rj.py`; tested in `tests/test_generic_rj.py`.

## Context
Three parts of the design need a generic (mainshock-only) aftershock model: the fallback of the
RJ-MLE refit when fewer than 10 events are available, the baseline for the recall probe, and a
generic-RJ reference forecast. The fallback had been California's 1989 values (a = -1.67,
b = 0.91, p = 1.08, c = 0.05), quoted from memory and wrong for subduction zones.

## Decision
Use exactly what the USGS operational system uses, taken from its own code rather than
transcribed from a paper:
- **Source:** `opensha/opensha-oaf` (USGS operational aftershock forecasting code, CC0 licence),
  commit `08a274bde278b9de12f58a34e7f4ca8d397d0cb6` (2026-10-14). Four resource files are stored
  unmodified in `data/raw/reference/opensha-oaf/08a274bde278/` with manifest entries:
  `GenericRJ_ParametersFetch.json` (operational parameters), `PageEtAlGenericParams_032116.csv`
  (the Page et al. 2016 table; a test asserts it equals the operational values for all 15
  Garcia regimes), `TectonicRegimeTable.dat` (Garcia et al. 2012 regimes on a 0.05-degree grid)
  and `MagCompPage_ParametersFetch.json` (time-dependent completeness by region).
- **Lookup** (ported from `OAFParameterSet.getRegion`, `TectonicRegimeTable`,
  `SphRegionMercPolygon`): special regions first (California polygons; first match wins), else
  the Garcia regime of the nearest grid point to the ComCat epicentre. STREC names map to Garcia
  names through OpenSHA's `TectonicRegime` constants (opensha commit e2ece620).
- **Generic model** (as `RJ_AftershockModel_Generic`): a ~ Normal(aValue_mean, sigma(Mm)) with
  sigma(M) = sqrt(sigma0^2 + sigma1^2 / 10^max(M, 6)), truncated to [aValue_min, aValue_max];
  b, p and c fixed (b = 1.0, c = 0.018 d for all Garcia regimes); counts Poisson given a.
- **Completeness** (`MagCompPage`): Mc(t) = max(Mcat, F*Mm - G - H*log10(t)); WORLD
  F = 0.5, G = 0.25, H = 1.0 (Page et al. 2016); ALASKA and California F = 1.0, G = 4.5,
  H = 0.75. The RJ-MLE refit starts at the time the catalog is complete to M4.95 under this
  rule (Flores 0.050 d, Panama 0.045 d, Kamchatka 0.158 d, Sand Point 0.001 d), replacing the
  arbitrary t >= 0.1 d.

## Validation
- The lookup reproduces the parameters of the first (purely generic, pSigma = 0) USGS RJ
  products of both US sequences in the benchmark: Sand Point (SZ-ONSHORE: a -2.34, p 0.81,
  c 0.018, aSigma 0.502 vs our 0.503; F/G/H 1/4.5/0.75, ALASKA) and Hubbard Glacier
  (ANSR-SHALCON: a -2.42, p 0.98, aSigma 0.522; F/G/H 0.5/0.25/1.0, WORLD, epicentre in Yukon).
  Both files are golden tests.
- Unambiguous points: Los Angeles -> CAL-SCSN, central Australia -> SCR-GENERIC, mid-Pacific ->
  SOR-GENERIC; the ALASKA completeness polygon is handled across the date line (Attu).

## Assignments (snapshot 20261021T1027Z)
| Sequence | Regime | a mean | sigma(Mm) | p | Completeness region |
|---|---|---|---|---|---|
| Offshore Chiapas | SZ-GENERIC | -2.47 | 0.506 | 0.88 | WORLD |
| Colombia | SZ-ONSHORE | -2.34 | 0.500 | 0.81 | WORLD |
| Flores Sea | SZ-ONSHORE | -2.34 | 0.494 | 0.81 | WORLD |
| Panama | SZ-GENERIC | -2.47 | 0.497 | 0.88 | WORLD |
| Sarangani | SZ-GENERIC | -2.47 | 0.495 | 0.88 | WORLD |
| Venezuela | ANSR-ABSLSHC | -2.85 | 0.510 | 1.06 | WORLD |
| Sand Point | SZ-ONSHORE | -2.34 | 0.503 | 0.81 | ALASKA |
| Kamchatka | SZ-GENERIC | -2.47 | 0.491 | 0.88 | WORLD |
| Hubbard Glacier | ANSR-SHALCON | -2.42 | 0.522 | 0.98 | WORLD |
| Aomori (dev) | SZ-ONSHORE | -2.34 | 0.496 | 0.81 | WORLD |
| Sanriku (dev) | SZ-GENERIC | -2.47 | 0.503 | 0.88 | WORLD |
Stored per sequence in `sequences.parquet` (`generic_*`, `magcomp_*` columns).

## Consequences
- The generic-RJ forecast becomes a T1 baseline. It is the information-matched reference for
  the mainshock-only (I0) arm, and for sequences without OAF it shows what the USGS generic
  method would have said.
- Caveat for the write-up: USGS international products are ETAS (Bayesian, with generic ETAS
  priors), not RJ; the generic-RJ baseline is USGS's RJ method applied globally, as in Page et al.
  (2016), not the product USGS actually issued for those sequences.
- Garcia regimes are assigned from the epicentre on a 0.05-degree grid; depth is not used
  outside the California special regions (same as the operational code). Colombia (116 km deep)
  is therefore SZ-ONSHORE.
- References (DOIs checked on Crossref): Page et al. (2016) BSSA 106(5) 2290-2301,
  doi 10.1785/0120160073; Garcia, Wald & Hearne (2012) BSSA 102(1) 185-203,
  doi 10.1785/0120110124.
