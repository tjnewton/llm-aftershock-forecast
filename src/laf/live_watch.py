"""Dry run of the live arm's detector (docs/adr/0017; prereg v2 sections 4-5): poll ComCat for
new OAF versions, apply the inclusion rule, and run each scheduled issue through the prospective
pipeline (`laf.prospective.run_issue`) without model calls. It spends nothing and scores nothing.

Every poll and every detected version is appended to `<out>/log.jsonl`. A detection records the
version's ComCat index time and update time, when the poll saw it, the inclusion decision, and,
for an included sequence, the ADR 0004 slot, how long fetching, building and the baselines took,
the two records' SHA-256, and any error. `matched_margin_s` is the matched item's first window
start minus the answers seal (negative: late; the dry run has no model time, so a paid issue's
margin is smaller by the models' latency); older versions found in the same poll are
`superseded`; `strict_margin_s` should always be positive. Each version is tried once and never
backfilled. Fetched raw data and the sealed dry-run records go to the live data directory
(gitignored), never into data/raw or the log. Outcomes stay sealed because `build_tables` seals
every confirmatory sequence (docs/adr/0013).
"""

import json
import shutil
import time
import urllib.parse
from datetime import UTC, datetime
from pathlib import Path

from laf.generic_rj import REFERENCE_REL
from laf.prospective import is_aftershock, qualifies, run_issue
from laf.registry import Sequence
from laf.usgs import FDSN, download, event_url, fetch_sequence, iso

POLL_S = 600  # every 10 minutes
CATALOG_MIN_MAG = 3.0


def poll_url(since_ms: int) -> str:
    q = {
        "format": "geojson",
        "producttype": "oaf",
        "updatedafter": iso(since_ms),
        "orderby": "time",
    }
    return f"{FDSN}/query?" + urllib.parse.urlencode(q)


def new_versions(event_doc: dict, seen: set[int]) -> list[dict]:
    """OAF versions in an event document (includesuperseded) whose updateTime is unseen."""
    out = []
    for p in event_doc["properties"]["products"].get("oaf", []):
        up = int(p["updateTime"])
        if up not in seen and "forecast.json" in p.get("contents", {}):
            out.append({"update_ms": up, "index_ms": int(p.get("indexTime", up))})
    return sorted(out, key=lambda v: v["update_ms"])


def _now_ms() -> int:
    return int(time.time() * 1000)


def _log(out: Path, rec: dict) -> None:
    with (out / "log.jsonl").open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")


def event_key(doc: dict, known) -> str:
    """The ID a sequence is tracked under: the first of its ComCat associated IDs already
    `known`, else its preferred ID, so a change of preferred ID is the same sequence."""
    ids = [i for i in (doc["properties"].get("ids") or "").split(",") if i]
    return next((i for i in ids if i in known), doc["id"])


def inclusion(doc: dict, key: str, included: dict, get=download) -> tuple[str | None, str]:
    """(tier, reason) under prereg v2 section 4: once included, always included; otherwise the
    magnitude rule (`qualifies`), then the backward aftershock check."""
    if key in included:
        return included[key], "included"
    p = doc["properties"]
    tier = qualifies(float(p["mag"]), p.get("net") or "")
    if tier is None:
        return None, "magnitude"
    lon, lat, _ = doc["geometry"]["coordinates"]
    if is_aftershock(lat, lon, int(p["time"]), float(p["mag"]), get):
        return None, "aftershock"
    included[key] = tier
    return tier, "included"


def dry_issue(data_dir: Path, event_id: str, now_ms: int, get=download) -> dict:
    """Fetch the sequence into a snapshot stamped now and run its newest version through the
    prospective pipeline without model calls; the sealed records go under data_dir/issues."""
    snap = datetime.fromtimestamp(now_ms / 1000, UTC).strftime("%Y%m%dT%H%MZ")
    t0 = time.time()
    fetch_sequence(data_dir, snap, event_id, CATALOG_MIN_MAG, now_ms=now_ms, get=get)
    seq = Sequence(id=event_id, name=event_id, role="test-post", catalog_min_mag=CATALOG_MIN_MAG)
    fetch_s = time.time() - t0
    rec = run_issue(None, data_dir, snap, seq, data_dir / "issues", dry_run=True)
    if "skipped" in rec:
        return {"fetch_s": fetch_s, "matched_update_ms": rec["update_ms"], "slot": None,
                "skipped": rec["skipped"]}  # fmt: skip
    a, b, t = rec["answers"], rec["baselines"], rec["timing"]
    first = {i.rsplit("@", 1)[1]: v["first_window_ms"] for i, v in a["items"].items()}
    return {
        "fetch_s": fetch_s, "build_s": t["build_s"], "baselines_s": t["baselines_s"],
        "matched_update_ms": t["update_ms"], "slot": t["slot"],
        "answers_sha256": a["record_sha256"], "baselines_sha256": b["record_sha256"],
        "matched_margin_s": (first["live-matched"] - a["sealed_ms"]) / 1000,
        "strict_margin_s": (first["live-strict"] - a["sealed_ms"]) / 1000,
    }  # fmt: skip


