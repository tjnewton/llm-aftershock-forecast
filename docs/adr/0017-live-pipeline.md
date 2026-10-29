# ADR 0017: Live (prospective) forecasting pipeline (C1)

Status: **living document, proposed.** Not built yet. It goes live only after the prereg v2
freeze, which is Tyler's call.

## Purpose
Prospective forecasts cannot be contaminated by training data or by hindsight. Each forecast is
committed, with a public hash, before its windows open. The live arm complements the
retrospective arms (ADR 0013).

## Design
- **Host:** a scheduled GitHub Actions workflow. Scheduled workflows run only from the default
  branch, so the workflow starts after hackathon judging ends. Until then the Windows machine can
  host a dry run. Commits go to a `live` branch. Tyler adds the API key as a repository secret.
- **Detector:**
  - Poll ComCat every ~10 minutes at off-peak minutes (for example :03, :13, ...), with one
    request per poll for events with an OAF product updated since the last poll.
  - A new sequence qualifies under the inclusion rules of prereg v2 (ADR 0013).
  - Each new OAF version defines an issue time, with the information cutoff of ADR 0004.
- **Per issue:**
  - Build the as-of catalog at the cutoff. Live, "as-of" is simply the catalog fetched at the
    poll, which is recorded.
  - Render the frozen prompts. Call Claude (frozen models and settings), the other-vendor model,
    and the baselines (ETAS refit, RJ-MLE, the rule of thumb).
  - The Windows 5090 runs the open models on a best-effort basis.
  - Write `calls.jsonl` and hash it (SHA-256). Commit the hash and an OpenTimestamps proof
    before the first window opens.
- **Disclosure:** hashes are public in real time. Full forecasts are published only after their
  windows close, with a note that they are not official forecasts (public-safety concern).
- **Latency and failures:**
  - Log detection latency (OAF version time to poll) and forecast latency (poll to hash).
  - An item whose hash is not committed before its first window opens is **late**. Late,
    missed and failed items are excluded, listed publicly with reasons, and never backfilled.
- **Rate limits:** one fetcher per IP (ComCat allows 500 requests per 5 minutes). The GitHub
  runner's IP is separate from the Mac's.
- **Budget:** the monthly guard (issue #4) gates every live call. The workflow's estimate per
  issue is stated before the freeze.
- **Failure tickets** (later): a failed run opens a GitHub issue with no secrets and no outcome
  data (docs/factory.md, ticket sources).

## Dry run (required before the freeze)
Run the detector and the pipeline with forecasters stubbed (no paid calls). First replay
archived OAF versions from development sequences, then run on the live feed for long enough to
measure the latency distribution and failure modes. Report the share of items that would have
been late.

## Open decisions (Tyler)
1. Prospective duration: until the power analysis's sequence count or 6 months, whichever comes
   first (already decided). The count comes from ADR 0018.
2. Which models run live (ADR 0014).

## Changelog
- 2026-10-29: first version.
