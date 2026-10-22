# Data license

- `data/raw/`: unmodified downloads from the USGS ANSS Comprehensive Earthquake Catalog
  (ComCat) and USGS operational aftershock forecast products. U.S. public domain. Please cite
  the U.S. Geological Survey, ANSS ComCat (https://earthquake.usgs.gov/data/comcat/) and the
  USGS aftershock forecast products (https://earthquake.usgs.gov/data/oaf/).
- `data/processed/`, `prompts/` and benchmark items derived from them: Creative Commons
  Attribution 4.0 International (CC BY 4.0), https://creativecommons.org/licenses/by/4.0/.
- `data/raw/reference/opensha-oaf/`: unmodified resource files from the USGS operational
  aftershock forecasting code (https://github.com/opensha/opensha-oaf, commit 08a274bd),
  CC0 1.0.
- `data/raw/literature/`: search responses from the Valency MCP Bond literature index
  (bibliographic metadata: titles, authors, identifiers, dates), kept as the raw record of the
  E2 queries; the papers themselves are not included and keep their publishers' terms.
- `data/processed/training/` (E1 and E1a training sets): derived from ComCat and the
  legacy-ETAS refit, CC BY 4.0 like the other derived data.
- Not distributed: the Adaption fine-tuned checkpoints and converted adapters (fetch them with
  `laf adaption download --run <run>` given access), and the rebuildable E1b preference pairs.
- `data/manifest.jsonl` records the source URL, retrieval time (UTC), size and SHA-256 of every
  raw file.
