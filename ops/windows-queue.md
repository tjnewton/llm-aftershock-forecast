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
