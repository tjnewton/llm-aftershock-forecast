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
