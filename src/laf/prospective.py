"""Prospective arm of the Seismica study (ADR 0017; ADR 0018 decisions 1, 5-7).

For one new official (OAF) version of a qualifying sequence: the matched and strict items
(catalog from M3, prompt v2A), forecasts from the live models at their study settings, the
pipeline's baselines on the same items (generic RJ, RJ-MLE, the rule of thumb, the legacy-ETAS
refit), then one sealed record and its SHA-256. A matched item enters the official comparison
only if the record was sealed before its first window opened; strict items always open after
the seal (next full hour, at least 30 minutes after detection).
"""

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from laf import openai_runner as O
from laf.items import Item, build_items
from laf.live import live_tables, next_full_hour
from laf.prompts import render, schema_for
from laf.providers import anthropic_params, call_anthropic, cost_usd, env_value
from laf.registry import Sequence
from laf.runner import CAP_VAR, remaining_usd, reserve_var

LIVE_MODELS = ("claude-opus-5-5", "gpt-6.1-sol")  # in budget priority (prereg v2 section 5)
K = 3
FLOOR = 3.0
PROMPT = "v2A"  # ADR 0015 decision 4
MAX_TOKENS = 32_000  # as the retrospective batches (prereg v2 section 3)
STRICT_LEAD_MS = 30 * 60_000
MIN_MAG = 5.0  # primary: M>=5 mainshocks (ADR 0013); US M4.0-4.9 are secondary


# ANSS regional networks: "US-network" mainshocks of ADR 0013 (the `us` network is global)
US_REGIONAL = frozenset({"ak", "ci", "hv", "mb", "nc", "nm", "nn", "pr", "se", "tx", "uu", "uw"})


def qualifies(mag: float, network: str) -> str | None:
    """'primary' for M>=5 mainshocks, 'secondary' for M4.0-4.9 mainshocks from a US regional
    network (ADR 0013), else None."""
    if mag >= MIN_MAG - 1e-9:
        return "primary"
    if mag >= 4.0 - 1e-9 and network.lower() in US_REGIONAL:
        return "secondary"
    return None


def issue(data_dir: Path, snapshot: str, seq: Sequence, now_ms: int):
    """(tables, items, update_ms): matched and strict items from today's catalog."""
    strict_ms = next_full_hour(now_ms + STRICT_LEAD_MS)
    tables, update_ms = live_tables(data_dir, snapshot, seq, now_ms, strict_ms)
    return tables, build_items(tables, FLOOR), update_ms


def provider(model: str) -> str:
    return "openai" if model in O.PRICES else "claude"


def _params(item: Item, model: str) -> dict:
    from laf.confirmatory import study_effort  # both providers (ADR 0014 decisions 5-7)

    system, user = render(item, "direct", "I1", PROMPT)
    schema, effort = schema_for("direct", PROMPT), study_effort(model)
    if provider(model) == "openai":
        return O.openai_params(
            model, system, user, schema, effort=effort, max_output_tokens=MAX_TOKENS
        )
    return anthropic_params(model, system, user, schema, effort=effort, max_tokens=MAX_TOKENS)


def _cost(model: str, usage: dict) -> float:
    """Standard (synchronous) price."""
    return O.cost_usd(model, usage) if provider(model) == "openai" else cost_usd(model, usage)


def call_bound_usd(item: Item, model: str) -> float:
    """The most one answer can cost: its whole output budget."""
    p = _params(item, model)
    return _cost(model, {"input_tokens": len(json.dumps(p)) / 1.25, "output_tokens": MAX_TOKENS})


def bound_usd(items: list[Item], models=LIVE_MODELS, k: int = K) -> float:
    """The most the calls for one issue can cost."""
    return sum(k * call_bound_usd(i, m) for i in items for m in models)


