"""Local models through llama.cpp `llama-server` (prereg section 3, ADR 0008, PLAN 10.4/10.5).

One model per server, started with the registered settings (checked through /props):
  llama-server -m <gguf> --alias <model id> -c 49152 -ngl all -fit off -np 1 --no-cache-prompt
    --cache-ram 0 --host 127.0.0.1 --port 9931 --no-webui --jinja
    --chat-template-file config/llamacpp/<model>.jinja
Then: uv run python -m laf.llamacpp --snapshot S --model gpt-oss-20b --block dev

Records go to runs/local-<model>/calls.jsonl (append-only; a rerun skips samples that already
have a response) and one line per invocation to runs/local-<model>/manifest.jsonl.
"""

import argparse
import hashlib
import json
import platform
import subprocess
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from laf.items import Item
from laf.pilot import load_items
from laf.prompts import PROMPT_DIR, render, schema
from laf.runner import BLOCKS, RUNS, _git, _jsonl, _sha256, request_id
from laf.schemas import validate

BASE_URL = "http://127.0.0.1:9931"
TEMPLATES = Path(__file__).resolve().parents[2] / "config" / "llamacpp"
CTX = 49_152  # longest scored prompt ~24k tokens (both tokenizers) + MAX_TOKENS
MAX_TOKENS = 16_000  # docs/model-registry.md
MODELS: dict[str, dict] = {
    "gpt-oss-20b": {
        "id": "openai/gpt-oss-20b",
        "gguf": "gpt-oss-20b-MXFP4.gguf",
        # openai/gpt-oss README, "Recommended Sampling Parameters"; no top-k or min-p
        "sampling": {"temperature": 1.0, "top_p": 1.0, "top_k": 0, "min_p": 0.0},
        "dated_template": True,
    },
    "olmo-3.1-32b-instruct": {
        "id": "allenai/Olmo-3.1-32B-Instruct",
        "gguf": "allenai_Olmo-3.1-32B-Instruct-Q4_K_M.gguf",
        # generation_config.json (temperature, top_p) and the card's example (top_k)
        "sampling": {"temperature": 0.6, "top_p": 0.95, "top_k": 50, "min_p": 0.0},
        "dated_template": False,
    },
}
# local: p1 only, k = 3 seeds (PLAN 4.1); dev is the format check, never scored
LOCAL_BLOCKS = {
    "core": {**BLOCKS["core"], "paras": ("p1",), "k": 3},
    "i0": {**BLOCKS["i0"], "k": 3},
    "dev": {**BLOCKS["core"], "roles": ("dev",), "paras": ("p1",), "k": 3},
}
STOP = {"stop": "end_turn", "length": "max_tokens"}  # finish_reason in the Claude vocabulary


def issue_date(issue_ms: int) -> str:
    return datetime.fromtimestamp(issue_ms / 1000, UTC).strftime("%Y-%m-%d")


def body(
    model: str, system: str, user: str, arm: Literal["direct", "params"], issue_ms: int, seed: int
) -> dict:
    return {
        "model": MODELS[model]["id"],
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": arm, "schema": schema(arm)},
        },
        "max_tokens": MAX_TOKENS,
        "seed": seed,
        **MODELS[model]["sampling"],
        "cache_prompt": False,
        "chat_template_kwargs": {"current_date": issue_date(issue_ms)},
    }


def expand(items: list[Item], block: str, model: str) -> list[dict]:
    spec = LOCAL_BLOCKS[block]
    jobs = []
    for item in items:
        if item.role not in spec["roles"]:
            continue
        for arm in spec["arms"]:
            for info in spec["infos"]:
                for para in spec["paras"]:
                    system, user = render(item, arm, info, para)
                    for s in range(spec["k"]):
                        b = body(model, system, user, arm, item.issue_ms, seed=s)
                        meta = {
                            "kind": "local",
                            "block": block,
                            "item_id": item.item_id,
                            "arm": arm,
                            "info": info,
                            "paraphrase": para,
                            "sample": s,
                            "seed": s,
                        }
                        jobs.append({"custom_id": request_id(b, s), "meta": meta, "body": b})
    return jobs


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _post(url: str, payload: dict, timeout: float = 1800) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def call(base_url: str, b: dict, build: str, *, attempts: int = 4) -> dict:
    """One chat completion; retries only 429/5xx/connection errors. Same fields as
    `providers.call_anthropic`, plus the reasoning text and the server timings."""
    started, t0, error = _now(), time.monotonic(), None
    for i in range(attempts):
        try:
            r = _post(base_url + "/v1/chat/completions", b)
            choice = r["choices"][0]
            msg = choice["message"]
            return {
                "started_utc": started,
                "latency_s": round(time.monotonic() - t0, 3),
                "attempts": i + 1,
                "id": r.get("id"),
                "model_requested": b["model"],
                "model_reported": r.get("model"),
                "stop_reason": STOP.get(choice["finish_reason"], choice["finish_reason"]),
                "stop_details": {"finish_reason": choice["finish_reason"]},
                "usage": r.get("usage"),
                "text": msg.get("content"),
                "reasoning": msg.get("reasoning_content"),
                "timings": r.get("timings"),
                "error": None,
                "sdk_version": f"llama.cpp {build}",
                "base_url": base_url,
            }
        except urllib.error.HTTPError as e:
            error = f"HTTPError {e.code}: {e.read()[:500].decode('utf-8', 'replace')}"
            if e.code != 429 and e.code < 500:  # request errors are not retried
                break
            time.sleep(2 ** (i + 1))
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
            error = f"{type(e).__name__}: {e}"
            time.sleep(2 ** (i + 1))
    return {
        "started_utc": started,
        "latency_s": round(time.monotonic() - t0, 3),
        "attempts": attempts,
        "model_requested": b["model"],
        "error": error,
        "sdk_version": f"llama.cpp {build}",
        "base_url": base_url,
    }


