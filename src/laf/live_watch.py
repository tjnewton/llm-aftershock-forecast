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
from functools import partial
from pathlib import Path

from laf.generic_rj import REFERENCE_REL
from laf.prospective import is_aftershock, live_budget, qualifies, run_issue
from laf.publish import branch, publish, push_receipt
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


def inclusion(doc: dict, key: str, decided: dict, get=download) -> tuple[str | None, str]:
    """(tier, reason) under prereg v2 section 4, decided on the values at the sequence's first
    detection: the magnitude rule (`qualifies`), then the backward aftershock check. Those values
    are kept in `decided` before the aftershock query, so a failed query is retried at the next
    version on them, never on revised ones; a later magnitude revision changes nothing."""
    if key not in decided:
        p = doc["properties"]
        lon, lat, _ = doc["geometry"]["coordinates"]
        tier = qualifies(float(p["mag"]), p.get("net") or "")
        decided[key] = {"tier": tier, "reason": "pending" if tier else "magnitude",
                        "mag": float(p["mag"]), "lat": lat, "lon": lon,
                        "time_ms": int(p["time"])}  # fmt: skip
    d = decided[key]
    if d["reason"] == "pending":
        if is_aftershock(d["lat"], d["lon"], d["time_ms"], d["mag"], get):
            d["tier"], d["reason"] = None, "aftershock"
        else:
            d["reason"] = "included"
    return d["tier"], d["reason"]


def live_issue(
    data_dir: Path, event_id: str, now_ms: int, get=download, publish_to: Path | None = None,
    clients: dict | None = None,
) -> dict:  # fmt: skip
    """Fetch the sequence into a snapshot stamped now and run its newest version through the
    prospective pipeline; the sealed records go under data_dir/issues and, with `publish_to`
    (a worktree of `live-test`, or of `live` when paid), their seals are pushed there. Without
    `clients` it makes no model calls; with them it spends only the live reserve, counted on
    the published ledger."""
    snap = datetime.fromtimestamp(now_ms / 1000, UTC).strftime("%Y%m%dT%H%MZ")
    t0 = time.time()
    fetch_sequence(data_dir, snap, event_id, CATALOG_MIN_MAG, now_ms=now_ms, get=get)
    seq = Sequence(id=event_id, name=event_id, role="test-post", catalog_min_mag=CATALOG_MIN_MAG)
    fetch_s = time.time() - t0
    pub = partial(publish, publish_to) if publish_to else None
    budget = partial(live_budget, publish_to) if clients and publish_to else None

    def seen(rel: str) -> bool:  # the branch, not this host's state, says what was issued
        return bool(publish_to) and (publish_to / rel / "answers.seal.json").exists()

    rec = run_issue(clients, data_dir, snap, seq, data_dir / "issues", dry_run=clients is None,
                    publish=pub, budget=budget or (lambda: {}), issued=seen)  # fmt: skip
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
        "matched_first_ms": first["live-matched"], "published": rec["published"],
    }  # fmt: skip


def check_receipts(out: Path, state: dict, get=download) -> None:
    """Look up GitHub's push time for each published answers seal not yet confirmed and log it
    with the matched item's margin from that receipt (the registered on-time criterion). A
    receipt still missing after a day is logged as missing."""
    keep = []
    for r in state.get("receipts", []):
        try:
            ms = push_receipt(r["repo"], r["branch"], r["commit"], get)
        except Exception:  # GitHub unreachable: try again next poll
            ms = None
        if ms is not None:
            margin_s, lag_s = (r["matched_first_ms"] - ms) / 1000, (ms - r["pushed_ms"]) / 1000
            _log(out, {"kind": "receipt", **r, "receipt_ms": ms,
                       "matched_receipt_margin_s": margin_s, "receipt_lag_s": lag_s})  # fmt: skip
        elif _now_ms() - r["pushed_ms"] > 86_400_000:
            _log(out, {"kind": "receipt", **r, "receipt_ms": None})
        else:
            keep.append(r)
    state["receipts"] = keep