def plan_calls(items: list[Item], left: dict[str, float], models=LIVE_MODELS, k: int = K):
    """(jobs, missed) in the registered budget priority (prereg v2 section 5): models in order,
    each model's matched item before its strict one. A group (item and model, k answers) runs
    only if its worst case fits what is left of its provider's budget; otherwise its answers
    are listed as "missed: budget"."""
    left = dict(left)
    ordered = sorted(items, key=lambda i: not i.item_id.endswith("@live-matched"))
    jobs, missed = [], []
    for m in models:
        for item in ordered:
            cost = k * call_bound_usd(item, m)
            if cost <= left.get(provider(m), 0.0):
                left[provider(m)] -= cost
                jobs += [(item.item_id, m, s, _params(item, m)) for s in range(k)]
            else:
                miss = {"item_id": item.item_id, "model_requested": m, "paraphrase": PROMPT,
                        "missed": "budget"}  # fmt: skip
                missed += [{**miss, "sample": s} for s in range(k)]
    return jobs, missed


def model_calls(clients: dict, items: list[Item], left: dict[str, float], models=LIVE_MODELS,
                k: int = K) -> list[dict]:  # fmt: skip
    """k synchronous answers per item and model within `left` (USD per provider), in the
    budget priority; `clients` maps "claude" and "openai" to their SDK clients."""
    jobs, missed = plan_calls(items, left, models, k)

    def call(job):
        item_id, m, s, params = job
        if provider(m) == "openai":
            effort, rec = params["reasoning"]["effort"], O.call_openai(clients["openai"], params)
        else:
            effort = params["output_config"]["effort"]
            rec = call_anthropic(clients["claude"], params, stream=True)
        return {"item_id": item_id, "paraphrase": PROMPT, "effort": effort, "sample": s, **rec}

    with ThreadPoolExecutor(6) as pool:
        recs = list(pool.map(call, jobs))
    return sorted(recs + missed, key=lambda r: (r["item_id"], r["model_requested"], r["sample"]))


def spend_rows(calls: list[dict]) -> list[dict]:
    """The spend of an issue's calls, without their text: what the live ledger publishes."""
    return [
        {"started_utc": c["started_utc"], "model_requested": c["model_requested"],
         "provider": provider(c["model_requested"]), "usage": c["usage"],
         "usd": _cost(c["model_requested"], c["usage"])}
        for c in calls if c.get("usage")
    ]  # fmt: skip


def local_budget() -> dict[str, float]:
    """One-off runs on this machine (`laf prospective`): each provider's cap minus its live
    reserve minus this month's spend."""
    return {
        "claude": remaining_usd(),
        "openai": remaining_usd(cap_var=O.CAP_VAR, month_spend=O.month_spend_usd),
    }


def live_budget(ledger: Path, month: str | None = None) -> dict[str, float]:
    """The live service: each provider's live reserve minus this month's live spend, summed
    from the spend files published on the live branch (`ledger` is its worktree), so every host
    reads the same ledger. A reserve must be set."""
    from datetime import UTC, datetime

    month = month or datetime.now(UTC).strftime("%Y-%m")
    spent = {"claude": 0.0, "openai": 0.0}
    for f in ledger.glob("**/spend.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r["started_utc"][:7] == month:
                spent[r["provider"]] += r["usd"]
    out = {}
    for prov, cap_var in (("claude", CAP_VAR), ("openai", O.CAP_VAR)):
        reserve = env_value(reserve_var(cap_var))
        if not reserve:
            raise SystemExit(f"{reserve_var(cap_var)} not set: the live service spends only it")
        out[prov] = float(reserve) - spent[prov]
    return out


def baseline_forecasts(tables: dict, items: list[Item], data_dir: Path) -> list[dict]:
    """The pipeline's baselines on the live items: generic RJ, RJ-MLE, the rule of thumb and
    the legacy-ETAS refit (ADR 0010 defaults), as M5 and M4 quantiles and P(M>=6)."""
    from laf import analysis as A
    from laf.etas import forecast_item, issue_seed
    from laf.generic_rj import REFERENCE_REL

    rows = {r["issue_id"]: r for r in tables["issue_times"].to_dict("records")}
    etas = []
    for item in items:
        cat = tables["catalog"][tables["catalog"]["sequence_id"] == item.sequence_id]
        etas += forecast_item(item, rows[item.item_id], cat, data_dir / REFERENCE_REL,
                              issue_seed(item.item_id))  # fmt: skip
    cells = pd.DataFrame(
        [{"issue_id": i.item_id, "sequence_id": i.sequence_id, "window": w.label,
          "oaf_cell": False, "issue_ms": i.issue_ms} for i in items for w in i.windows]
    )  # fmt: skip
    base = A.baselines({**tables, "etas_forecasts": pd.DataFrame(etas)},
                       {i.item_id: i for i in items}, cells)  # fmt: skip
    return [
        {"forecaster": name, "item_id": iid, "window": win, "m5": list(fc.m5),
         "m4": list(fc.m4) if fc.m4 else None, "p_m6": fc.p_m6}
        for (name, iid, win), fc in sorted(base.items())
        if name not in ("etas_hindsight", "etas_analyst")
    ]  # fmt: skip


def _jsonl(rows) -> str:
    return "".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in rows)


