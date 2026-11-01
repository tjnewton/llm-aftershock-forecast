import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from laf import prospective as P
from laf.cli import snapshot_ms
from laf.registry import load_sequences

PANAMA = next(s for s in load_sequences(Path("config/sequences.toml")) if s.id == "us6000u18k")
SNAP = "20261021T1027Z"
NOW = snapshot_ms(SNAP) - 3_600_000


@pytest.fixture(scope="module")
def built():
    return P.issue(Path("data"), SNAP, PANAMA, NOW)


def test_items_use_the_v2_catalog_and_strict_windows_open_after_the_lead(built):
    tables, items, _ = built
    assert [i.item_id for i in items] == ["us6000u18k@live-matched", "us6000u18k@live-strict"]
    strict = items[1]
    assert min(w.start_ms for w in strict.windows) >= NOW + P.STRICT_LEAD_MS
    assert all(r.mag >= P.FLOOR - 1e-6 for i in items for r in i.catalog)
    assert all(r.t_days * 86_400_000 + i.mainshock.origin_ms < i.issue_ms
               for i in items for r in i.catalog)  # fmt: skip
    assert "oaf_mc" in tables["issue_times"].columns


def test_answers_are_sealed_before_and_apart_from_the_baselines(built, tmp_path):
    _, items, _ = built
    matched_start = min(w.start_ms for w in items[0].windows)
    rec = P.seal_answers(tmp_path / "a", items, [{"x": 1}], clock=lambda: matched_start / 1000)
    assert rec["items"]["us6000u18k@live-matched"]["on_time"] is False  # sealed at the start
    assert rec["items"]["us6000u18k@live-strict"]["on_time"] is True
    saved = json.loads((tmp_path / "a/answers.seal.json").read_text())
    assert saved["record_sha256"] == rec["record_sha256"]
    assert set(rec["manifest"]) == {"items.jsonl", "calls.jsonl"}
    base = P.seal_baselines(tmp_path / "a", [{"y": 2}], clock=lambda: 0)
    assert set(base["manifest"]) == {"baselines.jsonl"}
    rec2 = P.seal_answers(tmp_path / "b", items, [{"x": 1}], clock=lambda: 0)
    assert rec2["record_sha256"] == rec["record_sha256"]  # content, not time, is hashed
    with pytest.raises(FileExistsError, match="already sealed"):
        P.seal_answers(tmp_path / "a", items, [], clock=lambda: 0)


def test_only_scheduled_versions_are_forecast(built):
    tables, _, _ = built
    ov = tables["oaf_versions"]
    valid = ov[ov["valid"] & ~ov["duplicate"].fillna(False).astype(bool)].sort_values("creation_ms")
    first = int(valid["update_ms"].iloc[0])
    slot = P.scheduled_slot(tables, first)
    assert slot is not None and slot.startswith("first")
    picked = [P.scheduled_slot(tables, int(u)) for u in valid["update_ms"]]
    assert 1 <= sum(x is not None for x in picked) <= 6  # first plus at most five targets
    assert P.scheduled_slot(tables, -1) is None


def test_aftershock_check_looks_backward_only():
    import json as _json

    origin = 1_790_000_000_000

    def feed(*events):
        feats = [
            {
                "properties": {"mag": m, "time": t, "types": ty},
                "geometry": {"coordinates": [lon, lat, 10.0]},
            }
            for m, t, ty, lat, lon in events
        ]
        return lambda url: _json.dumps({"features": feats}).encode()  # fmt: skip

    near = (6.5, origin - 30 * 86_400_000, ",origin,", 10.05, 20.0)  # larger, earlier, inside
    assert P.is_aftershock(10.0, 20.0, origin, 5.2, get=feed(near))
    later = (6.5, origin + 86_400_000, ",origin,", 10.05, 20.0)  # a later event never counts
    assert not P.is_aftershock(10.0, 20.0, origin, 5.2, get=feed(later))
    small = (5.6, origin - 86_400_000, ",origin,", 10.05, 20.0)  # not in the context set
    assert not P.is_aftershock(10.0, 20.0, origin, 5.2, get=feed(small))
    oaf = (5.6, origin - 86_400_000, ",origin,oaf,", 10.05, 20.0)  # an OAF event is
    assert P.is_aftershock(10.0, 20.0, origin, 5.2, get=feed(oaf))
    far = (6.5, origin - 86_400_000, ",origin,", 15.0, 20.0)  # outside its circle
    assert not P.is_aftershock(10.0, 20.0, origin, 5.2, get=feed(far))


