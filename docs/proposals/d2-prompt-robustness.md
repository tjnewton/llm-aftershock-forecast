# Proposal: prompt and effort robustness study (D2)

Status: **proposal, needs Tyler's approval.** It covers the prompt wording (a science decision)
and a paid batch on development items. No prompt file changes until it is approved. After
approval the changes go through a pull request with `frozen-override` (`prompts/` is frozen)
and a `docs/deviations.md` entry.

## Why
The registered study used one prompt (two paraphrases) and one effort level. A referee will ask
whether the results depend on wording, catalog presentation or effort. ADR 0015 also adds M>=3
targets, so the forecasters must be asked for M3 quantiles. D2 settles these on development
items, and prereg v2 then freezes 2-3 variants.

## Changes common to every variant
1. **Ask for M3 quantiles.** Task text adds: "the same nine quantiles for magnitude 3.0 or
   larger". `schema_direct.json` adds `m3_count_quantiles` (same nine fields). The validator
   adds an `incoherent_magnitudes` check (M3 >= M4 >= M5).
2. **Catalog shown from M3.0** (was M4.0), so the forecaster sees the same events it is asked
   to forecast. The existing 800-row cap with the daily-count table stays.
   - Effect on prompt length: median rows rise. Large sequences (Kamchatka) hit the cap
     earlier and get the daily-count table.

## Variants
| Variant | Wording | Catalog presentation |
|---|---|---|
| A | current `p1` wording + M3 | event list (as now) |
| B | current `p2` paraphrase + M3 | event list |
| C | `p1` wording + M3 | **summary**: daily counts at M3/M4/M5/M6 since the mainshock and the 20 largest events (no full list) |

Effort: every variant at `high` (registered setting). Sonnet 5.5 also runs variant A at
`medium` to measure effort sensitivity.

C tests whether the answer depends on how the catalog is presented. It is information-poorer
(no individual small events), which is the point: a robust forecaster should not move much.

## Design and cost (development items only)
- **Items:** E3 post-cutoff, 99 items in 18 sequences. Direct arm, I1.
- **Calls:** k = 3 samples per item and variant; Claude Opus 5.5 and Sonnet 5.5 for all three
  variants, plus Sonnet at medium on A; Haiku 5.5 optional.
- **Cost estimate:**
  - Basis: mean tokens of the E3 runs (input 1,847; output Opus 1,123, Sonnet 947), batch
    price, plus 15% for the extra M3 field.
  - Per model: Opus 891 calls, about $15.3; Sonnet 891 + 297 calls, about $8.9; Haiku 891
    calls, about $0.9.
  - **Total about $25**. October so far: $64.32 of $200.
- **Analysis** (exploratory, development data):
  - Per variant: representation-matched log score vs official, and the between-variant spread
    per cell (SD across variants) compared with the between-sample spread within a variant.
  - Invalid-answer rates.
  - Coherence: M3 >= M4 >= M5, and the M3:M4 ratio against b-value scaling (about 10 per unit).

## Decisions requested
1. Add M3 quantiles to the direct arm, and show the catalog from M3.0. (Recommended: yes.)
2. Variants A, B and C as above. (Recommended: yes. An alternative to C is a plain-language
   framing, but the plan keeps naturalistic queries to an appendix.)
3. Approve the paid D2 batch: about $25 (Opus + Sonnet + Haiku, E3 post items).
