# Proposal: behavioral probes (D1)

Status: **approved by Tyler on 2026-10-30** (all four recommendations: explicit adaptive thinking
on the 4.6 models, probes P1 to P4, Opus 4.6 and Sonnet 4.6 plus Opus 5.5, the pilot now and the
batch after it). The prompts stay as they are (v2A from D2), so no frozen file changes. Code:
`laf.d1` and `laf d1 build|pilot|run`.

Implementation notes (no change to what is measured):
- P1's Δ = 0 level is the P2 item at 1 day, and P4's decaying pattern is the P3 N = 10 item.
  The prompts would be identical, so they are built once: 17 items per base sequence, 306 in
  all, 612 calls per model (the cost estimate below assumed 684).
- Synthetic catalogs start with the mainshock row, as real catalogs do. Their magnitudes are the
  Gutenberg-Richter quantiles (i + 0.5) / N in random order, so the M4+ share does not vary by
  chance between levels. Times are kept at least 86 s after the mainshock.

## Why
Scores say how good a forecast is, but not how the model produced it. A referee will ask
whether an LLM that ties the official forecast applies aftershock physics or matches surface
patterns. D1 changes one input at a time and checks whether the forecast moves the way the
established laws say it should:
- **Productivity:** about 10 times more aftershocks per unit of mainshock magnitude (in the
  Reasenberg-Jones (RJ) model the expected count scales as 10^(b(Mmain - M)), b about 1).
- **Omori decay:** the aftershock rate falls as (t + c)^-p with p about 1, so a window that
  starts later holds fewer events.
- **Sequence-specific updating:** a sequence that has produced more aftershocks than usual so
  far should get a higher forecast, as the RJ Bayesian update does.
- **Gutenberg-Richter across thresholds:** M3, M4 and M5 counts in a ratio of about 10 per
  magnitude unit. Every answer gives this for free.

No answer is scored against what happened, so the probes need no outcomes.

## Base items
The 18 E3 post-cutoff mainshocks from D2 (M5.0 to 6.5, 2026-07-14 to 2026-09-23; Alaska, Marianas, Guam, Texas, Oregon).
They are after every model's training cutoff, so no model can recall the real sequence, and a
changed mainshock does not conflict with memory. Prompt v2A, direct arm, as in D2.

These sequences produced few aftershocks (most lists hold 0 to 8 events at M3), so the
catalog probe uses synthetic catalogs with a controlled productivity.

## Probes
| Probe | Changed | Held fixed | Levels | Catalog |
|---|---|---|---|---|
| P1 magnitude | mainshock magnitude, by Δ | place, issue time, windows, region radius | Δ = -1, -0.5, 0, +0.5, +1 | none (I0) |
| P2 elapsed time | issue time after the mainshock (windows start at the issue) | magnitude | 1 h, 6 h, 1 d, 3 d, 10 d, 30 d | none (I0) |
| P3 productivity | synthetic catalog up to day 3 with exactly N events at M3 or larger | magnitude, issue time | N = 0 (empty list), 1, 3, 10, 30, 100 | synthetic list (I1) |
| P4 time pattern (optional) | the same 10 synthetic events with Omori-decaying times or times spread evenly over the 3 days | count, magnitudes | decaying, even | synthetic list (I1) |

- Synthetic catalogs: the count N is fixed, not drawn, so every level has the count it names
  (a Poisson draw at low productivity is often empty). Given N, the times are a seeded draw
  from the region's generic Omori-Utsu density over the 3 days, magnitudes from
  Gutenberg-Richter with the region's b, and distances and depths around the mainshock. Each
  catalog is written once and committed, so the items can be rebuilt exactly.
- P3 at N = 0 against P2 at 3 days separates "no aftershocks were recorded" from "no list was
  given".
- k = 2 samples per item, as a check on within-condition noise (D2 found it small).

## Measures and references
Each forecast becomes a count distribution through its nine quantiles (latent PCHIP,
ADR 0015). For the probe statistics, the upper tail beyond the 97.5% quantile is
negative-binomial shaped (`laf.countdist.from_quantiles(..., tail="nb")`). The default
power tail can have an infinite mean: eight zero quantiles and a 97.5% quantile of 2 give a
tail exponent of about 0.97, below the 1 a finite mean needs. The negative-binomial tail
decays geometrically, so every mean is finite. As a check, the same slopes are computed from
E[log(1 + N)] under the default power tail, which is finite for any tail exponent above 0.
Scoring elsewhere keeps the default tail.

The reference is what the statistical models do with the same input, computed locally at no
cost:

