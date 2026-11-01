"""A rehearsal of the prospective inputs on development data (prereg v2 section 11: "`laf
confirmatory` has run end to end on a development snapshot, including the prospective inputs").

`laf live-rehearsal` runs the real prospective pipeline (`prospective.run_issue`: items, the
budget plan, model calls, the two seals, the spend file, the baselines) on a development
sequence, with stub clients in place of the APIs: every answer is the same synthetic forecast,
labelled as such, so nothing is spent and nothing is a model's work. It then adds what the live
service and the release would add (a receipt, the inclusion record, the release notice), so
`laf confirmatory-dryrun --live <dir>` can read it like the `live` branch. The receipt and the
settling override are synthetic: a rehearsal of the code path, never a result.
"""

import json
from pathlib import Path
from types import SimpleNamespace

from laf.schemas import QKEYS, WINDOWS

SYNTHETIC_NOTE = "Synthetic rehearsal answer."


def synthetic_answer() -> str:
    q = {k: int(i >= 4) + int(i >= 7) for i, k in enumerate(QKEYS)}  # non-decreasing counts
    win = {"m5_count_quantiles": q, "m4_count_quantiles": q, "m3_count_quantiles": q,
           "p_m6_at_least_one": 0.02}  # fmt: skip
    return json.dumps({**{w: win for w in WINDOWS}, "notes": SYNTHETIC_NOTE})


def stub_clients() -> dict:
    """SDK stand-ins with the call shapes `prospective.model_calls` uses; no network."""
    usage = {"input_tokens": 2000, "output_tokens": 500}

    def message(**params):
        return SimpleNamespace(
            id="rehearsal", model=params["model"], stop_reason="end_turn", stop_details=None,
            usage=SimpleNamespace(model_dump=lambda: usage),
            content=[SimpleNamespace(type="text", text=synthetic_answer())],
        )  # fmt: skip

    class Stream:
        def __init__(self, **params):
            self.msg = message(**params)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get_final_message(self):
            return self.msg

    def respond(**params):
        body = {"id": "rehearsal", "model": params["model"], "status": "completed",
                "usage": usage, "output": [{"type": "message", "content": [
                    {"type": "output_text", "text": synthetic_answer()}]}]}  # fmt: skip
        return SimpleNamespace(model_dump=lambda: body)

    return {
        "claude": SimpleNamespace(messages=SimpleNamespace(stream=Stream), base_url="stub"),
        "openai": SimpleNamespace(responses=SimpleNamespace(create=respond), base_url="stub"),
    }


def build(data_dir: Path, snapshot: str, seq, out: Path, now_ms: int) -> Path:
    """One rehearsal issue under `out` laid out as the `live` branch; returns its folder."""
    from laf import prospective as P

    # a development sequence's newest version is rarely one the schedule picks: in this
    # rehearsal only, every version is treated as scheduled
    scheduled = P.scheduled_slot
    P.scheduled_slot = lambda tables, update_ms: "rehearsal"
    try:
        rec = P.run_issue(stub_clients(), data_dir, snapshot, seq, out,
                          clock=lambda: now_ms / 1000,
                          budget=lambda: {"claude": 1e9, "openai": 1e9})  # fmt: skip
    finally:
        P.scheduled_slot = scheduled
    if "skipped" in rec:
        raise SystemExit(f"{seq.id}: {rec['skipped']}")
    d = out / seq.id / str(rec["timing"]["update_ms"])
    first = min(v["first_window_ms"] for v in rec["answers"]["items"].values())
    # synthetic: GitHub's receipt a minute before the first window, so every item is on time
    (d / "receipt.json").write_text(json.dumps({"receipt_ms": first - 60_000, "synthetic": True}))
    (out / seq.id / "inclusion.json").write_text(
        json.dumps({"key": seq.id, "tier": "primary", "synthetic": True})
    )
    (d / "NOTICE.txt").write_text("Rehearsal: synthetic answers on development data.\n")
    return d
