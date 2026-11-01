# ADR 0013: Development and confirmatory data (Seismica phase)

Status: **living document.** It describes the current rules; open decisions are marked and the
changelog at the end records changes. Preregistration v2 will copy the final version.

## Context
The hackathon analysis (prereg v1) rests on 11 registered sequences, and I have since looked at
the outcomes of 39 more (E3, ADR 0012) and of the historical adaptation pool. For a
confirmatory test, the sequences it uses must be ones whose outcomes nobody has scored while the
methods were still changing. Building code, prompts and baselines needs data whose outcomes can
be scored freely. This ADR says which data is which.

## Decision
- **Development data** (score freely, any number of times):
  - the 11 registered sequences (`config/sequences.toml`);
  - the 39 E3 sequences (`config/sequences_e3.toml`);
  - the historical adaptation sequences whose outcomes were used: the 515 E1 outcome catalogs
    (`data/raw/training/outcomes/`, 2010-01-01 to 2025-07-01). Sequences that appeared in the
    E1/E1a training sets only as prompt input (no outcome seen) are not development
    (decision 3 below).
- **Confirmatory data** (never scored against outcomes before the `prereg-v2` tag): every other
  sequence. That covers the OAF sequences not yet scored and every sequence of the prospective
  live arm. Default deny: a sequence id the code does not know as development is confirmatory.
- **Allowed on confirmatory data before the freeze**, because none of it uses outcomes:
  - fetching raw data;
  - as-of rebuilds and their validation against the official products' own observation counts;
  - building prompts;
  - running forecasters, and comparing forecasts with each other and with official products;
  - hindsight-catalog effects measured on the forecasts themselves (ADR 0016).
- **Not allowed before the freeze:** computing or displaying outcome counts in confirmatory
  forecast windows, scoring, or any plot or summary that uses them.
- **Adaptation:** a model adapted on data ending at date D is evaluated only on sequences with
  origin after D plus the buffer of ADR 0014.
