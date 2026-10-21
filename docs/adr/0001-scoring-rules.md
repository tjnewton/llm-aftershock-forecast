# ADR 0001: Scoring rules

## Context
Every forecaster (LLM arms, the official USGS forecast, refit baselines) is reduced to the same
representation: count quantiles at fixed levels, plus P(at least one M>=6). The official
forecast publishes 399 (ETAS) or 197 (Reasenberg-Jones) count fractiles, so it can be scored
without rerunning the USGS model. Counts span 0 to hundreds (Kamchatka), so natural-scale
interval scores would be dominated by the largest sequence.

## Decision
- Quantile levels K = {0.025, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.975}. All nine exist
  exactly in both official fractile grids (step 0.0025 and 0.005), so no interpolation.
- **Primary score: quantile score on the log scale**, QS = (1/9) * sum_k 2 * rho_tau_k(log(y+1) -
  log(q_k+1)), with pinball loss rho_tau(u) = u * (tau - 1{u<0}). This equals the weighted
  interval score over the 50/80/90/95% intervals plus median (Bracher et al. 2021) up to a
  constant, and the log transform follows Bosse et al. (2023). Lower is better. Proper.
- Secondary scores: the same QS on the natural scale; empirical coverage of the central 50, 80,
  90 and 95% intervals (always beside the official's and RJ-MLE's coverage); quantile-resolution
  randomized PIT histograms (rank of y among the nine quantiles, ties broken uniformly, bar heights
  divided by bin width), plus full-resolution randomized PIT (Czado et al. 2009) for forecasts
  with full fractiles (official, baselines, parameter arm); Brier score for
  P(N(M>=6) >= 1); log score for that probability with p clipped to [0.001, 0.999].
- Exploratory only: negative-binomial log score, with the NB fitted to the nine quantiles by
  minimum QS.
- Invalid samples: scored with the worst log-QS of any forecaster in the cell (prereg section 7).
- Skill: per cell, dQS = QS(model) - QS(reference). Reference is the official forecast where it
  exists and the RJ-MLE refit everywhere (docs/PLAN.md section 5).
- No LLM-as-judge anywhere. All scores are pure functions with closed-form unit tests.

## Consequences
pyCSEP's consistency tests target gridded or catalog forecasts; count-quantile scoring here is
custom code. pyCSEP's Brier implementation may be used as a cross-check in tests.
