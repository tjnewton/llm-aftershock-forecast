# Windows task queue (written by the Mac only)

The Windows session runs tasks marked `status: ready`, in file order, one at a time, and records
progress only in ops/windows-status.md. A task marked `status: hold` waits for a later edit. The
line `## END` below the last task means the queue is closed.

Task format:

    ## T<nn> <short-name>
    status: ready | hold
    server: <llama-server setup: model, gguf, alias, optional --lora file>
    prepare: <optional one-time steps, e.g. download and convert an adapter>
    run: <exact command(s)>
    outputs: <folders the run must produce>
    commit: <commit message>
    notes: <anything else>

## T01 e3-e1-adapted
status: ready
server: registered gpt-oss-20b command with --alias laf/gpt-oss-20b-e1 --lora <models dir>/gpt-oss-20b-e1-lora-f16.gguf (the adapter you converted for E1)
run: uv run python -m laf.llamacpp --snapshot 20261021T2300Z --model gpt-oss-20b-e1 --block e3all
outputs: runs/e3/extensions/e3all-gpt-oss-20b-e1/
commit: Local run: gpt-oss-20b-e1 on E3 (e3all, N of M succeeded)
notes: E3 extended exploratory set (docs/adr/0012-e3-extended-set.md). About 2.4 s per request.

## T02 e3-olmo
status: ready
server: registered olmo-3.1-32b-instruct command (no --lora)
run: uv run python -m laf.llamacpp --snapshot 20261021T2300Z --model olmo-3.1-32b-instruct --block e3all
outputs: runs/e3/e3all-olmo-3.1-32b-instruct/
commit: Local run: Olmo-3.1-32B-Instruct on E3 (e3all, N of M succeeded)
notes: About 7 s per request.

## T03 e3-gpt-oss
status: ready
server: registered gpt-oss-20b command (no --lora, alias openai/gpt-oss-20b)
run: uv run python -m laf.llamacpp --snapshot 20261021T2300Z --model gpt-oss-20b --block e3all
outputs: runs/e3/e3all-gpt-oss-20b/
commit: Local run: gpt-oss-20b on E3 (e3all, N of M succeeded)
notes: Long (about 30 s per request, several hours). If an E1a task becomes ready while this
  runs, finish this task first.

## T04 e1a-adapted
status: ready
prepare: uv run laf adaption download --run e1a (checks SHA-256 against runs/e1a-adaption/checkpoint.json once that file exists; otherwise records it); extract data/interim/e1a-adaption/best.tar.zst into a new empty data/interim/e1a-adaption/adapter/; convert exactly as for E1 with --outfile <models dir>/gpt-oss-20b-e1a-lora-f16.gguf
server: registered gpt-oss-20b command with --alias laf/gpt-oss-20b-e1a --lora <models dir>/gpt-oss-20b-e1a-lora-f16.gguf
run: uv run python -m laf.llamacpp --snapshot 20261021T1027Z --model gpt-oss-20b-e1a --block dev (report status counts only), then uv run python -m laf.llamacpp --snapshot 20261021T1027Z --model gpt-oss-20b-e1a --block e1, then uv run python -m laf.llamacpp --snapshot 20261021T2300Z --model gpt-oss-20b-e1a --block e3all
outputs: runs/extensions/dev-gpt-oss-20b-e1a/, runs/extensions/e1-gpt-oss-20b-e1a/, runs/e3/extensions/e3all-gpt-oss-20b-e1a/
commit: Local run: gpt-oss-20b-e1a dev check, e1 block and E3 (N of M succeeded)
notes: E1a = E1 recipe on 9,030 rows (M>=6.0 sequences). If T03 is still running when this
  becomes ready, run this first and then resume T03 (the runner re-sends only unanswered requests).

## T05 e1r1-adapted
status: hold
prepare: uv run laf adaption download --run e1r1 (records runs/e1r1-adaption/checkpoint.json); extract data/interim/e1r1-adaption/best.tar.zst into a new empty data/interim/e1r1-adaption/adapter/; convert exactly as for E1 with --outfile <models dir>/gpt-oss-20b-e1r1-lora-f16.gguf
server: registered gpt-oss-20b command with --alias laf/gpt-oss-20b-e1r1 --lora <models dir>/gpt-oss-20b-e1r1-lora-f16.gguf
run: uv run python -m laf.llamacpp --snapshot 20261021T1027Z --model gpt-oss-20b-e1r1 --block e1, then uv run python -m laf.llamacpp --snapshot 20261021T2300Z --model gpt-oss-20b-e1r1 --block e3all
outputs: runs/extensions/e1-gpt-oss-20b-e1r1/, runs/e3/extensions/e3all-gpt-oss-20b-e1r1/, runs/e1r1-adaption/checkpoint.json
commit: Local run: gpt-oss-20b-e1r1 e1 block and E3 (N of M succeeded)
notes: Exploratory (docs/deviations.md). About 40 min. Report the SHA-256 of the converted GGUF adapter in the done line.

