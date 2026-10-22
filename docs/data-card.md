# Data card: LLM aftershock-forecast benchmark

This card describes the registered scoring snapshot `20261021T1027Z`, taken on 2026-10-21 and
frozen with the preregistration, and, at the end, the data added after the freeze for the
exploratory extensions (docs/deviations.md).

## Sources and licence
| Source | Access | Licence |
|---|---|---|
| ANSS Comprehensive Earthquake Catalog (ComCat), FDSN event service `https://earthquake.usgs.gov/fdsnws/event/1/` | `query?eventid=<id>&format=geojson&includesuperseded=true`; `query?format=csv&latitude=..&longitude=..&maxradiuskm=..&minmagnitude=..&eventtype=earthquake&orderby=time-asc` | U.S. public domain |
| USGS operational aftershock forecasts (OAF), every version | `https://earthquake.usgs.gov/product/oaf/<id>/us/<updateTime>/forecast.json` | U.S. public domain |

Derived tables and prompts: CC BY 4.0 (data/LICENSE.md). Every raw file has a manifest line in
`data/manifest.jsonl` (URL, UTC retrieval time, bytes, SHA-256 of stored and of decoded bytes,
gzip flag, licence). `uv run laf verify` re-hashes every raw file (9,433 on 2026-10-22: the
snapshots, OAF versions, event histories, reference files, training catalogs and literature
queries) and re-validates every OAF file.

## Collection
- `uv run laf fetch` (snapshot 20261021T1027Z; resumed with `--snapshot`
  after truncated USGS responses): per sequence, the event document with superseded
  products; every OAF version not already stored; then a ComCat catalog for a circle centred on
  the epicentre with radius 1.5 x max over valid versions of (radius + centre offset) (or 1.5x
  the Wells & Coppersmith radius), from 30 days before to 90 days after the mainshock or to the
  snapshot time, at `catalog_min_mag` (2.5 for the Alaska sequences, 3.0 elsewhere). The count
  endpoint is checked first (limit 20,000). The snapshot id fixes the catalog end time, so a
  resumed fetch repeats identical queries.
- No personal identifiers are sent; User-Agent `laf-benchmark/0.1`; 0.5 s pause between requests.
- Size: raw 34 MB (event histories 19 MB), processed 2.8 MB.

## Sequences (roles by the outcome-blind rules of ADR 0006)
| Sequence (ComCat id) | Origin UTC | M (type) | Depth km | Role | Region | Valid OAF versions | Catalog rows | Issue times |
|---|---|---|---|---|---|---|---|---|
| Offshore Chiapas (us7000t1bu) | 2026-07-17 14:48 | 7.3 mww | 22 | test-post | W&C 110.4 km | none | 274 | 6 |
| Colombia (us6000tjl2) | 2026-08-10 12:34 | 7.4 mww | 116 | test-post | OAF 125.4 km | 21 of 24 | 88 | 6 |
| Flores Sea (us6000tkt2) | 2026-08-14 21:58 | 7.8 mww | 10 | test-post | OAF 227.8 km | 30 of 34 | 499 | 6 |
| Panama (us6000u18k) | 2026-10-09 17:56 | 7.7 mww | 13 | test-post | OAF 381.6 km | 12 of 13 | 138 | 4 |
| Sarangani (us7000srb1) | 2026-06-07 23:37 | 7.8 mww | 57 | ambiguous | W&C 217.8 km | none | 547 | 6 |
| Venezuela (us6000t7zp) | 2026-06-24 22:05 | 7.5 mww | 10 | ambiguous | OAF 145.2 km | 36 of 45 | 28 | 5 |
| Sand Point (us7000qd1y) | 2025-07-16 20:37 | 7.3 mww | 38 | test-pre | OAF 65.6 km | 77 of 77 | 1,031 | 6 |
| Kamchatka (us6000qw60) | 2025-07-29 23:24 | 8.8 mww | 35 | test-pre | OAF 1076.8 km | 61 of 80 | 3,748 | 4 |
| Hubbard Glacier (us6000rsy1) | 2025-12-06 20:41 | 7.0 mww | 10 | test-pre | OAF 60.0 km | 68 of 68 | 1,080 | 6 |
| Aomori (us6000rtdt) | 2025-12-08 14:15 | 7.6 mww | 41 | dev | W&C 166.0 km | none | 274 | 6 |
| Sanriku (us6000sri7) | 2026-04-20 07:52 | 7.4 mww | 25 | dev | W&C 126.5 km | none | 195 | 6 |

