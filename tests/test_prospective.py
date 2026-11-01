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
    valid = ov[ov["valid"] & ~ov["duplicate"].fillna(False).astype(bool)].sort_values(
        "info_cutoff_ms"
    )
    first = int(valid["update_ms"].iloc[0])
    slot = P.scheduled_slot(tables, first)
    assert slot is not None and slot.startswith("first")
    picked = [P.scheduled_slot(tables, int(u)) for u in valid["update_ms"]]
    assert 1 <= sum(x is not None for x in picked) <= 6  # first plus at most five targets
    assert P.scheduled_slot(tables, -1) is None
    # the same versions as the issue times registered for Panama in the snapshot (ADR 0004)
    import pandas as pd

    its = pd.read_parquet(f"data/processed/{SNAP}/issue_times.parquet")
    retro = set(its.loc[(its["sequence_id"] == PANAMA.id) & (its["source"] == "oaf"), "issue_ms"])
    live = {int(c) for c, x in zip(valid["info_cutoff_ms"], picked, strict=True) if x is not None}
    assert live == {int(x) for x in retro}


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


def _clients(seen):
    """SDK stubs: a Claude stream and an OpenAI Responses call that record their params."""

    def message(**params):
        seen.append(params)
        usage = SimpleNamespace(model_dump=lambda: {"input_tokens": 10, "output_tokens": 10})
        return SimpleNamespace(id="m", model=params["model"], stop_reason="end_turn",
                               stop_details=None, usage=usage,
                               content=[SimpleNamespace(type="text", text="{}")])  # fmt: skip

    class Stream:
        def __init__(self, **params):
            self.msg = message(**params)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get_final_message(self):
            return self.msg

    def respond(**params):
        seen.append(params)
        text = {"type": "output_text", "text": "{}"}
        body = {"id": "r", "model": params["model"], "status": "completed",
                "usage": {"input_tokens": 10, "output_tokens": 10},
                "output": [{"type": "message", "content": [text]}]}  # fmt: skip
        return SimpleNamespace(model_dump=lambda: body)

    return {
        "claude": SimpleNamespace(messages=SimpleNamespace(stream=Stream), base_url="x"),
        "openai": SimpleNamespace(responses=SimpleNamespace(create=respond), base_url="y"),
    }


def test_model_calls_use_the_study_settings(built):
    _, items, _ = built
    seen: list[dict] = []
    calls = P.model_calls(_clients(seen), items, {"claude": 1e9, "openai": 1e9})
    assert len(calls) == len(items) * len(P.LIVE_MODELS) * P.K
    assert all(c["error"] is None and c["usage"] for c in calls)
    opus = [p for p in seen if p["model"] == "claude-opus-5-5"]
    sol = [p for p in seen if p["model"] == "gpt-6.1-sol"]
    assert {p["output_config"]["effort"] for p in opus} == {"high"}  # Opus 5.5 as registered
    assert all("thinking" not in p for p in opus)
    assert {p["max_tokens"] for p in opus} == {32_000}  # streamed, as long as batch answers
    assert "magnitude 3.0 or larger" in opus[0]["messages"][0]["content"]  # v2A asks for M3
    assert {p["reasoning"]["effort"] for p in sol} == {"high"}  # ADR 0014 decision 7
    assert {p["max_output_tokens"] for p in sol} == {32_000}
    assert all(not ({"temperature", "top_p", "tools"} & set(p)) for p in seen)


def test_the_budget_priority_drops_strict_then_the_second_model(built):
    _, items, _ = built
    matched = next(i for i in items if i.item_id.endswith("@live-matched"))
    opus_matched = P.K * P.call_bound_usd(matched, "claude-opus-5-5")
    jobs, missed = P.plan_calls(items, {"claude": opus_matched * 1.5, "openai": 0.0})
    assert {(j[0], j[1]) for j in jobs} == {(matched.item_id, "claude-opus-5-5")}
    assert len(missed) == 3 * P.K and {m["missed"] for m in missed} == {"budget"}
    assert {m["model_requested"] for m in missed} == {"claude-opus-5-5", "gpt-6.1-sol"}


def test_the_live_budget_is_the_reserve_minus_the_published_live_spend(tmp_path, monkeypatch):
    usage = {"input_tokens": 1_000_000, "output_tokens": 0}
    calls = [{"started_utc": "2026-12-03T00:00:00+00:00", "model_requested": m, "text": "secret",
              "usage": usage} for m in ("claude-opus-5-5", "gpt-6.1-sol")]  # fmt: skip
    calls.append({"model_requested": "x", "error": "e"})  # a failed call costs nothing
    rows = P.spend_rows(calls)
    assert len(rows) == 2 and all("text" not in r for r in rows)
    (tmp_path / "us1/1").mkdir(parents=True)
    (tmp_path / "us1/1/spend.jsonl").write_text(P._jsonl(rows))
    monkeypatch.setenv("LAF_CLAUDE_LIVE_RESERVE_USD", "20")
    monkeypatch.setenv("LAF_OPENAI_LIVE_RESERVE_USD", "10")
    left = P.live_budget(tmp_path, month="2026-12")
    assert left["openai"] == pytest.approx(10 - 2.0)  # $2 per MTok input
    assert left["claude"] == pytest.approx(20 - P._cost("claude-opus-5-5", calls[0]["usage"]))
    assert P.live_budget(tmp_path, month="2027-01") == {"claude": 20.0, "openai": 10.0}
    monkeypatch.setenv("LAF_OPENAI_LIVE_RESERVE_USD", "")
    monkeypatch.setattr(P, "env_value", lambda var: "")
    with pytest.raises(SystemExit, match="LIVE_RESERVE"):
        P.live_budget(tmp_path)


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


def test_the_answers_seal_is_published_before_the_baselines_run(tmp_path, monkeypatch):
    tables, items, update_ms = P.issue(Path("data"), SNAP, PANAMA, NOW)
    monkeypatch.setattr(P, "issue", lambda *a: (tables, items, update_ms))
    monkeypatch.setattr(P, "scheduled_slot", lambda t, u: "first")
    order = []
    monkeypatch.setattr(P, "baseline_forecasts", lambda *a: order.append("baselines") or [])

    def publish(rel, seal, extra=()):
        order.append(seal.name)
        if seal.name.startswith("baselines"):
            raise OSError("push rejected")
        return {"commit": "c", "rel": rel, "extra": [f.name for f in extra]}

    rec = P.run_issue(None, Path("data"), SNAP, PANAMA, tmp_path, dry_run=True, publish=publish)
    assert order == ["answers.seal.json", "baselines", "baselines.seal.json"]
    assert rec["published"]["answers"] == {
        "commit": "c", "rel": f"{PANAMA.id}/{update_ms}", "extra": ["spend.jsonl"]}  # fmt: skip
    assert "OSError" in rec["published"]["baselines"]["error"]  # recorded, the issue completes
    assert (tmp_path / PANAMA.id / str(update_ms) / "baselines.seal.json").exists()