def machine() -> dict:
    """Hardware and software of this run; no host or user names."""
    try:
        gpu = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,driver_version,compute_cap,memory.total",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        gpu = ""
    return {
        "os": platform.platform(),
        "arch": platform.machine(),
        "cpu": platform.processor(),
        "gpu": gpu or None,
        "python": platform.python_version(),
    }


def server(base_url: str, model: str) -> dict:
    """The running server's settings; refuses unless they are the registered ones."""
    with urllib.request.urlopen(base_url + "/props", timeout=30) as r:
        p = json.load(r)
    template = (TEMPLATES / f"{model}.jinja").read_text(encoding="utf-8")
    info = {
        "build": p["build_info"],
        "model_alias": p["model_alias"],
        "gguf": Path(p["model_path"]).name,  # no local directories in the logs
        "n_ctx": p["default_generation_settings"]["n_ctx"],
        "total_slots": p["total_slots"],
        "chat_template_sha256": hashlib.sha256(p["chat_template"].encode("utf-8")).hexdigest(),
    }
    want = {
        "model_alias": MODELS[model]["id"],
        "gguf": MODELS[model]["gguf"],
        "n_ctx": CTX,
        "total_slots": 1,
        "chat_template_sha256": hashlib.sha256(template.encode("utf-8")).hexdigest(),
    }
    bad = {k: (info[k], v) for k, v in want.items() if info[k] != v}
    if bad:
        raise SystemExit(f"llama-server settings differ from the registered ones: {bad}")
    info["gguf_path"] = p["model_path"]
    return info


def check_date(base_url: str, model: str, job: dict) -> None:
    """The rendered prompt shows the issue date (dated templates) and never today's date."""
    prompt = _post(base_url + "/apply-template", job["body"], timeout=300)["prompt"]
    date = job["body"]["chat_template_kwargs"]["current_date"]
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    if MODELS[model]["dated_template"] and f"Current date: {date}" not in prompt:
        raise SystemExit(f"issue date {date} missing from the rendered prompt")
    if today != date and today in prompt:
        raise SystemExit(f"today's date {today} appears in the rendered prompt")
    if job["body"]["messages"][0]["content"] not in prompt:
        raise SystemExit("system message missing from the rendered prompt")


def _append(path: Path, row: dict) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


def _file_sha256(path: Path) -> str:
    with path.open("rb") as f:  # streamed: the GGUFs are 12-20 GB
        return hashlib.file_digest(f, "sha256").hexdigest()


def run(
    base_url: str, model: str, block: str, items: list[Item], snapshot: str, runs: Path = RUNS
) -> Counter[str]:
    jobs = expand(items, block, model)
    if not jobs:
        raise SystemExit(f"block {block} has no items")
    info = server(base_url, model)
    check_date(base_url, model, jobs[0])
    out = runs / f"local-{model}"
    out.mkdir(parents=True, exist_ok=True)
    calls = out / "calls.jsonl"
    done = {r["custom_id"] for r in _jsonl(calls) if not r["error"]} if calls.exists() else set()
    todo = [j for j in jobs if j["custom_id"] not in done]
    gguf = Path(info.pop("gguf_path"))
    mach = machine()
    _append(
        out / "manifest.jsonl",
        {
            "started_utc": _now(),
            "block": block,
            "n_jobs": len(jobs),
            "n_todo": len(todo),
            "snapshot": snapshot,
            "git_sha": _git("rev-parse", "HEAD"),
            "git_dirty": bool(_git("status", "--porcelain", "--untracked-files=no")),
            "prompt_hashes_sha256": _sha256(PROMPT_DIR / "HASHES.json"),
            "items_sha256": _sha256(Path("data/processed") / snapshot / "items.jsonl"),
            "gguf_sha256": _file_sha256(gguf) if gguf.exists() else None,
            "server": info,
            "machine": mach,
        },
    )
    tag = f"{mach['os']} | {mach['gpu']} | llama.cpp {info['build']}"
    counts: Counter[str] = Counter()
    for n, job in enumerate(todo, 1):
        rec = call(base_url, job["body"], info["build"])
        _append(calls, {"custom_id": job["custom_id"], **job["meta"], "machine": tag, **rec})
        counts["error" if rec["error"] else "response"] += 1
        if block == "dev" and not rec["error"]:  # scored outputs stay unread before scoring-v1
            counts[validate(job["meta"]["arm"], rec["text"], rec["stop_reason"])[0]] += 1
        print(f"{n}/{len(todo)} {dict(counts)}", flush=True)
    return counts


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m laf.llamacpp", description=__doc__)
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--model", required=True, choices=sorted(MODELS))
    ap.add_argument("--block", required=True, choices=sorted(LOCAL_BLOCKS))
    ap.add_argument("--base-url", default=BASE_URL)
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    a = ap.parse_args(argv)
    counts = run(a.base_url, a.model, a.block, load_items(a.data_dir, a.snapshot), a.snapshot)
    print(f"local-{a.model} {a.block}: {dict(counts)}")


if __name__ == "__main__":
    main()