"Valid" excludes schema failures, wrong-event versions and duplicate information cutoffs. Sand
Point and Hubbard Glacier use Reasenberg-Jones (US products); the others are ETAS. Place
strings in prompts are the preferred origin product's title (for example "66 km NNW of Ende,
Indonesia"), never the post-hoc event name ComCat gives notable earthquakes.

## Reference data (ADR 0009)
`data/raw/reference/opensha-oaf/08a274bde278/`: four unmodified resource files from the USGS
operational aftershock forecasting code (`opensha/opensha-oaf`, CC0, commit 08a274bd,
2026-10-14), retrieved from raw.githubusercontent.com: generic RJ
parameters per tectonic regime, the Page et al. (2016) table, the Garcia et al. (2012)
regime grid (0.05 degree) and completeness parameters per region. Each sequence's regime and
parameters are in `sequences.generic_*` and `sequences.magcomp_*`.

## Tables (`data/processed/<snapshot>/*.parquet`)
| Table | Grain | Key columns |
|---|---|---|
| `sequences` | sequence | `sequence_id, role, origin_ms, mag, mag_type, lat, lon, depth_km, region_*, n_oaf_versions, catalog_end_ms, generic_regime, generic_a_mean, generic_a_sigma0/1, generic_a_min/max, generic_b, generic_p, generic_c_days, magcomp_region, magcomp_mcat, magcomp_F/G/H` |
| `oaf_versions` | product version | `update_ms, valid, error, repaired_json, duplicate, creation_ms, time_start_ms, info_cutoff_ms, window_offset_min, late_post_hours, model, mc, sim_min_mag, region_*, obs_m3..obs_m8` |
| `forecast_bins` | version x window x magnitude bin | `info_cutoff_ms, window, magnitude, time_start_ms, time_end_ms, probability, median, p95minimum, p95maximum` |
| `forecast_fractiles` | version x window x bin x fractile | `info_cutoff_ms, window, magnitude, p, count` (1.96 M rows) |
| `issue_times` | selected issue time | `issue_id = <seq>@<target>, target, issue_ms, source (oaf/schedule), creation_ms, elapsed_days, region_*, mag_main, oaf_obs_m5, comcat_m5_at_cutoff, catalog_source (asof/hindsight), query_covers_x1_5, oaf_mc, oaf_b, oaf_ams, oaf_a, oaf_p, oaf_c, oaf_sim_min_mag` |
| `observed_counts` | issue x window x threshold | `window, magnitude in {3,4,4.5,5,6,7}, time_start_ms, time_end_ms, count, closed, days_since_close` |
| `catalog` | ComCat event | `id, time_ms, latitude, longitude, depth, mag, magType, status, t_days, dist_km` |
| `issue_catalogs` | issue x visible event | events with `time_ms < issue_ms`, from 7 days before the mainshock, inside the scoring circle, as ComCat showed them at the issue time (`catalog_source = asof`, ADR 0011): magnitudes and locations then, events not yet posted left out |

All times are epoch milliseconds UTC; windows are half open, `[start, end)`.

## Quality findings (all handled in code and covered by tests with real files)
1. **Windows can start before `creationTime`.** Window start minus creation ranges from
   -10,027 min (Kamchatka re-post) through -6 h (Flores) to +877 min (Colombia). Issue time is
   therefore min(creationTime, timeStart) (ADR 0004).
2. **Wrong-event products.** Kamchatka's first `oaf` product contains a Myanmar forecast created
   two days before the Kamchatka mainshock; Flores' first contains the Colombia forecast.
   Venezuela versions 1-6 are forecasts for the M7.2 foreshock 33 s before the M7.5 (magMain
   7.2), and four of them are also centred about 142 km away. All are rejected
   (`Forecast.event_mismatch`: creation before origin, centre offset, or magMain differing from
   the mainshock by more than 0.25).
