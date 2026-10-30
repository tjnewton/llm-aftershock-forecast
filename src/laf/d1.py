"""D1 behavioral probes (docs/proposals/d1-behavioral-probes.md): items that change one input of
a development item, their requests, the pilot, and the RJ references. Nothing here reads
observed outcomes.

Probes per base sequence (the 18 E3 post-cutoff mainshocks, prompt v2A):
- P1 `p1{delta:+.1f}`: mainshock magnitude + delta, issued 1 day after it, no catalog (I0). Its
  delta = 0 level is the P2 item at 1 day (an identical request would duplicate a custom_id).
- P2 `p2-{days:g}d`: issued `days` after the mainshock, no catalog (I0).
- P3 `p3-n{N}`: issued at day 3 with exactly N synthetic M3+ events, Omori-Utsu times (I1).
- P4 `p4-even`: the P3 N = 10 events with evenly spread times; its decaying counterpart is P3 n10.
"""

import hashlib
import json
import math
import statistics
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from numpy.polynomial.legendre import leggauss
from scipy import stats

from laf.forecast import poisson_mixture
from laf.items import DAY_MS, N_LARGEST, CatalogRow, Item, WindowSpec, utc
from laf.oaf import WindowLabel
from laf.prompts import Info, render, schema_for
from laf.providers import STUDY_SETTINGS, anthropic_params, call_anthropic, cost_usd, study_effort
from laf.runner import CHARS_PER_TOKEN, MAX_TOKENS_BATCH, _jsonl, check_budget, request_id
from laf.schemas import TARGETS_V2, validate

BASE_ROLE = "test-post"
DELTAS = (-1.0, -0.5, 0.5, 1.0)
P1_DAYS = 1.0
ELAPSED_DAYS = (1 / 24, 0.25, 1.0, 3.0, 10.0, 30.0)
COUNTS = (0, 1, 3, 10, 30, 100)
P3_DAYS = 3.0
P4_N = 10
FLOOR = 3.0
K = 2
PARAPHRASE = "v2A"
MODELS = ("claude-opus-4-6", "claude-sonnet-4-6", "claude-opus-5-5")
PILOT_MODELS = ("claude-opus-4-6", "claude-sonnet-4-6")
PILOT_TAGS = ("p1+1.0", "p2-0.04167d", "p3-n100", "p4-even")
MAX_TOKENS_SYNC = 16_000
WINDOWS: tuple[tuple[Literal["day", "week", "month"], WindowLabel, int], ...] = (
    ("day", "1 Day", 1),
    ("week", "1 Week", 7),
    ("month", "1 Month", 30),
)
P_GRID = np.linspace(0.5, 2.0, 31)  # uniform prior on Omori p for the Bayesian reference


def bases(items: list[Item]) -> list[Item]:
    """The earliest test-post item of each sequence: the template for mainshock and region."""
    first: dict[str, Item] = {}
    for i in sorted(items, key=lambda i: i.issue_ms):
        if i.role == BASE_ROLE:
            first.setdefault(i.sequence_id, i)
    return [first[s] for s in sorted(first)]


def _item(base: Item, tag: str, days: float, mag: float, rows: list[CatalogRow]) -> Item:
    issue = base.mainshock.origin_ms + round(days * DAY_MS)
    return base.model_copy(
        update={
            "item_id": f"{base.sequence_id}@d1-{tag}",
            "issue_ms": issue,
            "elapsed_days": days,
            "mainshock": base.mainshock.model_copy(update={"mag": mag}),
            "windows": [
                WindowSpec(key=k, label=lab, start_ms=issue, end_ms=issue + n * DAY_MS)
                for k, lab, n in WINDOWS
            ],
            "catalog": rows,
            "truncated": False,
            "daily_counts": None,
            "largest": sorted(rows, key=lambda r: (-r.mag, r.t_days))[:N_LARGEST],
        }
    )