def step(out: Path, data_dir: Path, state: dict, get=download) -> dict:
    """One poll: detect new OAF versions since the last poll and run each included sequence's
    newest version once."""
    t_poll = _now_ms()
    since = state.get("last_poll_ms", t_poll - POLL_S * 1000)
    rec = {"kind": "poll", "poll_ms": t_poll, "since_ms": since}
    try:
        feed = json.loads(get(poll_url(since)))
        ids = [f["id"] for f in feed.get("features", [])]
    except Exception as e:  # a failed poll is a failure mode to measure, not a crash
        _log(out, {**rec, "error": f"{type(e).__name__}: {e}"[:300]})
        return state
    _log(out, {**rec, "events": len(ids)})
    seen, included = state.setdefault("seen", {}), state.setdefault("included", {})
    for event_id in ids:
        det = {"kind": "detection", "pipeline": "prospective", "event_id": event_id,
               "poll_ms": t_poll}  # fmt: skip
        try:
            doc = json.loads(get(event_url(event_id)))
            key = event_key(doc, seen.keys() | included.keys())
            vs = new_versions(doc, set(seen.get(key, [])))
            if not vs:
                continue
            # tried once: a failure below is logged, never retried (prereg v2 section 5)
            seen[key] = sorted(set(seen.get(key, [])) | {v["update_ms"] for v in vs})
            p = doc["properties"]
            tier, reason = inclusion(doc, key, included, get)
            det |= {"key": key, "mag": p.get("mag"), "net": p.get("net"), "tier": tier,
                    "inclusion": reason}  # fmt: skip
            built = dry_issue(data_dir, event_id, t_poll, get) if tier else {}
            for v in vs:
                # only the version the matched item is built from has a slot and margins; an
                # older or invalid version detected in the same poll is superseded
                own = v["update_ms"] == built.get("matched_update_ms")
                _log(out, {
                    **det, **v, **(built if own else {}),
                    "detect_latency_s": (t_poll - v["index_ms"]) / 1000,
                    # indexed before this poll's window: a sequence seen for the first time
                    "backlog": v["index_ms"] < since,
                    "superseded": bool(tier) and not own,
                })  # fmt: skip
        except Exception as e:
            _log(out, {**det, "error": f"{type(e).__name__}: {e}"[:300]})
    state["last_poll_ms"] = t_poll
    (out / "state.json").write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
    return state


def run(out: Path, data_dir: Path, repo_data: Path, polls: int | None = None) -> None:
    """Poll every POLL_S seconds until stopped (or `polls` times)."""
    out.mkdir(parents=True, exist_ok=True)
    ref = data_dir / REFERENCE_REL
    if not ref.exists():  # generic-RJ reference tables, read by build_tables
        shutil.copytree(repo_data / REFERENCE_REL, ref)
    state_path = out / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    n = 0
    while polls is None or n < polls:
        state = step(out, data_dir, state)
        n += 1
        if polls is None or n < polls:
            time.sleep(POLL_S)


def version_slack_s(versions):
    """Seconds from each valid, non-duplicate OAF version's publication (`update_ms`) to its
    first window start (`time_start_ms`); negative when the window opened first. Timing
    columns only."""
    import numpy as np

    v = versions[versions["valid"] & ~versions["duplicate"].fillna(False).astype(bool)]
    v = v.drop_duplicates(["sequence_id", "update_ms"])
    return ((v["time_start_ms"] - v["update_ms"]) / 1000).to_numpy(dtype=float), np.unique(
        v["sequence_id"]
    ).size


def late_share(slack_s, lag_s, poll_s: float, forecast_s: float, n: int = 200_000) -> float:
    """Share of matched live items that would be late (docs/adr/0017): ComCat shows a version
    after an index lag (resampled from the dry run), the detector sees it at the next poll
    (uniform wait), and the hash follows after `forecast_s`; the item is late when that comes
    after the version's first window start."""
    import numpy as np

    rng = np.random.default_rng(20261030)
    s, lag = rng.choice(slack_s, n), rng.choice(lag_s, n)
    return float(np.mean(lag + rng.uniform(0, poll_s, n) + forecast_s > s))


def index_lags_s(log: Path) -> list[float]:
    """ComCat index time minus OAF update time for every detection in a dry-run log."""
    rows = [json.loads(x) for x in log.read_text(encoding="utf-8").split("\n") if x.strip()]
    return [
        (r["index_ms"] - r["update_ms"]) / 1000
        for r in rows
        if r.get("kind") == "detection" and r.get("index_ms") and r.get("update_ms")
    ]  # failed detections may lack the timestamps
