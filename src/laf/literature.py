"""E2 literature exposure (prereg section 11): distinct papers about each mainshock, from the
Valency queries stored in data/raw/literature/ and the screening in config/literature_screen.csv,
counted before each model's documented cutoff and before the sequence's issue times.

Descriptive covariate beside H5; no claim rests on it.
"""

import json
import re
from pathlib import Path

import pandas as pd

RAW = "raw/literature"
# First day after each documented cutoff month (docs/model-registry.md): a paper dated in the
# cutoff month counts as possibly seen.
CUTOFF = {"claude-5-5": "2026-07-01", "gpt-oss-20b": "2024-07-01", "olmo-3.1-32b": "2025-01-01"}


def papers(data_dir: Path, screen: Path) -> pd.DataFrame:
    """Included papers, one row per sequence and distinct paper (DOI, else versionless id).
    A screened paper must appear in that sequence's own query results."""
    s = pd.read_csv(screen, dtype=str)
    rows = []
    for sid, g in s[s["include"] == "true"].groupby("sequence_id"):
        found = {}
        for path in sorted((data_dir / RAW).glob(f"{sid}_q*.json")):
            for p in json.loads(path.read_text(encoding="utf-8"))["papers"]:
                found[re.sub(r"v\d+$", "", p["id"])] = p
        for pid in g["paper_id"]:
            if pid not in found:
                raise ValueError(f"{pid} is not in the {sid} query results")
            p = found[pid]
            rows.append(
                {
                    "sequence_id": sid,
                    "paper_id": pid,
                    "key": (p.get("doi") or "").lower() or pid,
                    "first_available": p["dates"]["first_available"]["value"],
                    "title": p["title"],
                }
            )
    return pd.DataFrame(rows).drop_duplicates(["sequence_id", "key"]).reset_index(drop=True)


def exposure(pap: pd.DataFrame, issues: pd.DataFrame, names: dict[str, str]) -> pd.DataFrame:
    """Per sequence: papers in all, before each model cutoff, and before its first and last
    issue time (a paper counts from 00:00 UTC of its first-available day)."""
    day_ms = pd.to_datetime(pap["first_available"], utc=True).dt.as_unit("ms").astype("int64")
    out = []
    for sid, name in names.items():
        mine = day_ms[pap["sequence_id"] == sid]
        iss = issues.loc[issues["sequence_id"] == sid, "issue_ms"]
        row = {"sequence_id": sid, "name": name, "n_papers": len(mine)}
        for model, cut in CUTOFF.items():
            cut_ms = pd.Timestamp(cut, tz="UTC").value // 1_000_000
            row[f"before_{model}"] = int((mine < cut_ms).sum())
        row["before_first_issue"] = int((mine < iss.min()).sum()) if len(iss) else None
        row["before_last_issue"] = int((mine < iss.max()).sum()) if len(iss) else None
        out.append(row)
    return pd.DataFrame(out)
