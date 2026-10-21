# Do LLMs forecast aftershocks like the USGS? A contamination-aware benchmark

Tyler Newton (solo). CRediT: conceptualization, data curation, software, formal analysis,
visualization, writing (T. Newton).

## Introduction

After a large earthquake, people ask chatbots how many more shocks to expect and how big they
might be. The US Geological Survey answers the same question with operational aftershock
forecasts (OAF), issued for US earthquakes since 2018 and for some large earthquakes abroad and
revised as each sequence unfolds; a prospective evaluation in Puerto Rico found its ETAS-based
forecast performed well. We asked whether
general-purpose language models, given exactly the information USGS had at each issue time,
forecast aftershock counts as well as the official product, and scored both with proper scoring
rules on sequences that began after the models' training cutoff.

## Results

We built every forecast question from ComCat and the archived OAF versions of eleven M≥7
sequences (July 2025 to October 2026): 61 issue times, each with 1-day, 1-week and 1-month
windows, and a prompt catalog rebuilt as ComCat stood at the issue time from its product
histories (the rebuild reproduces 95.1% of the official products' own observation counts).
Claude Haiku, Sonnet and Opus 5.5 answered 3,710 structured requests, either directly as nine
quantiles of the M≥5 count or as Reasenberg-Jones parameters, with and without the catalog. We
scored them against the observed counts with the log-scale quantile score, beside the official
forecast, a port of the USGS legacy-ETAS code refit at each issue time, and simpler baselines.
The hypotheses, cells and analysis were preregistered and frozen (tag `prereg-v1`, SHA-256
posted publicly) before any scored call, and the scoring code was frozen (`scoring-v1`) before
any result was read.

On the 33 settled cells of the post-cutoff sequences that have an official forecast (Colombia
and Flores Sea), Sonnet and Opus could not be distinguished from USGS at this scale: the pooled
score difference to the official forecast is −0.015 (95% block-bootstrap interval −0.081 to 0.017)
for Sonnet and −0.022 (−0.074 to 0.032) for Opus, with signs that differ between the two
sequences, while Haiku is worse than the official forecast (+0.057, 0.004 to 0.095; Figure 1).
Across all 132 primary cells the official forecast's central intervals are wide (50% intervals
cover 76% of outcomes, 90% intervals 92%); Sonnet's are closest to nominal at the 50% level (70%
and 92%), and Opus and Haiku are slightly narrow at 90% (87% and 85%). Asking for model
parameters instead of quantiles made every model worse (pooled differences +0.06 to +0.08), and
showing the catalog helped Sonnet (−0.042, −0.124 to −0.020) but not consistently the others.
Outputs were almost always usable: at most 2.7% of samples per model and arm were invalid
(non-monotone quantiles), with no refusals and no truncations. A fixed literature search
(Valency) found 23 papers about four of the eleven mainshocks, none available before any issue
time; only Kamchatka had papers dated before the Claude cutoff (12 of 18). Live forecasts for the ongoing
Panama sequence were hashed and published 46 minutes before their windows opened and will be
scored once the catalog settles. These are pilot-scale results: the headline rests on two
sequences, and per-sequence estimates, not significance tests, carry the claims.

![Figure 1](../figures/h1_vs_official.png)

*Figure 1. Score difference between each Claude model (direct quantiles, with the catalog) and
the USGS official forecast on settled post-cutoff cells; positive values favour USGS. Bars are
95% moving-block bootstrap intervals.*

## Future work

The benchmark grows prospectively with every new forecast-bearing sequence, which will turn the
pilot into a test with real power; we will add open-weight and tool-using models and test
whether adapted models trained on historical sequences approach the official forecast.

## Open-source materials

Code, data, prompts, preregistration and all model outputs:
https://github.com/tjnewton/llm-aftershock-forecast (tags `prereg-v1`, `scoring-v1`,
`live-panama-1`). Interactive results explorer and the frozen analysis notebook (marimo):
[EXPLORER LINK]. Literature search and citation checks: Valency MCP Bond. Video: [VIDEO LINK].

## References

1. Reasenberg, P. A. & Jones, L. M. (1989). Earthquake hazard after a mainshock in California.
   *Science* 243, 1173-1176. https://doi.org/10.1126/science.243.4895.1173
2. Hardebeck, J. L. et al. (2024). Aftershock forecasting. *Annu. Rev. Earth Planet. Sci.* 52,
   61-84. https://doi.org/10.1146/annurev-earth-040522-102129
3. van der Elst, N. J. et al. (2022). Prospective and retrospective evaluation of the U.S.
   Geological Survey public aftershock forecast for the 2019-2021 Southwest Puerto Rico
   earthquake and aftershocks. *Seismol. Res. Lett.* 93, 620-640.
   https://doi.org/10.1785/0220210222
4. Bosse, N. I. et al. (2023). Scoring epidemiological forecasts on transformed scales. *PLoS
   Comput. Biol.* 19, e1011393. https://doi.org/10.1371/journal.pcbi.1011393
5. Karger, E. et al. (2025). ForecastBench: a dynamic benchmark of AI forecasting capabilities.
   ICLR 2025. https://arxiv.org/abs/2409.19839
6. Zhu, W. (2026). Earthquake aftershock forecasting using conditional generative models
   (QuakeGen). https://arxiv.org/abs/2607.24109
