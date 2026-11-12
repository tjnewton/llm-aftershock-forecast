"""Output validation and the failure taxonomy (docs/PLAN.md 4.4, prereg section 7)."""

import itertools
import json
import re
from typing import Literal

Status = Literal[
    "ok", "refusal", "max_tokens", "schema_invalid", "non_monotone", "out_of_range",
    "transport_error", "model_mismatch",
]  # fmt: skip
WINDOWS = ("day", "week", "month")
QKEYS = ("q025", "q050", "q100", "q250", "q500", "q750", "q900", "q950", "q975")
TARGETS = ("m5_count_quantiles", "m4_count_quantiles")
TARGETS_V2 = (*TARGETS, "m3_count_quantiles")  # v2 prompts (D2) also ask for M3
PROBS = ("p_m6_at_least_one",)
# v3 prompts also ask for the probability of at least one earthquake at M>=5, 4 and 3
# (largest magnitude first, as TARGETS_V2)
PROBS_V3 = ("p_m6_at_least_one", "p_m5_at_least_one", "p_m4_at_least_one", "p_m3_at_least_one")
PARAM_RANGES = {"b": (0.3, 2.5), "p": (0.3, 2.5), "c_days": (1e-5, 10.0)}
A_RANGE = (-6.0, 2.0)


def fields(paraphrase: str | None) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(count targets, probabilities) an answer to this prompt must carry."""
    p = paraphrase or ""
    targets = TARGETS_V2 if p.startswith(("v2", "v3")) else TARGETS
    return targets, PROBS_V3 if p.startswith("v3") else PROBS


def _p_bounds(qs: list[int]) -> tuple[float, float]:
    """The range the nine quantiles leave for P(N >= 1): a quantile of 0 at level L means
    P(N = 0) >= L, a quantile of 1 or more means P(N = 0) < L."""
    levels = [int(k[1:]) / 1000 for k in QKEYS]
    zero = [lv for lv, q in zip(levels, qs, strict=True) if q == 0]
    pos = [lv for lv, q in zip(levels, qs, strict=True) if q > 0]
    return (1 - min(pos) if pos else 0.0), (1 - max(zero) if zero else 1.0)


def _direct(
    d: dict, targets: tuple[str, ...] = TARGETS, probs: tuple[str, ...] = PROBS
) -> tuple[Status, list[str]]:
    for w in WINDOWS:
        if not isinstance(d.get(w), dict):
            return "schema_invalid", []
        for t in targets:
            qs = d[w].get(t)
            if not isinstance(qs, dict) or any(not isinstance(qs.get(k), int) for k in QKEYS):
                return "schema_invalid", []
        if any(not isinstance(d[w].get(p), int | float) for p in probs):
            return "schema_invalid", []
    q = {(w, t): [d[w][t][k] for k in QKEYS] for w in WINDOWS for t in targets}
    if any(a > b for v in q.values() for a, b in itertools.pairwise(v)):
        return "non_monotone", []
    if any(x < 0 for v in q.values() for x in v) or any(
        not 0.0 <= d[w][p] <= 1.0 for w in WINDOWS for p in probs
    ):
        return "out_of_range", []
    warn = []
    for t in targets:
        if any(
            a > b
            for w1, w2 in (("day", "week"), ("week", "month"))
            for a, b in zip(q[(w1, t)], q[(w2, t)], strict=True)
        ):
            warn.append("incoherent_windows")
            break
    if any(
        a > b
        for w in WINDOWS
        for hi, lo in itertools.pairwise(targets)  # M5 <= M4 (<= M3)
        for a, b in zip(q[(w, hi)], q[(w, lo)], strict=True)
    ):
        warn.append("incoherent_magnitudes")
    # v3: each target is scored on its own numbers, so these are warnings with reported rates
    if any(d[w][hi] > d[w][lo] for w in WINDOWS for hi, lo in itertools.pairwise(probs)):
        warn.append("incoherent_probabilities")  # P(M>=5) above P(M>=4), and so on
    outside = False
    for w, t in q:
        name = f"p_{t[:2]}_at_least_one"  # the probability at the same magnitude, if asked
        if name in probs:
            lo, hi = _p_bounds(q[(w, t)])
            outside |= not lo - 1e-9 <= d[w][name] <= hi + 1e-9
    if outside:
        warn.append("probability_outside_quantiles")
    return "ok", warn


def stated_p5(text: str | None, stop_reason: str | None) -> dict[str, float | None]:
    """The answer's own probability of at least one M>=5 earthquake per window, wherever the
    answer was delivered whole, parses, and states a number in [0, 1], whatever else is wrong
    with it (prereg v2 section 7): the primary score reads nothing else. None for a refusal, a
    cut-off answer, unparseable text, or a missing or out-of-range probability."""
    none: dict[str, float | None] = dict.fromkeys(WINDOWS)
    if stop_reason in ("refusal", "max_tokens"):
        return none
    try:
        d = json.loads(text or "")
    except ValueError:
        return none
    if not isinstance(d, dict):
        return none
    out = dict(none)
    for w in WINDOWS:
        p = d[w].get("p_m5_at_least_one") if isinstance(d.get(w), dict) else None
        if isinstance(p, int | float) and not isinstance(p, bool) and 0.0 <= p <= 1.0:
            out[w] = float(p)
    return out


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
    arm: Literal["direct", "params"],
    text: str | None,
    stop_reason: str | None,
    targets: tuple[str, ...] = TARGETS,
    probs: tuple[str, ...] = PROBS,
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
    status, warn = _direct(d, targets, probs) if arm == "direct" else _params(d)
    if len(re.findall(r"[.!?](?:\s|$)", d["notes"])) > 2:
        warn.append("notes_too_long")
    return status, (d if status == "ok" else None), warn
