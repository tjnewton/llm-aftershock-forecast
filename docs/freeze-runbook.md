# Freeze and live-start runbook (prereg v2)

Steps from the freeze to the final analysis, in order. Tyler alone decides the freeze and
approves every paid batch with its estimate. Since 2026-11-03 every step runs on the Windows
machine: development in the repo root and `.claude\worktrees`, the detector in its service
worktree `..\laf-service` (section 0). Outages and restores: section 7.

## 0. Before the tag
Done before the freeze, because after it every code fix is a deviation.
1. Windows `.env` (Tyler types it; done 2026-11-02): `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
   `LAF_CLAUDE_MONTHLY_CAP_USD=200`, `LAF_OPENAI_MONTHLY_CAP_USD=150` (decision 20),
   `LAF_CLAUDE_LIVE_RESERVE_USD=20`, `LAF_OPENAI_LIVE_RESERVE_USD=25`.
2. The paid end-to-end check (asked first, with its estimate: about $0.85; at most about $6.30,
   every answer at the 32k output cap), on Windows, the live host. Take a dry-run detection whose issue ran (a scheduled version) and its
   snapshot; `laf --data-dir <the detector's data folder> prospective --snapshot <it>
   --sequence <id> --out runs/prospective-e2e`, published nowhere (a detected event needs no
   config entry). Check: 12 answers (2 items, 2 models, k = 3) with `model_reported` and
   `usage`, `spend.jsonl`, both seals, the baselines. A failure is fixed before the tag.
   Done 2026-11-02 (T14, T17): us6000tzna, 12 answers on the first attempt, all valid, the
   reported models as requested, $0.37.
3. The Windows host for 6 months (the clock does not pause for outages): sleep off; Windows
   Update notifies before a restart, active hours 06:00 to 24:00; the startup task
   `laf-detector` (Tyler registers it with his password, so it can read Git Credential
   Manager) runs `C:\Users\tjnew\git\laf-detector.ps1`, a loop that restarts the detector
   whenever it stops.
4. The service worktree: `git worktree add --detach ..\laf-service <commit>`; the script runs
   the detector there, so development in the repo root never changes the running code (many
   `laf` functions import modules when called) or its `config\live_stop.toml`. Nobody edits,
   pulls or commits in it. A deploy: right after a poll, `Stop-ScheduledTask laf-detector`,
   `git -C ..\laf-service checkout --detach <commit>`, `Start-ScheduledTask laf-detector`, one
   line in `ops\deploys.md` (UTC time, commit, reason). After the tag, a deploy that changes
   `src\laf` is also a deviation (section 12 of the prereg). The detector's commits run the
   repository's git hooks, which call the repo root's `.venv`: keep it installed.
5. Backups: every night an encrypted copy of the service worktree's `data\interim` and `runs`
   folders (the detector's state and the full live records, private until release) goes off
   the machine, with a key only Tyler holds. Without it, a lost disk turns unreleased items
   into failures. The daily task `laf-backup` (Tyler registers it, at 23:30) runs
   `C:\Users\tjnew\git\laf-backup.ps1`: it waits for the end of a poll (`state.json` is written
   last), packs both folders and the two task scripts with `tar`, encrypts the archive with
   Git's `gpg` to Tyler's public key `C:\Users\tjnew\git\laf-backup.pub.asc` (he keeps the
   private key off this machine) and writes `OneDrive\laf-backup\laf-backup-<weekday>.tar.gz.gpg`:
   seven nights, older copies in OneDrive's version history. Each night adds one line (ok with
   the size, or FAILED with the error) to `C:\Users\tjnew\git\laf-backup.log`. Restore:
   section 7.
6. Parity: `laf freeze-manifest` checks the committed items and baselines against a fresh
   rebuild, floats up to last-bit libm noise (macOS and Windows differ in P(M>=6) by at most
   4.4e-16), and hashes the committed bytes. Done 2026-11-04 (T18): Windows reproduces the
   manifest computed at 1edc91ef on 2026-11-03, 9de0daa4...0e6e0e.

## 1. Freeze (Tyler decides)
1. Every pull request merged; `uv run pytest` green on `post-submission`; the working tree
   clean (`git status --porcelain` prints nothing), because the manifest hashes the files on
   disk.
2. The prereg's status paragraph is rewritten to its frozen form first ("FROZEN at the tag
   `prereg-v2`", no draft wording): the manifest hashes the prereg, so it must see the final
   text.
3. `uv run laf freeze-manifest --snapshot 20261029T2000Z 20261101T2202Z` rebuilds and checks the
   frozen items and baselines and writes `results/freeze_manifest.json` (33 artifacts, one
   `manifest_sha256`). Commit the prereg and the manifest together; nothing changes between
   this step and the tag (rebuilding the manifest at the tag gives the same `manifest_sha256`).
   Before that commit, `uv run laf stamp results/freeze_manifest.json` writes OpenTimestamps
   proofs beside the manifest (only its SHA-256 leaves the machine): a witness outside GitHub.
   Commit the proofs with it; `ots upgrade` completes them once Bitcoin confirms. An OSF
   registration of the prereg is an optional second witness (Tyler's account).
4. Tyler tags that commit `prereg-v2` with `git tag -a` (the gate refuses a lightweight tag)
   and pushes the tag; the `freeze-tags` ruleset protects it.
5. Tyler posts the tag's commit hash and `manifest_sha256` publicly.

## 2. Live start (after the tag)
1. Create the orphan branch `live` (README, guard-only hooks, no workflows), as `live-test`.
   The `protect-live` ruleset (no deletion, no force-push) already covers it.
2. Tyler copies `.env` into `..\laf-service` (the paid detector reads its keys and caps
   there).
3. Worktree `..\laf-live` on `live`; deploy the tagged commit to `..\laf-service`; create the
   folder `..\laf-service\runs\live` (the script appends the detector's output there, and
   `cmd` refuses a redirect into a missing folder, so the detector would never start); point
   `laf-detector.ps1` at `laf live-watch --paid --publish ..\laf-live --out runs\live
   --live-data data\interim\live` and restart the task: its own state and issue folders,
   never the dry run's (`live_watch.run` refuses them). Before its first poll the paid
   detector commits `start.json` to `live`: L, its start time (prereg v2 section 5). It admits
   only sequences with origin at or after L. Check that `start.json` is on GitHub and that the
   first polls appear in `runs\live\log.jsonl`.
4. Point the backup's `-Out` default in `laf-backup.ps1` at
   `C:\Users\tjnew\git\laf-service\runs\live` (an absolute path: the task starts in
   System32; the script waits for that folder's `state.json`); the next night's line in
   `laf-backup.log` is ok.
5. Every working session: `uv run laf live-status --live ..\laf-live --out
   ..\laf-service\runs\live` (no model calls, no ComCat). It lists L, the eligible
   prospective sequences in order of first detection and S, and flags a stale poll, errors,
   unpushed commits, seals without a push receipt and this month's live spend; exit code 1
   means something needs a look. When it reports S as passed, go to section 5.

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
- S1 and the descriptive batches: `laf run --snapshot 20261029T2000Z --block confirmatory
  --model claude-opus-4-6` (S1), `--model claude-sonnet-4-6`; `laf openai run --snapshot
  20261029T2000Z --block confirmatory --model gpt-6.1-sol` (descriptive: S2 is prospective).
- Collect each with `laf collect` / `laf openai collect` once it ends, and within 29 days:
  Anthropic keeps batch results 29 days and OpenAI's output files expire too, so an uncollected
  batch loses answers already paid for. Results stay unscored (second gate). A batch with
  transport errors (errored, expired, missing, or an OpenAI batch that failed as a whole) is
  resent with the same command plus `--retry` (asked first, with its estimate), up to 10
  attempts.

## 4. After L: the supplementary snapshot
1. At least 7 days after L, so that every sequence that began shortly before L has its first
   OAF product (the selection stays outcome-blind: products and magnitudes only): `laf
   candidates --since 2026-10-29 --until <the day after L> --out
   config/sequences_supplementary.toml` (through a pull request).
2. `uv run laf --config config/sequences_supplementary.toml fetch` (each line starts with
   the new snapshot id), then, with the same `--config` before the command each time,
   `asof --snapshot <it> --workers 1`, `tables --snapshot <it>` and `etas --snapshot <it>`.
   Without the `--config`, `tables` silently builds the registered sequences. ComCat allows 500
   requests per 5 minutes per IP: one fetcher, paced at 1 per second, beside the detector's
   poll every 10 minutes from the same machine.
3. Before any batch on it: `laf freeze-manifest --snapshot <it> --out
   results/supplementary_manifest.json` (its items and baselines without outcomes, and their
   hashes), `laf stamp results/supplementary_manifest.json`, commit both and post the
   manifest's hash; the outcome snapshot refuses a frozen snapshot in no manifest.
4. The rest of B's retrospective arm, on it: `laf run --snapshot <it> --block confirmatory
   --model claude-opus-5-5 --name confirmatory/confirmatory-claude-opus-5-5-supplementary`, and
   `--block confirmatory-v2b --name confirmatory/confirmatory-v2b-claude-opus-5-5-supplementary`
   (distinct names: the defaults are section 3's runs on the candidates).

## 5. At S: the stop
1. S = min(L + 182 days, the latest origin among the first 26 eligible prospective M>=5
   sequences in order of first detection; eligible: included as primary at first detection,
   with origin at or after L). Normally the latest origin is the 26th's own. Prospective
   origins are in [L, S] (decisions 23 and 27). `laf live-status` (section 2.5) reports S.
2. The stop commit is the deployed commit plus the stop file, so the stop deploys no other
   code: `git worktree add -b live-stop ..\laf-stop <the commit of the last line in
   ops\deploys.md>`; in it, write `config/live_stop.toml` with `s_ms = <S>` (epoch ms),
   commit, push the branch `live-stop`, and check that `git diff <that commit> live-stop
   --stat` lists only `config/live_stop.toml`. Tyler tags that commit `prereg-v2-stop`
   (`git tag -a`: the gate refuses a lightweight tag) and pushes the tag; it descends from
   `prereg-v2`, as `laf.splits` requires. Merge it into `post-submission` through a pull request
   afterwards.
3. Deploy that commit to `..\laf-service` (section 0.4), so the file is in the detector's
   checkout. `laf.live_watch` reads it every poll: from then on a sequence whose origin is after
   S is not admitted ("after the stop" in the log), while admitted sequences keep their
   scheduled issues to the 28-day slot and releases continue.
4. Check: `git log -1 -- config/live_stop.toml` in the detector's checkout shows the stop
   commit; any qualifying sequence after S has `"inclusion": "after the stop"` in `log.jsonl`;
   no new sequence folder appears on `live` after S.
5. The stop takes effect once the file is in the detector's checkout: deploy it promptly. A
   sequence admitted with origin after S before that deploy is outside the analysis, which
   keeps origins in [L, S]; its records stay on `live` and are reported as such.

## 6. At S + 90 days: the analysis
1. `laf outcome-config --configs config/sequences_confirmatory.toml
   config/sequences_forward_excluded.toml config/sequences_supplementary.toml --live <worktree
   of live> --out config/sequences_outcome.toml` (through a pull request): every frozen
   sequence and every live item's sequence.
2. `laf --config config/sequences_outcome.toml fetch` (one fetcher, paced), then `laf
   --config config/sequences_outcome.toml tables --snapshot <fresh>`. Both gates are open
   (the tag `prereg-v2`; the tag `prereg-v2-stop` and S + 90 days), so counts are written.
3. `laf outcome-snapshot --frozen 20261029T2000Z 20261101T2202Z <supplementary> --fresh <fresh>
   --live <worktree of live> --out <fresh>-outcomes`: the frozen items, issue tables, official
   forecasts and ETAS refit, checked against `results/freeze_manifest.json` as committed at
   the tag and the supplementary snapshot against `results/supplementary_manifest.json`, with
   counts recounted from the fresh catalog in each issue's own circle; sequences with origin
   at L or later come from the fresh fetch.
4. `laf confirmatory --snapshot <fresh>-outcomes --runs runs/confirmatory --live <worktree of
   live>`; then `--test-a-all`. With `--live`, it and `laf outcome-snapshot` refuse a `live`
   worktree without `start.json` (L); it also writes `results/live_missed_<snapshot>.csv`,
   the scheduled versions that were never issued.
5. Report every table whatever its result; deviations go to the v2 section of
   `docs/deviations.md`.

## 7. Outages and restore
The live arm has one host (ADR 0017 decision 14). An outage (power, network, a restart) is not
bridged: the startup task restarts the detector at boot, issues missed meanwhile are listed as
missed and never backfilled, and the 6-month clock does not pause. If the machine proves
unreliable, decision 14's fallback applies (GitHub Actions with a private repository holding the
records until release), as a deviation.

If the service worktree or the disk is lost, restore on this machine or a replacement:
1. Only one detector at a time: `Stop-ScheduledTask laf-detector` if it still runs (two
   detectors could issue the same version twice before either publishes).
2. On a replacement, clone the repository to `C:\Users\tjnew\git\llm-aftershock-forecast` and
   add the worktree `..\laf-live` on `live` (before L, `..\laf-live-dryrun` on `live-dryrun`
   and `..\laf-live-test` on `live-test`; the dry run's log and state are in
   `..\laf-live-dryrun`, whose log is on GitHub up to its last commit).
   Then `git worktree add --detach ..\laf-service <commit>` at the commit of the last line in
   `ops\deploys.md`, and `uv sync --locked` there; after the live start Tyler copies `.env`
   in.
3. Tyler decrypts the newest backup with his private key (`gpg --output <a temporary
   folder>\laf-backup.tar.gz --decrypt laf-backup-<weekday>.tar.gz.gpg`; not `>`, which
   corrupts binary output in Windows PowerShell) and unpacks it with `tar -xzf <that file> -C
   C:\Users\tjnew\git`: the service worktree's `data\interim`
   and `runs`, and `laf-detector.ps1` and `laf-backup.ps1`. On a replacement he registers both
   tasks and the Windows Update setting again with `ops\register-tasks.ps1` (admin PowerShell;
   sections 0.3 and 0.5) and puts his public key back (`gpg --armor --export`).
4. `git -C ..\laf-live pull --ff-only origin live`: the detector reads issued seals and the
   spend ledger from it (a stale copy undercounts spend and repeats issues), and the `live`
   branch, not local state, decides what is already issued.
5. `Start-ScheduledTask laf-detector`; one line in `ops\deploys.md` (the restore and the
   backup it used).
