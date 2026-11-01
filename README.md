# live-test

Test records of the live publishing pipeline (`laf.publish`; prereg v2 section 5 and
docs/adr/0017-live-pipeline.md on `post-submission`). The detector's dry run pushes each sealed
record's seal file here exactly as the study will push to `live`, so the push receipt latency is
measured on the real mechanism while the `live` branch holds study records only.

- `<sequence id>/<OAF update ms>/answers.seal.json`: SHA-256 of the items and (empty, dry-run)
  model answers, and the seal time. Pushed before the baselines run.
- `<sequence id>/<OAF update ms>/baselines.seal.json`: SHA-256 of the pipeline's baselines.
- `*.ots`: OpenTimestamps proofs of each seal file, one per calendar, pending until Bitcoin
  confirms (`ots upgrade`, then `ots verify`, with the official client).

Nothing here is a forecast: the seal files hold hashes and times only. These are not official
forecasts and not study records.