def _omori_times(u: np.ndarray, c: float, p: float, t_end: float) -> np.ndarray:
    """Inverse of the normalized Omori-Utsu integral on (0, t_end]."""
    if abs(p - 1.0) < 1e-6:
        return c * ((t_end + c) / c) ** u - c
    total = ((t_end + c) ** (1 - p) - c ** (1 - p)) / (1 - p)
    return (c ** (1 - p) + (1 - p) * u * total) ** (1 / (1 - p)) - c


def synthetic(base: Item, seq: dict, n: int, pattern: str = "omori") -> list[CatalogRow]:
    """The mainshock row (as in real catalogs) and N events at M3+ before day 3, seeded by
    sequence and N (so P4 reuses P3's magnitudes, distances and depths). Magnitudes are the
    Gutenberg-Richter quantiles (i + 0.5) / N with the generic b, truncated below the
    mainshock and assigned to the times in random order, so the M4+ share does not vary by
    chance; distances within half the region radius; times Omori-Utsu with the generic c and
    p, or evenly spread ("even")."""
    key = hashlib.sha256(f"{base.sequence_id}|{n}".encode()).digest()
    rng = np.random.default_rng(int.from_bytes(key[:8], "big"))
    u_t, u_m, u_r, z = (
        rng.uniform(size=n),
        (rng.permutation(n) + 0.5) / max(n, 1),
        rng.uniform(size=n),
        rng.normal(size=n),
    )
    b, mm = seq["generic_b"], base.mainshock.mag
    mags = FLOOR - np.log10(1 - u_m * (1 - 10 ** (-b * (mm - FLOOR)))) / b
    mags = np.clip(np.floor(mags * 10 + 1e-9) / 10, FLOOR, mm - 0.1)
    if pattern == "even":
        t = (np.arange(n) + 0.5) * P3_DAYS / n
    else:
        t = np.sort(_omori_times(u_t, seq["generic_c_days"], seq["generic_p"], P3_DAYS))
    t = np.clip(t, 1e-3, P3_DAYS - 1e-3)  # nothing within 86 s of the mainshock
    dist = 0.5 * base.region.radius_km * np.sqrt(u_r)
    depth = np.maximum(base.mainshock.depth_km + 5.0 * z, 0.0)
    ms = base.mainshock
    o = ms.origin_ms
    main = CatalogRow(
        t_days=0.0, utc_time=ms.origin_utc, mag=ms.mag, mag_type=ms.mag_type,
        depth_km=round(ms.depth_km, 1), dist_km=0.0,
    )  # fmt: skip
    return [main] + [
        CatalogRow(
            t_days=round(float(t[i]), 4),
            utc_time=utc(o + round(float(t[i]) * DAY_MS)),
            mag=round(float(mags[i]), 1),
            mag_type="ml",
            depth_km=round(float(depth[i]), 1),
            dist_km=round(float(dist[i]), 1),
        )
        for i in range(n)
    ]


def probe_items(items: list[Item], sequences: pd.DataFrame) -> list[Item]:
    seqs = sequences.set_index("sequence_id").to_dict("index")
    out = []
    for base in bases(items):
        seq, mm = seqs[base.sequence_id], base.mainshock.mag
        out += [_item(base, f"p1{d:+.1f}", P1_DAYS, round(mm + d, 1), []) for d in DELTAS]
        out += [_item(base, f"p2-{t:.4g}d", t, mm, []) for t in ELAPSED_DAYS]
        out += [_item(base, f"p3-n{n}", P3_DAYS, mm, synthetic(base, seq, n)) for n in COUNTS]
        out.append(_item(base, "p4-even", P3_DAYS, mm, synthetic(base, seq, P4_N, "even")))
    return out


def info(item: Item) -> Info:
    return "I0" if item.item_id.split("@d1-")[1][:2] in ("p1", "p2") else "I1"


def items_jsonl(items: list[Item]) -> str:
    return "".join(i.model_dump_json() + "\n" for i in items)


