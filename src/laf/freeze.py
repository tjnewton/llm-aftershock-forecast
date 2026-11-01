"""The freeze manifest of prereg v2 section 11: SHA-256 of every artifact posted with the tag.

`laf freeze-manifest --snapshot S [S2 ...]` writes, for each snapshot (the candidates and the
forward-excluded ones), the items at catalog floor 3 (the v2 items, `items_m3.jsonl`) and the
pipeline's baseline forecasts on them (generic RJ, RJ-MLE, the rule of thumb and the
legacy-ETAS refit with its per-issue seeds, `baselines_m3.jsonl`), both computed without any
outcome: the cells come from the forecast windows, never from the counts. It then hashes this
document's artifacts into `results/freeze_manifest.json`, with one SHA-256 over the whole
manifest for the public post.
"""

import hashlib
import json
from pathlib import Path

import pandas as pd

PREREG = Path("docs/preregistration-v2.md")
PROMPT_HASHES = Path("prompts/v2/HASHES.json")
CONFIGS = ("config/splits.toml", "config/sequences.toml", "config/sequences_e3.toml",
           "config/sequences_confirmatory.toml",
           "config/sequences_forward_excluded.toml")  # fmt: skip
SRC = Path("src/laf")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def window_cells(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Every (issue, window) to forecast, from the windows alone: `analysis.cells` would need
    the outcome counts, which stay sealed."""
    oc = tables["observed_counts"].drop_duplicates(["issue_id", "window"])
    it = tables["issue_times"][["issue_id", "source", "issue_ms"]]
    c = oc[["issue_id", "sequence_id", "window"]].merge(it, on="issue_id")
    return c.assign(oaf_cell=c["source"].eq("oaf"))


def baseline_rows(tables: dict[str, pd.DataFrame], items: list) -> list[dict]:
    """The pipeline's baselines on every cell: M>=5 and M>=4 quantiles and P(M>=6). The ETAS
    refit comes from the snapshot's `etas_forecasts` (`laf etas`, seeded per issue)."""
    from laf import analysis as A

    base = A.baselines(tables, {i.item_id: i for i in items}, window_cells(tables))
    keep = ("generic_rj", "rj_mle", "naive", "etas")
    return [
        {"forecaster": name, "item_id": iid, "window": win, "m5": list(fc.m5),
         "m4": list(fc.m4) if fc.m4 else None, "p_m6": fc.p_m6}
        for (name, iid, win), fc in sorted(base.items()) if name in keep
    ]  # fmt: skip


def _jsonl(rows) -> str:
    return "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows)


def write_frozen_inputs(data_dir: Path, snapshot: str) -> list[Path]:
    """Write (or check, when present) the items and baseline files the manifest hashes."""
    from laf.pilot import load_items

    proc = data_dir / "processed" / snapshot
    if not (proc / "etas_forecasts.parquet").exists():
        raise SystemExit(f"{proc}: run `laf etas --snapshot {snapshot}` first (the ETAS refit)")
    tables = {p.stem: pd.read_parquet(p) for p in proc.glob("*.parquet")}
    cells = window_cells(tables)
    etas = set(zip(tables["etas_forecasts"]["issue_id"], tables["etas_forecasts"]["window"],
                   strict=True))  # fmt: skip
    missing = set(zip(cells["issue_id"], cells["window"], strict=True)) - etas
    if missing:  # `analysis.baselines` would skip them silently
        raise SystemExit(f"the ETAS refit lacks {len(missing)} cells, e.g. {sorted(missing)[:3]}")
    items = load_items(data_dir, snapshot, 3.0)
    bodies = {
        proc / "items_m3.jsonl": "".join(i.model_dump_json() + "\n" for i in items),
        proc / "baselines_m3.jsonl": _jsonl(baseline_rows(tables, items)),
    }
    for path, body in bodies.items():
        if path.exists() and path.read_text(encoding="utf-8") != body:
            raise SystemExit(f"{path} differs from a fresh rebuild: inputs changed")
        path.write_text(body, encoding="utf-8", newline="\n")
    return list(bodies)


def manifest(data_dir: Path, snapshots: list[str], inputs: list[Path]) -> dict:
    """{label: SHA-256} for every artifact of prereg v2 section 11, and their combined hash:
    the candidate snapshot and the forward-excluded one."""
    downloads = data_dir / "manifest.jsonl"  # the download inventory of this data directory
    files = {str(PREREG): PREREG, str(PROMPT_HASHES): PROMPT_HASHES, str(downloads): downloads}
    files |= {c: Path(c) for c in CONFIGS}
    for snapshot in snapshots:
        proc = data_dir / "processed" / snapshot
        files |= {str(p): p for p in sorted(proc.glob("*.parquet"))}
    files |= {str(p): p for p in inputs}
    out = {k: sha256(p) for k, p in sorted(files.items())}
    tree = {str(p): sha256(p) for p in sorted(SRC.rglob("*.py"))}
    out["src/laf (SHA-256 of its sorted file hashes)"] = hashlib.sha256(
        json.dumps(tree, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return {"snapshots": snapshots, "files": out, "src_files": tree,
            "manifest_sha256": hashlib.sha256(
                json.dumps(out, sort_keys=True).encode("utf-8")).hexdigest()}  # fmt: skip