- **Enforcement:** `laf.splits` (issue #2) checks outcome access in one place. `laf tables`
  writes sealed (null) counts for confirmatory sequences, and `analysis.cells` refuses them. The
  guard is a brake against accidents, not a proof: the raw catalogs on disk still contain the
  outcomes, so the human rule above is what matters.

## Candidate confirmatory set (outcome-blind facts)
Event list `data/raw/confirmatory/oaf_2024-01-01_2026-10-29.csv` (ComCat `producttype=oaf`,
retrieved 2026-10-29). In practice ComCat's OAF archive starts in November 2024
(`docs/research/data-availability.md`): the earliest event is 2024-11-14.

| | All | Registered | E3 | E1 outcome pool | E1a inputs only | Not yet used |
|---|---|---|---|---|---|---|
| Events with an OAF product | 254 | 7 | 39 | 3 | 1 | 204 |
| ... with M >= 5.0 | | | | | | 107 |
| ... with M >= 5.0 and origin from 2025-12-01 | | | | | | 26 |

Of the 204 not yet used:
- 128 are `us` network events and 76 are from US regional networks (nc 28, ci 13, nn 8, ak 7,
  tx 7, and others).
- 97 are below M5.0. They only carry information if the lower targets of ADR 0015 are used, and
  then only where the catalog is complete.
- 26 of the M>=5.0 events have origin from 2025-12-01, the period after the older Claude models'
  training cutoffs plus the buffer (ADR 0014).

The foreshock/aftershock rule of ADR 0006 is applied in config/sequences_confirmatory.toml (194
candidates): an event inside the Wells-Coppersmith circle of a larger event within 365 days is
dropped. The context is these OAF events plus ComCat M>=6 from 2023-11-01
(data/raw/confirmatory/m6_2023-11-01_2026-10-29.csv), as for E3 (`laf.e3.claimed`). Rechecked on
2026-10-31: 10 of the 254 OAF events are claimed, and none of them is a candidate.

nn00914068 (M5.68, 2026-04-14) was missing from the 194: it had been dropped for E3 because
ComCat would not return its full event document (`laf.e3.UNRETRIEVABLE`). It was retrieved on
2026-10-31 (2.8 MB, 53 OAF versions) and restored, making 195 candidates. Its outcomes stay
sealed (all 18,282 candidate counts are null), and its six issues have n_hindsight_m4 = 0.

## Decisions (Tyler, 2026-10-30)
1. **Start date:** the whole ComCat OAF archive, from 2024-11-14.
2. **Magnitude:** the primary set is M>=5.0 mainshocks. M>=3 targets are scored wherever the
   catalog is complete at M3 (ADR 0015). US-network mainshocks of M4.0-4.9 form a secondary set.
   Asking forecasters for M3 counts is a prompt change, approved separately.
3. **Training-pool overlap:** outcome exposure disqualifies, input exposure does not.
   - The three candidates in the E1 outcome pool are development: nc75095651 (M7.0, Cape
     Mendocino, 2024-12-05), us7000nzf3 (M7.3, Vanuatu, 2024-12-17) and us7000pn9s (M7.7,
     Myanmar, 2025-03-28).
   - us7000pllu (M6.2, south of Adak, 2025-03-21; E1a prompt input only) stays confirmatory.
   - Adapted models are scored only on sequences after their training data ends (2025-07-01)
     plus the buffer of ADR 0014.
4. **October 2026 events** (10, after the registered window closed on 2026-10-14) join the
   retrospective confirmatory set. Their windows had already opened, so they cannot be
   prospective.

## Known limitation: event matching uses today's mainshock
`laf tables` rejects an OAF version when its `magMain` differs from the mainshock magnitude by
more than 0.25, or its centre lies too far from the epicentre (ADR 0004). The comparison uses
today's ComCat values.
- In the candidate set this rejects 122 of 11,694 versions. 117 of the 119 magnitude
  rejections match the magnitude as ComCat showed it when they were issued: these are later
  revisions of 0.3-0.8 units, mostly in US-network M4-6 events.
- Checking against the as-of mainshock instead recovers 112 versions but rejects 19 others,
  because ComCat's index time lags the feed USGS uses. One of the 19 is a Colombia version in
  the registered analysis.
- The net gain is 13 of about 1,023 issue times, and the gained regions would need catalogs
  refetched with a larger query circle.

The rule stays as it is. The loss is about 1% of issue times; most are later versions of the
same targets, and the median first-issue latency is unchanged.

## The exclusion rule and future information (Tyler, 2026-10-31)
3 of the 10 excluded events were excluded only by a later, larger event, which can fall inside
their own forecast windows. They were counted without viewing their identities.
- The candidate list stays as built.
- Prospective sequences get only the backward (aftershock) half of the rule.
- Tests A, B and S1 are also reported with the 3 included, as a sensitivity analysis.

## The second gate (2026-11-01; prereg v2 section 5, ADR 0018 decision 11)
No confirmatory score or test is computed before S + 90 days, so the tag `prereg-v2` alone no
longer unseals. `laf.splits.unsealed` also needs the tag `prereg-v2-stop` on the commit that
records S (the live arm's stop time, epoch ms) in config/live_stop.toml, and the clock past
S + 90 days. S is read from the tagged commit, and the tag falls under the `freeze-tags` ruleset
(`prereg-*`). Live sequences are never development, so `laf live-score` refuses v2 records
until then; the Panama record (development) still scores.

## Changelog
- 2026-11-01: the second gate (`prereg-v2-stop`, S + 90 days).
- 2026-10-31: the forward half of the exclusion rule; prospective sequences use only the backward half.
- 2026-10-31: nn00914068 restored (195 candidates).
- 2026-10-31: the foreshock/aftershock rule is applied (rechecked; note corrected).
- 2026-10-29: first version; candidate list fetched; guard specified in issue #2.
- 2026-10-30: decisions 1-4 recorded; development set narrowed to outcome exposure
  (`config/splits.toml` drops the training-catalog folder).