def _params(item: Item, model: str, max_tokens: int) -> dict:
    system, user = render(item, "direct", info(item), PARAPHRASE)
    return anthropic_params(
        model, system, user, schema_for("direct", PARAPHRASE),
        effort=study_effort(model), max_tokens=max_tokens,
    )  # fmt: skip


def expand(items: list[Item], model: str, k: int = K) -> list[dict]:
    reqs = []
    for item in items:
        params = _params(item, model, MAX_TOKENS_BATCH)
        for s in range(k):
            meta = {
                "item_id": item.item_id, "arm": "direct", "info": info(item),
                "paraphrase": PARAPHRASE, "sample": s, "block": "d1", "model": model,
                "effort": study_effort(model),
            }  # fmt: skip
            reqs.append({"custom_id": request_id(params, s), "meta": meta, "params": params})
    if len({r["custom_id"] for r in reqs}) != len(reqs):
        raise ValueError("duplicate requests: two probe items render the same prompt")
    return reqs


def bound_usd(params: dict, *, batch: bool) -> float:
    """The most a request can cost: its prompt (from the request length, an overestimate) and
    every output token up to `max_tokens`."""
    usage = {
        "input_tokens": len(json.dumps(params, ensure_ascii=False)) / CHARS_PER_TOKEN,
        "output_tokens": params["max_tokens"],
    }
    return cost_usd(params["model"], usage, batch=batch)


def pilot(client, items: list[Item], out: Path, budget_usd: float = 0.5) -> float:
    """Synchronous calls on one sequence (the largest mainshock), one item per probe, for each
    4.6 model; a call is made only if its worst-case cost (`bound_usd`) still fits in
    `budget_usd`. Logs each call with its validation status to out/calls.jsonl. Returns the
    spend."""
    check_budget(budget_usd)
    seq = max(bases(items), key=lambda i: i.mainshock.mag).sequence_id
    chosen = [i for t in PILOT_TAGS for i in items if i.item_id == f"{seq}@d1-{t}"]
    spent = 0.0
    out.mkdir(parents=True, exist_ok=True)
    for item in chosen:  # models alternate, so a stop still leaves both measured
        for model in PILOT_MODELS:
            params = _params(item, model, MAX_TOKENS_SYNC)
            if spent + bound_usd(params, batch=False) > budget_usd:
                continue
            rec = call_anthropic(client, params)
            spent += cost_usd(model, rec.get("usage") or {})
            status, _, warn = validate(
                "direct", rec.get("text"), rec.get("stop_reason"), TARGETS_V2
            )
            row = {"item_id": item.item_id, "info": info(item), "paraphrase": PARAPHRASE,
                   "effort": study_effort(model), "status": status, "warnings": warn,
                   **rec}  # fmt: skip
            with (out / "calls.jsonl").open("a", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(row, sort_keys=True) + "\n")
    return spent


# Settings pilot (Tyler, 2026-10-30): thinking and effort on the 4.6 models, one batch. The
# output caps keep the worst case (every call at its cap) within $2.50; a capped answer is
# itself the finding that the setting is too costly.
SETTINGS_TAGS = ("p1+1.0", "p3-n100", "p4-even")
SETTINGS = {  # name: (adaptive thinking, effort, max_tokens for Opus 4.6, for Sonnet 4.6)
    "adaptive-high": (True, "high", 12_000, 32_000),
    "adaptive-medium": (True, "medium", 12_000, 16_000),
    "off-high": (False, "high", 4_000, 4_000),
}
# (model, setting, adaptive thinking, effort, max_tokens) per request group
GRIDS = {
    "grid": [
        (model, name, thinking, effort, cap)
        for name, (thinking, effort, *caps) in SETTINGS.items()
        for model, cap in zip(PILOT_MODELS, caps, strict=True)
    ],
    # follow-up check (Tyler, 2026-10-30): does Sonnet 4.6 finish with adaptive thinking at low?
    "sonnet-low": [("claude-sonnet-4-6", "adaptive-low", True, "low", 16_000)],
}


