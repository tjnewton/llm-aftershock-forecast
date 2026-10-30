"""Dry run of the live arm's detector (docs/adr/0017): poll ComCat for new OAF versions and
time each step of building the live items. It makes no model calls and scores nothing.

Every poll and every detected version is appended to `<out>/log.jsonl`. A detection records
the version's ComCat index time and update time, when the poll saw it, how long fetching the
sequence and building the items took, the items' SHA-256, and any error. The items are the live
ones (`laf.live.live_items`): matched to the newest valid OAF version, and strict, with windows
opening at the next full hour. `matched_margin_s` is that version's first window start minus the
hash time (negative: the matched item would be late); older versions found in the same poll are
`superseded`; `strict_margin_s` should always be positive. Fetched raw data goes
to a separate data directory (gitignored), never into data/raw. Outcomes stay sealed because
`build_tables` seals every confirmatory sequence (docs/adr/0013).
"""

import hashlib
import json
import shutil
import time
import urllib.parse
from datetime import UTC, datetime
from pathlib import Path

from laf.generic_rj import REFERENCE_REL
from laf.live import live_items, next_full_hour
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


def build_live_items(data_dir: Path, event_id: str, now_ms: int, get=download) -> dict:
    """Fetch the sequence into a snapshot stamped now and build the live items the arm would
    forecast (`laf.live.live_items`): one matched to the newest valid OAF version and one strict,
    whose windows open at the next full hour at least 30 minutes after now. Outcomes sealed."""
    snap = datetime.fromtimestamp(now_ms / 1000, UTC).strftime("%Y%m%dT%H%MZ")
    fetch_sequence(data_dir, snap, event_id, CATALOG_MIN_MAG, now_ms=now_ms, get=get)
    seq = Sequence(id=event_id, name=event_id, role="test-post", catalog_min_mag=CATALOG_MIN_MAG)
    strict_ms = next_full_hour(now_ms + 30 * 60_000)
    items, newest_update_ms = live_items(data_dir, snap, seq, now_ms, strict_ms)
    body = "".join(i.model_dump_json() + "\n" for i in items)
    matched = next(i for i in items if i.item_id.endswith("@live-matched"))
    return {
        "items_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "matched_update_ms": newest_update_ms,
        "matched_window_start_ms": min(w.start_ms for w in matched.windows),
        "strict_window_start_ms": strict_ms,
    }


def step(out: Path, data_dir: Path, state: dict, get=download) -> dict:
    """One poll: detect new OAF versions since the last poll and time each one's items."""
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
    seen = state.setdefault("seen", {})
    for event_id in ids:
        t0 = _now_ms()
        det = {"kind": "detection", "event_id": event_id, "poll_ms": t_poll}
        try:
            doc = json.loads(get(event_url(event_id)))
            vs = new_versions(doc, set(seen.get(event_id, [])))
            if not vs:
                continue
            mag = doc["properties"].get("mag")
            built = build_live_items(data_dir, event_id, t_poll, get)
            t1 = _now_ms()
            for v in vs:
                # only the version the matched item is built from has a margin; an older or
                # invalid version detected in the same poll is superseded, not on time
                own = v["update_ms"] == built["matched_update_ms"]
                _log(out, {
                    **det, **v, **built, "mag": mag,
                    "detect_latency_s": (t_poll - v["index_ms"]) / 1000,
                    # indexed before this poll's window: a sequence seen for the first time
                    "backlog": v["index_ms"] < since,
                    "build_s": (t1 - t0) / 1000,
                    "matched_margin_s": (
                        (built["matched_window_start_ms"] - t1) / 1000 if own else None
                    ),
                    "strict_margin_s": (built["strict_window_start_ms"] - t1) / 1000,
                    "superseded": not own,
                })  # fmt: skip
            seen[event_id] = sorted(set(seen.get(event_id, [])) | {v["update_ms"] for v in vs})
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