| Probe | LLM measure | Reference |
|---|---|---|
| P1 | slope of log10 mean count on Δ, per target magnitude and window | generic RJ, same statistic (analytic slope b, about 1.0, for context) |
| P1 | P(M6+) at each Δ and window | generic RJ P(M6+) at the same Δ (it saturates as the expected count grows, so its slope is not b) |
| P2 | implied Omori p: fit of log mean count against the RJ window integral, c fixed at the generic value | generic RJ, same statistic (the region's generic p for context) |
| P3 | elasticity: slope of log mean forecast on log N (N >= 1); N = 0 reported on its own | Bayesian RJ update on the same catalogs (below) |
| P4 | ratio of the even-pattern forecast to the decaying one | Bayesian RJ update on each catalog |
| all | M3:M4:M5 ratios (implied b); spread, log(1 + 97.5% quantile) - log(1 + 2.5% quantile) | the same spread of the RJ reference |

- **Bayesian RJ update (P3, P4).** The MLE fit in `laf.forecast.fit_rj_mle` needs at least 10
  events at M5, so it is undefined on most synthetic catalogs. The reference is instead a grid
  posterior: the region's generic prior on a, b and c at their generic values, p uniform on
  [0.5, 2.0], and the Omori-Utsu point-process likelihood of the M3 events before the issue
  (the synthetic catalogs are complete at M3 by construction). It is defined for any count,
  including an empty list, where only the integral term remains. Through p it also responds
  to the time pattern in P4; with p fixed, the posterior would depend on the count alone.
- **Same representation for the references (ADR 0015).** Every reference measure is computed
  from the RJ forecast's own nine integer quantiles, passed through the same latent-PCHIP
  reconstruction as the LLM answers. Small counts make this necessary: Poisson means from
  0.0001 to 0.01 all have nine zero quantiles and one reconstructed mean, so an answer that
  follows RJ exactly would show a zero slope against the analytic b. The analytic b and p are
  shown for context only. Conditions where the reference's nine quantiles are all 0 carry no
  slope information; their share is reported. P(M6+) is answered directly, so it needs no
  reconstruction.
- **Spread.** The 2.5% quantile is often 0 for these small counts (7,856 of 8,019 quantile
  sets in the D2 Opus answers), so the spread uses log(1 + q) rather than log q.

Intervals come from a bootstrap over the 18 base sequences. The results are exploratory and
reported as such.

## Models and thinking
The probes describe the models the confirmatory claims rest on: `claude-opus-4-6` and
`claude-sonnet-4-6` at effort `high` (ADR 0014). `claude-opus-5-5` runs the same probes as a
bridge to D2 and the registered study. The OpenAI models follow once their runner exists, with
their spend tracked separately.

**Finding that needs a decision.** ADR 0014 says the 4.6 models take the same request shape as
the 5.5 models. They accept the same fields, but a missing `thinking` field means different
things. On the 5.5 models it runs adaptive thinking. On Opus 4.6 and Sonnet 4.6 it runs with
no thinking (Claude API model migration notes). The current request shape would therefore run
the 4.6 models without reasoning, while the 5.5 models reason.
- Recommended: send `thinking: {"type": "adaptive"}` explicitly on the 4.6 models and leave the
  5.5 requests as they are (adaptive is already their default). The setting goes into ADR 0014
  and prereg v2, and it applies to the confirmatory runs too.
- Alternative: thinking off on the 4.6 models. It is cheaper, but it compares reasoning 5.5
  models with non-reasoning 4.6 models.

## Cost
- **Calls per model:** P1 180, P2 216, P3 216, P4 72; 684 in total (612 without P4).
- **Tokens per call:**
  - Basis: D2 means were 2,071 input tokens; output 1,317 for Opus 5.5 and 1,165 for Sonnet 5.5.
  - Assumed here: 2,500 input and 1,500 output. I0 prompts are shorter, and P3 at N = 100 is
    longer.
  - The 4.6 models use the older tokenizer (about 30% fewer tokens for the same text). Their
    thinking length at `high` is unknown, so the estimate keeps the 5.5 output length.
- **Batch prices** (Anthropic pricing page, per million tokens, input / output): Opus 4.6
  $2.50 / $12.50; Sonnet 4.6 $1.50 / $7.50; Opus 5.5 $2 / $10.

| Model | Per call | 684 calls |
|---|---|---|
| Opus 4.6 | $0.025 | $17.1 |
| Sonnet 4.6 | $0.015 | $10.3 |
| Opus 5.5 | $0.020 | $13.7 |
| **Total** | | **about $41** (about $27 for the 4.6 pair alone) |

- **Pilot first:** 6 synchronous calls per 4.6 model, one per probe, for under $0.50. The pilot
  measures thinking output and checks that structured outputs validate with adaptive thinking.
  The batch guard is then set at 1.5 times the revised estimate.
- **Budget:** October so far is $89.56 of $200. D1 would most likely run in November.

## Code needed after approval
- `laf.providers`: prices and the thinking setting for the 4.6 models. Not a frozen file.
- `laf.d1`: probe item builders (perturbed mainshock, shifted issue time, synthetic catalogs),
  the Bayesian RJ reference, a runner block, the analysis, and tests. It reuses `laf.forecast`
  (frozen) read-only.

## Decisions requested
1. Thinking on the 4.6 models: explicit adaptive (recommended) or off. The choice also applies
   to the confirmatory runs.
2. Probes P1 to P3 as above, and P4. (Recommended: include P4; it costs about $5.)
3. Models: Opus 4.6 and Sonnet 4.6, plus Opus 5.5 as the bridge. (Recommended: yes.)
4. Approve the spend: the pilot (under $0.50), then the batch (about $41, guard at 1.5 times
   the estimate after the pilot).
