# Deviations from preregistration v1 (tag prereg-v1)

Each entry: UTC time, change, reason, expected effect on the registered analyses.

- 2026-10-21T17:44Z. E2 literature queries keep only papers first available on or after each
  mainshock's origin date (Valency `start_date`). Reason: earlier papers cannot be about that
  mainshock. Effect: none on counts of relevant papers.
- 2026-10-21T20:43Z. E1 adapted-model runs are written to runs/extensions/, outside the
  registered forecasters' invalid-sample penalty pool. Reason: E1 is a descriptive extension
  (section 11), not a registered forecaster. Effect: registered scores are unchanged by E1.
- 2026-10-21T23:00Z. API budget raised by Tyler to about $200 total; runner spend guard 140 ->
  195 USD and spend accounting now includes nested run folders. Effect: none on scoring.
- 2026-10-21T23:00Z. E3 extended exploratory set (docs/adr/0012-e3-extended-set.md): 40
  further sequences with an official forecast, own config and snapshot, scored with the frozen
  code. Reason: the registered official-forecast comparison rests on two sequences. Effect: none
  on registered analyses; E3 results are reported as exploratory.
