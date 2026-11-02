# Freeze and live-start runbook (prereg v2)

Steps from the freeze to the final analysis, in order. Tyler alone decides the freeze and
approves every paid batch with its estimate. Commands run from the repo root on the Mac unless
marked Windows.

## 0. Before the tag
Done before the freeze, because after it every code fix is a deviation.
1. Windows `.env` (Tyler types it): `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
   `LAF_CLAUDE_MONTHLY_CAP_USD=200`, `LAF_OPENAI_MONTHLY_CAP_USD=100`,
   `LAF_CLAUDE_LIVE_RESERVE_USD=20`, `LAF_OPENAI_LIVE_RESERVE_USD=25`.
2. The paid end-to-end check (asked first, with its estimate: about $0.85; at most about $6.30,
   every answer at the 32k output cap), on Windows, the live host. Tyler lets the worker make
   this one run. Take a dry-run detection whose issue ran (a scheduled version) and its
   snapshot; `laf --data-dir <the detector's data folder> prospective --snapshot <it>
   --sequence <id> --out runs/prospective-e2e`, published nowhere (a detected event needs no
   config entry). Check: 12 answers (2 items, 2 models, k = 3) with `model_reported` and
   `usage`, `spend.jsonl`, both seals, the baselines. A failure is fixed before the tag.
3. The Windows host for 6 months (the clock does not pause for outages): sleep off; Windows
   Update restarts outside active hours, or paused, with Tyler watching for forced ones; the
   detector started at boot by a scheduled task that restarts it on failure.

## 1. Freeze (Tyler decides)
1. Every pull request merged; `uv run pytest` green on `post-submission`.
2. The prereg's status line changes from DRAFT to FROZEN, first: the manifest hashes the
   prereg, so it must see the final text.
3. `uv run laf freeze-manifest --snapshot 20261029T2000Z 20261101T2202Z` rebuilds and checks the
   frozen items and baselines and writes `results/freeze_manifest.json` (31 artifacts, one
   `manifest_sha256`). Commit the prereg and the manifest together; nothing changes between
   this step and the tag (rebuilding the manifest at the tag gives the same `manifest_sha256`).
   Before that commit, `uv run laf stamp results/freeze_manifest.json` writes OpenTimestamps
   proofs beside the manifest (only its SHA-256 leaves the machine): a witness outside GitHub.
   Commit the proofs with it; `ots upgrade` completes them once Bitcoin confirms. An OSF
   registration of the prereg is an optional second witness (Tyler's account).
4. Tyler tags that commit `prereg-v2` (annotated) and pushes the tag; the `freeze-tags` ruleset
   protects it.
5. Tyler posts the tag's commit hash and `manifest_sha256` publicly.

## 2. Live start (after the tag)
1. Create the orphan branch `live` (README, guard-only hooks, no workflows), as `live-test`.
   The `protect-live` ruleset (no deletion, no force-push) already covers it.
2. The worker prompt allows API calls for the detector service only; Tyler restarts the loop.
3. A queue task: worktree `..\laf-live` on `live`; stop the dry run; start
   `laf live-watch --paid --publish ..\laf-live --out runs\live --live-data data\interim\live`
   (Windows) through the boot task of section 0: its own state and issue folders, never the dry
   run's (`live_watch.run` refuses them). L is the first sealed live record.

## 3. Retrospective batches (each approved with its estimate)
Retirement dates (checked 2026-11-02): gpt-5.1 is deprecated and shuts down 2027-04-01; Claude
Opus 4.6 not before 2027-02-05, Sonnet 4.6 not before 2027-02-17, Opus 5.5 not before
2027-09-22. So the Claude batches on the candidates run right after the tag, and test A
finishes in January (decision 20).
- Test A, two half-parts a month from November to January (OpenAI cap $150; Tyler sets $100 on
  2027-02-01 and $50 in March):
  `laf openai run --snapshot 20261029T2000Z --block confirmatory --chunk 1/2` then `2/2`;
  `--block confirmatory-sens --chunk 1/2`, `2/2`; `--block confirmatory-v2b --chunk 1/2`, `2/2`;
  then `--block confirmatory-unbuffered` (about $13, decision 21).
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
  A batch with transport errors (errored, expired, missing) is resent with the same command
  plus `--retry` (asked first, with its estimate), up to 10 attempts.

## 4. At L: the supplementary snapshot
1. `laf candidates --since 2026-10-29 --until <day after L> --out config/sequences_supplementary.toml`
   (through a pull request).
2. `laf --config config/sequences_supplementary.toml fetch`, `asof --workers 1`, `tables`, `etas`.
   ComCat allows 500 requests per 5 minutes per IP: one fetcher on the Mac, paced at 1 per
   second, beside the detector's poll every 10 minutes if both share the home address.
3. Before any batch on it: `laf freeze-manifest --snapshot <it> --out
   results/supplementary_manifest.json` (its items and baselines without outcomes, and their
   hashes), `laf stamp results/supplementary_manifest.json`, commit both and post the
   manifest's hash; the outcome snapshot refuses a frozen snapshot in no manifest.
4. The rest of B's retrospective arm, on it: `laf run --snapshot <it> --block confirmatory
   --model claude-opus-5-5 --name confirmatory/confirmatory-claude-opus-5-5-supplementary`, and
   `--block confirmatory-v2b --name confirmatory/confirmatory-v2b-claude-opus-5-5-supplementary`
   (distinct names: the defaults are section 3's runs on the candidates).

## 5. At S: the stop
1. S = min(L + 182 days, the origin of the 26th eligible prospective M>=5 sequence: included
   as primary at first detection). Prospective origins are in [L, S] (decision 23).
2. Commit `config/live_stop.toml` with `s_ms = <S>` to `post-submission`; Tyler tags it
   `prereg-v2-stop`.
3. Windows pulls `post-submission` (its queue loop does), so the file is in the detector's
   checkout. `laf.live_watch` reads it every poll: from then on a sequence whose origin is after
   S is not admitted ("after the stop" in the log), while admitted sequences keep their
   scheduled issues to the 28-day slot and releases continue. No restart.
4. Check: `git log -1 -- config/live_stop.toml` in the detector's checkout shows the stop
   commit; any qualifying sequence after S has `"inclusion": "after the stop"` in `log.jsonl`;
   no new sequence folder appears on `live` after S.
5. The stop takes effect once the file is merged into the detector's checkout: merge it
   promptly. A sequence admitted between S and that pull is outside the analysis, which keeps
   origins in [L, S); its records stay on `live` and are reported as such.

## 6. At S + 90 days: the analysis
1. `laf outcome-config --configs config/sequences_confirmatory.toml
   config/sequences_forward_excluded.toml config/sequences_supplementary.toml --live <worktree
   of live> --out config/sequences_outcome.toml` (through a pull request): every frozen
   sequence and every live item's sequence.
2. `laf --config config/sequences_outcome.toml fetch` (one fetcher, paced), then `tables
   --snapshot <fresh>`. Both gates are open (the tag `prereg-v2`; the tag `prereg-v2-stop` and S + 90 days), so counts are
   written.
3. `laf outcome-snapshot --frozen 20261029T2000Z 20261101T2202Z <supplementary> --fresh <fresh>
   --live <worktree of live> --out <fresh>-outcomes`: the frozen items, issue tables, official
   forecasts and ETAS refit, checked against `results/freeze_manifest.json`, with counts
   recounted from the fresh catalog in each issue's own circle; sequences with origin at L or
   later come from the fresh fetch.
4. `laf confirmatory --snapshot <fresh>-outcomes --runs runs/confirmatory --live <worktree of
   live>`; then `--test-a-all`.
5. Report every table whatever its result; deviations go to the v2 section of
   `docs/deviations.md`.
