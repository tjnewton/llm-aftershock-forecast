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
    SETS = {"Registered": "Preregistered", "E3": "39 more sequences (exploratory)"}
    return COLOR, SETS, alt, contextlib, mo, pd


@app.cell
def _(SETS, contextlib, mo, pd):
    import io
    import urllib.request

    def _read(path):
        # In the browser the CSV arrives over HTTP already decompressed while the response still
        # says gzip, which pandas would decompress again: read the bytes, then parse them.
        if str(path).startswith("http"):
            with urllib.request.urlopen(str(path)) as r:
                return pd.read_csv(io.BytesIO(r.read()))
        return pd.read_csv(str(path))

    _base = mo.notebook_location() / "public"
    _frames = [_read(_base / "explorer.csv").assign(set=SETS["Registered"])]
    with contextlib.suppress(Exception):  # the exploratory table is optional
        _frames.append(_read(_base / "explorer_e3.csv").assign(set=SETS["E3"]))
    all_data = pd.concat(_frames, ignore_index=True)
    summary = _read(_base / "summary.csv")
    mo.md(
        """# Do AI chatbots forecast aftershocks as well as the USGS?

After a large earthquake, smaller **aftershocks** follow for weeks, and people need to know how
many to expect. The US Geological Survey (USGS) publishes official aftershock forecasts for
that. I gave large language models exactly the information USGS had when it issued each
forecast (the main earthquake and the list of quakes recorded so far) and asked them the same
question: how many aftershocks of magnitude 5 or larger in the next day, week and month? I
then compared both with what actually happened, on earthquakes that occurred after the models
were trained, so they could not have memorized the answers.

**What I found**

- **Claude Opus 5.5 sits in the top tier with the official USGS forecast** and its statistical
  model (ETAS), on the preregistered test and again on 18 more recent sequences. Sonnet 5.5 tied
  on the first and was very slightly worse on the second. With only two earthquakes, though,
  the test can't tell these top forecasters apart: even a simple rule of thumb (take the
  aftershock count so far and extend it with the usual decay) scores about as well as USGS
  there. More earthquakes will sharpen that, and the benchmark grows with every new forecast.
- **The benchmark does separate weaker forecasters**: Haiku 5.5 and the small open models
  (gpt-oss-20b, Olmo 3.1 32B) were clearly worse, and the open models often gave unusable
  answers; fine-tuning one of them fixed the format but not the skill.
- **Seeing the list of recent quakes matters**: without it, forecasts were worse.
- **No sign of memorization**: the models did no better on earthquakes from before their training
  cutoff.

The methods, preregistration and full results are in the project repository:
https://github.com/tjnewton/llm-aftershock-forecast (see `docs/writeup.md`)."""
    )
    return all_data, summary


@app.cell
def _(mo):
    mo.accordion(
        {
            "How to read the chart": mo.md(
                """Each panel is one forecaster. Moving left to right, each point in time is a
moment when a forecast was made (days after the main earthquake). The **shaded bands** are the
forecaster's range for the number of magnitude-5+ aftershocks in the coming window (light: 90%
range, dark: middle 50%), the **line** is its most likely number, and the **black dots** are
the number that actually happened. A good forecast has the dots inside the bands, close to the
line, with bands no wider than needed. Hover over a dot for the numbers."""
            ),
            "Glossary": mo.md(
                """- **Mainshock / aftershocks / sequence**: the large earthquake, the smaller ones
that follow it, and the two together.
- **Magnitude (M)**: earthquake size on a logarithmic scale; each step up is about 30 times more
energy, and roughly 10 times rarer. **M>=5** means magnitude 5 or larger, strong enough to damage
buildings near the epicentre.
- **Issue time / window**: when a forecast is made, and the period it covers (the next day, week
or month).
- **USGS official**: the published US Geological Survey operational aftershock forecast.
- **Legacy-ETAS refit, RJ-MLE refit, Generic RJ, Naive**: standard statistical forecasting methods
(ETAS and Reasenberg-Jones models), and a simple baseline that extends the number of M5+
aftershocks so far with the usual decay over time.
- **catalog / no catalog**: whether the model saw the list of earthquakes recorded so far.
- **direct**: the model answered with the numbers; **params**: it gave model parameters instead.
- **Score (log-scale quantile score)**: how far the forecast range is from what happened, on a
logarithmic scale; lower is better, 0 is perfect.
- **Difference vs USGS**: a forecaster's score minus the USGS score on the same windows; negative
means better than USGS.
- **Preregistered**: the hypotheses and analysis were fixed and published before any forecast
was made. **Exploratory**: added afterwards, reported as such.
- **Training cutoff / contamination**: the date after which a model saw no training data; events
after it cannot have been memorized.
- **Adapted (E1, E1a)**: gpt-oss-20b fine-tuned on forecasts for past earthquakes."""
            ),
        }
    )
    return


@app.cell
def _(SETS, all_data, mo):
    dataset = mo.ui.dropdown(
        [x for x in SETS.values() if x in set(all_data["set"])],
        value=SETS["Registered"],
        label="Earthquake set",
    )
    dataset  # noqa: B018 (marimo displays the last expression)
    return (dataset,)