def _record(out: Path, name: str, bodies: dict[str, str], clock) -> dict:
    """Write the files, then `<name>.seal.json`: a SHA-256 over the manifest of the files'
    hashes and the time it was taken. A record is never sealed twice."""
    if (out / f"{name}.seal.json").exists():
        raise FileExistsError(f"{out}/{name}.seal.json exists: already sealed")
    for fname, body in bodies.items():
        (out / fname).write_text(body, encoding="utf-8", newline="\n")
    manifest = {n: hashlib.sha256(b.encode("utf-8")).hexdigest() for n, b in bodies.items()}
    sha = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode("utf-8")).hexdigest()
    return {"record_sha256": sha, "manifest": manifest, "sealed_ms": int(clock() * 1000)}


def _save(out: Path, name: str, rec: dict) -> dict:
    (out / f"{name}.seal.json").write_text(
        json.dumps(rec, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    return rec


def seal_answers(out: Path, items: list[Item], calls: list[dict], clock=time.time) -> dict:
    """The first record: the items and the models' answers, sealed before the baselines run
    (prereg v2 section 5), with each item's eligibility. `on_time` here uses the local seal
    time; the registered criterion is the push receipt of this record's hash."""
    out.mkdir(parents=True, exist_ok=True)
    bodies = {
        "items.jsonl": "".join(i.model_dump_json() + "\n" for i in items),
        "calls.jsonl": _jsonl(calls),
    }
    rec = _record(out, "answers", bodies, clock)
    rec["items"] = {
        i.item_id: {
            "first_window_ms": min(w.start_ms for w in i.windows),
            "on_time": rec["sealed_ms"] < min(w.start_ms for w in i.windows),
        }
        for i in items
    }
    return _save(out, "answers", rec)


def seal_baselines(out: Path, baselines: list[dict], clock=time.time) -> dict:
    """The second record: the pipeline's baselines on the same items."""
    return _save(
        out, "baselines", _record(out, "baselines", {"baselines.jsonl": _jsonl(baselines)}, clock)
    )


def scheduled_slot(tables: dict, update_ms: int) -> str | None:
    """The ADR 0004 target ("first", "1d", ..., merged as "first+1d") that the version
    `update_ms` fills, or None if the schedule does not pick it: the same rule as the
    retrospective issue times (`laf.tables.select_issue_times`) over the valid versions seen."""
    from laf.tables import select_issue_times

    ov = tables["oaf_versions"]
    valid = ov[ov["valid"] & ~ov["duplicate"].fillna(False).astype(bool)]
    # information cutoffs, as `build_tables` passes them (ADR 0004)
    mine = valid.loc[valid["update_ms"] == update_ms, "info_cutoff_ms"]
    if mine.empty:
        return None
    origin = int(tables["sequences"]["origin_ms"].iloc[0])
    picks = select_issue_times(origin, [int(c) for c in valid["info_cutoff_ms"]])
    return next((p.target for p in picks if p.issue_ms == int(mine.iloc[0])), None)


CONTEXT_MIN_MAG = 6.0  # the retrospective context: OAF events plus ComCat M>=6 (ADR 0013)


def context_url(lat: float, lon: float, origin_ms: int, mag: float) -> str:
    """ComCat events larger than `mag` in the 365 days before `origin_ms`, within the largest
    circle any event can have (M9.5)."""
    import urllib.parse

    from laf.catalog import wells_coppersmith_radius_km
    from laf.usgs import FDSN, iso

    q = {
        "format": "geojson",
        "starttime": iso(origin_ms - 365 * 86_400_000),
        "endtime": iso(origin_ms),
        "minmagnitude": f"{mag:.2f}",
        "latitude": f"{lat:.4f}",
        "longitude": f"{lon:.4f}",
        "maxradiuskm": f"{wells_coppersmith_radius_km(9.5):.1f}",
    }
    return f"{FDSN}/query?" + urllib.parse.urlencode(q)


def is_aftershock(lat: float, lon: float, origin_ms: int, mag: float, get=None) -> bool:
    """The backward half of the ADR 0006 rule (prereg v2 section 4): the new event lies inside
    the circle of a larger context event (an OAF event or ComCat M>=6) from the previous 365
    days. A later, larger event never excludes a sequence."""
    from laf.catalog import haversine_km, wells_coppersmith_radius_km
    from laf.usgs import download

    feats = json.loads((get or download)(context_url(lat, lon, origin_ms, mag)))["features"]
    for f in feats:
        p, (flon, flat, _) = f["properties"], f["geometry"]["coordinates"]
        types = (p.get("types") or "").strip(",").split(",")
        context = p["mag"] >= CONTEXT_MIN_MAG - 1e-9 or "oaf" in types
        inside = haversine_km(lat, lon, flat, flon) <= wells_coppersmith_radius_km(p["mag"])
        if context and p["mag"] > mag and p["time"] < origin_ms and inside:
            return True
    return False


def run_issue(clients, data_dir: Path, snapshot: str, seq: Sequence, out_root: Path, *,
              dry_run: bool = False, clock=time.time, publish=None,
              budget=local_budget) -> dict:  # fmt: skip
    """One issue end to end; `dry_run` skips the model calls (no spend) and times the rest.
    Only versions the ADR 0004 schedule picks are forecast; others return a skip record.
    `budget()` gives what each provider may still spend (`local_budget`, or `live_budget` on
    the live branch's ledger). `publish(rel, seal_path, extra=...)` (`laf.publish.publish`
    bound to a worktree) pushes each seal as soon as it exists: the answers, with the issue's
    spend file, before the baselines run. A publishing failure is recorded, never fatal."""
    t0 = clock()
    tables, items, update_ms = issue(data_dir, snapshot, seq, int(t0 * 1000))
    slot = scheduled_slot(tables, update_ms)
    if slot is None:
        return {"skipped": "not a scheduled version (ADR 0004)", "update_ms": update_ms}
    out = out_root / seq.id / str(update_ms)
    out.mkdir(parents=True, exist_ok=False)  # reserved before any paid call: no duplicate issue
    t1 = clock()
    calls = [] if dry_run else model_calls(clients, items, budget())
    (out / "calls.jsonl").write_text(_jsonl(calls), encoding="utf-8", newline="\n")  # spend log
    (out / "spend.jsonl").write_text(_jsonl(spend_rows(calls)), encoding="utf-8", newline="\n")
    published: dict = {}

    def post(name: str, extra: tuple[Path, ...] = ()) -> None:
        if publish is None:
            return
        try:
            seal = out / f"{name}.seal.json"
            published[name] = publish(f"{seq.id}/{update_ms}", seal, extra=extra)
        except Exception as e:  # the item is then not on time; the issue still completes
            published[name] = {"error": f"{type(e).__name__}: {e}"[:300]}

    answers = seal_answers(out, items, calls, clock)
    post("answers", (out / "spend.jsonl",))
    t2 = clock()
    base = baseline_forecasts(tables, items, data_dir)
    baselines = seal_baselines(out, base, clock)
    post("baselines")
    timing = {"build_s": t1 - t0, "models_s": t2 - t1, "baselines_s": clock() - t2,
              "dry_run": dry_run, "update_ms": update_ms, "slot": slot}  # fmt: skip
    return {"answers": answers, "baselines": baselines, "timing": timing, "published": published}
