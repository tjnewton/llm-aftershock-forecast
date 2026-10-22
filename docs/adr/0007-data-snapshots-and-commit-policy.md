# ADR 0007: Data snapshots, look-ahead and what goes in git

Status: proposed.

## Decision
- Raw data are immutable. OAF versions are written once to `data/raw/oaf/<event>/<updateTime>.json`;
  mutable documents (event detail, catalogs) live under `data/raw/snapshots/<UTC id>/`.
  `data/manifest.jsonl` records URL, retrieval time, bytes, SHA-256 and licence per file.
  `laf verify` re-hashes every file.
- The scoring snapshot for the hackathon is the one taken on the morning of 2026-10-21; prompts
  and observations both come from it.
- The snapshot id is the catalog end time (`laf.cli.snapshot_ms`), so a resumed fetch issues
  identical queries.
- ComCat now holds revised magnitudes and locations and late
  additions that USGS did not have at issue time (Panama day-1 M>=5 count rose from 14 to 16).
  We quantify it by comparing each version's `observations` field with ComCat counts at the information cutoff
  (`issue_times.oaf_obs_m5`, `comcat_m5_at_cutoff`): Flores +2 to +8, Kamchatka +54 to +60,
  Panama +2 to +3 M>=5 events at issue time.
- Commit everything: raw (about 34 MB), manifest, processed parquet (about 3 MB). Total well under
  50 MB.
- Two USGS products had invalid JSON (trailing commas). They are repaired by removing only
  trailing commas, and the repair is flagged (`oaf_versions.repaired_json`). Seven Kamchatka
  versions have non-monotone fractiles; they are rejected, not repaired.

Update (2026-10-22): the exploratory E3 snapshot (`20261021T2300Z`), the live refetch
(`20261022T0001Z`), the E1/E1a training sets, outcome catalogs and literature queries are
committed the same way (raw files with manifest lines; about 100 MB of raw data in total). Not
committed: model weights, Adaption checkpoints and converted adapters (SHA-256 in
`runs/*-adaption/checkpoint.json` and docs/model-registry.md), and the 90 MB E1b preference-pair
file, which `laf outcome-training` rebuilds (its SHA-256 is in `runs/e1b-adaption/dataset.json`).
