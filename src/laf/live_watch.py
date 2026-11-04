"""The live arm's detector (docs/adr/0017; prereg v2 sections 4-5): poll ComCat for new OAF
versions, apply the inclusion rule, and run each scheduled issue through the prospective
pipeline (`laf.prospective.run_issue`). The dry run makes no model calls and spends nothing;
`--paid` spends only the live reserve. Neither scores anything.

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
import os
import shutil
import subprocess
import time
import urllib.parse
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

from laf.generic_rj import REFERENCE_REL
from laf.prospective import is_aftershock, live_budget, qualifies, run_issue
from laf.publish import (
    SEALS,
    add_record,
    branch,
    introduced_by,
    publish,
    push_pending,
    push_times,
    release,
    released,
    repo_slug,
    seal_commit,
)
from laf.registry import Sequence
from laf.usgs import FDSN, download, event_url, fetch_sequence, iso

POLL_S = 600  # every 10 minutes
CATALOG_MIN_MAG = 3.0
# each poll looks an hour further back than the last one: a version ComCat indexed late, or
# whose event document failed to load, is seen again (`seen` drops the repeats)
OVERLAP_MS = 3_600_000
# ComCat's starttime defaults to 30 days ago, which would hide the 28-day slot's versions; the
# schedule's last slot closes 35 days after the origin (ADR 0004)
LOOKBACK_MS = 40 * 86_400_000
START_FILE = "start.json"  # L, at the root of the live branch (prereg v2 section 5)


def poll_url(since_ms: int) -> str:
    q = {
        "format": "geojson",
        "producttype": "oaf",
        "updatedafter": iso(since_ms),
        "starttime": iso(since_ms - LOOKBACK_MS),
        "orderby": "time",
    }
    return f"{FDSN}/query?" + urllib.parse.urlencode(q)


def start_ms(publish_to: Path | None) -> int | None:
    """L: the paid detector's start, as `start.json` on the live branch records it (None
    before the start, and always for the dry run)."""
    path = publish_to / START_FILE if publish_to else None
    if path is None or not path.exists():
        return None
    return int(json.loads(path.read_text(encoding="utf-8"))["start_ms"])


def _save_state(path: Path, state: dict) -> None:
    """Write `state.json` whole or not at all: a half-written file would stop every restart."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


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


STOP_FILE = Path("config/live_stop.toml")


def admission_stop_ms(path: Path = STOP_FILE) -> int | None:
    """S from config/live_stop.toml in the running checkout (the commit Tyler tags
    `prereg-v2-stop`, deployed to the service worktree), or None before the stop."""
    import tomllib

    return int(tomllib.loads(path.read_text(encoding="utf-8"))["s_ms"]) if path.exists() else None


def inclusion(
    doc: dict, key: str, decided: dict, get=download, stop_ms: int | None = None,
    start: int | None = None, now_ms: int | None = None,
) -> tuple[str | None, str]:  # fmt: skip
    """(tier, reason) under prereg v2 section 4, decided on the values at the sequence's first
    detection (`now_ms`, kept as `detected_ms`): the magnitude rule (`qualifies`), then the
    backward aftershock check. Those values are kept in `decided` before the aftershock query,
    so a failed query is retried at the next version on them, never on revised ones; a later
    magnitude revision changes nothing. Prospective sequences have origin in [L, S] (prereg v2
    section 5): a new sequence whose origin is before L (`start`) or after S is not admitted;
    admitted sequences keep their scheduled issues."""
    if key not in decided:
        p = doc["properties"]
        lon, lat, _ = doc["geometry"]["coordinates"]
        tier = qualifies(float(p["mag"]), p.get("net") or "")
        reason = "pending" if tier else "magnitude"
        if tier and start is not None and int(p["time"]) < start:  # retrospective (before L)
            tier, reason = None, "before the start"
        if tier and stop_ms is not None and int(p["time"]) > stop_ms:  # [L, S] (decision 23)
            tier, reason = None, "after the stop"
        decided[key] = {"tier": tier, "reason": reason, "mag": float(p["mag"]), "lat": lat,
                        "lon": lon, "time_ms": int(p["time"]), "detected_ms": now_ms}  # fmt: skip
    d = decided[key]
    if d["reason"] == "pending":
        if is_aftershock(d["lat"], d["lon"], d["time_ms"], d["mag"], get):
            d["tier"], d["reason"] = None, "aftershock"
        else:
            d["reason"] = "included"
    return d["tier"], d["reason"]