@app.cell
def _(dataset, mo, summary):
    _s = summary[summary["set"] == dataset.value].sort_values("dQS")

    def _reading(r):
        if r["hi"] < 0:
            return "better than USGS"
        if r["lo"] > 0:
            return "worse than USGS"
        return "not distinguishable from USGS"

    _tab = _s.assign(
        **{
            "Difference vs USGS": _s["dQS"].round(3),
            "95% interval": _s.apply(lambda r: f"{r['lo']:.3f} to {r['hi']:.3f}", axis=1),
            "Reading": _s.apply(_reading, axis=1),
            "Windows scored": _s["cells"].astype(int),
        }
    )[["forecaster", "Difference vs USGS", "95% interval", "Reading", "Windows scored"]]
    _which = (
        "the two preregistered sequences with a USGS forecast (Colombia and Flores Sea)"
        if dataset.value.startswith("Pre")
        else "18 sequences after the Claude training cutoff (exploratory)"
    )
    mo.vstack(
        [
            mo.md(f"""## Who forecasts as well as USGS?
Average score difference from the official USGS forecast on {_which}; negative is better than
USGS, and the interval shows the uncertainty (block bootstrap)."""),
            mo.ui.table(
                _tab.rename(columns={"forecaster": "Forecaster"}).reset_index(drop=True),
                selection=None,
                show_column_summaries=False,
                show_data_types=False,
                show_download=False,
                show_search=False,
                page_size=20,
            ),
        ]
    )
    return


@app.cell
def _(all_data, dataset):
    data = all_data[all_data["set"] == dataset.value]
    return (data,)


@app.cell
def _(data, mo):
    seqs = sorted(data["seq_label"].unique())
    labels = sorted(data["label"].unique())
    _start = next((s for s in seqs if "Flores" in s), seqs[0])
    sequence = mo.ui.dropdown(seqs, value=_start, label="Earthquake sequence")
    window = mo.ui.dropdown(["1 Day", "1 Week", "1 Month"], value="1 Week", label="Forecast window")
    default = [
        x
        for x in ("USGS official", "Opus 5.5 direct, catalog", "gpt-oss-20b direct, catalog")
        if x in labels
    ]
    chosen = mo.ui.multiselect(
        labels, value=default, label="Forecasters (up to 4)", max_selections=4
    )
    primary_only = mo.ui.checkbox(
        value=False, label="Only windows whose outcome is final (closed 21+ days ago)"
    )
    mo.vstack(
        [
            mo.md("## Forecasts against what happened"),
            mo.hstack([sequence, window, chosen, primary_only], justify="start", wrap=True),
        ]
    )
    return chosen, primary_only, sequence, window


@app.cell
def _(chosen, data, primary_only, sequence, window):
    view = data[
        (data["seq_label"] == sequence.value)
        & (data["window"] == window.value)
        & data["label"].isin(chosen.value)
    ]
    if primary_only.value:
        view = view[view["primary"]]
    return (view,)


@app.cell
def _(COLOR, alt, chosen, mo, sequence, view, window):
    if view.empty:
        _out = mo.md("No forecasts for this selection.")
    else:
        _domain = list(chosen.value)
        _range = [COLOR.get(x, "#8a8980") for x in _domain]
        _color = alt.Color("label:N", scale=alt.Scale(domain=_domain, range=_range), legend=None)
        _x = alt.X(
            "elapsed_days:Q",
            scale=alt.Scale(type="log", nice=False),
            axis=alt.Axis(values=[0.3, 1, 3, 7, 14, 28], grid=False),
            title=["days after the main earthquake", "when the forecast was made"],
        )
        _tip = [
            alt.Tooltip("target:N", title="forecast made"),
            alt.Tooltip("q050:Q", title="low end (5%)"),
            alt.Tooltip("q500:Q", title="most likely"),
            alt.Tooltip("q950:Q", title="high end (95%)"),
            alt.Tooltip("y5:Q", title="actually happened"),
            alt.Tooltip("log_qs:Q", title="score (lower is better)", format=".3f"),
        ]
        _base = alt.Chart(view).encode(x=_x)
        _outer = _base.mark_area(opacity=0.18).encode(
            y=alt.Y("q050:Q", title="number of M5+ aftershocks in the window"),
            y2="q950:Q",
            color=_color,
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
        _out = mo.vstack(
            [
                mo.ui.altair_chart(_chart),
                mo.md(
                    f"""*{sequence.value}, {window.value.lower()} windows: shaded bands are each
forecaster's range (light 90%, dark 50%), the line its most likely number, black dots what
actually happened.*"""
                ),
            ]
        )
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
    mo.vstack(
        [
            mo.md("**Score at each forecast time** (lower is better; 0 would be perfect)"),
            mo.ui.table(
                _tab.reset_index() if not view.empty else _tab,
                selection=None,
                show_column_summaries=False,
                show_data_types=False,
                show_download=False,
                show_search=False,
            ),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
