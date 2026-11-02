# Freeze and live-start runbook (prereg v2)

Steps from the freeze to the final analysis, in order. Tyler alone decides the freeze and
approves every paid batch with its estimate. Commands run from the repo root on the Mac unless
marked Windows.

## 1. Freeze (Tyler decides)
1. Every pull request merged; `uv run pytest` green on `post-submission`.
2. The prereg's status line changes from DRAFT to FROZEN, first: the manifest hashes the
   prereg, so it must see the final text.
3. `uv run laf freeze-manifest --snapshot 20261029T2000Z 20261101T2202Z` rebuilds and checks the
   frozen items and baselines and writes `results/freeze_manifest.json` (31 artifacts, one
   `manifest_sha256`). Commit the prereg and the manifest together; nothing changes between
   this step and the tag (rebuilding the manifest at the tag gives the same `manifest_sha256`).
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
- Test B's retrospective arm on the candidates (October 1-28 at Opus 5.5's clean start):
  `laf run --snapshot 20261029T2000Z --block confirmatory --model claude-opus-5-5`, and
  `--block confirmatory-v2b` (about $4.73).
- S1, S2, descriptive: `laf run --snapshot 20261029T2000Z --block confirmatory --model
  claude-opus-4-6` (and `claude-sonnet-4-6`); `laf openai run --snapshot 20261029T2000Z --block
  confirmatory --model gpt-6.1-sol`.
- Collect each with `laf collect` / `laf openai collect`; results stay unscored (second gate).

## 4. At L: the supplementary snapshot
1. `laf candidates --since 2026-10-29 --until <day after L> --out config/sequences_supplementary.toml`
   (through a pull request).
2. `laf --config config/sequences_supplementary.toml fetch`, `asof --workers 1`, `tables`, `etas`.
3. The rest of B's retrospective arm, on it: `laf run --snapshot <it> --block confirmatory
   --model claude-opus-5-5 --name confirmatory/confirmatory-claude-opus-5-5-supplementary`, and
   `--block confirmatory-v2b --name confirmatory/confirmatory-v2b-claude-opus-5-5-supplementary`
   (distinct names: the defaults are section 3's runs on the candidates).

## 5. At S: the stop
1. S = min(L + 182 days, the 26th eligible prospective M>=5 sequence).
2. Commit `config/live_stop.toml` with `s_ms = <S>` to `post-submission`; Tyler tags it
   `prereg-v2-stop`.
3. Windows pulls `post-submission` (its queue loop does), so the file is in the detector's
   checkout. `laf.live_watch` reads it every poll: from then on a sequence whose origin is at S
   or later is not admitted ("after the stop" in the log), while admitted sequences keep their
   scheduled issues to the 28-day slot and releases continue. No restart.
4. Check: `git log -1 -- config/live_stop.toml` in the detector's checkout shows the stop
   commit; any qualifying sequence after S has `"inclusion": "after the stop"` in `log.jsonl`;
   no new sequence folder appears on `live` after S.
5. The stop takes effect once the file is merged into the detector's checkout: merge it
   promptly. A sequence admitted between S and that pull is outside the analysis, which keeps
   origins in [L, S); its records stay on `live` and are reported as such.

## 6. At S + 90 days: the analysis
1. One outcome snapshot: fetch the candidate, forward-excluded, supplementary and live
   sequences' configs into one snapshot; `tables` (the gate now opens).
2. `laf confirmatory --snapshot <it> --runs runs/confirmatory --live <worktree of live>`; then
   `--test-a-all`.
3. Report every table whatever its result; deviations go to the v2 section of
   `docs/deviations.md`.
