"""Local models through llama.cpp `llama-server` (prereg section 3, ADR 0008, PLAN 10.4/10.5).

One model per server, started with the registered settings (checked through /props):
  llama-server -m <gguf> --alias <model id> -c 49152 -ngl all -fit off -np 1 --no-cache-prompt
    --cache-ram 0 --host 127.0.0.1 --port 9931 --no-webui --jinja
    --chat-template-file config/llamacpp/<model>.jinja
Then: uv run python -m laf.llamacpp --snapshot S --model gpt-oss-20b --block core
E1 (prereg section 11): the same server for gpt-oss-20b plus `--lora gpt-oss-20b-e1-lora-f16.gguf
--alias laf/gpt-oss-20b-e1`, then --model gpt-oss-20b-e1 with --block dev (format check) and e1;
outputs go to runs/extensions/.

Each block x model writes runs/<block>-<model>/ in the batch layout that the frozen scoring code
reads (`laf.analysis.llm_samples`): requests.jsonl (the design, written first) and results.jsonl
(one row per request, rebuilt at the end of every invocation). Attempts and progress go to the
append-only local_log.jsonl; a rerun retries only requests without a response.
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
        "effort": "medium",  # the template's reasoning_effort default, checked when rendered
        "rendered": ("Current date: {date}", "Reasoning: medium"),
    },
    "olmo-3.1-32b-instruct": {
        "id": "allenai/Olmo-3.1-32B-Instruct",
        "gguf": "allenai_Olmo-3.1-32B-Instruct-Q4_K_M.gguf",
        # generation_config.json (temperature, top_p) and the card's example (top_k)
        "sampling": {"temperature": 0.6, "top_p": 0.95, "top_k": 50, "min_p": 0.0},
        "effort": "none",  # not a reasoning model
        "rendered": (),  # the template shows no date
    },
}
# E1: the base GGUF plus the AutoScientist LoRA (runs/e1-adaption/checkpoint.json), converted by
# llama.cpp's convert_lora_to_gguf.py; registered settings otherwise identical to the base model
MODELS["gpt-oss-20b-e1"] = {
    **MODELS["gpt-oss-20b"],
    "id": "laf/gpt-oss-20b-e1",
    "template": "gpt-oss-20b",
    "lora": "gpt-oss-20b-e1-lora-f16.gguf",
}
# E1a (exploratory): the same recipe on the M>=6.0 training set (runs/e1a-adaption/)
MODELS["gpt-oss-20b-e1a"] = {
    **MODELS["gpt-oss-20b-e1"],
    "id": "laf/gpt-oss-20b-e1a",
    "lora": "gpt-oss-20b-e1a-lora-f16.gguf",
}
# local: p1 only, k = 3 seeds (PLAN 4.1); dev is the format check, never scored
LOCAL_BLOCKS = {
    "core": {**BLOCKS["core"], "paras": ("p1",), "k": 3},
    "i0": {**BLOCKS["i0"], "k": 3},
    "dev": {**BLOCKS["core"], "roles": ("dev",), "paras": ("p1",), "k": 3},
    "e1": {**BLOCKS["core"], "arms": ("direct",), "paras": ("p1",), "k": 3},
    # E3 extended exploratory set (ADR 0012), on the E3 snapshot; outputs under runs/e3/
    "e3": {**BLOCKS["e3"], "k": 3},
    "e3all": {**BLOCKS["e3"], "roles": ("test-post", "test-pre"), "k": 3},
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


def _canonical_sha256(d: dict) -> str:
    return hashlib.sha256(json.dumps(d, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


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
                            "item_id": item.item_id,
                            "arm": arm,
                            "info": info,
                            "paraphrase": para,
                            "sample": s,
                            "block": block,
                            "model": MODELS[model]["id"],
                            "effort": MODELS[model]["effort"],
                            "seed": s,
                            "temperature": b["temperature"],
                            "params_sha256": _canonical_sha256(b),
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
    """One chat completion; retries only 429/5xx/connection errors."""
    started, t0, error, n = _now(), time.monotonic(), None, 0
    for n in range(1, attempts + 1):
        try:
            r = _post(base_url + "/v1/chat/completions", b)
            choice = r["choices"][0]
            msg = choice["message"]
            return {
                "started_utc": started,
                "latency_s": round(time.monotonic() - t0, 3),
                "attempts": n,
                "id": r.get("id"),
                "model_reported": r.get("model"),
                "stop_reason": STOP.get(choice["finish_reason"], choice["finish_reason"]),
                "usage": r.get("usage"),
                "text": msg.get("content"),
                "reasoning": msg.get("reasoning_content"),
                "timings": r.get("timings"),
                "error": None,
                "server_build": build,
            }
        except urllib.error.HTTPError as e:
            error = f"HTTPError {e.code}: {e.read()[:500].decode('utf-8', 'replace')}"
            if e.code != 429 and e.code < 500:  # request errors are not retried
                break
            time.sleep(2**n)
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
            error = f"{type(e).__name__}: {e}"
            time.sleep(2**n)
    return {
        "started_utc": started,
        "latency_s": round(time.monotonic() - t0, 3),
        "attempts": n,
        "error": error,
        "server_build": build,
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


def template_path(model: str) -> Path:
    return TEMPLATES / f"{MODELS[model].get('template', model)}.jinja"


def server(base_url: str, model: str) -> dict:
    """The running server's settings; refuses unless they are the registered ones."""
    with urllib.request.urlopen(base_url + "/props", timeout=30) as r:
        p = json.load(r)
    template = template_path(model).read_text(encoding="utf-8")
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
    if "lora" in MODELS[model]:
        with urllib.request.urlopen(base_url + "/lora-adapters", timeout=30) as r:
            lora = [(Path(x["path"]).name, x["scale"]) for x in json.load(r)]
        if lora != [(MODELS[model]["lora"], 1.0)]:
            raise SystemExit(f"LoRA adapters differ from the registered one: {lora}")
        info["lora"] = lora[0][0]
    info["gguf_path"] = p["model_path"]
    return info


