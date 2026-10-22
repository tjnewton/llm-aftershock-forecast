"""Figures for the write-up and video, and the compact table behind the results explorer.

Presentation only: every number comes from laf.analysis (frozen at scoring-v1).
Colors: the validated reference palette (dataviz skill), categorical slots 1-3 for the three
Claude models, ink gray for the official forecast.
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
    "laf/gpt-oss-20b-e1": "gpt-oss-20b adapted (E1)",
    "laf/gpt-oss-20b-e1a": "gpt-oss-20b adapted, more data (E1a)",
    "laf/gpt-oss-20b-e1r1": "gpt-oss-20b adapted (E1 repeat 1)",
    "laf/gpt-oss-20b-e1r2": "gpt-oss-20b adapted (E1 repeat 2)",
    "laf/gpt-oss-20b-e1ar2": "gpt-oss-20b adapted, more data (E1a repeat)",
    "laf/gpt-oss-20b-e1b": "gpt-oss-20b adapted on outcomes (E1b)",
}
COLOR = {
    "claude-haiku-5-5": "#2a78d6",
    "claude-sonnet-5-5": "#eb6834",
    "claude-opus-5-5": "#1baf7a",
    "official": "#52514e",
    "etas": "#6250d6",
}
INK, MUTED, SURFACE = "#0b0b0b", "#52514e", "#fcfcfb"
SHORT = {  # figure labels: no arm or effort jargon (the figures show direct, catalog only)
    "openai/gpt-oss-20b": "gpt-oss-20b",
    "allenai/Olmo-3.1-32B-Instruct": "Olmo 3.1 32B",
    "laf/gpt-oss-20b-e1": "gpt-oss-20b fine-tuned",
    "laf/gpt-oss-20b-e1a": "gpt-oss-20b fine-tuned, 3x data",
    "etas": "ETAS refit",
    "rj_mle": "Reasenberg-Jones refit",
}
DQS_AXIS = "score difference from USGS   (\u2190 better than USGS | worse \u2192)"


def display_name(forecaster: str) -> str:
    """'claude-sonnet-5-5|direct|I1|high' -> 'Sonnet 5.5 direct, catalog'."""
    if "|" not in forecaster:
        return LABEL.get(forecaster, forecaster)
    model, arm, info, effort = forecaster.split("|")
    name = LABEL.get(model, model.split("/")[-1])
    info_txt = "catalog" if info == "I1" else "no catalog"
    low = ", effort low" if effort == "low" else ""
    return f"{name} {arm}, {info_txt}{low}"


def short_name(forecaster: str) -> str:
    model = forecaster.split("|")[0]
    return SHORT.get(model, LABEL.get(model, model))


def explorer_table(df: pd.DataFrame, seqs: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per forecaster x cell: nine M>=5 quantiles (quantile-averaged over valid samples
    for LLMs), answer-level log-QS, the observed count and cell metadata; with `seqs`, a
    reader-facing sequence label (magnitude, name and, unless the name has one, month)."""
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
            "sequence_id",
        ]
    ]
    n = ok.groupby(keys).size().rename("n_samples").reset_index()
    out = qs.merge(score, on=keys).merge(n, on=keys).merge(meta, on=["issue_id", "window"])
    out["label"] = out["forecaster"].map(display_name)
    out["target"] = out["issue_id"].str.split("@").str[1]
    if seqs is not None:
        s = seqs.set_index("sequence_id")
        dated = s["name"].str.contains(r"\d{4}-\d{2}-\d{2}$")
        when = pd.to_datetime(s["origin_ms"], unit="ms").dt.strftime(" (%b %Y)").where(~dated, "")
        s_label = "M" + s["mag"].map("{:.1f}".format) + " " + s["name"] + when
        out["seq_label"] = out["sequence_id"].map(s_label)
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
    ax.set_xlabel(DQS_AXIS, fontsize=9, color=MUTED)
    _style(ax, "Claude vs the USGS forecast, preregistered post-cutoff sequences")
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


