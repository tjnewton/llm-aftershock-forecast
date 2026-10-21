# ADR 0010: Legacy-ETAS refit at each issue time

Status: Sections 1-7 describe the current method and its validation.

## 1. Decision
Refit the USGS legacy ETAS model ("Epidemic-Type aftershock model (Bayesian Combination)", the
van der Elst code in opensha-oaf `etas/`, which writes the published international OAF
products) at every benchmark issue time, with a Python port (`src/laf/etas.py`), and use it as a
secondary baseline. The port is validated against the published products and against the USGS
Java code itself (section 4).

## 2. Purpose
1. An ETAS reference on every scored cell, including sequences without an official forecast
   (offshore Chiapas, Sarangani, the US and dev sequences).
2. An overdispersed reference for calibration plots (Poisson-mixture RJ is too
   narrow by construction).
3. **Hindsight effect:** the refit on today's revised ComCat versus the official
   forecast, split into the catalog effect (refit on today's catalog vs refit on the as-of
   catalog, ADR 0011) and the code-and-analyst effect (refit on the as-of catalog vs official).

## 3. Method
Formulas and Java file:line references: `docs/research/legacy-etas-formulas.md`.

### 3.1 Prior and grid
- Generic parameters `etas/vdEGenericETASParams_080919.csv` for the Garcia regime
  (`laf.generic_rj.garcia_regime`, GLOBAL-AVERAGE fallback). The Java code takes the prior from
  the hypocentre and the grid ranges, aSigma and Mmax from the aftershock-zone centre; the two
  regimes coincide for all 11 benchmark sequences.
- Prior: trivariate normal on (a, p, log10 c) with mean (A0, p_csv, -2.5), A0 = a_csv +
  log10((Mmax - Mref)/(Mmax - Mc)), covariance from the CSV (N = 2099), times N(ams; A0, asig);
  unnormalized.
- Grid: ams and a in A0 +/- 4 asig, p in p_csv +/- 4 sqrt(N covpp) (floor 0.1), c0 log-spaced
  1e-5..1 d with the legacy step (range)/n; 31 points each (GUI default). The command line uses
  (51, 31, 31, 21); both are supported (`Grid`).

### 3.2 Data
- Events: ComCat events inside the issue's forecast circle, after the mainshock and before the
  information cutoff, keeping every event at or above the 1,000th-largest magnitude (legacy
  `maxCatalogNumberParam`, ties kept). Catalog: today's ComCat (`--catalog hindsight`, the
  catalog-effect variant, `etas_forecasts_hindsight.parquet`) or ComCat as it
  stood at the cutoff (`--catalog asof`, the default and the registered refit, ADR 0011).
- Mc and b: those of the matched official version where one exists, else Mc 4.95 and b 1.0.
  alpha = min(b, 1) (legacy `link_alpha`). Mainshock magnitude: the version's magMain, else the
  ComCat magnitude (as in prompts).

### 3.3 Fit
Bayesian grid posterior of `ETAS_AftershockModel_SequenceSpecific`: likelihood of events M >= Mc
with the magnitude-dependent c of timeDepMc (c_i = c0 (10^ac K_i)^(1/p), GUI default on; off is
supported), two passes (ac = A0, then the pass-1 MAP ams); subcritical nodes only (branching
ratio over the forecast horizon < 1, c* = c0 10^(ac/p)); weights exp(lp - max), cut below -20.

### 3.4 Forecast
10,000 simulated catalogs, one posterior draw each (`ETAScatalog`): seeds are the mainshock (at
magnitude Mms + ams - a) and every fetched event with M >= minMag; generation-1 parents use a,
all others a' = a + log10((Mmax - Mc)/(Mmax - minMag)); c0 for every parent; GR magnitudes with
b, capped at Mmax. Counts of simulated m >= M per window (no 0.05 offset).

### 3.5 Minimum simulated magnitude
With alpha = 1 < b, M>=5 counts depend on minMag (about 3x between 3.0 and 5.8 at b = 1.11-1.14),
and the rule changed four times in 2025-26 (table in `legacy-etas-formulas.md` section 5).
- Where the matched official version's fractiles reveal its own minMag (they are then
  10^(b (minMag - M)) times integers below it; `Forecast.simulated_min_mag`, column
  `oaf_sim_min_mag`), that value is used, as the version's Mc and b are. This covers the 2025
  Kamchatka products (5.8, from the Feb-2025 build 8b8dfbedcb).