def settings_requests(items: list[Item], grid: str = "grid") -> list[dict]:
    seq = max(bases(items), key=lambda i: i.mainshock.mag).sequence_id
    chosen = [i for t in SETTINGS_TAGS for i in items if i.item_id == f"{seq}@d1-{t}"]
    reqs = []
    for item in chosen:
        system, user = render(item, "direct", info(item), PARAPHRASE)
        for model, name, thinking, effort, cap in GRIDS[grid]:
            params = anthropic_params(
                model, system, user, schema_for("direct", PARAPHRASE),
                effort=effort, max_tokens=cap,
            )  # fmt: skip
            params.pop("thinking", None)
            if thinking:
                params["thinking"] = {"type": "adaptive"}
            meta = {"item_id": item.item_id, "arm": "direct", "info": info(item),
                    "paraphrase": PARAPHRASE, "sample": 0, "block": "d1-settings",
                    "model": model, "effort": effort, "setting": name}  # fmt: skip
            reqs.append({"custom_id": request_id(params, 0), "meta": meta, "params": params})
    return reqs


def settings_summary(run: Path) -> pd.DataFrame:
    """Per model and setting: valid answers, output tokens and batch cost per call."""
    meta = {r["custom_id"]: r for r in _jsonl(run / "requests.jsonl")}
    rows = []
    for res in _jsonl(run / "results.jsonl"):
        m = meta[res["custom_id"]]
        status = (
            validate("direct", res.get("text"), res.get("stop_reason"), TARGETS_V2)[0]
            if res["result"] == "succeeded"
            else "transport_error"
        )
        u = res.get("usage") or {}
        rows.append({"model": m["model"], "setting": m["setting"], "item_id": m["item_id"],
                     "status": status, "output_tokens": u.get("output_tokens"),
                     "usd": cost_usd(m["model"], u, batch=True)})  # fmt: skip
    df = pd.DataFrame(rows)
    return (
        df.groupby(["model", "setting"])
        .agg(
            calls=("status", "size"),
            valid=("status", lambda s: int((s == "ok").sum())),
            out_mean=("output_tokens", "mean"),
            out_max=("output_tokens", "max"),
            usd_per_call=("usd", "mean"),
        )
        .reset_index()
    )


def study_setting(model: str) -> str:
    """The settings-pilot name of a model's study setting, e.g. "adaptive-medium"; "registered"
    for models that keep the registered request (the 5.5 models, adaptive by default)."""
    if model not in STUDY_SETTINGS:
        return "registered"
    thinking, effort = STUDY_SETTINGS[model]
    return f"{'adaptive' if thinking else 'off'}-{effort}"


def estimate_usd(reqs: list[dict], pilot_runs: list[Path], d2_results: Path) -> float:
    """Batch cost: input from the request length (an overestimate), output 1.25 times the mean
    of the settings-pilot answers at the model's study setting (4.6 models) or of the D2
    answers (Opus 5.5)."""
    out_tokens: dict[str, list[int]] = {}
    for run in pilot_runs:
        meta = {r["custom_id"]: r for r in _jsonl(run / "requests.jsonl")}
        for r in _jsonl(run / "results.jsonl"):
            m = meta[r["custom_id"]]
            if r.get("usage") and m["setting"] == study_setting(m["model"]):
                out_tokens.setdefault(m["model"], []).append(r["usage"]["output_tokens"])
    for r in _jsonl(d2_results):
        if r.get("usage"):
            out_tokens.setdefault(r["model"], []).append(r["usage"]["output_tokens"])
    total = 0.0
    for r in reqs:
        model = r["meta"]["model"]
        usage = {
            "input_tokens": len(json.dumps(r["params"], ensure_ascii=False)) / CHARS_PER_TOKEN,
            "output_tokens": 1.25 * statistics.mean(out_tokens[model]),
        }
        total += cost_usd(model, usage, batch=True)
    return total


