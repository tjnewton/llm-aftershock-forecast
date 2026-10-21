"""Figures for the write-up and video, and the compact table behind the results explorer.

Presentation only: every number comes from laf.analysis (frozen at scoring-v1).
Colours: the validated reference palette (dataviz skill), categorical slots 1-3 for the three
Claude models, ink grey for the official forecast.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from laf import analysis as A

QCOLS = ("q025", "q050", "q100", "q250", "q500", "q750", "q900", "q950", "q975")
MODELS = ("claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5")
LABEL = {
    "claude-haiku-5-5": "Haiku 5.5",
    "claude-sonnet-5-5": "Sonnet 5.5",
    "claude-opus-5-5": "Opus 5.5",
    "official": "USGS official",
    "etas": "Legacy-ETAS refit",
    "rj_mle": "RJ-MLE refit",
    "generic_rj": "Generic RJ",
    "naive": "Naive",
}
COLOR = {
    "claude-haiku-5-5": "#2a78d6",
    "claude-sonnet-5-5": "#eb6834",
    "claude-opus-5-5": "#1baf7a",
    "official": "#52514e",
    "etas": "#6250d6",
}
INK, MUTED, SURFACE = "#0b0b0b", "#52514e", "#fcfcfb"


def display_name(forecaster: str) -> str:
    """'claude-sonnet-5-5|direct|I1|high' -> 'Sonnet 5.5 direct, catalog'."""
    if "|" not in forecaster:
        return LABEL.get(forecaster, forecaster)
    model, arm, info, effort = forecaster.split("|")
    name = LABEL.get(model, model.split("/")[-1])
    info_txt = "catalog" if info == "I1" else "no catalog"
    low = ", effort low" if effort == "low" else ""
    return f"{name} {arm}, {info_txt}{low}"


def explorer_table(df: pd.DataFrame) -> pd.DataFrame:
    """One row per forecaster x cell: nine M>=5 quantiles (quantile-averaged over valid samples
    for LLMs), answer-level log-QS, the observed count and cell metadata."""
    ok = df[df["status"].eq("ok") & df["m5"].notna()]
    keys = ["forecaster", "issue_id", "window"]
    q = ok.groupby(keys)["m5"].apply(lambda s: np.mean(np.vstack(s.to_list()), axis=0))
    qs = pd.DataFrame(q.to_list(), index=q.index, columns=list(QCOLS)).reset_index()
    score = A.answer_scores(df).groupby(keys)["log_qs"].mean().reset_index()
    meta = df.drop_duplicates(["issue_id", "window"])[
        [
            "issue_id",
            "window",
            "name",
            "role",
            "primary",
            "oaf_cell",
            "elapsed_days",
            "y5",
            "time_start_ms",
        ]
    ]
    n = ok.groupby(keys).size().rename("n_samples").reset_index()
    out = qs.merge(score, on=keys).merge(n, on=keys).merge(meta, on=["issue_id", "window"])
    out["label"] = out["forecaster"].map(display_name)
    out["target"] = out["issue_id"].str.split("@").str[1]
    return out.sort_values(["name", "window", "elapsed_days", "forecaster"])


def _style(ax, title: str | None = None) -> None:
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#c3c2b7")
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(axis="x", color="#e7e6e1", linewidth=0.8)
    ax.set_axisbelow(True)
    if title:
        ax.set_title(title, loc="left", fontsize=11, color=INK)


def fig_h1(h1: pd.DataFrame, path: Path) -> None:
    """H1 per OAF sequence and pooled: dQS(model, official) with 95% bootstrap intervals."""
    seqs = [s for s in ("Colombia", "Flores Sea") if s in set(h1["sequence"])] + ["pooled"]
    fig, ax = plt.subplots(figsize=(6.4, 3.8), dpi=200, facecolor=SURFACE)
    offsets = {m: o for m, o in zip(MODELS, (0.22, 0.0, -0.22), strict=True)}
    for m in MODELS:
        g = h1[h1["model"] == m].set_index("sequence")
        for i, s in enumerate(seqs):
            if s not in g.index:
                continue
            r = g.loc[s]
            y = len(seqs) - 1 - i + offsets[m]
            ax.plot([r["lo"], r["hi"]], [y, y], color=COLOR[m], linewidth=2, solid_capstyle="round")
            ax.scatter(
                [r["dQS"]],
                [y],
                s=42,
                color=COLOR[m],
                edgecolor=SURFACE,
                linewidth=1.5,
                zorder=3,
                label=LABEL[m] if i == 0 else None,
            )
    ax.axvline(0, color=MUTED, linewidth=1)
    ax.set_yticks(range(len(seqs)), [s for s in reversed(seqs)], fontsize=9, color=INK)
    ax.set_xlabel(
        "dQS = log-QS(model) - log-QS(official)   (> 0: official better)", fontsize=9, color=MUTED
    )
    _style(ax, "Claude vs the USGS official forecast, test-post OAF cells (H1)")
    ax.legend(
        frameon=False,
        fontsize=8,
        labelcolor=INK,
        ncol=3,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.22),
    )
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def fig_fan(
    tab: pd.DataFrame, sequence: str, window: str, forecasters: list[str], path: Path
) -> None:
    """Small multiples: one panel per forecaster; 5-95% and 25-75% bands and the median of
    N(M>=5) at each issue time, observed counts as dots."""
    t = tab[(tab["name"] == sequence) & (tab["window"] == window)]
    fig, axes = plt.subplots(
        1,
        len(forecasters),
        figsize=(3.0 * len(forecasters), 2.9),
        dpi=200,
        sharey=True,
        facecolor=SURFACE,
    )
    for ax, f in zip(np.atleast_1d(axes), forecasters, strict=True):
        g = t[t["forecaster"] == f].sort_values("elapsed_days")
        c = COLOR.get(f.split("|")[0], MUTED)
        x = g["elapsed_days"].to_numpy()
        ax.fill_between(x, g["q050"], g["q950"], color=c, alpha=0.18, linewidth=0)
        ax.fill_between(x, g["q250"], g["q750"], color=c, alpha=0.35, linewidth=0)
        ax.plot(x, g["q500"], color=c, linewidth=2)
        obs = t.drop_duplicates("issue_id").sort_values("elapsed_days")
        ax.scatter(obs["elapsed_days"], obs["y5"], s=26, color=INK, zorder=3, label="observed")
        ax.set_xscale("log")
        ax.set_xlabel("issue time, days after mainshock", fontsize=8, color=MUTED)
        _style(ax, display_name(f))
    np.atleast_1d(axes)[0].set_ylabel(f"N(M>=5), {window} window", fontsize=9, color=MUTED)
    np.atleast_1d(axes)[0].legend(frameon=False, fontsize=8, labelcolor=INK)
    fig.suptitle(
        f"{sequence}: forecast fans vs observed counts", x=0.01, ha="left", fontsize=11, color=INK
    )
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def fig_coverage(df: pd.DataFrame, path: Path) -> None:
    """Empirical coverage of central intervals vs nominal, all primary cells (valid samples)."""
    cov = A.coverage_table(df, df["primary"])
    rows = ["official"] + [f"{m}|direct|I1|high" for m in MODELS]
    levels = (50, 80, 90, 95)
    fig, ax = plt.subplots(figsize=(4.6, 3.6), dpi=200, facecolor=SURFACE)
    ax.plot([45, 100], [45, 100], color="#c3c2b7", linewidth=1, linestyle=(0, (3, 3)))
    for f in rows:
        if f not in cov.index:
            continue
        y = [100 * float(cov.at[f, f"cov{lv}"]) for lv in levels]  # type: ignore[arg-type]
        c = COLOR.get(f.split("|")[0], MUTED)
        ax.plot(
            levels,
            y,
            color=c,
            linewidth=2,
            marker="o",
            markersize=5,
            markeredgecolor=SURFACE,
            label=display_name(f),
        )
    ax.set_xlim(45, 100)
    ax.set_ylim(45, 100)
    ax.set_xlabel("nominal central-interval coverage (%)", fontsize=9, color=MUTED)
    ax.set_ylabel("empirical coverage (%)", fontsize=9, color=MUTED)
    _style(ax, "Calibration of N(M>=5) intervals, primary cells")
    ax.legend(frameon=False, fontsize=7.5, labelcolor=INK, loc="upper left")
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