3. **Invalid JSON.** Two Kamchatka versions (2025-07-31) contain trailing commas; repaired by
   removing trailing commas only, flagged `repaired_json`.
4. **Non-monotone fractiles.** Seven Kamchatka versions have fractile[0] > fractile[1] in the
   1-Month or 1-Year bins (for example 3904 then 3112); rejected.
5. **Display rounding.** In 2025 products `median` and `p95*` are rounded to two significant
   figures (Kamchatka M3 fractile 534 shown as 530); 2026 products are exact. Scoring uses
   `fractileValues` only.
6. **FDSN time precision.** `starttime` is truncated to whole seconds, so a query from
   mainshock + 1 ms still returns the mainshock. All window counts are filtered locally in ms.
7. **Catalog revisions.** Panama day-1 M>=5 count (OAF circle) was 14
   (research notes) and is 16 in this snapshot. Prompts and observations both come from one snapshot,
   and revisions since issue time are quantified via the `observations` field.
8. **`observations` lacks M4 in some products** (Panama v1 reports M3, M5, M6, M7 only).

## Catalog advantage at issue time (M>=5 in the scoring circle, OAF issues)
`comcat_m5_at_cutoff - oaf_obs_m5`: Flores +6/+4/+6/+8/+7/+2 (first/1d/3d/7d/14d/28d); Kamchatka
+60/+60/+56/+54 (first/1d/3d/14d); Panama +3/+3/+3/+2; Colombia, Sand Point, Hubbard Glacier and
Venezuela between -1 and +1. The LLM and refit baselines see the larger (revised) catalog; the official
forecast did not.

## Scored cells available (M>=5, this snapshot; generated by code)
61 issue times (test-post 22, test-pre 16, ambiguous 11, dev 12).
Primary rule (window closed >= 21 days before the snapshot): test-post 51 (Chiapas, Colombia,
Flores; Panama 0), test-pre 48, ambiguous 33; dev 36 are never scored. With 2-day settling:
test-post 60 (Panama 6). P(M>=6) positive cells under the primary rule: test-post 0,
test-pre 17, ambiguous 11. This is a pilot-scale sample.

## Derived baseline: legacy-ETAS refit (ADR 0010)
`etas_forecasts.parquet`: one row per issue x window with M>=5 quantiles at the nine levels,
P(M>=6), mean, M>=5 count histogram (10,000 simulated catalogs), MAP and posterior summaries,
Mc, b, regime, minimum simulated magnitude and its source (`official`: revealed by the matched
product's fractiles; `rule`: code rule by date), capped share and seed (20261021 + crc32 of the
issue id). Built by
`uv run laf etas --snapshot S` in under 2 minutes for all 61 issues.
`etas_forecasts_hindsight.parquet`: the same refit on today's catalog (catalog effect).
`etas_forecasts_analyst.parquet`: labelled sensitivity variant with the analyst settings
inferred for the Colombia and Venezuela products (`config/analyst_settings.toml`; column
`settings`; ADR 0010 section 4.1). `etas_validation.parquet`:
the V2 re-simulations of official versions from their published parameters, with the official
M>=5 fractiles, `ratio` and `ok` (`uv run laf etas --snapshot S --validate` exits 1 below 0.80).
`sim_min_mag` (`oaf_versions`) and `oaf_sim_min_mag` (`issue_times`): the legacy-ETAS minimum
simulated magnitude a product reveals when it lies above the lowest bin (its fractiles are then
10^(b (minMag - M)) times integers). Kamchatka: 5.8 (50 versions, 2025) and 4.8 (22, 2026);
one Panama version 3.7; none elsewhere. When minMag > 5 (Kamchatka), the refit's M>=5 quantiles,
mean and histogram are scaled the same way (ADR 0010 section 3.6).

