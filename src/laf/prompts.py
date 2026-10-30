"""Render prompt templates (prompts/*.txt) for an item; hash templates for freezing."""

import hashlib
import json
from pathlib import Path
from string import Template
from typing import Literal

from laf.items import N_LARGEST, Item, utc

PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"
Arm = Literal["direct", "params"]
Info = Literal["I0", "I1"]
Paraphrase = Literal["p1", "p2", "v2A", "v2B", "v2C"]
# v2 (D2, docs/proposals/d2-prompt-robustness.md): direct arm only, M3 quantiles, catalog from
# M3.0; A and B reuse the p1 and p2 wording, C is A with the catalog given as a summary
V2 = {"v2A": ("A", "list"), "v2B": ("B", "list"), "v2C": ("A", "summary")}
V2_FLOOR = 3.0
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


def _catalog_section(item: Item, floor: float = 4.0) -> str:
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
                f"day {d['day']}: "
                + (f"M3+ {d['m3']}, " if "m3" in d else "")
                + f"M4+ {d['m4']}, M5+ {d['m5']}, M6+ {d['m6']}"
                for d in item.daily_counts
            )
            + "."
        )
    return _t("catalog_section.txt").substitute(
        catalog_floor=f"{floor:.1f}", truncation_note=note, catalog_csv="\n".join(rows)
    )


def _catalog_summary(item: Item) -> str:
    """Variant C: daily counts at M3/M4/M5/M6 and the largest events instead of the list."""
    days = item.daily_counts
    if days is None:  # not truncated: count from the listed events
        by_day: dict[int, list[float]] = {}
        for r in item.catalog:
            by_day.setdefault(int(r.t_days // 1), []).append(r.mag)
        days = [
            {"day": d, **{f"m{k}": sum(m >= k - 1e-6 for m in ms) for k in (3, 4, 5, 6)}}
            for d, ms in sorted(by_day.items())
        ]
    lines = [
        f"- day {d['day']}: M3+ {d['m3']}, M4+ {d['m4']}, M5+ {d['m5']}, M6+ {d['m6']}"
        for d in days
    ] or ["- (no events)"]
    # the whole period's largest events (items built at floor 3.0 carry them even when the
    # listed catalog is truncated to the most recent rows)
    largest = item.largest if item.largest is not None else item.catalog
    largest = sorted(largest, key=lambda r: (-r.mag, r.t_days))[:N_LARGEST]
    rows = ["t_days,utc_time,mag,mag_type,depth_km,dist_km"] + [
        f"{r.t_days:.4f},{r.utc_time},{r.mag:.1f},{r.mag_type},{r.depth_km:g},{r.dist_km:g}"
        for r in sorted(largest, key=lambda r: r.t_days)
    ]
    return _t("v2/catalog_summary.txt").substitute(
        daily_counts="\n".join(lines), n_largest=len(largest), largest_csv="\n".join(rows)
    )


def render(item: Item, arm: Arm, info: Info, paraphrase: Paraphrase) -> tuple[str, str]:
    """(system, user) text for one request. Raises KeyError on a missing template field."""
    m, r = item.mainshock, item.region
    v2 = V2.get(paraphrase)
    if v2 and arm != "direct":
        raise ValueError("v2 prompts are defined for the direct arm only")
    if info == "I0":
        catalog = (PROMPT_DIR / "catalog_none.txt").read_text(encoding="utf-8")
    elif v2 and v2[1] == "summary":
        catalog = _catalog_summary(item)
    else:
        catalog = _catalog_section(item, V2_FLOOR if v2 else 4.0)
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
    if v2:
        task = (PROMPT_DIR / "v2" / f"task_{arm}_{v2[0]}.txt").read_text(encoding="utf-8")
        system = (PROMPT_DIR / "v2" / f"system_{v2[0]}.txt").read_text(encoding="utf-8").strip()
    else:
        task = (PROMPT_DIR / f"task_{arm}_{paraphrase}.txt").read_text(encoding="utf-8")
        system = (PROMPT_DIR / f"system_{paraphrase}.txt").read_text(encoding="utf-8").strip()
    return system, f"{context.strip()}\n\n{task.strip()}"


def schema_for(arm: Arm, paraphrase: Paraphrase) -> dict:
    """The response schema of a request: v2 direct answers carry M3 quantiles too."""
    if paraphrase in V2:
        return json.loads((PROMPT_DIR / "v2" / "schema_direct.json").read_text(encoding="utf-8"))
    return schema(arm)


def schema(name: Literal["direct", "params", "probe"]) -> dict:
    return json.loads((PROMPT_DIR / f"schema_{name}.json").read_text(encoding="utf-8"))


def template_hashes(sub: str = "") -> dict[str, str]:
    """SHA-256 per template in prompts/ (registered, `sub` empty) or prompts/<sub>/."""
    d = PROMPT_DIR / sub
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(d.iterdir())
        if p.suffix in {".txt", ".json"} and p.name != "HASHES.json"
    }
