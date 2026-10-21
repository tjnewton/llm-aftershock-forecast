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

No tasks yet.
