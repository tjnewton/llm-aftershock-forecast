# Analyst settings of the Venezuela and Colombia legacy-ETAS products

Forensics behind ADR 0010 section 4.1. Scripts run from the repository root with `uv run python
<script>`; they write their outputs next to themselves.

| File | What |
|---|---|
| `regime_dist.py`, `regime_dist_us6000t7zp_us6000tjl2.parquet` | per version x regime x timeDepMc: distance (posterior sd) between the published MAP and our MAP on the as-of catalog (41-point grids) |
| `exact_search2.py`, `exact2_us6000t7zp_1_35.parquet`, `exact2_us6000tjl2_0_72.parquet` | exact-MAP search over regime x grid x c range x the Mc at which prior and ranges were set |
| `fixed_c_dist.py`, `fixed_c01_dist.py`, `fixed_c_dist_colombia.parquet`, `fixed_c01_dist_colombia.parquet` | Colombia versions with c pinned at 0.003 or 0.1 (one-point c grid) |
| `lattice2.py` | which grids contain a block of published values |
| `config/analyst_settings.toml` | settings identified per version, as day-range rules |
| `v3_identified.py`, `v3_venezuela_identified.parquet`, `v3_colombia_identified.parquet` | V3 emulation with those settings (see ADR 0010 section 4.1 for the summary numbers) |
