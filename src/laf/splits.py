"""Development and confirmatory data (docs/adr/0013-data-splits.md).

Outcomes of a confirmatory sequence (event counts in its forecast windows) are sealed until the
tag `prereg-v2` exists: `build_tables` writes them as nulls and every function that counts or
scores outcomes calls `require_outcomes` first. A sequence id not listed as development in
config/splits.toml is confirmatory.
"""

import hashlib
import subprocess
import tomllib
from collections.abc import Iterable
from functools import cache
from pathlib import Path

import pandas as pd

CONFIG = Path("config/splits.toml")
UNSEAL_TAG = "prereg-v2"


@cache
def development_ids(config: Path = CONFIG) -> frozenset[str]:
    cfg = tomllib.loads(config.read_text(encoding="utf-8"))
    ids: set[str] = set()
    for p in cfg["sequence_configs"]:
        ids |= {s["id"] for s in tomllib.loads(Path(p).read_text(encoding="utf-8"))["sequence"]}
    for d in cfg["id_dir"]:
        stems = sorted(f.name.split(".")[0] for f in Path(d["path"]).iterdir() if f.is_file())
        digest = hashlib.sha256("\n".join(stems).encode("utf-8")).hexdigest()
        if (len(stems), digest) != (d["n"], d["sha256"]):
            raise SystemExit(f"{d['path']}: inventory differs from config/splits.toml")
        ids |= set(stems)
    return frozenset(ids)


def is_development(sequence_id: str) -> bool:
    return sequence_id in development_ids()


def unsealed() -> bool:
    tags = subprocess.run(["git", "tag", "--list", UNSEAL_TAG], capture_output=True, text=True)
    return bool(tags.stdout.strip())


def sealed(sequence_ids: Iterable[str]) -> list[str]:
    """The confirmatory ids among `sequence_ids` while outcomes are sealed."""
    confirmatory = sorted(set(sequence_ids) - development_ids())
    return confirmatory if confirmatory and not unsealed() else []


def require_outcomes(sequence_ids: Iterable[str]) -> None:
    if bad := sealed(sequence_ids):
        raise SystemExit(
            f"outcomes sealed until tag {UNSEAL_TAG} (docs/adr/0013-data-splits.md): "
            f"confirmatory sequences {', '.join(bad)}"
        )


def seal_counts(oc: pd.DataFrame) -> pd.DataFrame:
    """Null the counts of sealed sequences; their windows stay, because items need them."""
    if oc.empty:
        return oc
    hidden = oc["sequence_id"].isin(sealed(oc["sequence_id"].unique()))
    if not hidden.any():
        return oc
    oc = oc.assign(count=oc["count"].astype("Int64"), sealed=hidden)
    oc.loc[hidden, "count"] = pd.NA
    return oc


def require_outcome_table(oc: pd.DataFrame) -> None:
    """Refuse sealed sequences, and tables built while outcomes were sealed."""
    require_outcomes(oc["sequence_id"].unique())
    if oc["count"].isna().any():
        raise SystemExit("observed_counts has sealed (null) counts: rebuild with `laf tables`")
