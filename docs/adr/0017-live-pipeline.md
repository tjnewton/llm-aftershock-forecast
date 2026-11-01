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

## Dry-run results (living)
- **Replay of archived versions** (`laf live-late --snapshot 20261021T1027Z 20261021T2300Z
  20261029T2000Z`, timing columns only; `results/live_late_share.csv`):
  - Across 13,437 OAF versions in 240 sequences, the first window opens a median 12 minutes
    after the version is published. In 30.4% of versions it opens before publication, so an
    item on the version's own windows (a matched item) is late whatever the pipeline does.
  - Share of matched items that would be late:

    | Poll interval | 0.5 min to hash | 2 min | 5 min |
    |---|---|---|---|
    | 2 min | 0.378 | 0.398 | 0.433 |
    | 5 min | 0.397 | 0.415 | 0.457 |
    | 10 min | 0.431 | 0.452 | 0.498 |

  - The ComCat index lag comes from the live dry run (8 detections so far): about 5 s, but
    20 minutes once.
- **Live feed (Windows, from 2026-10-30):** first live detection us7000tu3j (M5.0), seen 438 s
  after publication; items built in 9.6 s; the strict item had 88 minutes to spare and the
  matched item would have been 12 minutes late. The latency distribution needs a longer run.
- **Model latency** (D1 pilot, synchronous, adaptive thinking at effort high): Opus 4.6 120 s,
  Sonnet 4.6 259 s (cut off at 16,000 tokens). The settings finally chosen in ADR 0014 set the
  live forecast time.

## Decisions (Tyler, 2026-10-30)
1. **Strict items are primary.** Their windows open at the next full hour at least 30 minutes
   after detection, so every item can be hashed before its window opens. The primary live
   contrast is the LLM against the baselines run by this pipeline (ETAS refit, RJ-MLE, generic
   RJ, the rule of thumb) on the same strict windows and the same catalog.
2. **Matched items are secondary.** Only matched items hashed before their first window are
   compared with the official forecast. Late ones are excluded and listed (as above), and the
   analysis reports whether on-time and late versions differ in magnitude and time since the
   mainshock. The confirmatory comparison with the official forecast stays in the
   retrospective arm.
3. **Poll every 10 minutes.** Scheduled GitHub Actions runs can be delayed by 10 minutes or
   more, and faster polling lowers the matched late share by only about 3 points.
4. **Strict window rule kept for now** (next full hour at least 30 minutes after detection).
   Once the live forecast time is measured with the final model settings, rounding to the next
   10 minutes instead may shrink the offset from the official windows (now 30 to 90 minutes).

## Decisions (Tyler, 2026-10-31), from the prereg v2 checks
These replace decisions 1-2 above where they conflict (docs/preregistration-v2.md section 13).
5. **On-time matched items enter test B** (ADR 0018), against the official forecast. Strict
   items serve S5, the contrast with this pipeline's baselines on identical windows.
6. **Issue schedule:** prospectively, only the versions that ADR 0004's schedule selects get
   items: the first valid version, plus for each target in {1, 3, 7, 14, 28} days the
   earliest valid version in its window. Applied in real time.
7. **On time** means the answer record's hash reached the GitHub push receipt (or an
   OpenTimestamps calendar) before the item's first window opened.
   - Answers are sealed before the baselines, in two records.
   - On-time and late versions are compared on outcome-blind covariates.
8. **Inclusion:** a new event inside the circle of a larger event from the previous 365 days is
   an aftershock and excluded (the backward half of ADR 0006). A sequence once included is
   never removed.
9. **Live models:** Opus 5.5, and gpt-6.1-sol once its effort is set by a pilot.
10. **Budget priority:** a fixed live reserve. If the cap binds, the order is Opus 5.5 matched,
    then Opus 5.5 strict, then gpt-6.1-sol. Misses are listed as "missed: budget".

## Decisions (Tyler, 2026-11-01)
11. **Strict window rule final** (decision 4): the next full hour at least 30 minutes after
    detection. The dry run built the items and both records in about 21 s before model time;
    10-minute rounding would shrink the offset from the official windows by under 50 minutes
    on windows of a day or more.
12. **Live start:** right after the `prereg-v2` tag, once one paid end-to-end check has passed
    (on a version the study does not use, published nowhere). L is the time of the first
    sealed live record.

13. **Host (Tyler, 2026-11-01):** the Windows machine runs the paid live arm from L until
    hackathon judging ends, then the scheduled GitHub Actions workflow takes over. Same command
    on both: `laf live-watch --paid --publish <worktree of live>`. Windows needs both API keys
    in its `.env` (Tyler), and the worker prompt allows API calls for this service only.

14. **Host, revised (Tyler, 2026-11-01): the Windows machine runs the paid live arm for its
    whole duration**, replacing decision 13's handover to GitHub Actions. An issue's full records
    (the forecasts) must stay private until its windows close, more than a month later, and a
    GitHub Actions run keeps nothing between runs: its disk is wiped, and artifacts of a public
    repository can be downloaded by anyone. On Windows the records wait on disk until the
    release (`laf.publish.release`). Downtime is the risk: issues missed while the service is
    down are listed as missed, and the 6-month clock does not pause. If Windows proves
    unreliable, the fallback is GitHub Actions with a second, private repository holding the
    records until release.

## The paid path (2026-11-01)
- **Live reserve:** each provider's monthly cap is split. Batch and one-off runs may spend the
  cap minus `LAF_<PROVIDER>_LIVE_RESERVE_USD`; the live service may spend only the reserve.
  The live ledger is the `spend.jsonl` published beside each answers seal on `live` (model,
  token usage, cost, no text), so every host reads the same ledger and an ephemeral GitHub
  Actions checkout loses nothing. The amounts come with the confirmatory cost plan.
- **Priority (decision 10):** within an issue, Opus 5.5 matched, Opus 5.5 strict, gpt-6.1-sol
  matched, gpt-6.1-sol strict; a group (item and model, k answers) runs only if its worst case
  fits what is left, else its answers are listed as `missed: budget`.
- **Guards:** `--paid` refuses unless it publishes to a worktree of `live` and both reserves
  are set; the dry run refuses `live`.

## Open decisions (Tyler)
1. ~~Prospective duration~~: decided 2026-10-31 (ADR 0018 decision 5): 6 months or 26
   eligible prospective M>=5 sequences, whichever comes first; one analysis at the stop.
2. Which models run live (ADR 0014).
3. ~~The strict window rounding~~: decided 2026-11-01 (decision 11).

## Changelog
- 2026-11-01: decision 14 (Windows hosts the whole live arm; GitHub Actions cannot hold the
  records privately until release).
- 2026-11-01: decision 13 (host); the paid path (live reserve, ledger, priority, guards).
- 2026-11-01: decisions 11-12 (strict window rule final, live start).
- 2026-10-31: decisions 5-10 (from the prereg v2 checks); decisions 1-2 replaced where they conflict.
- 2026-10-30: dry-run results so far; decisions 1-4 (Tyler).
- 2026-10-29: first version.
