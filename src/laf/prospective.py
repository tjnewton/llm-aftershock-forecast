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

from laf.items import Item, build_items
from laf.live import live_tables, next_full_hour
from laf.prompts import render, schema_for
from laf.providers import anthropic_params, call_anthropic, cost_usd, study_effort
from laf.registry import Sequence
from laf.runner import check_budget

LIVE_MODELS = ("claude-opus-5-5",)  # gpt-6.1-sol joins once its runner and effort are set
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


def _params(item: Item, model: str) -> dict:
    system, user = render(item, "direct", "I1", PROMPT)
    return anthropic_params(
        model, system, user, schema_for("direct", PROMPT),
        effort=study_effort(model), max_tokens=MAX_TOKENS,
    )  # fmt: skip


def bound_usd(items: list[Item], models=LIVE_MODELS, k: int = K) -> float:
    """The most the calls for one issue can cost: every answer at its whole output budget."""
    total = 0.0
    for item in items:
        for model in models:
            p = _params(item, model)
            usage = {"input_tokens": len(json.dumps(p)) / 1.25, "output_tokens": MAX_TOKENS}
            total += k * cost_usd(model, usage)
    return total


def model_calls(client, items: list[Item], models=LIVE_MODELS, k: int = K) -> list[dict]:
    """k synchronous answers per item and model, after the monthly spend guard."""
    check_budget(bound_usd(items, models, k))
    jobs = [(i.item_id, m, s, _params(i, m)) for i in items for m in models for s in range(k)]

    def call(job):
        item_id, _, s, params = job
        effort = params["output_config"]["effort"]
        rec = call_anthropic(client, params, stream=True)
        return {"item_id": item_id, "paraphrase": PROMPT, "effort": effort, "sample": s, **rec}

    with ThreadPoolExecutor(6) as pool:
        recs = list(pool.map(call, jobs))
    return sorted(recs, key=lambda r: (r["item_id"], r["model_requested"], r["sample"]))


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


def run_issue(client, data_dir: Path, snapshot: str, seq: Sequence, out_root: Path,
              *, dry_run: bool = False, clock=time.time) -> dict:  # fmt: skip
    """One issue end to end; `dry_run` skips the model calls (no spend) and times the rest.
    Only versions the ADR 0004 schedule picks are forecast; others return a skip record."""
    t0 = clock()
    tables, items, update_ms = issue(data_dir, snapshot, seq, int(t0 * 1000))
    slot = scheduled_slot(tables, update_ms)
    if slot is None:
        return {"skipped": "not a scheduled version (ADR 0004)", "update_ms": update_ms}
    out = out_root / seq.id / str(update_ms)
    out.mkdir(parents=True, exist_ok=False)  # reserved before any paid call: no duplicate issue
    t1 = clock()
    calls = [] if dry_run else model_calls(client, items)
    (out / "calls.jsonl").write_text(_jsonl(calls), encoding="utf-8", newline="\n")  # spend log
    answers = seal_answers(out, items, calls, clock)
    t2 = clock()
    base = baseline_forecasts(tables, items, data_dir)
    baselines = seal_baselines(out, base, clock)
    timing = {"build_s": t1 - t0, "models_s": t2 - t1, "baselines_s": clock() - t2,
              "dry_run": dry_run, "update_ms": update_ms, "slot": slot}  # fmt: skip
    return {"answers": answers, "baselines": baselines, "timing": timing}
