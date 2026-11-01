# Freeze and live-start runbook (prereg v2)

Steps from the freeze to the final analysis, in order. Tyler alone decides the freeze and
approves every paid batch with its estimate. Commands run from the repo root on the Mac unless
marked Windows.

## 1. Freeze (Tyler decides)
1. Every pull request merged; `uv run pytest` green on `post-submission`.
2. `uv run laf freeze-manifest --snapshot 20261029T2000Z 20261101T2202Z` rebuilds and checks the
   frozen items and baselines and writes `results/freeze_manifest.json` (31 artifacts, one
   `manifest_sha256`).
3. The prereg's status line changes from DRAFT to FROZEN; commit it with the manifest.
4. Tyler tags that commit `prereg-v2` (annotated) and pushes the tag; the `freeze-tags` ruleset
   protects it.
5. Tyler posts the tag's commit hash and `manifest_sha256` publicly.

## 2. Live start (after the tag)
1. Create the orphan branch `live` (README, guard-only hooks, no workflows), as `live-test`.
2. Windows `.env` (Tyler types it): `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
   `LAF_CLAUDE_MONTHLY_CAP_USD=200`, `LAF_OPENAI_MONTHLY_CAP_USD=100`,
   `LAF_CLAUDE_LIVE_RESERVE_USD=20`, `LAF_OPENAI_LIVE_RESERVE_USD=25`.
3. The worker prompt allows API calls for the detector service only; Tyler restarts the loop.
4. Paid end-to-end check (asked first, with its estimate): `laf prospective` on a version the
   study does not use, published nowhere.
5. A queue task: worktree `..\laf-live` on `live`; stop the dry run; start
   `laf live-watch --paid --publish ..\laf-live` (Windows). L is the first sealed live record.

## 3. Retrospective batches (each approved with its estimate)
- Test A, by 2027-03-01, about one part a month (OpenAI cap $100 to February):
  `laf openai run --snapshot 20261029T2000Z --block confirmatory --chunk 1/2` then `2/2`;
  `--block confirmatory-sens --chunk 1/2`, `2/2`; `--block confirmatory-v2b --chunk 1/2`, `2/2`.
- Forward-excluded: `laf openai run --snapshot 20261101T2202Z --block confirmatory
  --forward-excluded` and `laf run --snapshot 20261101T2202Z --block confirmatory --model
  claude-opus-4-6 --forward-excluded` (about $1.76).
- S1, S2, descriptive: `laf run --block confirmatory --model claude-opus-4-6` (and
  `claude-sonnet-4-6`); `laf openai run --block confirmatory --model gpt-6.1-sol`.
- Collect each with `laf collect` / `laf openai collect`; results stay unscored (second gate).

## 4. At L: the supplementary snapshot
1. `laf candidates --since 2026-10-29 --until <day after L> --out config/sequences_supplementary.toml`
   (through a pull request).
2. `laf --config config/sequences_supplementary.toml fetch`, `asof --workers 1`, `tables`, `etas`.
3. B's retrospective batches on it: `laf run --block confirmatory` and `confirmatory-v2b` with
   `--model claude-opus-5-5`.

## 5. At S: the stop
1. S = min(L + 182 days, the 26th eligible prospective M>=5 sequence).
2. Commit `config/live_stop.toml` with `s_ms = <S>`; Tyler tags it `prereg-v2-stop`.
3. The detector stops admitting new sequences; issues of admitted ones continue to their 28-day
   slot; releases continue.

## 6. At S + 90 days: the analysis
1. One outcome snapshot: fetch the candidate, forward-excluded, supplementary and live
   sequences' configs into one snapshot; `tables` (the gate now opens).
2. `laf confirmatory --snapshot <it> --runs runs/confirmatory --live <worktree of live>`; then
   `--test-a-all`.
3. Report every table whatever its result; deviations go to the v2 section of
   `docs/deviations.md`.