def check_prompt(base_url: str, model: str, job: dict) -> None:
    """The rendered prompt holds the system message and the registered template lines (issue
    date, reasoning effort), and never today's date."""
    prompt = _post(base_url + "/apply-template", job["body"], timeout=300)["prompt"]
    date = job["body"]["chat_template_kwargs"]["current_date"]
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    for line in MODELS[model]["rendered"]:
        if line.format(date=date) not in prompt:
            raise SystemExit(f"{line.format(date=date)!r} missing from the rendered prompt")
    if today != date and today in prompt:
        raise SystemExit(f"today's date {today} appears in the rendered prompt")
    if job["body"]["messages"][0]["content"] not in prompt:
        raise SystemExit("system message missing from the rendered prompt")


def _append(path: Path, row: dict) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


def _write(path: Path, rows: list[dict]) -> None:
    text = "".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in rows)
    path.write_text(text, encoding="utf-8", newline="\n")


def _file_sha256(path: Path) -> str:
    with path.open("rb") as f:  # streamed: the GGUFs are 12-20 GB
        return hashlib.file_digest(f, "sha256").hexdigest()


def finalize(out: Path) -> Counter[str]:
    """results.jsonl: per request the last attempt without an error, else the last error."""
    best: dict[str, dict] = {}
    for r in _jsonl(out / "local_log.jsonl"):
        if r["event"] == "call":
            prev = best.get(r["custom_id"])
            if r["error"] is None or prev is None or prev["error"] is not None:
                best[r["custom_id"]] = r
    rows = []
    for req in _jsonl(out / "requests.jsonl"):
        a = best[req["custom_id"]]
        row = {
            "custom_id": req["custom_id"],
            "result": "errored" if a["error"] else "succeeded",
            "model": req["model"],
            "seed": req["seed"],
            "latency_s": a["latency_s"],
            "server_build": a["server_build"],
            "machine": a["machine"],
        }
        if a["error"]:
            row["error"] = a["error"]
        else:
            u = a["usage"] or {}
            row |= {
                "id": a["id"],
                "model_reported": a["model_reported"],
                "stop_reason": a["stop_reason"],
                "text": a["text"],
                "usage": {
                    "input_tokens": u.get("prompt_tokens"),
                    "output_tokens": u.get("completion_tokens"),
                },
            }
        rows.append(row)
    _write(out / "results.jsonl", rows)
    return Counter(r["result"] for r in rows)


