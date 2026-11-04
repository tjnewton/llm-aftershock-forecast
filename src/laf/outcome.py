"""The outcome snapshot at S + 90 days (prereg v2 section 5): the one directory `laf confirmatory`
reads.

Forecast-time inputs stay as they were frozen, in the snapshot each sequence was taken in (the
candidates, the forward-excluded ones, the supplementary snapshot at L): the items, the issue
times and catalogs, the official forecasts and the ETAS refit. Only outcomes are new: a fresh
fetch of every sequence at S + 90 days gives its catalog, recounted in each frozen issue's own
circle and windows, and its catalog end, which decides settling. Sequences with origin at L or
later belong to the prospective part (a sequence belongs to exactly one part) and come from the
fresh fetch alone (no counts: `laf.live_scores` counts their live items there).

`laf outcome-config` writes the fresh fetch's config (the frozen configs and every live item's
sequence); `laf outcome-snapshot` assembles the directory.
"""

import json
import tomllib
from pathlib import Path

import pandas as pd

MANIFEST = Path("results/freeze_manifest.json")
# the snapshot taken at L, after the freeze: hashed when taken (`laf freeze-manifest --out`)
SUPPLEMENTARY_MANIFEST = Path("results/supplementary_manifest.json")
# forecast-time tables that a later fetch would extend: kept from the frozen snapshot, and taken
# from the fresh one for the live sequences, whose matched items use the official forecasts
VERSION_TABLES = ("oaf_versions", "forecast_bins", "forecast_fractiles")


def config(configs: list[Path], live: Path | None, out: Path) -> int:
    """Write one config: the sequences of `configs`, then each live item's sequence ID not among
    them (a changed preferred ID adds the new one); returns the number of sequences."""
    from laf.live_watch import CATALOG_MIN_MAG

    seqs = [s for c in configs for s in tomllib.loads(c.read_text(encoding="utf-8"))["sequence"]]
    ids = {s["id"] for s in seqs}
    for p in sorted(live.glob("*/*/items.jsonl")) if live else []:
        for x in p.read_text(encoding="utf-8").split("\n"):
            sid = json.loads(x)["sequence_id"] if x.strip() else None
            if sid and sid not in ids:
                ids.add(sid)
                seqs.append({"id": sid, "name": f"live {sid}", "role": "test-post",
                             "catalog_min_mag": CATALOG_MIN_MAG})  # fmt: skip
    lines = [
        "# The outcome snapshot's fetch (prereg v2 section 5), written by `laf outcome-config`."
    ]
    for s in seqs:
        lines += ["", "[[sequence]]", *(f"{k} = {json.dumps(v)}" for k, v in s.items())]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return len(seqs)


def check_committed(
    manifests: tuple[Path, ...] = (MANIFEST, SUPPLEMENTARY_MANIFEST),
    revs: tuple[str, ...] = ("prereg-v2", "HEAD"),
) -> None:
    """Each manifest present is the one committed at its revision: the freeze manifest at the
    tag prereg-v2, the supplementary one at HEAD (committed when taken, at L). A working copy
    that differs, or is not committed there, is refused: the posted hashes govern."""
    import subprocess

    for path, rev in zip(manifests, revs, strict=True):
        if not path.exists():
            continue  # the freeze manifest's absence is refused by `_check_frozen`
        shown = subprocess.run(["git", "show", f"{rev}:{path.as_posix()}"], capture_output=True)
        if shown.returncode != 0 or shown.stdout != path.read_bytes():
            raise SystemExit(f"{path}: differs from the copy committed at {rev}")


def _check_frozen(proc: Path, snapshot: str, manifests: tuple[Path, ...]) -> Path | None:
    """The manifest that lists `snapshot`, once every file it lists for it still has its hash;
    None when none does. The first (the freeze manifest) must exist."""
    from laf.freeze import sha256

    if not manifests[0].exists():
        raise SystemExit(
            f"{manifests[0]}: no freeze manifest (`laf freeze-manifest`, at the freeze)"
        )
    for path in (m for m in manifests if m.exists()):
        m = json.loads(path.read_text(encoding="utf-8"))
        if snapshot not in m["snapshots"]:
            continue
        for k, h in m["files"].items():
            f = Path(k)
            if f.parent.name == snapshot and sha256(proc / f.name) != h:
                raise SystemExit(f"{proc / f.name}: differs from {path}")
        return path
    return None