- Otherwise the rule in force at the forecast time: 3.0 with 366-day calibration before
  2026-10-14 19:21:40 UTC (commit 08a274bd), max magnitude - 4 with 1-day calibration after;
  lowered by 1 until all 100 calibration catalogs contain an event (floor -3).

### 3.6 Reporting below minMag
For M below minMag the legacy code reports 10^(b (minMag - M)) times the discrete fractile at
minMag, replacing fractiles <= 1 by a continuous Poisson quantile at the rate implied by the
probability of the smallest count (`legacy_fractiles`); `hist_m5` is then the histogram of the
scaled counts and `mean_m5` the scaled mean. P(M>=6) is simulated directly and reported as
P(N >= 1) (the legacy `probability`, 1 - weight at the smallest count, is emulated only for
validation).

### 3.7 Outputs and seeds
`uv run laf etas --snapshot S [--catalog asof]` writes `etas_forecasts[_asof].parquet`: per issue x
window the M>=5 quantiles at the nine scoring levels, P(M>=6), mean and histogram, MAP and
posterior summaries, Mc, b, regime, minMag and its source, capped share and seed. Seeds are
20261021 + crc32(issue id), so they do not depend on which other items a snapshot holds.

## 4. Validation (`uv run laf etas-validate --snapshot S`; outputs in `runs/etas_validation/S/`)
All checks are outcome-blind: they compare with official products, with the USGS Java code, or
with synthetic truth.

| Check | What is compared | Result |
|---|---|---|
| V0 catalog | official `observations` counts vs the as-of catalog (ADR 0011) | 95.1% exact of 674 checkable counts (hindsight 69.1%); Colombia, Panama, Venezuela, Sand Point 100%, Flores 99%, Kamchatka 95%, Hubbard 73% (one event split by ComCat after the fact) |
| Java differential | port vs opensha-oaf 08a274bde278 command line, identical inputs, 5 issues | MAP identical to full precision 5/5; minMag from the port's own rule identical 5/5; fractile discrepancy at or below the Java run-to-run noise (M3/M4 0.008/0.006 vs 0.009; M>=5 0.000) (`runs/java_differential/`) |
| V1 fit | refit MAP on the as-of catalog vs published MAP | Panama 12/12 exact under GUI defaults (2/12 on the hindsight catalog); Flores 1/30 (one or two grid steps off); Colombia 1/21, Venezuela 0/36 (1-6 fit events; analyst settings); Kamchatka at most 7/61 over six grid configurations (21, 31, 41 points; ams/a/p/c 51/31/31/21, 41/41/41/21, 41/41/41/31; mixed GUI and command-line runs) (`runs/etas_validation/S/v1_exact.py`) |
| V3 emulation | full forecast of each official version (as-of catalog, posterior, product minMag, GUI defaults) vs its published fractiles, M3-M7 x 1 Day/1 Week/1 Month, against a second-seed null | 90th-percentile discrepancy at M>=5 (null): Panama 0.019 (0.028), Flores 0.039 (0.032), Kamchatka 0.038 (0.030), Colombia 0.122 (0.009), Venezuela 0.246 (0.000); P(M>=6) p90 at the null level except Colombia (0.018 vs 0.004) and Venezuela (0.049 vs 0.004) |
| V2 simulator | each official version re-simulated from its published MAP on the as-of catalog (`laf etas --validate`) | 72/75 = 0.960 (Kamchatka 12/12) |
| Recovery | 2,400 synthetic sequences from the prior (SZ-GENERIC, M7.5, fits at 1, 3, 7 d) | posterior ranks uniform (KS p 0.19-0.82), 50% / 90% coverage 0.48-0.54 / 0.89-0.92; next-week M>=5 forecast PIT uniform (KS p 0.50-0.66), coverage 0.50-0.52 / 0.89-0.91 |

Discrepancy = mean |log((ours + 1)/(official + 1))| over the nine scoring levels. The Java
differential is also a unit test (`test_fit_reproduces_the_usgs_java_map_exactly`).

Emulation details: events are cut at min(timeStart, creationTime) (the fetch), while the fit
horizon, minMag calibration and simulation start are timeStart (legacy dataEnd = forecastStart);
the as-of catalog falls back to the hindsight row for any event without a history
(`as_of_or_hindsight`), and versions whose data window extends beyond the snapshot catalog are
skipped.