def live_sequence(event_id: str) -> Sequence:
    """A detected event as a sequence (it is in no config)."""
    return Sequence(id=event_id, name=event_id, role="test-post", catalog_min_mag=CATALOG_MIN_MAG)


SECONDARY_KEEP = 0.5  # secondary sequences stop once half of a provider's reserve is spent


def live_issue(
    data_dir: Path, event_id: str, now_ms: int, get=download, publish_to: Path | None = None,
    clients: dict | None = None, tier: str = "primary",
) -> dict:  # fmt: skip
    """Fetch the sequence into a snapshot stamped now and run its newest version through the
    prospective pipeline; the sealed records go under data_dir/issues and, with `publish_to`
    (a worktree of `live-test`, or of `live` when paid), their seals are pushed there. Without
    `clients` it makes no model calls; with them it spends only the live reserve, counted on
    the published ledger, and a secondary sequence only the part of it above
    `SECONDARY_KEEP`, which is kept for primary sequences."""
    snap = datetime.fromtimestamp(now_ms / 1000, UTC).strftime("%Y%m%dT%H%MZ")
    t0 = time.time()
    fetch_sequence(data_dir, snap, event_id, CATALOG_MIN_MAG, now_ms=now_ms, get=get)
    seq = live_sequence(event_id)
    fetch_s = time.time() - t0
    pub = partial(publish, publish_to) if publish_to else None
    keep = SECONDARY_KEEP if tier == "secondary" else 0.0
    budget = partial(live_budget, publish_to, keep=keep) if clients and publish_to else None

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


RECEIPT_GIVE_UP_MS = 86_400_000


def check_receipts(out: Path, state: dict, publish_to: Path | None, page=None) -> None:
    """Look up GitHub's push time (the registered on-time criterion) for every answers seal on
    the branch without a `receipt.json`, log it with the matched item's margin, and commit it
    beside its seal, so the branch keeps the evidence however long GitHub keeps its activity
    list. The pending seals come from the branch, not from this host's memory: a seal whose
    push was retried at a later poll, whose proof push failed, or whose detector stopped
    before saving its state still gets its receipt. One still missing a day after this host
    first saw it pushed is logged as missing once and not looked up again."""
    try:
        repo = repo_slug(publish_to) if publish_to else None
    except Exception:  # not a clone (tests), or git failing: the next poll tries again
        repo = None
    if publish_to is None or repo is None:
        return  # no GitHub origin: no receipt
    gave_up = state.setdefault("receipts_missing", [])
    pending: dict[str, tuple[str, int]] = {}
    for seal in sorted(publish_to.glob(f"*/*/{SEALS[0]}")):
        rel = seal.parent.relative_to(publish_to).as_posix()
        if rel in gave_up or (seal.parent / "receipt.json").exists():
            continue
        if found := seal_commit(publish_to, rel):  # None until pushed
            pending[found[0]] = (rel, found[1])
    now, old = _now_ms(), state.get("receipts_since", {})
    # when this host first saw each seal pushed: a push that failed for a day still gets a day
    since = state["receipts_since"] = {rel: old.get(rel, now) for rel, _ in pending.values()}
    if not pending:
        state["receipts"] = []
        return
    br = branch(publish_to)
    try:
        times = push_times(repo, br, {c: t for c, (_, t) in pending.items()},
                           introduced=introduced_by(publish_to),
                           **({"page": page} if page else {}))  # fmt: skip
    except Exception as e:  # GitHub unreachable: try again next poll
        _log(out, {"kind": "receipt", "error": f"{type(e).__name__}: {e}"[:300]})
        return
    pushed = {r["commit"]: r["pushed_ms"] for r in state.get("receipts", [])}  # this host's
    for commit, (rel, _) in pending.items():
        ms = times.get(commit)
        if ms is None:
            if now - since[rel] > RECEIPT_GIVE_UP_MS:
                _log(out, {"kind": "receipt", "rel": rel, "commit": commit, "receipt_ms": None})
                gave_up.append(rel)
            continue
        seal = json.loads((publish_to / rel / SEALS[0]).read_text(encoding="utf-8"))
        first = [v.get("first_window_ms") for i, v in (seal.get("items") or {}).items()
                 if i.endswith("@live-matched")]  # fmt: skip  # a hand-made test seal has none
        rec = {"commit": commit, "receipt_ms": ms, "pushed_ms": pushed.get(commit),
               "source": f"api.github.com/repos/{repo}/activity (push to {br})"}  # fmt: skip
        lag_s = (ms - pushed[commit]) / 1000 if commit in pushed else None
        margin_s = (first[0] - ms) / 1000 if first and first[0] is not None else None
        _log(out, {"kind": "receipt", "rel": rel, **rec, "matched_receipt_margin_s": margin_s,
                   "receipt_lag_s": lag_s})  # fmt: skip
        try:
            add_record(publish_to, rel, "receipt.json", rec)
        except Exception as e:  # logged above; looked up again next poll
            _log(out, {"kind": "receipt_record", "rel": rel,
                       "error": f"{type(e).__name__}: {e}"[:300]})  # fmt: skip
    open_ = {c for c, (rel, _) in pending.items() if c not in times and rel not in gave_up}
    state["receipts"] = [r for r in state.get("receipts", []) if r["commit"] in open_]