def _omori(c: float, p: np.ndarray, t1: float, t2: float) -> np.ndarray:
    p = np.asarray(p, dtype=float)
    near1 = np.abs(p - 1.0) < 1e-6
    q = np.where(near1, 2.0, 1 - p)  # placeholder exponent where p = 1
    general = ((t2 + c) ** q - (t1 + c) ** q) / q
    return np.where(near1, math.log((t2 + c) / (t1 + c)), general)


def reference(item: Item, seq: dict) -> dict[str, dict]:
    """The RJ forecast for the item's windows: nine quantiles at M5, M4 and M3, and P(M6+).

    No catalog (I0): the generic model, a ~ Normal(mean, sigma(Mm)) truncated to [a_min, a_max]
    (as `laf.forecast.generic_rj`) with the generic b, p and c. With a catalog (I1): the grid
    posterior over a and p, from that prior on a, p uniform on [0.5, 2], and the Omori-Utsu
    likelihood of the M3+ events before the issue; defined for any count, including none."""
    mm = item.mainshock.mag
    b, c = seq["generic_b"], seq["generic_c_days"]
    sigma = math.sqrt(
        seq["generic_a_sigma0"] ** 2 + seq["generic_a_sigma1"] ** 2 / 10 ** max(mm, 6.0)
    )
    x, w = leggauss(200)
    lo, hi = seq["generic_a_min"], seq["generic_a_max"]
    a = lo + (x + 1) * (hi - lo) / 2
    log_w_a = np.log(w) + stats.norm.logpdf(a, seq["generic_a_mean"], sigma)
    if info(item) == "I0":
        A, P, log_w = a, np.full_like(a, seq["generic_p"]), log_w_a
    else:
        A, P = (g.ravel() for g in np.meshgrid(a, P_GRID, indexing="ij"))
        t = np.array([r.t_days for r in item.catalog if r.mag >= FLOOR - 1e-6 and r.t_days > 0])
        log_k = (A + b * (mm - FLOOR)) * math.log(10)  # ln rate of M3+ at unit Omori kernel
        integral = _omori(c, P, 0.0, item.elapsed_days)
        log_lik = len(t) * log_k - P * np.log(t + c).sum() - np.exp(log_k) * integral
        log_w = np.repeat(log_w_a, len(P_GRID)) + log_lik
    weights = np.exp(log_w - log_w.max())
    keep = weights > 1e-12 * weights.max()
    A, P, weights = A[keep], P[keep], weights[keep] / weights[keep].sum()
    out = {}
    t1 = item.elapsed_days
    for key, _, n in WINDOWS:
        lam = {m: 10 ** (A + b * (mm - m)) * _omori(c, P, t1, t1 + n) for m in (3, 4, 5, 6)}
        out[key] = {f"m{m}_count_quantiles": poisson_mixture(lam[m], weights)[0] for m in (5, 4, 3)}
        out[key]["p_m6"] = float(1 - (weights * np.exp(-lam[6])).sum())
    return out


# Analysis (proposal "Measures and references"). Every statistic comes from the nine quantiles,
# for the answers and the RJ references alike (ADR 0015). The mean uses the negative-binomial
# tail; where that tail falls back to a power law with an infinite mean, the mean is NaN and
# E[log(1 + N)] (finite for any tail) still covers the answer.
TARGETS = (("m5", "m5_count_quantiles"), ("m4", "m4_count_quantiles"), ("m3", "m3_count_quantiles"))


def _survival(dist, n_max: int) -> np.ndarray:
    return 1.0 - dist.cdf(np.arange(n_max))


def mean_count(q) -> float:
    from laf.countdist import from_quantiles

    d = from_quantiles(q, tail="nb")
    if d.nb is None and d.tail <= 1.0:
        return float("nan")
    n_max = int(20 * (q[-1] + 10))
    while True:
        s = _survival(d, n_max)
        if s[-1] * n_max < 1e-6 or n_max >= 4_000_000:
            return float(s.sum())
        n_max *= 4


