import json
from pathlib import Path

from laf import analysis as A
from laf.schemas import QKEYS

P = Path("data/processed/20261021T1027Z")
ITEM = "us6000tkt2@3d"


def _direct_text():
    w = {
        "m5_count_quantiles": dict(zip(QKEYS, (0, 0, 0, 1, 1, 2, 3, 4, 5), strict=True)),
        "m4_count_quantiles": dict(zip(QKEYS, (1, 2, 3, 4, 6, 9, 12, 15, 18), strict=True)),
        "p_m6_at_least_one": 0.05,
    }
    return json.dumps({"day": w, "week": w, "month": w, "notes": "Fake."})


def test_samples_are_scored_and_invalid_ones_get_the_worst_score_in_the_cell(tmp_path):
    run = tmp_path / "core-fake"
    run.mkdir()
    meta = {
        "item_id": ITEM,
        "info": "I1",
        "paraphrase": "p1",
        "sample": 0,
        "block": "core",
        "model": "claude-haiku-5-5",
        "effort": "high",
    }
    reqs = [
        {"custom_id": "a", "arm": "direct", **meta},
        {"custom_id": "b", "arm": "params", **meta},
        {"custom_id": "c", "arm": "direct", **meta},
    ]
    res = [
        {
            "custom_id": "a",
            "result": "succeeded",
            "stop_reason": "end_turn",
            "text": _direct_text(),
        },
        {"custom_id": "b", "result": "succeeded", "stop_reason": "refusal", "text": None},
        {"custom_id": "c", "result": "errored"},
    ]
    (run / "requests.jsonl").write_text("".join(json.dumps(r) + "\n" for r in reqs), "utf-8")
    (run / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in res), "utf-8")
    tables, items = A.load_tables(P), A.load_items(P)
    c = A.cells(tables)
    c = c[c["issue_id"] == ITEM]
    df = A.score_all(c, A.baselines(tables, items, c), A.llm_samples([run], items))
    assert set(df["window"]) == {"1 Day", "1 Week", "1 Month"}
    for _, g in df.groupby("window"):
        worst = g.loc[g["status"] == "ok", "log_qs"].max()
        assert (g.loc[g["status"] == "refusal", "log_qs"] == worst).all()
        assert g.loc[g["status"] == "transport_error", "log_qs_valid_only"].isna().all()
        assert {"official", "etas", "rj_mle", "generic_rj", "naive"} <= set(g["forecaster"])
