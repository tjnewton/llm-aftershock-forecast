# Do LLMs forecast aftershocks like the USGS? A contamination-aware benchmark

Tyler Newton (sole author). CRediT: conceptualization, methodology, software, data curation,
investigation, validation, formal analysis, visualization, writing – original draft, writing –
review & editing.

## Introduction

Aftershocks kill: the 2011 M6.2 Christchurch aftershock killed 185 people five months after its
mainshock. People now ask chatbots how many aftershocks to expect, and the US Geological Survey
(USGS) answers the same question with operational aftershock forecasts [2, 3], a core task of
statistical seismology. I asked whether general-purpose language models, given exactly what USGS
knew at each forecast time, forecast as well. To my knowledge (arXiv and OpenAlex searches) this is
the first such test.

## Results

The obvious test, asking chatbots about past earthquakes, is contaminated twice: the models may
have read the answers, and today's catalog holds revisions no forecaster had at the time. I
removed both. Test sequences began after the models' training cutoff [5], and each prompt held
only the ComCat catalog as it stood at the forecast time, rebuilt from its revision histories (it
reproduces 95.1% of the official forecasts' own counts). Eleven M≥7 sequences (July 2025 to October
2026) gave 61 forecast times, each asking for the number of M≥5 aftershocks in the
next day, week and month. Claude Haiku, Sonnet and Opus 5.5 answered 3,710 requests, scored with the
log-scale quantile score [4] beside the official forecast, a validated Python port of the USGS
ETAS model and simpler Reasenberg-Jones baselines [1]. Hypotheses and analysis were frozen and their SHA-256 posted
publicly before any scored call (tag `prereg-v1`), and live forecasts for the ongoing Panama
sequence were hashed before their windows opened.

On the 33 settled windows of the two post-cutoff sequences with an official forecast (Colombia
and Flores Sea), Opus and Sonnet could not be distinguished from USGS (Opus: score difference
−0.022, 95% interval −0.074 to 0.032; negative favours the model), while Haiku was worse
(+0.124; Figure 1b). With only two earthquakes the test cannot tell these top forecasters apart:
the ETAS refit and even a naive rule of thumb (the aftershock count so far, extended with the
usual decay) also tie USGS. It does separate weaker forecasters: two open models run locally,
gpt-oss-20b and Olmo 3.1 32B, were far behind, with 12% and 54% of answers unusable against at
most 2.7% for Claude, and fine-tuning gpt-oss-20b on ETAS forecasts (Adaption) fixed the
format but not the skill (+0.14). The benchmark also tests the
official product: across all 132 settled windows, USGS's 50% ranges held 76% of outcomes, wider
than stated, and USGS and Opus both under-predicted the early Flores Sea aftershocks (Figure 1a).

![Figure 1](../figures/headline.png)

*Figure 1. (a) Forecasts of the number of M≥5 aftershocks in the next week after the M7.8 Flores
Sea earthquake, by USGS and Opus 5.5 (bands: 50% and 90% ranges; dots: observed). (b) Mean
score difference from USGS on the 33 preregistered windows (95% block-bootstrap intervals; left
of zero favours the forecaster).*

After the freeze I scored 39 more sequences with an official forecast (M≥5; exploratory, frozen
code). On the 18 after the Claude cutoff, Opus again matched USGS (+0.002, −0.002 to 0.007).
Claude did no better on the 21 before its cutoff, and the open models, trained before both sets, kept the same gap on both:
no sign of memorization.

## Impact and future work

Seismologists can use the as-of catalogs and the ETAS port to test any forecaster, including
machine-learning models and the official product, without hindsight; AI developers get a
benchmark that cannot be memorized and grows with every USGS forecast; emergency managers and
the public learn which chatbot answers to trust; learners can explore how probabilistic
forecasts work. Next: enough sequences to tell the top forecasters apart,
tool-using models that run ETAS themselves, and the same design for other hazard forecasts.

## Open-source materials

Code, data, prompts, preregistration and every model output (tags `prereg-v1`, `scoring-v1`,
`live-panama-1`, `live-panama-2`): https://github.com/tjnewton/llm-aftershock-forecast.
Interactive explorer (marimo): https://tjnewton.github.io/llm-aftershock-forecast/.
Video: https://youtu.be/qpPUB_VTlBY.

## References

1. Reasenberg, P. A. & Jones, L. M. (1989). Earthquake hazard after a mainshock in California.
   *Science* 243, 1173-1176. doi:10.1126/science.243.4895.1173
2. Hardebeck, J. L. et al. (2024). Aftershock forecasting. *Annu. Rev. Earth Planet. Sci.* 52,
   61-84. doi:10.1146/annurev-earth-040522-102129
3. van der Elst, N. J. et al. (2022). Prospective and retrospective evaluation of the U.S.
   Geological Survey public aftershock forecast for the 2019-2021 Southwest Puerto Rico
   earthquake and aftershocks. *Seismol. Res. Lett.* 93, 620-640.
   doi:10.1785/0220210222
4. Bosse, N. I. et al. (2023). Scoring epidemiological forecasts on transformed scales. *PLoS
   Comput. Biol.* 19, e1011393. doi:10.1371/journal.pcbi.1011393
5. Karger, E. et al. (2025). ForecastBench: a dynamic benchmark of AI forecasting capabilities.
   ICLR 2025. https://arxiv.org/abs/2409.19839
