# Prompts v0 (DRAFT, not yet run)

Templates use Python `string.Template` (`${name}`) so rendering needs no dependency and fails
loudly on a missing field (`Template.substitute`). The rendered request is

    system = system_p{1,2}.txt
    user   = user_context.txt (+ catalog_section.txt or catalog_none.txt) + task_{arm}_p{1,2}.txt
    output = schema_{arm}.json via output_config.format (Claude) or response_format (llama.cpp)

| Factor | Levels | Files |
|---|---|---|
| Arm | `direct` (count quantiles + P(M>=6)), `params` (Reasenberg-Jones a, b, p, c; code computes the forecast) | `task_direct_*`, `task_params_*`, `schema_*` |
| Information | `I1` mainshock + catalog to the information cutoff; `I0` mainshock only | `catalog_section.txt`, `catalog_none.txt` |
| Paraphrase | `p1`, `p2`: same content, different wording and order | `system_p*`, `task_*_p*` |
| Probe | closed-book recall of the real sequence (memorization check) | `probe_recall.txt`, `schema_probe.json` |

## Design rationale
- **Same information as USGS at the issue time:** mainshock origin, magnitude, depth and place;
  the forecast circle; ComCat events up to the information cutoff (ADR 0004). The prompt never
  shows USGS forecast numbers, parameters, Mc or the official region radius as "official".
- **Place names and dates are shown** because USGS forecasts use them and a user would give them.
  This makes recall possible, which is what the pre/post-cutoff contrast and the recall probe
  measure. An anonymized variant (no names, relative dates) is a stretch goal.
- **Catalog format:** CSV `t_days,utc_time,mag,mag_type,depth_km,dist_km`, events M>=4.0 from 7
  days before the mainshock to the cutoff (median 39 rows; maximum 759 at Kamchatka 14 d). If
  more than 800 rows, keep the 800 most recent and add a daily count table at M>=4/5/6 for the
  full span; `truncation_note` says so.
- **Quantiles as named integer fields** (`q025` ... `q975`): the structured-output schema cannot
  enforce array length or numeric ranges (`minItems` 0/1 only; no `minimum`), so ranges,
  monotonicity and coherence are checked after parsing (docs/PLAN.md section 4.4).
- **Parameter arm** separates seismological knowledge from arithmetic: the model supplies a, b,
  p, c and a 90% interval on a; `laf.forecast.rj_predictive` integrates the rate and mixes
  Poisson counts over a ~ Normal(a_p50, (a_p95 - a_p05)/3.29). P(M>=6) and M>=4 counts follow
  from b.
- **No anchoring examples, no worked numbers** in any prompt. The `notes` field is last so the
  numbers are not conditioned on a long written rationale; it is capped at two sentences.
- **Scoring is explained to the model** ("proper scoring rule", too narrow and too wide both
  lose), as a well-specified elicitation should.

## Freezing
`laf prompts hash` (event-day task) writes `prompts/HASHES.json`: SHA-256 of every template and
schema. The preregistration records these hashes; any change after the tag is a deviation.
Only the dev sequences (Aomori, Hubbard Glacier) may be used to iterate before the freeze.
