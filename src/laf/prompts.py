"""Render prompt templates (prompts/*.txt) for an item; hash templates for freezing."""

import hashlib
import json
from pathlib import Path
from string import Template
from typing import Literal

from laf.items import Item, utc

PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"
Arm = Literal["direct", "params"]
Info = Literal["I0", "I1"]
Paraphrase = Literal["p1", "p2"]
DAY_MS = 86_400_000


def _t(name: str) -> Template:
    return Template((PROMPT_DIR / name).read_text(encoding="utf-8"))


def _windows_table(item: Item) -> str:
    o = item.mainshock.origin_ms
    return "\n".join(
        f"- {w.key}: {utc(w.start_ms)} to {utc(w.end_ms)} UTC "
        f"(days {(w.start_ms - o) / DAY_MS:.2f} to {(w.end_ms - o) / DAY_MS:.2f})"
        for w in item.windows
    )


def _catalog_section(item: Item) -> str:
    rows = ["t_days,utc_time,mag,mag_type,depth_km,dist_km"] + [
        f"{r.t_days:.4f},{r.utc_time},{r.mag:.1f},{r.mag_type},{r.depth_km:g},{r.dist_km:g}"
        for r in item.catalog
    ]
    if not item.catalog:
        rows.append("(no events)")
    note = ""
    if item.truncated and item.daily_counts:
        note = (
            f"Only the {len(item.catalog)} most recent events are listed. Daily counts for the "
            "whole period (day = whole days after the mainshock): "
            + "; ".join(
                f"day {d['day']}: M4+ {d['m4']}, M5+ {d['m5']}, M6+ {d['m6']}"
                for d in item.daily_counts
            )
            + "."
        )
    return _t("catalog_section.txt").substitute(
        catalog_floor=f"{4.0:.1f}", truncation_note=note, catalog_csv="\n".join(rows)
    )


def render(item: Item, arm: Arm, info: Info, paraphrase: Paraphrase) -> tuple[str, str]:
    """(system, user) text for one request. Raises KeyError on a missing template field."""
    m, r = item.mainshock, item.region
    catalog = (
        _catalog_section(item)
        if info == "I1"
        else (PROMPT_DIR / "catalog_none.txt").read_text(encoding="utf-8")
    )
    context = _t("user_context.txt").substitute(
        origin_utc=m.origin_utc,
        place=m.place,
        lat=f"{m.lat:.4f}",
        lon=f"{m.lon:.4f}",
        depth_km=f"{m.depth_km:.1f}",
        mag=f"{m.mag:.1f}",
        mag_type=m.mag_type,
        radius_km=f"{r.radius_km:.1f}",
        region_lat=f"{r.lat:.4f}",
        region_lon=f"{r.lon:.4f}",
        issue_utc=utc(item.issue_ms),
        elapsed_days=f"{item.elapsed_days:.2f}",
        windows_table=_windows_table(item),
        catalog_section=catalog.strip(),
    )
    task = (PROMPT_DIR / f"task_{arm}_{paraphrase}.txt").read_text(encoding="utf-8")
    system = (PROMPT_DIR / f"system_{paraphrase}.txt").read_text(encoding="utf-8").strip()
    return system, f"{context.strip()}\n\n{task.strip()}"


def schema(name: Literal["direct", "params", "probe"]) -> dict:
    return json.loads((PROMPT_DIR / f"schema_{name}.json").read_text(encoding="utf-8"))


def template_hashes() -> dict[str, str]:
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(PROMPT_DIR.iterdir())
        if p.suffix in {".txt", ".json"} and p.name != "HASHES.json"
    }
