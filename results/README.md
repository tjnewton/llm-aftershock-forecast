# Results

Everything here is regenerated from committed data by the commands shown; none of it is edited
by hand. "Registered" means preregistered (tag `prereg-v1`) and scored by the frozen code (tag
`scoring-v1`); everything else is exploratory (docs/deviations.md).

| File | Made by | Contents |
|---|---|---|
| `analysis.html` | `uv run marimo export html notebooks/analysis.py -o results/analysis.html` | The frozen analysis notebook, rendered: every registered table (hypotheses H1-H5, calibration, invalid rates, sensitivity analyses) |
| `e1.csv`, `e1a.csv`, `e1r1.csv`, ... | `uv run laf e1 --snapshot 20261021T1027Z --model gpt-oss-20b-<run>` | One adapted model (E1 is registered as descriptive; the others are exploratory) against base gpt-oss, the legacy-ETAS refit and the official forecast, per sequence and pooled, under the registered invalid-answer penalty and valid answers only |
| `replicates.csv` | `uv run laf replicates` | Every adapted run side by side: registered cells vs official and ETAS, and E3 post-cutoff cells (M>=5 and M>=4) |
| `e3_dqs_main.csv` | `uv run laf e3 --snapshot 20261021T2300Z` | E3 (39 more sequences): every forecaster minus the official forecast, per sequence and pooled, by role (`test-post` = after the Claude cutoff, `test-pre` = before) and scoring (`penalty`, `valid-only`, `m4 valid-only`) |
| `e3_dqs_extensions.csv` | same | The adapted models on E3, scored apart from the registered forecasters' penalty pool |
| `e3_invalid.csv`, `e3_coverage.csv` | same | Invalid-answer shares and central-interval coverage on E3 |
| `combined_<snapshot>.csv` | `uv run laf combined --snapshot <snapshot> [--runs runs/e3]` | Equal-weight average of each Claude model's quantiles and the official ones, minus the official forecast |
| `e2_literature.csv` | `uv run laf literature --snapshot 20261021T1027Z` | Papers about each registered mainshock, counted before each model's cutoff and before its issue times |
| `etas_recal_fit.json` | `uv run laf outcome-training` | Best global rate and spread transform of the ETAS refit on historical outcomes (the identity) |
| `live-panama-1_provisional.csv` | `uv run laf live-score --snapshot <refetch> --name live-panama-1 --version <update_ms>` | Provisional scores of the live Panama forecasts whose windows have closed |

Columns in the score tables: `dQS` is the mean difference in log-scale quantile score (lower is
better, so a negative value favours the first forecaster), `lo` and `hi` its 95% moving-block
bootstrap interval, `cells` the number of scored cells.