def run(
    base_url: str, model: str, block: str, items: list[Item], snapshot: str, runs: Path = RUNS
) -> Counter[str]:
    jobs = expand(items, block, model)
    if not jobs:
        raise SystemExit(f"block {block} has no items")
    # extension models (E1) sit one level down, outside the frozen analysis's runs/*/ glob and
    # so outside the registered forecasters' invalid-sample penalty pool
    out = (
        runs
        / ("e3" if block.startswith("e3") else "")
        / ("extensions" if "lora" in MODELS[model] else "")
        / f"{block}-{model}"
    )
    ledger = [{"custom_id": j["custom_id"], **j["meta"]} for j in jobs]
    if (out / "requests.jsonl").exists() and _jsonl(out / "requests.jsonl") != ledger:
        raise SystemExit(f"{out}/requests.jsonl holds a different design")
    info = server(base_url, model)
    check_prompt(base_url, model, jobs[0])
    out.mkdir(parents=True, exist_ok=True)
    _write(out / "requests.jsonl", ledger)
    log = out / "local_log.jsonl"
    rows = _jsonl(log) if log.exists() else []
    done = {r["custom_id"] for r in rows if r["event"] == "call" and r["error"] is None}
    todo = [j for j in jobs if j["custom_id"] not in done]
    gguf, mach, sha = Path(info.pop("gguf_path")), machine(), _git("rev-parse", "HEAD")
    _append(
        log,
        {
            "event": "start",
            "utc": _now(),
            "n_jobs": len(jobs),
            "n_todo": len(todo),
            "snapshot": snapshot,
            "git_sha": sha,
            "git_dirty": bool(_git("status", "--porcelain", "--untracked-files=no")),
            "prompt_hashes_sha256": _sha256(PROMPT_DIR / "HASHES.json"),
            "items_sha256": _sha256(Path("data/processed") / snapshot / "items.jsonl"),
            "gguf_sha256": _file_sha256(gguf) if gguf.exists() else None,
            "server": info,
            "machine": mach,
        },
    )
    tag = f"{mach['os']} | {mach['gpu']} | llama.cpp {info['build']} | git {sha[:7]}"
    counts: Counter[str] = Counter()
    for n, job in enumerate(todo, 1):
        rec = call(base_url, job["body"], info["build"])
        _append(log, {"event": "call", "custom_id": job["custom_id"], "machine": tag, **rec})
        counts["error" if rec["error"] else "response"] += 1
        if block == "dev" and not rec["error"]:  # scored outputs stay unread
            counts[validate(job["meta"]["arm"], rec["text"], rec["stop_reason"])[0]] += 1
        print(f"{n}/{len(todo)} {dict(counts)}", flush=True)
    results = finalize(out)
    _append(log, {"event": "end", "utc": _now(), "results": dict(results)})
    return counts + Counter({f"results_{k}": v for k, v in results.items()})


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m laf.llamacpp", description=__doc__)
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--model", required=True, choices=sorted(MODELS))
    ap.add_argument("--block", required=True, choices=sorted(LOCAL_BLOCKS))
    ap.add_argument("--base-url", default=BASE_URL)
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    a = ap.parse_args(argv)
    counts = run(a.base_url, a.model, a.block, load_items(a.data_dir, a.snapshot), a.snapshot)
    print(f"{a.block}-{a.model}: {dict(counts)}")


if __name__ == "__main__":
    main()
