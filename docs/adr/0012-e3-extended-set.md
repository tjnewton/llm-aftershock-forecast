# ADR 0012: E3 extended exploratory set

Status: accepted 2026-10-21 (after `prereg-v1` and `scoring-v1`; exploratory, logged in
docs/deviations.md).

## Context
The registered comparison with the official forecast rests on two sequences (Colombia, Flores
Sea). ADR 0006 sends new qualifying sequences to a separate set. USGS also issues OAF products
for many smaller US-region earthquakes, which can add sequences without touching the registered
roles.

## Decision
Candidates are ComCat events with an OAF product (`producttype=oaf`), magnitude >= 5.0:
- **e3-post** (role `test-post` in the E3 config): every candidate with origin 2026-07-01 to
  2026-09-30, after the Claude cutoff month.
- **e3-pre** (role `test-pre`): the 60 most recent candidates with origin 2026-01-01 to
  2026-05-31, before the Claude cutoff month (contamination contrast).
- Dropped: the 11 registered sequences, and any candidate inside the Wells & Coppersmith circle
  of a larger event within 365 days (ADR 0006 rule). Larger events are those with an OAF
  product or M >= 6.0 with origin 2025-01-01 to 2026-10-14.
- The magnitude floor is set from the candidate list's magnitudes only: smaller mainshocks
  almost never produce M >= 5 (or M >= 4) aftershocks, so their cells carry no information.

`laf e3-select` writes config/sequences_e3.toml (18 e3-post, 22 e3-pre; fewer than 60 pre-cutoff
candidates qualify) from raw event lists stored under data/raw/e3/ with manifest lines. The set
is fetched into its own snapshot with the registered pipeline and scored with the frozen
`laf.analysis` functions; runs live under runs/e3/, outside the registered analysis. Every E3
result is exploratory.