**Decomposition** (`decomposition.parquet`; 1 Day/1 Week/1 Month cells of the 25 issues matched
to an official ETAS product; median / 90th percentile of the M>=5 quantile distance):

| Sequence | official vs as-of refit (code and analyst) | as-of vs hindsight refit (catalog) |
|---|---|---|
| Panama | 0.004 / 0.018 | 0.032 / 0.114 |
| Flores Sea | 0.000 / 0.022 | 0.057 / 0.166 |
| Kamchatka | 0.010 / 0.026 | 0.170 / 0.384 |
| Colombia | 0.047 / 0.143 | 0.000 / 0.040 |
| Venezuela | 0.077 / 0.352 | 0.000 / 0.069 |

**Reading.** The port is the USGS code: on identical inputs the fit lands on the same grid node
and the forecasts agree within Monte Carlo noise. Differences between our refit and a published
product come from the catalog (today's vs then) and from settings an analyst chose in the GUI
(grids, ranges, timeDepMc, Mc); where those match the defaults (Panama) the published MAP is
reproduced exactly; for Flores and Kamchatka the forecast distributions still agree within noise.
Colombia and Venezuela (1-6 fit events per version) were issued with non-default analyst
settings, identified in section 4.1 (a regime override for Venezuela; pinned c and changing
regimes for Colombia); with them, these too are emulated within noise. Where catalogs were revised heavily (Kamchatka, Flores) the catalog effect dominates
the refit-vs-official difference; where the data are sparse (Colombia, Venezuela) the analyst
settings do.

### 4.1 Analyst settings behind the Colombia and Venezuela products
The GUI lets an analyst override the regime, pin or narrow parameter ranges and choose grids; the
JSON records none of it. Three tests on the as-of catalog identify the settings
(`runs/etas_validation/20261021T1027Z/analyst_settings/`): the distance in posterior sd between
the published MAP and our MAP for every regime x timeDepMc; an exact-MAP search over regime x
grid x c range x the Mc at which the prior and ranges were set; and fits with c pinned where the
published c is a constant, off-grid round value.

- **Venezuela, days 1.6-32.7 (24 versions): regime overridden to SZ-GENERIC** (the code assigns
  "ACR shallow (above slab)" = ANSR-ABSLSHC at the hypocentre, confirmed by the Java run). Best
  regime for 22 of the 24 versions; SZ-GENERIC at 0.05-0.52 sd (default regime 1.0-4.7 sd); 9 versions
  reproduced exactly with 31-point grids, a c range [1e-5, 0.9998] (the published 0.9998 and
  0.4757 are its top and 29th values) and prior/ranges set at Mc 4.25 (days 2-7) or 4.75 (days
  13-28) while the fit uses Mc 4.45; 12 of the other 15 match three of the four published parameters.
  **From day 39.7: the code's own regime** (ANSR-ABSLSHC; 0.03-0.43 sd).
- **Colombia (M7.4 at 116 km depth): settings changed from session to session.** c was pinned at
  0.003 on days 1.1-8.1 (six versions) and at 0.1 on days 35-42 (distance with c pinned
  0.09-0.53 sd vs 1.1-1.8 with a free c); the regime alternates between the code's SZ-ONSHORE,
  GLOBAL-AVERAGE and SZ-INLBACK (`config/analyst_settings.toml`). Only 3 versions reproduce exactly; the
  per-version regime is chosen by distance, so this is an identification, not a blind test.

V3 with the identified settings (M>=5 90th percentile, null in brackets; dP = |P_ours - P_official|):

| Sequence | Settings | all-M p90 | M>=5 p90 | dP(M>=5) p90 | dP(M>=6) p90 |
|---|---|---|---|---|---|
| Venezuela | code defaults | 0.579 | 0.246 (0.000) | 0.228 | 0.049 |
| Venezuela | SZ-GENERIC before day 35, defaults after | 0.023 | 0.028 (0.017) | 0.008 | 0.003 |
| Colombia | code defaults | 0.275 | 0.122 (0.009) | 0.082 | 0.018 |
| Colombia | c pinned in two blocks + per-session regime | 0.048 | 0.000 (0.000) | 0.018 | 0.004 |

With the analysts' settings, all five ETAS sequences are emulated within Monte Carlo noise. The
registered refit keeps the code defaults (section 3): it is what the operational code does on
its own, the settings above are not recorded anywhere, and the Colombia ones are inferred per
version. The code-and-analyst component of the decomposition for Venezuela and Colombia is
therefore almost entirely analyst settings.

**Sensitivity variant: refit with the inferred analyst settings.** `uv run laf etas --snapshot S
--settings analyst` applies `config/analyst_settings.toml` (the settings above as day-range
rules; Venezuela SZ-GENERIC before day 35; Colombia per session, c pinned in two blocks) to the
11 Venezuela and Colombia issues and writes `etas_forecasts_analyst.parquet`, column `settings`
= analyst / default; the other 50 issues are identical to the registered refit. On
20261021T1027Z (`a58d5b67babcc558...`), median / 90th-percentile distance of the M>=5 quantiles
to the official forecast:

| Sequence | registered refit (code defaults) | analyst-settings refit |
|---|---|---|
| Venezuela | 0.077 / 0.352 | 0.000 / 0.037 |
| Colombia | 0.047 / 0.143 | 0.000 / 0.039 |

With SZ-GENERIC, Venezuela's refit P(M>=6) rises 2-4x (for example 0.148 vs 0.041 in the first
1-Month window); Colombia's falls slightly.

