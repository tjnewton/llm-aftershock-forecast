# ADR 0006: Development and test split, contamination classes

Status: accepted. Roles follow outcome-blind
rules. Roles live in config/sequences.toml.

## Decision
Candidates: ComCat M>=7.0 mainshocks with origin 2025-07-01 to 2026-10-14
(docs/research/data-availability.md section 2), excluding foreshocks and aftershocks of a
larger listed event (inside its circle within a year).
- **test-post** (primary): every candidate from 2026-07-01: offshore Chiapas (2026-07-17, no
  OAF), Colombia (2026-08-10, OAF, 116 km deep), Flores Sea (2026-08-14, OAF), Panama
  (2026-10-09, OAF).
- **ambiguous** (secondary): every candidate in the cutoff month, June 2026: Sarangani,
  Venezuela (OAF; doublet with an M7.2 33 s earlier).
- **test-pre** (exploratory contrast): every candidate before June 2026 that has an OAF
  product: Sand Point (2025-07-16), Kamchatka (2025-07-29), Hubbard Glacier (2025-12-06).
- **dev** (prompt iteration for format and schema compliance only; never scored): Aomori
  (2025-12-08) and Sanriku (2026-04-20), pre-cutoff candidates without OAF.
- Other pre-cutoff candidates without OAF (Macquarie, two Drake Passage events, Philippines,
  Bitung, deep Malaysia, Tonga and Vanuatu events) are not used: no official baseline.
- Kumamoto (2026-07-28, M6.8) is below the magnitude rule and is dropped.

Contamination class is per model: a sequence is post-cutoff if its origin is after the end of
the model's documented training-data cutoff month; undocumented cutoffs count as pre-cutoff for
every sequence before the model's release. No contamination claim is made (prereg H5).

No sequence may be added or removed after the tag; new qualifying sequences enter a separate
prospective set.