def test_a_repeated_issue_fails_before_any_paid_call(tmp_path, monkeypatch):
    monkeypatch.setattr(P, "model_calls", lambda *a, **k: pytest.fail("paid call"))
    tables, items, update_ms = P.issue(Path("data"), SNAP, PANAMA, NOW)
    monkeypatch.setattr(P, "issue", lambda *a: (tables, items, update_ms))
    monkeypatch.setattr(P, "scheduled_slot", lambda t, u: "7d")
    (tmp_path / PANAMA.id / str(update_ms)).mkdir(parents=True)  # sealed (or running) before
    with pytest.raises(FileExistsError):
        P.run_issue(object(), Path("data"), SNAP, PANAMA, tmp_path)


def test_an_unscheduled_version_is_skipped_without_spending(tmp_path, monkeypatch):
    monkeypatch.setattr(P, "model_calls", lambda *a, **k: pytest.fail("paid call"))
    tables, items, update_ms = P.issue(Path("data"), SNAP, PANAMA, NOW)
    monkeypatch.setattr(P, "issue", lambda *a: (tables, items, update_ms))
    monkeypatch.setattr(P, "scheduled_slot", lambda t, u: None)
    rec = P.run_issue(object(), Path("data"), SNAP, PANAMA, tmp_path)
    assert rec["skipped"].startswith("not a scheduled version") and not any(tmp_path.iterdir())


def test_model_calls_use_the_study_settings_after_the_budget_check(built, monkeypatch):
    _, items, _ = built
    seen = []

    def create(**params):
        seen.append(params)
        usage = SimpleNamespace(model_dump=lambda: {"input_tokens": 10, "output_tokens": 10})
        return SimpleNamespace(id="m", model=params["model"], stop_reason="end_turn",
                               stop_details=None, usage=usage,
                               content=[SimpleNamespace(type="text", text="{}")])  # fmt: skip

    checked = []
    monkeypatch.setattr(P, "check_budget", lambda usd: checked.append(usd))

    class Stream:
        def __init__(self, **params):
            self.msg = create(**params)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get_final_message(self):
            return self.msg

    client = SimpleNamespace(messages=SimpleNamespace(stream=Stream), base_url="x")
    calls = P.model_calls(client, items)
    assert checked and checked[0] == pytest.approx(P.bound_usd(items))
    assert len(calls) == len(items) * len(P.LIVE_MODELS) * P.K
    assert {p["output_config"]["effort"] for p in seen} == {"high"}  # Opus 5.5 as registered
    assert all("thinking" not in p for p in seen)
    assert {p["max_tokens"] for p in seen} == {32_000}  # streamed, as long as batch answers
    assert "magnitude 3.0 or larger" in seen[0]["messages"][0]["content"]  # v2A asks for M3


def test_qualification_rule():
    assert P.qualifies(5.0, "us") == "primary"
    assert P.qualifies(4.6, "nc") == "secondary"
    assert P.qualifies(4.6, "us") is None
    assert P.qualifies(3.9, "ci") is None


def test_paid_runs_must_write_where_the_spend_ledger_looks(tmp_path):
    from laf.cli import main

    with pytest.raises(SystemExit, match="spend ledger"):
        main(["prospective", "--snapshot", SNAP, "--sequence", PANAMA.id,
              "--out", str(tmp_path / "elsewhere")])  # fmt: skip