## As-of catalog (ADR 0011)
`raw/events/<id>.geojson.gz`: every product version of each catalog event near a mainshock
(`laf asof --snapshot S`, paced at 1 request/s for ComCat's 500-per-5-minute limit). The as-of
catalog at time T keeps, per event, the preferred origin among the versions indexed by T; it
reproduces the official products' own observation counts in 95% of 674 checks (69% for today's
catalog; V0, ADR 0011). Coverage (4,691 events): every event of the four 2026 ETAS sequences to
+90 days; Kamchatka above current M2.9 to day 16 and above M4.9 to day 90; the other sequences
above M2.9 to one day after their last issue time. Events without a history keep their current
origin (`issue_catalogs.from_hindsight`; none at M >= 4 in any prompt). Outcomes stay on the
snapshot's current catalog.

## Validation outputs (`runs/etas_validation/<snapshot>/`, `runs/java_differential/`)
`laf etas-validate --snapshot S` writes V0 (`v0_observations.parquet`), V3 emulation of every
official legacy-ETAS version (`v3_versions/bins/compare.parquet`), the USGS Java differential
(`java_fits.csv`, `java_cells.parquet`; archived Java inputs, logs and outputs, user paths
scrubbed) and synthetic recovery (`recovery.parquet`). `laf.etas_validate.sensitivity` writes
the sensitivity runs (`sensitivity.parquet`); `v1_exact.py` prints the V1 exact-MAP counts.
Results: ADR 0010 sections 4-5.

## Known limitations
- `catalog` is ComCat as of the snapshot, not the catalog USGS saw at issue time (finding 7);
  `issue_catalogs` is rebuilt as of each issue time instead (ADR 0011). Deleted events are not
  reconstructed.
- International ComCat is incomplete below about M4.5, and much worse in the first hours.
- Region circles differ between versions of one sequence; each issue is scored in its own circle.
- Sequences without OAF have no official baseline and use an approximate W&C circle.
- USGS legacy-ETAS `probability` is 1 - (share of simulated catalogs at the smallest count), which falls slightly below 1 when every catalog has an M>=6; values are scored as published (6 of 111 scored M>=6 values are >= 0.99).

## Data added after the freeze (exploratory)
Fetched with the same code and stored the same way (raw files with manifest lines); none of it
changes the registered snapshot or its scores.

| Data | Location | Contents |
|---|---|---|
| E3 snapshot `20261021T2300Z` | `config/sequences_e3.toml`, `data/raw/snapshots/20261021T2300Z/`, `data/processed/20261021T2300Z/` | 39 sequences with an official forecast, M >= 5 (18 after the Claude cutoff, 21 before; docs/adr/0012-e3-extended-set.md); 630 cells, 536 settled; the as-of catalog rebuild reproduces 97.6% of 4,563 checkable official observation counts |
| E3 candidate lists | `data/raw/e3/` | ComCat event lists with OAF products and the M >= 6 context list used for the fore/aftershock rule |
| Live Panama refetch | `data/raw/snapshots/20261022T0001Z/` | Panama event, catalog and OAF versions for live round 2 |
| E1 training set | `data/raw/training/`, `data/processed/training/e1_train.jsonl` | 515 ComCat M >= 6.5 sequences, 2010-01-01 to 2025-06-30, 3,090 prompt/completion rows; completions are legacy-ETAS refits; SHA-256 b72a83a6db55895c5f60b269bd2f5ed3e5ee2084e773162533e635e3920b0948 |
| E1a training set | same, `e1a_train.jsonl` | 1,505 M >= 6.0 sequences, 9,030 rows; SHA-256 3ee98483493babcb9f70fc09827aa2a156de16c4fb3bad7c7b53975512543cce |
| Outcome catalogs | `data/raw/training/outcomes/` | the E1 sequences' catalogs to day 60, for the E1b preference pairs (`laf outcome-training`; the 90 MB pairs file is rebuilt, not committed) |
| Literature queries (E2) | `data/raw/literature/`, `data/raw/literature/e3/`, `config/literature_screen.csv` | exact Valency search responses (bibliographic metadata) and the screening decisions |

No training sequence is a benchmark sequence: every training origin is before 2025-07-01.
