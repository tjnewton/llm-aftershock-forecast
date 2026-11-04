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
import math
from pathlib import Path

import pandas as pd

PREREG = Path("docs/preregistration-v2.md")
PROMPT_HASHES = Path("prompts/v2/HASHES.json")
CONFIGS = ("config/splits.toml", "config/sequences.toml", "config/sequences_e3.toml",
           "config/sequences_confirmatory.toml",
           "config/sequences_forward_excluded.toml")  # fmt: skip
SUPPLEMENTARY_CONFIG = Path("config/sequences_supplementary.toml")
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


def _close(a, b) -> bool:
    """Equal JSON values, floats up to libm noise: macOS and Windows differ in the last bits of
    P(M>=6) (at most 4.4e-16 absolute on the frozen snapshots)."""
    if isinstance(a, float) or isinstance(b, float):
        return all(isinstance(x, int | float) for x in (a, b)) and math.isclose(
            a, b, rel_tol=1e-9, abs_tol=1e-12
        )
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(map(_close, a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_close(a[k], b[k]) for k in a)
    return a == b


def same_jsonl(old: str, new: str) -> bool:
    """The committed file and a fresh rebuild agree line by line (floats within `_close`)."""
    a, b = old.splitlines(), new.splitlines()
    return len(a) == len(b) and all(
        _close(json.loads(x), json.loads(y)) for x, y in zip(a, b, strict=True)
    )


def write_frozen_inputs(data_dir: Path, snapshot: str) -> list[Path]:
    """Write (or check, when present) the items and baseline files the manifest hashes. A
    present file is never rewritten: the manifest hashes the committed bytes, so it is the same
    on every machine."""
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
        if not path.exists():
            path.write_text(body, encoding="utf-8", newline="\n")
        elif not same_jsonl(path.read_text(encoding="utf-8"), body):
            raise SystemExit(f"{path} differs from a fresh rebuild: inputs changed")
    return list(bodies)


def manifest(data_dir: Path, snapshots: list[str], inputs: list[Path]) -> dict:
    """{label: SHA-256} for every artifact of prereg v2 section 11, and their combined hash:
    the candidate snapshot and the forward-excluded one."""
    downloads = data_dir / "manifest.jsonl"  # the download inventory of this data directory
    # keys in POSIX form, so the manifest is the same on every operating system
    files = {p.as_posix(): p for p in (PREREG, PROMPT_HASHES, downloads)}
    files |= {c: Path(c) for c in CONFIGS}
    if SUPPLEMENTARY_CONFIG.exists():  # written at L, after the freeze
        files[SUPPLEMENTARY_CONFIG.as_posix()] = SUPPLEMENTARY_CONFIG
    for snapshot in snapshots:
        proc = data_dir / "processed" / snapshot
        files |= {p.as_posix(): p for p in sorted(proc.glob("*.parquet"))}
    files |= {p.as_posix(): p for p in inputs}
    out = {k: sha256(p) for k, p in sorted(files.items())}
    tree = {p.as_posix(): sha256(p) for p in sorted(SRC.rglob("*.py"))}
    out["src/laf (SHA-256 of its sorted file hashes)"] = hashlib.sha256(
        json.dumps(tree, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return {"snapshots": snapshots, "files": out, "src_files": tree,
            "manifest_sha256": hashlib.sha256(
                json.dumps(out, sort_keys=True).encode("utf-8")).hexdigest()}  # fmt: skip
