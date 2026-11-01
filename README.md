# live-dryrun

Logs of the live arm's detector dry run (docs/adr/0017-live-pipeline.md on `post-submission`),
kept on their own branch so the log commits stay out of the code history.

- `runs/live-dryrun/log.jsonl`: one line per ComCat poll and per detected OAF version
  (`laf.live_watch`). Append-only.
- `runs/live-dryrun/state.json`: the detector's resume state.
- `runs/live-dryrun/stdout.log`, `stderr.log`: the service's console output.

The dry run makes no model calls and scores nothing. Logs from 2026-10-30 to 2026-11-01 are also
in the history of `post-submission`; this branch starts from that state.

The Windows worker commits here (ops/windows-queue.md, T09 and T10 on `post-submission`).
