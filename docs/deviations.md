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
  further sequences (39 after one unretrievable event) with an official forecast, own config and snapshot, scored with the frozen
  code. Reason: the registered official-forecast comparison rests on two sequences. Effect: none
  on registered analyses; E3 results are reported as exploratory.
- 2026-10-22T00:05Z. Live round 2 for Panama (runs/live-panama-2, tag live-panama-2): the same
  procedure as live-panama-1 on a refetch (snapshot 20261022T0001Z); no newer official version
  existed, so the matched item repeats round 1's, and the strict item's windows open
  2026-10-22T01:00Z. Outputs SHA-256
  84b02c81f7870231aa321fc49cb0e06d1b7013de017cbb5b202bd8336e8b1079, hashed 00:05:19Z. No new
  M>=6 sequence with an OAF product appeared after 2026-10-14. Effect: none on registered
  analyses; prospective record only.
  The tag was created before a rebase onto a Windows status commit, so it points to
  781d2c8, a twin of main's 44ae96f with identical files (calls.jsonl SHA-256 as above); tag
  rules forbid moving it.
- 2026-10-22T04:50Z. E1a (exploratory): the E1 recipe on a larger training set (ComCat M>=6.0
  instead of 6.5, same years and rules: 1,505 sequences, 9,030 rows), AutoScientist with E1's
  best hyperparameters and one iteration (time). E1d (Olmo base) skipped: Adaption does not
  offer that model. Effect: none on registered analyses; descriptive only.
- 2026-10-22T04:50Z. Combined forecast (exploratory, rule fixed before scoring): equal-weight
  average of each Claude model's quantile-averaged valid samples and the official quantiles.
- 2026-10-22T10:20Z. E2 method on E3's six M>=6 sequences (data/raw/literature/e3/; one shared
  "Nikolski Alaska earthquake 2026" query for the three Nikolski events, from the earliest
  origin): no paper about any of these mainshocks (all matches weak and about other events), so
  the contamination covariate is zero for every E3 sequence screened.
- 2026-10-22T11:40Z. Adaption replicates (exploratory): two more runs on the E1 data (e1r1,
  e1r2; e1r2 on a re-upload of the same file, since Adaption allows one run per dataset at a
  time) and one more on the E1a data (e1ar2), all with E1's best hyperparameters and one
  iteration, so data size and run-to-run variation can be separated. Effect: none on
  registered analyses.
- 2026-10-22T11:40Z. Outcome-aware adaptation (exploratory; laf.outcome_training): outcome
  catalogs to day 60 for the 515 E1 training sequences (2010-2025, no benchmark sequence).
  Candidates are the ETAS refit transformed by a rate factor and a spread factor on the
  log(x + 1) scale, scored by the registered log-scale quantile score against realized counts.
  E1b: preference pairs (best candidate chosen, the untransformed refit rejected), Adaption
  alignment training. E1c: SFT on the single best global transform (recalibrated ETAS). The
  same fitted transform applied to the ETAS refit on benchmark cells is a non-LLM baseline
  (`etas_recal`), which separates recalibration from anything an LLM adds.
- 2026-10-22T12:05Z. Result of the recalibration fit: on the 3,090 E1 training items the best
  global transform of the ETAS refit is the identity (k = 1, s = 1; mean log-QS 0.323), so the
  refit is already calibrated within this family; the `etas_recal` baseline and E1c (SFT on it)
  would equal ETAS and E1 and were dropped. E1b uses five preference pairs per item (the best
  candidate against the untransformed refit, unless it is best, and the worst candidates),
  15,450 rows, because Adaption alignment needs at least 12,000; one iteration.
- 2026-10-22T17:05Z. Provisional scores of live-panama-1 (results/live-panama-1_provisional.csv)
  from a refetch at the hackathon deadline (snapshot 20261022T1700Z), for the 1-day windows that
  had closed (matched and strict; no M>=5 aftershock in either). Reason: the live windows settle
  after the hackathon. Effect: none on the registered analysis; settled scores replace these.
