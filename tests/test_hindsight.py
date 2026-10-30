from pathlib import Path

import numpy as np

from laf import analysis as A
from laf import hindsight as H

P = Path("data/processed/20261021T1027Z")


def _m4(df):
    big = df[df["mag"] >= 3.95]
    return set(zip(big["issue_id"], big["id"], strict=True))


def test_hindsight_catalogs_use_the_issue_selection():
    t = A.load_tables(P)
    hc = H.hindsight_catalogs(t)
    its = t["issue_times"].set_index("issue_id")
    assert set(hc["issue_id"]) <= set(its.index)
    assert (hc["time_ms"].to_numpy() < its.loc[hc["issue_id"], "issue_ms"].to_numpy()).all()
    # nearly every event available at the issue time still exists today (deletions and merges
    # are rare); today's catalog has more, because ComCat backfills sequences for months
    a, h = _m4(t["issue_catalogs"]), _m4(hc)
    assert len(a & h) / len(a) > 0.95 and len(h) >= len(a)


def test_same_catalog_gives_zero_difference(monkeypatch):
    t, items = A.load_tables(P), A.load_items(P)
    monkeypatch.setattr(H, "hindsight_catalogs", lambda tables: tables["issue_catalogs"])
    df = H.compare(t, items)
    base = df[df["forecaster"].isin(["naive", "rj_mle"])]
    assert len(base) > 0 and np.allclose(base[["d_ls5", "d_qs5"]].to_numpy(), 0.0)
    s = H.summary(df, b=50)
    assert set(s["forecaster"]) == {"naive", "rj_mle", "etas"}