def release_closed(out: Path, data_dir: Path, publish_to: Path, now_ms: int) -> None:
    """Release every sealed issue whose forecast windows have all closed (prereg v2 section 5):
    its records under data_dir/issues go to the branch beside its seals (`publish.release`)."""
    root = data_dir / "issues"
    for items_file in sorted(root.glob("*/*/items.jsonl")):
        rel = items_file.parent.relative_to(root).as_posix()
        if released(publish_to, rel) or not (publish_to / rel / SEALS[0]).exists():
            continue  # released already, or never published
        try:  # a damaged record is logged and skipped; the detector keeps polling
            lines = items_file.read_text(encoding="utf-8").split("\n")
            last = max(
                w["end_ms"] for line in lines if line.strip() for w in json.loads(line)["windows"]
            )
            if last > now_ms:
                continue  # a window is still open
            commit = release(publish_to, rel, items_file.parent)
            _log(out, {"kind": "release", "rel": rel, "commit": commit})
        except Exception as e:  # listed, never forced: a mismatch needs a look by hand
            _log(out, {"kind": "release", "rel": rel, "error": f"{type(e).__name__}: {e}"[:300]})


def step(
    out: Path, data_dir: Path, state: dict, get=download, publish_to: Path | None = None,
    clients: dict | None = None,
) -> dict:  # fmt: skip
    """One poll: detect new OAF versions since the last poll (and the hour before it) and run
    each included sequence's newest version once; then confirm push receipts, push what an
    earlier failed push left behind and release closed issues. Detection goes first, so a slow
    GitHub never delays an issue."""
    t_poll = _now_ms()
    since = state.get("last_poll_ms", t_poll - POLL_S * 1000)
    if detect(out, data_dir, state, t_poll, since, get, publish_to, clients):
        state["last_poll_ms"] = t_poll
    if publish_to:
        try:
            if n := push_pending(publish_to):
                _log(out, {"kind": "push_pending", "commits": n})
        except Exception as e:
            _log(out, {"kind": "push_pending", "error": f"{type(e).__name__}: {e}"[:300]})
        # housekeeping never stops the detector: a failure is logged and retried next poll
        for kind, task in (
            ("receipt", lambda: check_receipts(out, state, publish_to)),
            ("release", lambda: release_closed(out, data_dir, publish_to, t_poll)),
        ):
            try:
                task()
            except Exception as e:
                _log(out, {"kind": kind, "error": f"{type(e).__name__}: {e}"[:300]})
    _save_state(out / "state.json", state)
    return state


def _decision_on_branch(publish_to: Path | None, doc: dict, event_id: str) -> dict | None:
    """An included sequence's first-detection decision as published (`inclusion.json`), under
    any of the event's ComCat IDs, so a lost local state never decides it again on revised
    values, even after a change of preferred ID. The record keeps its tracking `key`."""
    if publish_to is None:
        return None
    ids = [event_id, doc["id"], *(i for i in (doc["properties"].get("ids") or "").split(",") if i)]
    for name in dict.fromkeys(ids):
        path = publish_to / name / "inclusion.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8")) | {"folder": name}
    return None


