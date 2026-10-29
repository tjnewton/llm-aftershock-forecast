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
  - the historical adaptation pool: every sequence in the E1/E1a training sets (2010-01-01 to
    2025-07-01) and the E1 outcome catalogs (`data/raw/training/outcomes/`).
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

The foreshock/aftershock rule of ADR 0006 has not yet been applied: candidates inside the circle
of a larger event within 365 days are dropped.

## Open decisions (Tyler)
1. **Start date.** Is the confirmatory set the whole archive from 2024-11-14, or a later start?
2. **Magnitude floor.** M>=5.0 as in E3, or lower (for example M>=4.0 in US networks), paired
   with M3 targets where Mc allows (ADR 0015).
3. **Overlap with the training pool.** Three M>=7 sequences from 2024-12 to 2025-03 are in the E1
   outcome pool, so they are development by the rule above. One M6.0-6.5 sequence is in the E1a
   inputs only (prompts and ETAS targets, no outcomes). My recommendation: treat outcome exposure
   as disqualifying and input exposure as not, except for adapted models (rule above).
4. **The October 2026 events.** There are 10, after the registered window ended on 2026-10-14.
   They could join the retrospective confirmatory set or seed the prospective set.

## Changelog
- 2026-10-29: first version; candidate list fetched; guard specified in issue #2.
