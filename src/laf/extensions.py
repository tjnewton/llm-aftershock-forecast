"""E1 evaluation (prereg section 11), descriptive only: the adapted model scored by the frozen
analysis code. Its run sits in runs/extensions/, outside the primary analysis; here it joins the
invalid-sample penalty pool for this table only."""

from pathlib import Path

import numpy as np
import pandas as pd

from laf import analysis as A

RUN = Path("runs/extensions/e1-gpt-oss-20b-e1")
E1 = "laf/gpt-oss-20b-e1|direct|I1|medium"
BASE = "openai/gpt-oss-20b|direct|I1|medium"


def e1_table(
    proc: Path, runs: list[Path], seed: int = 20261021, b: int = 10_000
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """dQS(adapted, base) and dQS(adapted, legacy-ETAS refit) on primary cells, dQS(adapted,
    official) on OAF cells, under the registered penalty and valid-only; and invalid rates."""
    tables, items = A.load_tables(proc), A.load_items(proc)
    cells = A.cells(tables)
    cells = cells[cells["role"] != "dev"].reset_index(drop=True)
    df = A.score_all(cells, A.baselines(tables, items, cells), A.llm_samples([*runs, RUN], items))
    out = []
    for scoring, col in (("penalty", "log_qs"), ("valid-only", "log_qs_valid_only")):
        s = A.answer_scores(df, col).rename(columns={col: "log_qs"})
        prim = s["primary"]
        oaf = prim & s["oaf_cell"] & s["role"].eq("test-post")
        for ref, mask in ((BASE, prim), ("etas", prim), ("official", oaf)):
            t = A.ci_table(A.dqs(s, E1, ref, mask), np.random.default_rng(seed), b)
            out.append(t.assign(scoring=scoring, reference=ref))
    inv = A.invalid_table(df)
    return pd.concat(out), inv[inv.index.get_level_values("model").str.contains("gpt-oss")]


E3_RUNS = Path("runs/e3")
REFERENCES = ("etas", "rj_mle", "generic_rj", "naive")


def e3_tables(proc: Path, seed: int = 20261021, b: int = 10_000) -> dict[str, pd.DataFrame]:
    """E3 (ADR 0012), exploratory: every forecaster vs the official forecast on primary cells,
    per role (test-post, test-pre), for M>=5 under the registered penalty and valid-only, and
    the exploratory M>=4 score (valid samples); invalid rates and coverage. Runs under
    runs/e3/*/ form the penalty pool; adapted models (runs/e3/extensions/) are scored apart."""
    tables, items = A.load_tables(proc), A.load_items(proc)
    cells = A.cells(tables)
    cells = cells[cells["role"] != "dev"].reset_index(drop=True)
    base = A.baselines(tables, items, cells)
    runs = sorted(p.parent for p in E3_RUNS.glob("*/results.jsonl"))
    ext = sorted(p.parent for p in (E3_RUNS / "extensions").glob("*/results.jsonl"))
    out = {}
    for tag, rs in (("main", runs), ("extensions", runs + ext)):
        df = A.score_all(cells, base, A.llm_samples(rs, items))
        llm = sorted(df.loc[df["arm"] != "baseline", "forecaster"].unique())
        if tag == "extensions":
            llm = [f for f in llm if f.startswith("laf/")]
        rows = []
        for scoring, col in (
            ("penalty", "log_qs"),
            ("valid-only", "log_qs_valid_only"),
            ("m4 valid-only", "log_qs_m4"),
        ):
            s = A.answer_scores(df, col).rename(columns={col: "log_qs"})
            for role in ("test-post", "test-pre"):
                mask = s["primary"] & s["role"].eq(role)
                for f in [*llm, *(REFERENCES if tag == "main" else ())]:
                    d = A.dqs(s, f, "official", mask)
                    if d.empty:
                        continue
                    t = A.ci_table(d, np.random.default_rng(seed), b)
                    rows.append(t.assign(forecaster=f, role=role, scoring=scoring))
        out[f"e3_dqs_{tag}"] = pd.concat(rows) if rows else pd.DataFrame()
        if tag == "extensions":
            from laf.figures import explorer_table

            out["explorer_e3"] = explorer_table(df)
        if tag == "main":
            out["e3_invalid"] = A.invalid_table(df).reset_index()
            out["e3_coverage"] = A.coverage_table(df, df["primary"]).reset_index()
    return out


CLAUDE = ("claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5")


def combined_table(
    proc: Path, runs: list[Path], forecasters: list[str], seed: int = 20261021, b: int = 10_000
) -> pd.DataFrame:
    """Exploratory, rule fixed before scoring: per cell, the equal-weight average of a model's
    quantile-averaged valid samples and the official quantiles, scored like one forecast;
    dQS(combined, official) on primary cells with an official forecast, per role."""
    from laf.scoring import quantile_score

    tables, items = A.load_tables(proc), A.load_items(proc)
    cells = A.cells(tables)
    cells = cells[cells["role"] != "dev"].reset_index(drop=True)
    base = A.baselines(tables, items, cells)
    df = A.score_all(cells, base, A.llm_samples(runs, items))
    meta = {(c["issue_id"], c["window"]): c for c in cells.to_dict("records")}
    official = df[df["forecaster"] == "official"]
    off = {(r["issue_id"], r["window"]): r["log_qs"] for r in official.to_dict("records")}
    rows = []
    for f in forecasters:
        ok = df[(df["forecaster"] == f) & df["status"].eq("ok") & df["m5"].notna()]
        for r in (
            ok.groupby(["issue_id", "window"])["m5"].apply(list).reset_index().to_dict("records")
        ):
            key = (r["issue_id"], r["window"])
            c = meta.get(key)
            if key not in off or ("official", *key) not in base or c is None or not c["primary"]:
                continue
            q = (np.mean(np.vstack(r["m5"]), axis=0) + np.array(base[("official", *key)].m5)) / 2
            d = quantile_score(q.tolist(), int(c["y5"])) - off[key]
            rows.append({"f": f, "role": c["role"], "name": c["name"], "issue_id": key[0],
                         "elapsed_days": c["elapsed_days"], "d": d})  # fmt: skip
    d = pd.DataFrame(rows)
    out = []
    for f in forecasters:
        for role in ("test-post", "test-pre"):
            g = d[(d["f"] == f) & (d["role"] == role)] if len(d) else d
            if len(g):
                t = A.ci_table(g, np.random.default_rng(seed), b)
                out.append(t.assign(forecaster=f"{f} + official", role=role))
    return pd.concat(out) if out else pd.DataFrame()