## 5. Sensitivity (`runs/etas_validation/S/sensitivity.parquet`; 61 issues x 3 windows)
Discrepancy of the M>=5 quantiles to the registered refit (median / 90th percentile / max) and
90th percentile of |dP(M>=6)|:

| Variant | Discrepancy | dP(M>=6) p90 |
|---|---|---|
| second seed (Monte Carlo null) | 0.000 / 0.032 / 0.087 | 0.010 |
| 30,000 simulations | 0.000 / 0.032 / 0.109 | 0.007 |
| 21- / 41-point grids | 0.000 / 0.042 / 0.109; 0.000 / 0.032 / 0.124 | 0.007; 0.008 |
| Mmax -0.5 / +0.5 | 0.000 / 0.045 / 0.137; 0.000 / 0.045 / 0.109 | 0.011; 0.008 |
| timeDepMc off | 0.017 / 0.090 / 0.273 | 0.021 |
| minMag = Mc (internally consistent) | 0.102 / 0.250 / 0.618 | 0.072 (max 0.161) |

Grid size, Mmax and the number of simulations matter no more than Monte Carlo noise; the
simulation minimum magnitude is the one setting that matters, a property of the legacy model
itself (alpha capped at 1 while b > 1).

## 6. Registration (to be copied into the preregistration at the freeze)
- The legacy-ETAS refit (`laf etas --snapshot S`, as-of catalog, defaults of section 3) is a
  secondary baseline on all scored cells (M>=5 quantiles and P(M>=6)), computed on the scoring
  snapshot before any LLM run; the SHA-256 of `etas_forecasts.parquet` is recorded.
- Catalog effect: dQS(refit on today's catalog, as-of refit) on all cells; code-and-analyst
  effect: dQS(as-of refit, official) on OAF cells, with each sequence's V3 result. The refit stays
  registered if `laf etas --snapshot S --validate` (seed offset 0) exits 0.
- Sensitivity variant, labelled as such and never a registered baseline: the refit with the
  inferred analyst settings (`--settings analyst`, section 4.1), reported beside the registered
  refit on the Colombia and Venezuela cells; dQS(analyst refit, official) is the residual
  code-and-analyst effect once the inferred settings are applied.
- Official P(M>=6) is scored as published, although the legacy `probability` is 1 - (share of
  catalogs at the smallest count), slightly below 1 when every catalog has an M>=6 (6 of 111
  scored values are >= 0.99, 0.9908-0.9999; negligible under the Brier and the clipped log score).

## 7. Limitations
- Official forecasts mix analyst settings that are not recorded in the JSON (regime overrides,
  pinned or narrowed ranges, grids, the Mc at which ranges were set). They can be inferred from
  the published MAPs (section 4.1) but not recovered with certainty, especially where few events
  constrain the fit (Colombia).
- Deleted ComCat events are not in the as-of catalog (ADR 0011).
- Products made after 2026-10-14 whose fractiles show minMag <= 3 get the new rule's 3.7 where
  the official calibration stepped down to 2.7 (three Panama versions; M3-M4 bins only; scoring
  uses M>=5).
- Kamchatka's 2026 weekly updates show minMag 4.8, consistent with either the Feb-2025 rule or the
  2026-10 rule; they are outside the benchmark's issue times.