def assemble(
    data_dir: Path, frozen: list[str], fresh: str, live_start: int | None,
    manifests: tuple[Path, ...] = (MANIFEST, SUPPLEMENTARY_MANIFEST), unlisted: bool = False,
) -> tuple[dict[str, pd.DataFrame], list[str], list[str]]:  # fmt: skip
    """(tables, item lines, notes) of the outcome snapshot. `live_start` is L; without it every
    frozen sequence counts as retrospective."""
    from laf.analysis import load_tables
    from laf.catalog import count_in_window, haversine_km
    from laf.oaf import Circle
    from laf.splits import seal_counts
    from laf.tables import DAY_MS
    from laf.usgs import read_raw

    proc = data_dir / "processed"
    new = load_tables(proc / fresh)
    parts: dict[str, list[pd.DataFrame]] = {}
    lines: list[str] = []
    notes: list[str] = []
    owner: dict[str, str] = {}
    for snap in frozen:
        d = proc / snap
        listed = _check_frozen(d, snap, manifests)
        if listed is None and not unlisted:  # `unlisted`: rehearsals on development data
            raise SystemExit(f"{snap}: in no manifest ({', '.join(map(str, manifests))})")
        notes.append(f"{snap}: {f'matches {listed}' if listed else 'in no manifest'}")
        t = load_tables(d)
        s = t["sequences"]
        keep = set(s["sequence_id"] if live_start is None else s.loc[s["origin_ms"] < live_start,
                                                                     "sequence_id"])  # fmt: skip
        if clash := sorted(keep & set(owner)):
            raise SystemExit(f"{snap}: sequences also in {owner[clash[0]]}: {', '.join(clash)}")
        owner |= dict.fromkeys(keep, snap)
        issues = set(t["issue_times"].loc[t["issue_times"]["sequence_id"].isin(keep), "issue_id"])
        for name, df in t.items():
            if name == "catalog":
                continue  # outcomes come from the fresh fetch
            mine = (
                df["sequence_id"].isin(keep) if "sequence_id" in df else df["issue_id"].isin(issues)
            )
            parts.setdefault(name, []).append(df[mine])
        for x in (d / "items_m3.jsonl").read_text(encoding="utf-8").split("\n"):
            if x.strip() and json.loads(x)["sequence_id"] in keep:
                lines.append(x)
    fresh_ids = set(new["sequences"]["sequence_id"])
    if missing := sorted(set(owner) - fresh_ids):
        raise SystemExit(f"the fresh snapshot {fresh} lacks {', '.join(missing)}")
    others = fresh_ids - set(owner)  # the prospective part's sequences
    # their issue times too: the informative estimand reads each sequence's first issue
    # (`confirmatory.informative`); scored cells come from observed_counts, which they lack
    for name in ("sequences", "issue_times", *VERSION_TABLES):
        parts.setdefault(name, []).append(new[name][new[name]["sequence_id"].isin(others)])
    out = {name: pd.concat(dfs, ignore_index=True) for name, dfs in parts.items()}
    out["catalog"] = new["catalog"]

    end = new["sequences"].set_index("sequence_id")["catalog_end_ms"]
    out["sequences"]["catalog_end_ms"] = out["sequences"]["sequence_id"].map(end)
    its = out["issue_times"].set_index("issue_id")
    uncovered = []  # an issue circle the fresh query circle does not hold would be undercounted
    for sid in owner:
        meta = json.loads(read_raw(data_dir, f"raw/snapshots/{fresh}/catalog/{sid}.meta.json"))
        mine = its[its["sequence_id"] == sid]
        lat, lon = mine["region_lat"], mine["region_lon"]
        dist = haversine_km(meta["center_lat"], meta["center_lon"], lat, lon)
        query = float(meta["radius_km"]) + 1e-6
        uncovered += list(mine.index[dist + mine["region_radius_km"] > query])
        # the radius sensitivity recounts in this catalog (`d2.recount_m5`): coverage is its
        its.loc[mine.index, "query_covers_x1_5"] = dist + 1.5 * mine["region_radius_km"] <= query
    out["issue_times"] = its.reset_index()
    if uncovered:
        raise SystemExit(f"the fresh query circle misses issues {', '.join(sorted(uncovered))}")
    oc = out["observed_counts"].drop(columns=["count", "closed", "days_since_close", "sealed"],
                                     errors="ignore")  # fmt: skip
    cat = dict(tuple(new["catalog"].groupby("sequence_id")))
    none = new["catalog"].iloc[:0]
    circles = {i: Circle(float(r["region_lat"]), float(r["region_lon"]),
                         float(r["region_radius_km"])) for i, r in its.iterrows()}  # fmt: skip
    oc["count"] = [
        count_in_window(cat.get(r["sequence_id"], none), circles[r["issue_id"]],
                        int(r["time_start_ms"]), int(r["time_end_ms"]), float(r["magnitude"]))
        for r in oc.to_dict("records")
    ]  # fmt: skip
    oc_end = oc["sequence_id"].map(end)
    oc["closed"] = oc["time_end_ms"] <= oc_end
    oc["days_since_close"] = (oc_end - oc["time_end_ms"]) / DAY_MS
    out["observed_counts"] = seal_counts(oc)  # null until the second gate opens (laf.splits)
    notes.append(f"{len(owner)} frozen sequences, {len(lines)} items; {len(others)} from {fresh}")
    return out, lines, notes


def write(data_dir: Path, name: str, tables: dict[str, pd.DataFrame], lines: list[str]) -> Path:
    from laf.tables import write_tables

    d = data_dir / "processed" / name
    if d.exists():
        raise SystemExit(f"{d} exists: the outcome snapshot is written once")
    if tables["observed_counts"]["count"].isna().any():  # written once, so never sealed
        raise SystemExit("outcomes are sealed (laf.splits): the outcome snapshot is written "
                         "only once both gates are open")  # fmt: skip
    write_tables(tables, d)
    (d / "items.jsonl").write_text("".join(x + "\n" for x in lines), encoding="utf-8", newline="\n")
    return d