def mean_log1p(q) -> float:
    """E[log(1 + N)] under the default (power) tail, with the remainder of the tail sum."""
    from laf.countdist import from_quantiles

    d = from_quantiles(q)
    n_max = int(20 * (q[-1] + 10))
    s = _survival(d, n_max)
    inc = np.log((np.arange(n_max) + 2) / (np.arange(n_max) + 1))
    return float((s * inc).sum() + s[-1] / d.tail)


def _tag(item_id: str) -> tuple[str, float]:
    """(probe, level): P1 delta, P2 days, P3 N; P4 is level 1 (even)."""
    tag = item_id.split("@d1-")[1]
    if tag.startswith("p1"):
        return "p1", float(tag[2:])
    if tag.startswith("p2"):
        return "p2", float(tag[3:-1])
    if tag.startswith("p3"):
        return "p3", float(tag[4:])
    return "p4", 1.0


def answer_stats(items: list[Item], sequences: pd.DataFrame, runs: list[Path]) -> pd.DataFrame:
    """One row per (forecaster, item, sample, window, target): mean, E[log(1 + N)], spread and
    P(M6+). The RJ reference is forecaster "rj" (sample 0)."""
    by_id = {i.item_id: i for i in items}
    seqs = sequences.set_index("sequence_id").to_dict("index")
    rows = []

    def p6(a: dict) -> float:  # answers name it p_m6_at_least_one, the reference p_m6
        return float(a["p_m6"] if "p_m6" in a else a["p_m6_at_least_one"])

    def add(model, item, sample, status, answer):
        probe, level = _tag(item.item_id)
        for w in ("day", "week", "month"):
            for t, key in TARGETS:
                q = answer[w][key] if answer else None
                if isinstance(q, dict):
                    q = [
                        q[k]
                        for k in (
                            "q025",
                            "q050",
                            "q100",
                            "q250",
                            "q500",
                            "q750",
                            "q900",
                            "q950",
                            "q975",
                        )
                    ]
                rows.append({
                    "model": model, "item_id": item.item_id, "sequence_id": item.sequence_id,
                    "probe": probe, "level": level, "sample": sample, "window": w, "target": t,
                    "status": status,
                    "mean": mean_count(q) if q else np.nan,
                    "elog1p": mean_log1p(q) if q else np.nan,
                    "spread": math.log1p(q[-1]) - math.log1p(q[0]) if q else np.nan,
                    "p_m6": p6(answer[w]) if answer else np.nan,
                })  # fmt: skip

    for item in items:
        add("rj", item, 0, "ok", reference(item, seqs[item.sequence_id]))
    for run in runs:
        meta = {r["custom_id"]: r for r in _jsonl(run / "requests.jsonl")}
        for res in _jsonl(run / "results.jsonl"):
            m = meta[res["custom_id"]]
            if res["result"] != "succeeded":
                status, parsed = "transport_error", None
            else:
                status, parsed, _ = validate(
                    "direct", res.get("text"), res.get("stop_reason"), TARGETS_V2
                )
            add(
                m["model"],
                by_id[m["item_id"]],
                m["sample"],
                status,
                parsed if status == "ok" else None,
            )
    return pd.DataFrame(rows)


def _boot(values: list[float], n: int = 2000) -> tuple[float, float, float]:
    """Mean over sequences and its 95% sequence-bootstrap interval."""
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return (np.nan, np.nan, np.nan)
    b = np.random.default_rng(20261030).choice(x, size=(n, len(x))).mean(axis=1)
    return float(x.mean()), float(np.quantile(b, 0.025)), float(np.quantile(b, 0.975))


def _slope(x: np.ndarray, y: np.ndarray) -> float:
    ok = np.isfinite(y)
    return float(np.polyfit(x[ok], y[ok], 1)[0]) if ok.sum() >= 3 else np.nan