def step(
    out: Path, data_dir: Path, state: dict, get=download, publish_to: Path | None = None,
    clients: dict | None = None,
) -> dict:  # fmt: skip
    """One poll: confirm pending push receipts, detect new OAF versions since the last poll and
    run each included sequence's newest version once."""
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
    check_receipts(out, state, get)
    seen, decided = state.setdefault("seen", {}), state.setdefault("inclusion", {})

    def version(v: dict) -> dict:
        # indexed before this poll's window: a sequence seen for the first time
        return {**v, "detect_latency_s": (t_poll - v["index_ms"]) / 1000,
                "backlog": v["index_ms"] < since}  # fmt: skip

    for event_id in ids:
        det = {"kind": "detection", "pipeline": "prospective", "event_id": event_id,
               "poll_ms": t_poll}  # fmt: skip
        vs: list[dict] = []
        try:
            doc = json.loads(get(event_url(event_id)))
            key = event_key(doc, seen.keys() | decided.keys())
            vs = new_versions(doc, set(seen.get(key, [])))
            if not vs:
                continue
            # tried once: a failure below is logged, never retried (prereg v2 section 5)
            seen[key] = sorted(set(seen.get(key, [])) | {v["update_ms"] for v in vs})
            p = doc["properties"]
            tier, reason = inclusion(doc, key, decided, get)
            det |= {"key": key, "mag": p.get("mag"), "net": p.get("net"), "tier": tier,
                    "inclusion": reason}  # fmt: skip
            built = live_issue(data_dir, event_id, t_poll, get, publish_to, clients) if tier else {}
            answers = (built.get("published") or {}).get("answers") or {}
            if answers.get("commit") and answers.get("repo"):
                state.setdefault("receipts", []).append({
                    "key": key, "update_ms": built["matched_update_ms"],
                    "matched_first_ms": built["matched_first_ms"],
                    **{k: answers[k] for k in ("repo", "branch", "commit", "pushed_ms")},
                })  # fmt: skip
            for v in vs:
                # only the version the matched item is built from has a slot and margins; an
                # older or invalid version detected in the same poll is superseded
                own = v["update_ms"] == built.get("matched_update_ms")
                _log(out, {**det, **version(v), **(built if own else {}),
                           "superseded": bool(tier) and not own})  # fmt: skip
        except Exception as e:  # one record per version tried, so failures stay countable
            err = {"error": f"{type(e).__name__}: {e}"[:300]}
            for v in vs or [None]:
                _log(out, {**det, **(version(v) if v else {}), **err})
    state["last_poll_ms"] = t_poll
    (out / "state.json").write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
    return state


def run(
    out: Path, data_dir: Path, repo_data: Path, polls: int | None = None,
    publish_to: Path | None = None, paid: bool = False,
) -> None:  # fmt: skip
    """Poll every POLL_S seconds until stopped (or `polls` times). `paid` runs the live models
    and must publish to the `live` branch; the dry run must not."""
    on = branch(publish_to) if publish_to else None
    if paid and on != "live":
        raise SystemExit("--paid publishes to a worktree of branch live (--publish)")
    if not paid and on == "live":
        raise SystemExit("the dry run never publishes to live: use a worktree of live-test")
    clients = None
    if paid:
        from laf.openai_runner import client as openai_client
        from laf.providers import client as anthropic_client

        assert publish_to is not None  # a live worktree, checked above
        live_budget(publish_to)  # refuses before the first poll if a reserve is unset
        clients = {"claude": anthropic_client(), "openai": openai_client()}
    out.mkdir(parents=True, exist_ok=True)
    ref = data_dir / REFERENCE_REL
    if not ref.exists():  # generic-RJ reference tables, read by build_tables
        shutil.copytree(repo_data / REFERENCE_REL, ref)
    state_path = out / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    n = 0
    while polls is None or n < polls:
        state = step(out, data_dir, state, publish_to=publish_to, clients=clients)
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