def _fan_panel(ax, t: pd.DataFrame, f: str, window: str) -> None:
    """5-95% and 25-75% bands and the median of N(M>=5) per issue time; observed as dots."""
    g = t[t["forecaster"] == f].sort_values("elapsed_days")
    c = COLOR.get(f.split("|")[0], MUTED)
    x = g["elapsed_days"].to_numpy()
    ax.fill_between(x, g["q050"], g["q950"], color=c, alpha=0.18, linewidth=0)
    ax.fill_between(x, g["q250"], g["q750"], color=c, alpha=0.35, linewidth=0)
    ax.plot(x, g["q500"], color=c, linewidth=2)
    obs = t.drop_duplicates("issue_id").sort_values("elapsed_days")
    ax.scatter(obs["elapsed_days"], obs["y5"], s=26, color=INK, zorder=3, label="observed")
    ax.set_xscale("log")
    ax.set_xticks([0.3, 1, 3, 10, 30], ["0.3", "1", "3", "10", "30"])
    ax.set_xlabel("days after mainshock (forecast time)", fontsize=8, color=MUTED)
    _style(ax, short_name(f))
    ax.set_ylabel(
        f"M\u22655 aftershocks in next {window.split()[1].lower()}", fontsize=9, color=MUTED
    )


def fig_fan(
    tab: pd.DataFrame, sequence: str, window: str, forecasters: list[str], path: Path
) -> None:
    """Small multiples: one forecast fan per forecaster."""
    t = tab[(tab["name"] == sequence) & (tab["window"] == window)]
    fig, axes = plt.subplots(
        1,
        len(forecasters),
        figsize=(3.0 * len(forecasters), 2.9),
        dpi=200,
        sharey=True,
        facecolor=SURFACE,
    )
    for i, (ax, f) in enumerate(zip(np.atleast_1d(axes), forecasters, strict=True)):
        _fan_panel(ax, t, f, window)
        if i:
            ax.set_ylabel("")
    np.atleast_1d(axes)[0].legend(frameon=False, fontsize=8, labelcolor=INK)
    fig.suptitle(
        f"{sequence}: forecast ranges vs observed counts", x=0.01, ha="left", fontsize=11, color=INK
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


OVERVIEW = (
    "claude-opus-5-5|direct|I1|high",
    "claude-sonnet-5-5|direct|I1|high",
    "claude-haiku-5-5|direct|I1|high",
    "openai/gpt-oss-20b|direct|I1|medium",
    "allenai/Olmo-3.1-32B-Instruct|direct|I1|none",
    "laf/gpt-oss-20b-e1|direct|I1|medium",
    "laf/gpt-oss-20b-e1a|direct|I1|medium",
    "etas",
    "rj_mle",
    "generic_rj",
    "naive",
)
FAMILY = {
    "openai/gpt-oss-20b": "#eda100",
    "allenai/Olmo-3.1-32B-Instruct": "#e87ba4",
    "laf/gpt-oss-20b-e1": "#008300",
    "laf/gpt-oss-20b-e1a": "#e34948",
}


GROUPS = (3, 7)  # rows before which a separator falls: open models, statistical baselines


def _forest_panel(ax, t: pd.DataFrame, rows: list[str], title: str) -> None:
    """Pooled dQS(forecaster, official) with 95% intervals; linear x clipped at the panel's
    range, values beyond it marked with an arrow and printed (open models' gaps are an order
    of magnitude larger than Claude's)."""
    t = t.set_index("forecaster")
    shown = t.loc[t.index.intersection(rows)]
    xmax = 0.5 if float(shown["hi"].max()) > 0.5 else max(0.05, float(shown["hi"].max()) * 1.15)
    xmin = min(-0.1, float(shown["lo"].min()) * 1.15)
    for i, f in enumerate(rows):
        y = len(rows) - 1 - i
        if i in GROUPS:
            ax.axhline(y + 0.5, color="#e7e6e1", linewidth=0.8)
        if f not in t.index:
            continue
        c = COLOR.get(f.split("|")[0], FAMILY.get(f.split("|")[0], MUTED))
        d, lo, hi = t.loc[f, ["dQS", "lo", "hi"]].to_numpy(dtype=float)
        lo, hi = max(lo, xmin), min(hi, xmax)
        ax.plot([lo, hi], [y, y], color=c, linewidth=2, solid_capstyle="round")
        if d > xmax:
            ax.scatter([xmax], [y], s=46, marker=">", color=c, zorder=3, clip_on=False)
            ax.annotate(f"+{d:.2f}", (xmax, y), xytext=(-8, 5), textcoords="offset points",
                        ha="right", fontsize=7, color=MUTED)  # fmt: skip
        else:
            ax.scatter([d], [y], s=36, color=c, edgecolor=SURFACE, linewidth=1.5, zorder=3)
    ax.axvline(0, color=MUTED, linewidth=1)
    ax.set_xlim(xmin, xmax)
    ax.set_xlabel(DQS_AXIS, fontsize=8, color=MUTED)
    ax.set_title(title, loc="left", fontsize=9, color=INK)
    _style(ax)
    ax.grid(axis="y", visible=False)


def _row_labels(ax, rows: list[str]) -> None:
    ax.set_yticks(range(len(rows)), [short_name(f) for f in reversed(rows)], fontsize=8, color=INK)


def fig_overview(panels: list[tuple[str, pd.DataFrame]], path: Path) -> None:
    """Every forecaster against the official forecast, one panel per cell set, rows in a fixed
    order grouped as Claude, open models, statistical baselines."""
    rows = [f for f in OVERVIEW if any(f in set(t["forecaster"]) for _, t in panels)]
    fig, axes = plt.subplots(
        1, len(panels), figsize=(3.6 * len(panels) + 1.6, 0.36 * len(rows) + 1.4), dpi=200,
        sharey=True, facecolor=SURFACE,
    )  # fmt: skip
    for ax, (title, t) in zip(np.atleast_1d(axes), panels, strict=True):
        _forest_panel(ax, t, rows, title)
    _row_labels(np.atleast_1d(axes)[0], rows)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def fig_headline(tab: pd.DataFrame, reg: pd.DataFrame, path: Path) -> None:
    """The write-up figure: (a) USGS and Opus forecast fans for the Flores Sea week windows,
    (b) every forecaster against the official forecast on the registered cells."""
    rows = [f for f in OVERVIEW if f in set(reg["forecaster"])]
    fig = plt.figure(figsize=(11.5, 3.6), dpi=200, facecolor=SURFACE)
    gs = fig.add_gridspec(1, 3, width_ratios=(1, 1, 1.45), wspace=0.12)
    t = tab[(tab["name"] == "Flores Sea") & (tab["window"] == "1 Week")]
    a0 = fig.add_subplot(gs[0])
    a1 = fig.add_subplot(gs[1], sharey=a0)
    for ax, f in ((a0, "official"), (a1, "claude-opus-5-5|direct|I1|high")):
        _fan_panel(ax, t, f, "1 Week")
    a1.set_ylabel("")
    a1.tick_params(labelleft=False)
    a0.set_title("(a) Flores Sea M7.8: USGS official", loc="left", fontsize=10, color=INK)
    a1.set_title("Opus 5.5", loc="left", fontsize=10, color=INK)
    a0.legend(frameon=False, fontsize=8, labelcolor=INK)
    a2 = fig.add_subplot(gs[2])
    _forest_panel(a2, reg, rows, "")
    a2.set_title("(b) All forecasters vs USGS, preregistered test", loc="left", fontsize=10,
                 color=INK)  # fmt: skip
    _row_labels(a2, rows)
    a2.yaxis.tick_right()
    a2.tick_params(axis="y", length=0, pad=10)
    fig.subplots_adjust(left=0.05, right=0.8, bottom=0.17, top=0.88)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
