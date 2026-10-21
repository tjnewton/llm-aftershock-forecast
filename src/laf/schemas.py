"""Output validation and the failure taxonomy (docs/PLAN.md 4.4, prereg section 7)."""

import itertools
import json
import re
from typing import Literal

Status = Literal[
    "ok", "refusal", "max_tokens", "schema_invalid", "non_monotone", "out_of_range",
    "transport_error",
]  # fmt: skip
WINDOWS = ("day", "week", "month")
QKEYS = ("q025", "q050", "q100", "q250", "q500", "q750", "q900", "q950", "q975")
TARGETS = ("m5_count_quantiles", "m4_count_quantiles")
PARAM_RANGES = {"b": (0.3, 2.5), "p": (0.3, 2.5), "c_days": (1e-5, 10.0)}
A_RANGE = (-6.0, 2.0)


def _direct(d: dict) -> tuple[Status, list[str]]:
    for w in WINDOWS:
        if not isinstance(d.get(w), dict):
            return "schema_invalid", []
        for t in TARGETS:
            qs = d[w].get(t)
            if not isinstance(qs, dict) or any(not isinstance(qs.get(k), int) for k in QKEYS):
                return "schema_invalid", []
        if not isinstance(d[w].get("p_m6_at_least_one"), int | float):
            return "schema_invalid", []
    q = {(w, t): [d[w][t][k] for k in QKEYS] for w in WINDOWS for t in TARGETS}
    if any(a > b for v in q.values() for a, b in itertools.pairwise(v)):
        return "non_monotone", []
    if any(x < 0 for v in q.values() for x in v) or any(
        not 0.0 <= d[w]["p_m6_at_least_one"] <= 1.0 for w in WINDOWS
    ):
        return "out_of_range", []
    warn = []
    for t in TARGETS:
        if any(
            a > b
            for w1, w2 in (("day", "week"), ("week", "month"))
            for a, b in zip(q[(w1, t)], q[(w2, t)], strict=True)
        ):
            warn.append("incoherent_windows")
            break
    if any(
        a > b for w in WINDOWS for a, b in zip(q[(w, TARGETS[0])], q[(w, TARGETS[1])], strict=True)
    ):
        warn.append("incoherent_magnitudes")
    return "ok", warn


def _params(d: dict) -> tuple[Status, list[str]]:
    keys = ("b", "p", "c_days", "a_p05", "a_p50", "a_p95")
    if any(not isinstance(d.get(k), int | float) for k in keys):
        return "schema_invalid", []
    if any(not lo <= d[k] <= hi for k, (lo, hi) in PARAM_RANGES.items()):
        return "out_of_range", []
    a = (d["a_p05"], d["a_p50"], d["a_p95"])
    if any(not A_RANGE[0] <= x <= A_RANGE[1] for x in a) or not a[0] <= a[1] <= a[2]:
        return "out_of_range", []
    return "ok", []


def validate(
    arm: Literal["direct", "params"], text: str | None, stop_reason: str | None
) -> tuple[Status, dict | None, list[str]]:
    """(status, parsed JSON or None, warnings). Exactly one status per sample."""
    if stop_reason == "refusal":
        return "refusal", None, []
    if stop_reason == "max_tokens":
        return "max_tokens", None, []
    try:
        d = json.loads(text or "")
    except ValueError:
        return "schema_invalid", None, []
    if not isinstance(d, dict) or not isinstance(d.get("notes"), str):
        return "schema_invalid", None, []
    status, warn = _direct(d) if arm == "direct" else _params(d)
    if len(re.findall(r"[.!?](?:\s|$)", d["notes"])) > 2:
        warn.append("notes_too_long")
    return status, (d if status == "ok" else None), warn
