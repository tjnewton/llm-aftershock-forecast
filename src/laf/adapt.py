"""E1 on Adaption (prereg section 11): raw upload of the training set (no rephrasing, no web
search), AutoScientist supervised LoRA fine-tuning of gpt-oss-20b, status and checkpoint
download. Records go to runs/e1-adaption/."""

import json
import os
from pathlib import Path

RUN = Path("runs/e1-adaption")
MODEL = "openai/gpt-oss-20b"


def api_key(env_file: Path = Path(".env")) -> str:
    """ADAPTION_API_KEY from the environment or .env; never printed."""
    key = os.environ.get("ADAPTION_API_KEY", "")
    if not key and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "ADAPTION_API_KEY":
                key = value.strip().strip('"').strip("'")
    if not key:
        raise SystemExit("ADAPTION_API_KEY not set (environment or .env)")
    return key


def client():
    from adaption import Adaption

    return Adaption(api_key=api_key())


def _record(name: str, data: dict) -> None:
    RUN.mkdir(parents=True, exist_ok=True)
    (RUN / name).write_text(
        json.dumps(data, indent=1, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def upload(c, path: Path) -> str:
    """Raw processing: rows are trained as written (prereg: no rephrasing, no web search)."""
    import hashlib

    ds = c.datasets.upload_file(
        str(path),
        name="laf-e1-etas-refit",
        processing_mode="raw",
        column_mapping={"prompt": "prompt", "completion": "completion"},
    )
    c.datasets.wait_for_completion(ds.dataset_id)
    status = c.datasets.get_status(ds.dataset_id)
    _record(
        "dataset.json",
        {
            "dataset_id": ds.dataset_id,
            "file": str(path),
            "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "row_count": status.row_count,
            "status": status.status,
        },
    )
    return ds.dataset_id


def recommend(c, dataset_id: str, model: str = MODEL) -> dict:
    rec = c.autoscientist.recommend_hyperparams(dataset_id=dataset_id, model=model)
    data = rec.model_dump() if hasattr(rec, "model_dump") else dict(rec)
    _record("recommendation.json", data)
    return data


def launch(c, dataset_id: str, model: str = MODEL, hyperparams: dict | None = None) -> str:
    """Spends Adaption credits: supervised (instruction) LoRA fine-tuning; the checkpoint used
    is the one AutoScientist reports as best."""
    kw: dict[str, object] = {
        "dataset_id": dataset_id,
        "model": model,
        "training_method": "instruction",
    }  # raw upload already canonicalized the prompt and completion columns
    if hyperparams:
        kw["hyperparams"] = {k: v for k, v in hyperparams.items() if v is not None}
    run = c.autoscientist.create(**kw)
    _record(
        "run.json",
        {"run_id": run.id, "model": model, "dataset_id": dataset_id, "hyperparams": hyperparams},
    )
    return run.id


def status(c, run_id: str) -> dict:
    run = c.autoscientist.get(run_id)
    return run.model_dump() if hasattr(run, "model_dump") else dict(run)


CHECKPOINT = Path("data/interim/e1-adaption/best.tar.zst")


def fetch_checkpoint(c, run_id: str, out: Path = CHECKPOINT) -> str:
    """Download the best checkpoint; the first download records its SHA-256 in checkpoint.json,
    later ones (another machine) must match it."""
    import hashlib

    got = hashlib.sha256(download(c, run_id, out).read_bytes()).hexdigest()
    ck = RUN / "checkpoint.json"
    if ck.exists():
        want = json.loads(ck.read_text(encoding="utf-8"))["sha256"]
        if got != want:
            raise SystemExit(f"{out}: SHA-256 {got} differs from {ck} ({want})")
    else:
        _record(
            "checkpoint.json",
            {
                "run_id": run_id,
                "file": out.name,
                "sha256": got,
                "bytes": out.stat().st_size,
                "format": "tar + zstd: PEFT LoRA adapter_model.safetensors, tokenizer, template",
            },
        )
    return f"{out} sha256 {got}"


def download(c, experiment_id: str, out: Path) -> Path:
    """The best checkpoint (format as served by Adaption) to `out`; weights are not committed."""
    resp = c.autoscientist.download(experiment_id)
    out.parent.mkdir(parents=True, exist_ok=True)
    resp.write_to_file(str(out))
    return out