def implied_p(t: np.ndarray, log_y: np.ndarray, c: float, window_days: float) -> float:
    """The Omori p whose window integrals [t, t + window) best fit the log mean counts, with a
    free scale; least squares on a 0.01 grid over [0.2, 3]."""
    ok = np.isfinite(log_y)
    if ok.sum() < 3:
        return np.nan
    t, log_y = t[ok], log_y[ok]
    grid = np.arange(0.2, 3.0001, 0.01)
    sse = []
    for p in grid:
        r = log_y - np.log([_omori(c, np.array([p]), ti, ti + window_days)[0] for ti in t])
        sse.append(float(((r - r.mean()) ** 2).sum()))
    return float(grid[int(np.argmin(sse))])


def _seq_measures(h: pd.DataFrame, stat: str, c: float, window_days: float) -> dict[str, float]:
    """The probe measures of one sequence, on log10 of the mean ("mean") or E[log(1 + N)]."""
    tr = np.log10 if stat == "mean" else (lambda v: v)
    by = {k: g.set_index("level")[stat] for k, g in h.groupby("probe")}
    p1, p2, p3, p4 = (by.get(k, pd.Series(dtype=float)) for k in ("p1", "p2", "p3", "p4"))
    if 1.0 in p2.index:  # P1's delta = 0 is the P2 item at 1 day
        p1 = pd.concat([p1, pd.Series({0.0: p2[1.0]})]).sort_index()
    pos = p3[p3.index > 0]
    get = lambda s, k: float(tr(s[k])) if k in s.index else np.nan  # noqa: E731
    return {
        "p1_slope": _slope(p1.index.to_numpy(), tr(p1.to_numpy())),
        "p2_implied_p": (
            implied_p(p2.index.to_numpy(), np.log(p2.to_numpy()), c, window_days)
            if stat == "mean"
            else np.nan
        ),
        "p3_elasticity": _slope(np.log10(pos.index.to_numpy()), tr(pos.to_numpy())),
        "p3_empty_vs_none": get(p3, 0.0) - get(p2, 3.0),
        "p4_even_vs_decaying": get(p4, 1.0) - get(p3, float(P4_N)),
    }


def summarize(stats_df: pd.DataFrame, sequences: pd.DataFrame) -> pd.DataFrame:
    """Per forecaster, window and target: each probe measure averaged over base sequences, with
    a sequence-bootstrap interval; plus the median spread and the implied b between targets."""
    c_of = sequences.set_index("sequence_id")["generic_c_days"].to_dict()
    days = {k: n for k, _, n in WINDOWS}
    keys = ["model", "sequence_id", "probe", "level", "window", "target"]
    cell = stats_df[stats_df["status"] == "ok"].groupby(keys)[["mean", "elog1p", "spread"]]
    cell = cell.mean().reset_index()
    out = []
    for (model, w, t), g in cell.groupby(["model", "window", "target"]):
        for stat in ("mean", "elog1p"):
            per = [
                _seq_measures(h, stat, c_of[str(seq)], days[str(w)])
                for seq, h in g.groupby("sequence_id")
            ]
            for k in per[0]:
                est, lo, hi = _boot([m[k] for m in per])
                n = int(np.isfinite([m[k] for m in per]).sum())
                out.append(dict(model=model, window=w, target=t, stat=stat, measure=k,
                                estimate=est, lo95=lo, hi95=hi, sequences=n))  # fmt: skip
        out.append(dict(model=model, window=w, target=t, stat="spread", measure="median_spread",
                        estimate=float(g["spread"].median()), lo95=np.nan, hi95=np.nan,
                        sequences=g["sequence_id"].nunique()))  # fmt: skip
    wide = cell.pivot_table(index=keys[:-1], columns="target", values="mean")
    for model, g in wide.groupby(level="model"):
        for a, b in (("m3", "m4"), ("m4", "m5")):
            ib = np.log10((g[a] / g[b]).to_numpy(dtype=float))
            out.append(dict(model=model, window="all", target=f"{a}/{b}", stat="mean",
                            measure="implied_b", estimate=float(np.nanmedian(ib[np.isfinite(ib)])),
                            lo95=np.nan, hi95=np.nan,
                            sequences=g.index.get_level_values(1).nunique()))  # fmt: skip
    return pd.DataFrame(out)
