"""`laf live-status`: the live arm at a glance, from the live branch and the detector's folder
(no model calls, no ComCat, no outcome). It reports L, the eligible prospective sequences and
S (prereg v2 section 5), and what needs a look: a stale poll, errors, unpushed commits, seals
without a push receipt, and this month's live spend.

S = min(L + 182 days, the latest origin among the first 26 eligible sequences in order of
first detection): eligible means included as primary at first detection (`inclusion.json` on
the branch) with origin at or after L. Normally the latest origin is the 26th's own; taking the
latest keeps all 26 inside [L, S].
"""

import json
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

ELIGIBLE_N = 26  # decision 23
WINDOW_MS = 182 * 86_400_000
STALE_POLL_MS = 30 * 60_000  # three missed polls
RECEIPT_LAG_MS = 2 * 3_600_000


def _utc(ms: int | None) -> str:
    return "-" if ms is None else datetime.fromtimestamp(ms / 1000, UTC).strftime("%Y-%m-%d %H:%MZ")


def eligible(live: Path, start_ms: int) -> list[dict]:
    """Eligible prospective sequences in order of first detection, one per tracked sequence."""
    by_key: dict[str, dict] = {}
    for p in live.glob("*/inclusion.json"):
        r = json.loads(p.read_text(encoding="utf-8")) | {"folder": p.parent.name}
        if r.get("tier") != "primary" or r.get("reason") != "included" or r["time_ms"] < start_ms:
            continue
        r["order_ms"] = r.get("detected_ms") or r["time_ms"]
        key = r.get("key") or r["folder"]  # a changed preferred ID is one sequence
        if key not in by_key or r["order_ms"] < by_key[key]["order_ms"]:
            by_key[key] = r
    return sorted(by_key.values(), key=lambda r: (r["order_ms"], r["time_ms"]))


def stop_ms(start_ms: int, seqs: list[dict]) -> tuple[int, str]:
    """(S, why): L + 182 days, or the latest origin among the first 26 if earlier."""
    s, why = start_ms + WINDOW_MS, "L + 182 days"
    if len(seqs) >= ELIGIBLE_N:
        latest = max(r["time_ms"] for r in seqs[:ELIGIBLE_N])
        if latest < s:
            s, why = latest, f"the first {ELIGIBLE_N} eligible sequences"
    return s, why


def _log_health(log: Path, now_ms: int) -> tuple[int | None, int]:
    """(last poll time, error records in the last 24 h) from the detector's log."""
    last, errors, day_ago = None, 0, now_ms - 86_400_000
    if not log.exists():
        return None, 0
    for line in log.read_text(encoding="utf-8").split("\n"):
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("kind") == "poll":
            last = r["poll_ms"]
        if r.get("error") and (last or 0) >= day_ago:
            errors += 1
    return last, errors


def status(live: Path, out: Path, now_ms: int | None = None) -> tuple[list[str], list[str]]:
    """(report lines, attention lines)."""
    now = int(time.time() * 1000) if now_ms is None else now_ms
    lines, attention = [], []
    start_path = live / "start.json"
    start = json.loads(start_path.read_text(encoding="utf-8"))["start_ms"] if (
        start_path.exists()) else None  # fmt: skip
    lines.append(f"L: {_utc(start)}" + ("" if start else " (no paid start on this branch)"))
    if start is not None:
        seqs = eligible(live, start)
        s, why = stop_ms(start, seqs)
        lines.append(f"eligible prospective sequences: {len(seqs)} of {ELIGIBLE_N}")
        lines += [f"  {i + 1:2d}. {r['folder']} M{r['mag']:.1f} origin {_utc(r['time_ms'])}, "
                  f"detected {_utc(r.get('detected_ms'))}" for i, r in enumerate(seqs)]  # fmt: skip
        lines.append(f"S: {_utc(s)} ({why})")
        if now >= s:
            attention.append(f"S has passed ({_utc(s)}): commit config/live_stop.toml (runbook 5)")
    last, errors = _log_health(out / "log.jsonl", now)
    lines.append(f"last poll: {_utc(last)}; error records in the last 24 h: {errors}")
    if last is None or now - last > STALE_POLL_MS:
        attention.append("the detector has not polled for over 30 minutes")
    if errors:
        attention.append(f"{errors} error records in the last 24 h (log.jsonl)")

    # inherited GIT_* variables (a commit hook's GIT_DIR) would point git at another repository
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}

    def git(*args: str) -> str:
        return subprocess.run(["git", "-C", str(live), *args], capture_output=True,
                              text=True, env=env).stdout.strip()  # fmt: skip

    branch = git("branch", "--show-current")
    ahead = git("rev-list", "--count", f"origin/{branch}..HEAD")
    if ahead not in ("", "0"):
        attention.append(f"{ahead} local commits not pushed to {branch}")
    state_path = out / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    missing = set(state.get("receipts_missing", []))
    waiting = []
    for seal in live.glob("*/*/answers.seal.json"):
        rel = seal.parent.relative_to(live).as_posix()
        if (seal.parent / "receipt.json").exists() or rel in missing:
            continue
        sealed = json.loads(seal.read_text(encoding="utf-8")).get("sealed_ms")
        if sealed is not None and now - sealed > RECEIPT_LAG_MS:
            waiting.append(rel)
    if waiting or missing:
        given_up = ", ".join(sorted(missing)) or "-"
        attention.append(f"seals without a push receipt: {len(waiting)} waiting over 2 h, "
                         f"{len(missing)} given up ({given_up})")  # fmt: skip
    month = datetime.fromtimestamp(now / 1000, UTC).strftime("%Y-%m")
    spent = {"claude": 0.0, "openai": 0.0}
    for f in live.glob("**/spend.jsonl"):
        for line in f.read_text(encoding="utf-8").split("\n"):
            if line.strip() and (r := json.loads(line))["started_utc"][:7] == month:
                spent[r["provider"]] += r["usd"]
    lines.append(f"live spend {month}: Claude ${spent['claude']:.2f}, "
                 f"OpenAI ${spent['openai']:.2f}")  # fmt: skip
    return lines, attention