## T06 e1r2-adapted
status: hold
prepare: uv run laf adaption download --run e1r2 (records runs/e1r2-adaption/checkpoint.json); extract data/interim/e1r2-adaption/best.tar.zst into a new empty data/interim/e1r2-adaption/adapter/; convert exactly as for E1 with --outfile <models dir>/gpt-oss-20b-e1r2-lora-f16.gguf
server: registered gpt-oss-20b command with --alias laf/gpt-oss-20b-e1r2 --lora <models dir>/gpt-oss-20b-e1r2-lora-f16.gguf
run: uv run python -m laf.llamacpp --snapshot 20261021T1027Z --model gpt-oss-20b-e1r2 --block e1, then uv run python -m laf.llamacpp --snapshot 20261021T2300Z --model gpt-oss-20b-e1r2 --block e3all
outputs: runs/extensions/e1-gpt-oss-20b-e1r2/, runs/e3/extensions/e3all-gpt-oss-20b-e1r2/, runs/e1r2-adaption/checkpoint.json
commit: Local run: gpt-oss-20b-e1r2 e1 block and E3 (N of M succeeded)
notes: Exploratory (docs/deviations.md). About 40 min. Report the SHA-256 of the converted GGUF adapter in the done line.

## T07 e1ar2-adapted
status: hold
prepare: uv run laf adaption download --run e1ar2 (records runs/e1ar2-adaption/checkpoint.json); extract data/interim/e1ar2-adaption/best.tar.zst into a new empty data/interim/e1ar2-adaption/adapter/; convert exactly as for E1 with --outfile <models dir>/gpt-oss-20b-e1ar2-lora-f16.gguf
server: registered gpt-oss-20b command with --alias laf/gpt-oss-20b-e1ar2 --lora <models dir>/gpt-oss-20b-e1ar2-lora-f16.gguf
run: uv run python -m laf.llamacpp --snapshot 20261021T1027Z --model gpt-oss-20b-e1ar2 --block e1, then uv run python -m laf.llamacpp --snapshot 20261021T2300Z --model gpt-oss-20b-e1ar2 --block e3all
outputs: runs/extensions/e1-gpt-oss-20b-e1ar2/, runs/e3/extensions/e3all-gpt-oss-20b-e1ar2/, runs/e1ar2-adaption/checkpoint.json
commit: Local run: gpt-oss-20b-e1ar2 e1 block and E3 (N of M succeeded)
notes: Exploratory (docs/deviations.md). About 40 min. Report the SHA-256 of the converted GGUF adapter in the done line.

## T08 e1b-adapted
status: hold
prepare: uv run laf adaption download --run e1b (records runs/e1b-adaption/checkpoint.json); extract data/interim/e1b-adaption/best.tar.zst into a new empty data/interim/e1b-adaption/adapter/; convert exactly as for E1 with --outfile <models dir>/gpt-oss-20b-e1b-lora-f16.gguf
server: registered gpt-oss-20b command with --alias laf/gpt-oss-20b-e1b --lora <models dir>/gpt-oss-20b-e1b-lora-f16.gguf
run: uv run python -m laf.llamacpp --snapshot 20261021T1027Z --model gpt-oss-20b-e1b --block dev (status counts only), then uv run python -m laf.llamacpp --snapshot 20261021T1027Z --model gpt-oss-20b-e1b --block e1, then uv run python -m laf.llamacpp --snapshot 20261021T2300Z --model gpt-oss-20b-e1b --block e3all
outputs: runs/extensions/dev-gpt-oss-20b-e1b/, runs/extensions/e1-gpt-oss-20b-e1b/, runs/e3/extensions/e3all-gpt-oss-20b-e1b/, runs/e1b-adaption/checkpoint.json
commit: Local run: gpt-oss-20b-e1b e1 block and E3 (N of M succeeded)
notes: Exploratory (docs/deviations.md). About 40 min. Report the SHA-256 of the converted GGUF adapter in the done line.

## END