def detect(
    out: Path, data_dir: Path, state: dict, t_poll: int, since: int, get=download,
    publish_to: Path | None = None, clients: dict | None = None,
) -> bool:  # fmt: skip
    """The detection half of a poll; False when the poll itself failed."""
    rec = {"kind": "poll", "poll_ms": t_poll, "since_ms": since}
    try:
        feed = json.loads(get(poll_url(since - OVERLAP_MS)))
        ids = [f["id"] for f in feed.get("features", [])]
    except Exception as e:  # a failed poll is a failure mode to measure, not a crash
        _log(out, {**rec, "error": f"{type(e).__name__}: {e}"[:300]})
        return False
    _log(out, {**rec, "events": len(ids)})
    stop = admission_stop_ms()  # read every poll: the stop takes effect once deployed
    start = start_ms(publish_to)
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
            if key not in decided and (known := _decision_on_branch(publish_to, doc, event_id)):
                key = known.pop("key", None) or known["folder"]  # its original tracking key
                known.pop("folder")
                decided.setdefault(key, known)
            vs = new_versions(doc, set(seen.get(key, [])))
            if not vs:
                continue
            # tried once: a failure below is logged, never retried (prereg v2 section 5)
            seen[key] = sorted(set(seen.get(key, [])) | {v["update_ms"] for v in vs})
            p = doc["properties"]
            tier, reason = inclusion(doc, key, decided, get, stop, start, t_poll)
            det |= {"key": key, "mag": p.get("mag"), "net": p.get("net"), "tier": tier,
                    "inclusion": reason}  # fmt: skip
            seq_dir = publish_to / event_id if publish_to else None
            if tier and seq_dir and not (seq_dir / "inclusion.json").exists():
                # the first-detection decision, which the analysis must use (prereg v2 s4),
                # before the issue runs: a later failure must not lose it
                try:
                    add_record(
                        seq_dir.parent, event_id, "inclusion.json", {"key": key, **decided[key]}
                    )
                except Exception as e:  # logged; the decision is also in state.json
                    _log(out, {**det, "kind": "inclusion_record",
                               "error": f"{type(e).__name__}: {e}"[:300]})  # fmt: skip
            built = (live_issue(data_dir, event_id, t_poll, get, publish_to, clients, tier)
                     if tier else {})  # fmt: skip
            answers = (built.get("published") or {}).get("answers") or {}
            if answers.get("commit") and answers.get("repo"):
                state.setdefault("receipts", []).append({
                    "key": key, "update_ms": built["matched_update_ms"],
                    "rel": f"{event_id}/{built['matched_update_ms']}",
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
    return True


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
    state_path = out / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    # the paid detector never resumes a dry run's state (seen versions, last poll) nor shares
    # its issue folders: each mode keeps its own --out and --live-data
    mode = "paid" if paid else "dry"
    marker = data_dir / "mode.txt"
    # folders from before this marker existed are the dry run's
    held = {out: state.get("mode") or ("dry" if state else None),
            data_dir: marker.read_text(encoding="utf-8").strip() if marker.exists() else (
                "dry" if (data_dir / "issues").exists() else None)}  # fmt: skip
    for folder, other in held.items():
        if other not in (None, mode):
            raise SystemExit(f"{folder} holds the {other} run: the paid detector and the dry run "
                             "each keep their own --out and --live-data")  # fmt: skip
    state["mode"] = mode
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
    marker.write_text(mode + "\n", encoding="utf-8")
    if paid and publish_to and start_ms(publish_to) is None:
        # L (prereg v2 section 5): published once, before the first paid poll; sequences with
        # origin before it are retrospective and never admitted
        here = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
        start = {"start_ms": _now_ms(), "commit": here.stdout.strip()}
        add_record(publish_to, ".", START_FILE, start, what="Start")
    n = 0
    while polls is None or n < polls:
        t0 = time.time()
        state = step(out, data_dir, state, publish_to=publish_to, clients=clients)
        n += 1
        if polls is None or n < polls:  # every POLL_S, however long the step took
            time.sleep(max(0.0, POLL_S - (time.time() - t0)))


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
