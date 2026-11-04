"""Development and confirmatory data (docs/adr/0013-data-splits.md).

Outcomes of a confirmatory sequence (event counts in its forecast windows) are sealed behind two
gates: the tag `prereg-v2`, and S + 90 days, where S is the live arm's stop time recorded in
config/live_stop.toml at the tag `prereg-v2-stop` (no interim looks: prereg v2 section 5, ADR
0018 decision 11). `build_tables` writes sealed counts as nulls and every function that counts
or scores outcomes calls `require_outcomes` first. A sequence id not listed as development in
config/splits.toml is confirmatory; live sequences are never listed, so their records stay
sealed too.
"""

import hashlib
import subprocess
import time
import tomllib
from collections.abc import Iterable
from functools import cache
from pathlib import Path

import pandas as pd

CONFIG = Path("config/splits.toml")
UNSEAL_TAG = "prereg-v2"
STOP_TAG = "prereg-v2-stop"  # protected by the freeze-tags ruleset (prereg-*)
STOP_FILE = "config/live_stop.toml"
SETTLE_MS = 90 * 86_400_000  # A and B together on one snapshot at S + 90 days


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


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True)


def _tagged(tag: str) -> bool:
    """The gate tag exists. It must be annotated (a lightweight tag is refused, never taken
    for a freeze): the freeze-tags ruleset protects it and its tagger time is on record."""
    kind = _git("cat-file", "-t", f"refs/tags/{tag}")
    if kind.returncode != 0:
        return False
    if kind.stdout.strip() != "tag":
        raise SystemExit(f"tag {tag} is lightweight: the gates need an annotated tag (git tag -a)")
    return True


def stop_ms() -> int | None:
    """S (epoch ms) as recorded at the tag `prereg-v2-stop`, or None before that tag. Read from
    the tagged commit, so a later edit of the file changes nothing. Refused unless that tag
    descends from `prereg-v2` and S is epoch ms after the freeze commit, within 400 days of it
    (S <= L + 182 days): a value in seconds would otherwise open the second gate at once."""
    shown = _git("show", f"refs/tags/{STOP_TAG}:{STOP_FILE}")
    if shown.returncode != 0:
        return None
    if not (_tagged(STOP_TAG) and _tagged(UNSEAL_TAG)):
        raise SystemExit(f"tag {STOP_TAG} without tag {UNSEAL_TAG}")
    if _git("merge-base", "--is-ancestor", UNSEAL_TAG, STOP_TAG).returncode != 0:
        raise SystemExit(f"tag {STOP_TAG} does not descend from tag {UNSEAL_TAG}")
    s = tomllib.loads(shown.stdout)["s_ms"]
    frozen_ms = int(_git("log", "-1", "--format=%ct", f"{UNSEAL_TAG}^{{commit}}").stdout) * 1000
    if type(s) is not int or not frozen_ms < s < frozen_ms + 400 * 86_400_000:
        raise SystemExit(f"{STOP_FILE} at tag {STOP_TAG}: s_ms = {s!r} is not epoch ms within "
                         f"400 days after the {UNSEAL_TAG} commit")  # fmt: skip
    return s


def unsealed(now_ms: float | None = None) -> bool:
    """Both gates passed: the tag prereg-v2 exists and S + 90 days have gone by."""
    if not _tagged(UNSEAL_TAG):
        return False
    s = stop_ms()
    now = time.time() * 1000 if now_ms is None else now_ms
    return s is not None and now >= s + SETTLE_MS


def sealed(sequence_ids: Iterable[str]) -> list[str]:
    """The confirmatory ids among `sequence_ids` while outcomes are sealed."""
    confirmatory = sorted(set(sequence_ids) - development_ids())
    return confirmatory if confirmatory and not unsealed() else []


def require_outcomes(sequence_ids: Iterable[str]) -> None:
    if bad := sealed(sequence_ids):
        raise SystemExit(
            f"outcomes sealed until tag {UNSEAL_TAG} and S + 90 days (tag {STOP_TAG}; "
            "docs/adr/0013-data-splits.md): "
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
