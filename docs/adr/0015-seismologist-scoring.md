# ADR 0015: Scores a seismologist expects, and lower magnitude targets

Status: **living document, proposed** (workstreams B2 and A2). The quantile score of ADR 0001
stays as a robustness score.

## Context
Referees from statistical seismology expect forecasts as count distributions, scored with
CSEP-style consistency tests and log scores, with information gain against a reference. The
registered score, the log-scale quantile score, is proper but unfamiliar to them. Cells with
only M>=5 targets carry little information: most M5-6 mainshocks have no M>=5 aftershock in a
day or a week.

## Decision: count distributions
Every forecaster becomes a probability mass function p(n), n = 0..N_max, for each cell and target
magnitude:
- **Official, ETAS refit, RJ-MLE, generic RJ, params arm:** the full distribution the model
  defines. For official products this comes from the published fractiles (197 or 399 levels), as
  a step CDF.
- **Direct arm (nine quantiles only), implemented in `laf.countdist`:**
  1. **Latent-PCHIP (default).** A continuous latent Y has F_Y(n) = F_N(n) at every integer
     n. The tau-quantile of Y lies in (q - 1, q); knots go inside that interval, with tied
     quantiles spread evenly. F_Y is interpolated with PCHIP on z = log(y + 1). Below the first
     knot F_Y rises linearly from 0 at y = -1. Above the last knot it has a power-law tail,
     1 - F decaying as exp(-lam (z - z_K)), with lam from the last segment's slope. Every
     input quantile is reproduced exactly (tested on random quantile sets). An option uses the
     survival function of the fitted negative binomial for the tail instead (`tail="nb"`).
  2. **Negative binomial** fitted by least squares between tau and the NB CDF midway between
     q - 1 and q. This is a sensitivity analysis only (see validation).
- **Forecasts given as simulated histograms** (the ETAS refit, 10,000 catalogs) put zero
  probability on some observed counts. They are smoothed by taking their 399 fractiles
  (0.0025 steps) and applying the same reconstruction.
- A floor of 1e-6 on p(n) before any log, reported in the methods, so that one impossible count
  does not dominate a mean. How often the floor binds is reported.

## Validation on development data (`laf countdist-check`, 2026-10-29)
Log score of N(M>=5) on primary cells. The "full" score uses each forecaster's whole
distribution: 197 or 399 official fractiles, or the smoothed ETAS histogram. The "9q" score
uses only its nine quantiles, through the latent-PCHIP method.

| Set | Forecaster | Cells | Mean LS full | 9q - full: mean | median | MAE | corr |
|---|---|---|---|---|---|---|---|
| Registered (large sequences) | official | 96 | 1.988 | -0.267 | -0.007 | 0.408 | 0.926 |
| Registered | ETAS refit | 132 | 2.210 | -0.261 | +0.008 | 0.451 | 0.895 |
| E3 (mostly M5-6, small counts) | official | 536 | 0.206 | -0.006 | +0.004 | 0.039 | 0.958 |
| E3 | ETAS refit | 536 | 0.176 | +0.006 | +0.005 | 0.025 | 0.987 |

- Smoothing the raw ETAS histogram removes the zero-probability penalties. The mean LS on the
  registered set drops from 2.679 to 2.210, because the 1e-6 floor bound in 11 cells.
- Among nine-quantile reconstructions, latent-PCHIP with the power tail has the lowest MAE and
  the highest correlation with the full score. The NB-shaped tail is no better on average. A
  pure NB fit is clearly worse (MAE 0.15-0.52).
- Synthetic checks: on Poisson and NB forecasts the nine-quantile reconstruction loses at most
  about 0.05 nats of expected log score (it never beats the truth, as a proper score must).
- **Representation effect.** Where counts are large, the score depends on how the forecast is
  represented: about a quarter of a nat on the registered set, as large as the differences
  between forecasters. Comparing a nine-quantile forecaster (the LLM direct arm) with
  full-distribution forecasters (official, ETAS) would mix that effect into the contrast.

## Decision: scores and tests
- **Log score** LS = -log p(n_obs) per cell. This is the primary score for the paper, with the
  quantile score as robustness. Choosing the primary score is Tyler's decision before prereg v2.
- **Information gain** of model A over reference B: IG = LS_B - LS_A per cell. Summed over cells
  and divided by the number of observed target events, this gives the information gain per
  earthquake (IGPE, Rhoades et al. 2011). Cells with zero observed events are reported
  separately, because IGPE is undefined for them alone.
- **N-test** (CSEP; Zechar et al. 2010). For each cell, delta1 = P(N >= n_obs) and
  delta2 = P(N <= n_obs). Report the share of cells with delta1 or delta2 below 0.025 (a two-sided
  5% test), per forecaster, as a calibration diagnostic. These are not independent tests
  (nested windows, ADR 0018).
- **PIT histograms:** the randomized PIT from each p(n) (Czado et al. 2009), 10 bins, per
  forecaster.
- **P(M>=6):** Brier score and the clipped log score, as in ADR 0001.
- Cross-check: on synthetic Poisson forecasts, pyCSEP's N-test on a single-bin gridded forecast
  must equal ours.

## Decision: lower magnitude targets (A2)
- OAF products publish fractiles for M>=3, 4, 5, 6 and 7 (all 1,928 local product files; some
  also have M>=8).
- **Targets:** M>=3, 4 and 5 counts plus P(M>=6). M>=3 is scored only where the catalog is
  complete at M3 for the whole window. The rule is Mc <= 3.0 from the official product's own
  `Mc` (the value USGS used), plus a time-dependent completeness check after the mainshock
  (`MagComp.complete_after_days`, ADR 0009): cells whose window starts before M3 completeness
  are excluded at M3.
- Mc per sequence is stated in a table in the paper.
- **Stratify by issue time:** first day (< 1 d), 1-7 d, > 7 d. Most information is in the first
  day.
- New prompts must ask for the M3 quantiles. That changes the prompts and needs Tyler's
  approval. It would be worked out on development items in D2 (prompt robustness).

## Open decisions (Tyler)
1. Primary score for the paper: log score of the count distribution (recommended), with the
   quantile score as robustness, or the reverse.
2. **Representation-matched scoring (recommended):** score every forecaster through its nine
   quantiles with the same latent-PCHIP reconstruction for the primary comparison, and report
   full-distribution scores of the official and ETAS forecasts as a sensitivity analysis.
   This removes the representation effect from forecaster contrasts.
3. Whether to add M>=3 targets to the prompts.

## Changelog
- 2026-10-29: first version.
- 2026-10-29: `laf.countdist` implemented (latent-PCHIP, NB tail and NB fit, log score, N-test,
  PIT) and validated on the development snapshots; the geometric tail of the first draft was
  replaced by the power-law tail. Results: results/countdist_check_<snapshot>.csv.
