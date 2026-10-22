import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium", app_title="LLM aftershock forecasts vs USGS")


@app.cell
def _():
    import contextlib

    import altair as alt
    import marimo as mo
    import pandas as pd

    COLOR = {
        "USGS official": "#52514e",
        "Legacy-ETAS refit": "#6250d6",
        "Haiku 5.5 direct, catalog": "#2a78d6",
        "Sonnet 5.5 direct, catalog": "#eb6834",
        "Opus 5.5 direct, catalog": "#1baf7a",
        "gpt-oss-20b direct, catalog": "#eda100",
        "Olmo-3.1-32B-Instruct direct, catalog": "#e87ba4",
        "gpt-oss-20b adapted (E1) direct, catalog": "#008300",
        "gpt-oss-20b adapted, more data (E1a) direct, catalog": "#e34948",
    }
    return COLOR, alt, contextlib, mo, pd


@app.cell
def _(contextlib, mo, pd):
    _base = mo.notebook_location() / "public"
    _frames = [pd.read_csv(str(_base / "explorer.csv")).assign(set="Registered")]
    with contextlib.suppress(Exception):  # the exploratory E3 table is optional
        _frames.append(pd.read_csv(str(_base / "explorer_e3.csv")).assign(set="E3 (exploratory)"))
    all_data = pd.concat(_frames, ignore_index=True)
    mo.md(
        """# Do LLMs forecast aftershocks like the USGS?
Each panel shows one forecaster's N(M>=5) forecast at every issue time of a sequence: the
5-95% band, the 25-75% band and the median, with the count that was later observed. Claude
answers are quantile-averaged over their valid samples. Scores are log-scale quantile scores
(lower is better) from the code frozen at tag `scoring-v1`; the analysis plan was frozen at
`prereg-v1`. The "E3 (exploratory)" set holds 39 further sequences with an official forecast,
added after the freeze (docs/adr/0012-e3-extended-set.md). Source:
https://github.com/tjnewton/llm-aftershock-forecast"""
    )
    return (all_data,)


@app.cell
def _(all_data, mo):
    dataset = mo.ui.dropdown(
        sorted(all_data["set"].unique(), reverse=True), value="Registered", label="Set"
    )
    dataset  # noqa: B018 (marimo displays the last expression)
    return (dataset,)


@app.cell
def _(all_data, dataset):
    data = all_data[all_data["set"] == dataset.value]
    return (data,)


@app.cell
def _(data, mo):
    seqs = sorted(data["name"].unique())
    labels = sorted(data["label"].unique())
    sequence = mo.ui.dropdown(
        seqs, value="Flores Sea" if "Flores Sea" in seqs else seqs[0], label="Sequence"
    )
    window = mo.ui.dropdown(["1 Day", "1 Week", "1 Month"], value="1 Week", label="Window")
    default = [
        x
        for x in ("USGS official", "Legacy-ETAS refit", "Sonnet 5.5 direct, catalog")
        if x in labels
    ]
    chosen = mo.ui.multiselect(labels, value=default, label="Forecasters", max_selections=4)
    primary_only = mo.ui.checkbox(value=False, label="Primary cells only (settled >= 21 days)")
    mo.hstack([sequence, window, chosen, primary_only], justify="start", wrap=True)
    return chosen, primary_only, sequence, window


@app.cell
def _(chosen, data, primary_only, sequence, window):
    view = data[
        (data["name"] == sequence.value)
        & (data["window"] == window.value)
        & data["label"].isin(chosen.value)
    ]
    if primary_only.value:
        view = view[view["primary"]]
    return (view,)


@app.cell
def _(COLOR, alt, chosen, mo, view):
    if view.empty:
        _out = mo.md("No cells for this selection.")
    else:
        _domain = list(chosen.value)
        _range = [COLOR.get(x, "#c3c2b7") for x in _domain]
        _color = alt.Color("label:N", scale=alt.Scale(domain=_domain, range=_range), legend=None)
        _x = alt.X(
            "elapsed_days:Q",
            scale=alt.Scale(type="log", nice=False),
            axis=alt.Axis(values=[0.3, 1, 3, 7, 14, 28], grid=False),
            title="issue time, days after mainshock",
        )
        _tip = [
            alt.Tooltip("target:N", title="issue"),
            alt.Tooltip("q050:Q", title="5%"),
            alt.Tooltip("q500:Q", title="median"),
            alt.Tooltip("q950:Q", title="95%"),
            alt.Tooltip("y5:Q", title="observed"),
            alt.Tooltip("log_qs:Q", title="log-QS", format=".3f"),
        ]
        _base = alt.Chart(view).encode(x=_x)
        _outer = _base.mark_area(opacity=0.18).encode(
            y=alt.Y("q050:Q", title="N(M>=5)"), y2="q950:Q", color=_color
        )
        _inner = _base.mark_area(opacity=0.35).encode(y="q250:Q", y2="q750:Q", color=_color)
        _median = _base.mark_line(strokeWidth=2).encode(y="q500:Q", color=_color)
        _obs = _base.mark_circle(size=70, color="#0b0b0b", opacity=1).encode(y="y5:Q", tooltip=_tip)
        _chart = (
            alt.layer(_outer, _inner, _median, _obs)
            .properties(width=230, height=220)
            .facet(column=alt.Column("label:N", title=None, sort=_domain))
            .configure_view(stroke=None)
        )
        _out = mo.ui.altair_chart(_chart)
    _out  # noqa: B018 (marimo displays the last expression)
    return


@app.cell
def _(mo, view):
    _tab = (
        view.pivot_table(index=["target", "elapsed_days"], columns="label", values="log_qs")
        .sort_index(level="elapsed_days")
        .round(3)
        if not view.empty
        else view
    )
    mo.vstack([mo.md("**Log-QS per issue time** (lower is better)"), _tab])
    return


@app.cell
def _(data, dataset, mo):
    _p = data[data["primary"]]
    _col = "name" if dataset.value == "Registered" else "role"
    _tab = (
        _p.pivot_table(index="label", columns=_col, values="log_qs")
        .assign(**{"all primary cells": _p.groupby("label")["log_qs"].mean()})
        .sort_values("all primary cells")
        .round(3)
    )
    mo.vstack(
        [
            mo.md("""**Mean log-QS over primary cells, every forecaster** (forecasters
without a catalog, or at low effort, were run on the test-post sequences only, so compare within
a column)"""),
            _tab,
        ]
    )
    return


if __name__ == "__main__":
    app.run()
