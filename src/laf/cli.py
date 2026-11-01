"""Command line: ``laf fetch | tables | verify``."""

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from laf.registry import load_sequences

SNAPSHOT_FORMAT = "%Y%m%dT%H%MZ"


def snapshot_ms(snapshot: str) -> int:
    """The snapshot id is the catalog end time, so resuming a snapshot repeats its queries."""
    return int(datetime.strptime(snapshot, SNAPSHOT_FORMAT).replace(tzinfo=UTC).timestamp() * 1000)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="laf")
    p.add_argument("--data-dir", type=Path, default=Path("data"))
    p.add_argument("--config", type=Path, default=Path("config/sequences.toml"))
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="download a new raw snapshot (idempotent per snapshot)")
    f.add_argument("--snapshot", help="resume an existing snapshot id, e.g. 20261019T1900Z")
    f.add_argument("--only", nargs="*", help="sequence ids (default: all in config)")
    ao = sub.add_parser("asof", help="fetch ComCat product histories for as-of catalogs")
    ao.add_argument("--snapshot", required=True)
    ao.add_argument("--only", nargs="*", help="sequence ids (default: all in config)")
    ao.add_argument("--workers", type=int, default=3)
    ao.add_argument("--deleted", action="store_true", help="also sweep deleted events")
    ao.add_argument("--min-mag", type=float, default=-9.0, help="current magnitude floor")
    ao.add_argument("--max-days", type=float, default=90.0, help="days after the mainshock")
    t = sub.add_parser("tables", help="build data/processed/<snapshot>/*.parquet")
    t.add_argument("--snapshot", required=True)
    sub.add_parser("verify", help="check manifest hashes and re-validate every OAF file")
    it = sub.add_parser("items", help="write data/processed/<snapshot>/items.jsonl")
    it.add_argument("--snapshot", required=True)
    sub.add_parser("prompts-hash", help="write prompts/HASHES.json (SHA-256 per template)")
    sub.add_parser("spend", help="recorded API spend per UTC month and in total (runs/**)")
    bs = sub.add_parser(
        "batch-status", help="processing status and counts of a batch id (no results)"
    )
    bs.add_argument("batch_id")
    rn = sub.add_parser("run", help="SPENDS MONEY: submit one design block as a Message Batch")
    rn.add_argument("--snapshot", required=True)
    rn.add_argument(
        "--block",
        required=True,
        choices=("core", "i0", "sonnet-low", "e3", "e3pre", "e3i0", "d2", "d2-medium", "d2-46"),
    )
    rn.add_argument("--model", required=True)
    rn.add_argument("--name", help="run name under runs/ (default <block>-<model>)")
    rn.add_argument("--dry-run", action="store_true", help="count requests and estimate cost")
    st = sub.add_parser("status", help="batch status and counts of a run (no results)")
    st.add_argument("name")
    co = sub.add_parser("collect", help="write runs/<name>/results.jsonl (needs tag scoring-v1)")
    co.add_argument("name")
    et = sub.add_parser("etas", help="legacy-ETAS refit forecasts (ADR 0010); --validate for V2")
    et.add_argument("--snapshot", required=True)
    et.add_argument("--only", nargs="*", help="issue ids (default: all)")
    et.add_argument("--validate", action="store_true", help="re-simulate official versions")
    et.add_argument("--seed-offset", type=int, default=0, help="add to every per-issue seed")
    et.add_argument("--out", help="output parquet name (default by mode)")
    et.add_argument(
        "--catalog",
        choices=("asof", "hindsight"),
        default="asof",
        help="ComCat as it stood at each issue / version time (default; docs/adr/0011), or today's",
    )
    et.add_argument(
        "--settings",
        choices=("default", "analyst"),
        default="default",
        help="code defaults (registered), or analyst settings inferred from the official products "
        "(config/analyst_settings.toml; a labelled sensitivity variant, ADR 0010 section 4.1)",
    )
    ev = sub.add_parser("etas-validate", help="ETAS validation suite (docs/adr/0010 section 4)")
    ev.add_argument("--snapshot", required=True)
    ev.add_argument("--only", nargs="*", help="sequence ids for v0/v3 (default: all ETAS)")
    ev.add_argument("--parts", nargs="*", default=["v0", "v3", "java", "recovery", "decomp"])
    ev.add_argument("--recovery-n", type=int, default=800, help="sequences per fit time")
    sub.add_parser("smoke", help="SPENDS MONEY (<= $1): one tiny call per Claude model")
    ad = sub.add_parser(
        "adaption", help="E1 on Adaption: upload | recommend | launch (credits) | status"
    )
    ad.add_argument("action", choices=("upload", "recommend", "launch", "status", "download"))
    ad.add_argument("--file", type=Path, default=Path("data/processed/training/e1_train.jsonl"))
    ad.add_argument("--run", default="e1", help="records in runs/<run>-adaption/ (E1: e1)")
    ad.add_argument("--best-from", help="launch with another run's best hyperparameters")
    ad.add_argument("--max-iterations", type=int, help="AutoScientist iterations (default 3)")
    ad.add_argument("--pairs", action="store_true", help="preference pairs (alignment training)")
    tr = sub.add_parser("training-set", help="E1 training set (ComCat requests; prereg sec. 11)")
    tr.add_argument("--start", default="2010-01-01")
    tr.add_argument("--end", default="2025-07-01", help="exclusive end (origin < end)")
    tr.add_argument("--workers", type=int, default=8)
    tr.add_argument("--min-mag", type=float, default=6.5, help="mainshock floor (E1: 6.5)")
    tr.add_argument("--out", default="e1_train.jsonl", help="file in data/processed/training/")
    fg = sub.add_parser("figures", help="figures/*.png and the explorer table (no API calls)")
    fg.add_argument("--snapshot", required=True)
    sub.add_parser("e3-select", help="E3 candidate list -> config/sequences_e3.toml (ComCat)")
    ls_ = sub.add_parser("live-score", help="provisional scores of closed live windows (no API)")
    ls_.add_argument("--snapshot", required=True, help="fresh Panama refetch after the windows")
    ls_.add_argument("--name", required=True, help="live run under runs/, e.g. live-panama-1")
    ls_.add_argument("--version", type=int, required=True, help="matched official update_ms")
    ls_.add_argument("--sequence", default="us6000u18k")
    cb = sub.add_parser("combined", help="exploratory Claude + official average (no API calls)")
    cb.add_argument("--snapshot", required=True)
    cb.add_argument("--runs", type=Path, default=Path("runs"), help="runs/ or runs/e3")
    sub.add_parser("replicates", help="adapted-model replicate summary -> results/replicates.csv")
    d2p = sub.add_parser("d2", help="D2 prompt-robustness tables from runs/d2 (development data)")
    d2p.add_argument("--snapshot", required=True)
    d2p.add_argument("--runs", type=Path, default=Path("runs/d2"))
    d1p = sub.add_parser(
        "d1", help="D1 behavioral probes: build items (free); pilot and run SPEND MONEY"
    )
    d1p.add_argument("action", choices=("build", "pilot", "run", "analyze"))
    d1p.add_argument("--snapshot", required=True)
    d1p.add_argument("--model", choices=("claude-opus-4-6", "claude-sonnet-4-6", "claude-opus-5-5"))
    d1p.add_argument("--dry-run", action="store_true", help="count requests and estimate cost")
    d1p.add_argument(
        "--settings", choices=("grid", "sonnet-low"), help="pilot: a thinking and effort batch"
    )
    lw = sub.add_parser(
        "live-watch", help="dry run of the live detector (ComCat polls; no model calls)"
    )
    lw.add_argument("--out", type=Path, default=Path("runs/live-dryrun"))
    lw.add_argument("--live-data", type=Path, default=Path("data/interim/live-dryrun"))
    lw.add_argument("--polls", type=int, help="stop after this many polls (default: run on)")
    lw.add_argument("--publish", type=Path, help="worktree of live-test (or live): push each seal")
    lw.add_argument(
        "--paid", action="store_true",
        help="SPENDS MONEY: the live models within the live reserve; --publish must be live",
    )  # fmt: skip
    ll = sub.add_parser(
        "live-late", help="share of matched live items that would be late (ADR 0017; no network)"
    )
    ll.add_argument("--snapshot", nargs="+", required=True, help="snapshots with OAF versions")
    ll.add_argument("--log", type=Path, default=Path("runs/live-dryrun/log.jsonl"))
    oa = sub.add_parser(
        "openai", help="OpenAI models (ADR 0014): run SPENDS MONEY on the OpenAI key"
    )
    oa.add_argument("action", choices=("run", "status", "collect"))
    oa.add_argument("name", nargs="?", help="status/collect: run name under runs/")
    oa.add_argument("--snapshot")
    oa.add_argument("--block", choices=("pilot", "d2"), default="d2")
    oa.add_argument(
        "--model", default="gpt-5.1-2025-11-13", choices=("gpt-5.1-2025-11-13", "gpt-6.1-sol")
    )
    oa.add_argument("--effort", nargs="+", choices=("none", "low", "medium", "high"))
    oa.add_argument("--dry-run", action="store_true", help="count requests, estimate cost")
    pp = sub.add_parser(
        "prospective",
        help="SPENDS MONEY: one live issue (ADR 0017): items, forecasts, baselines, sealed record",
    )
    pp.add_argument("--snapshot", required=True, help="snapshot holding the fresh fetch")
    pp.add_argument("--sequence", required=True)
    pp.add_argument("--out", type=Path, default=Path("runs/prospective"))
    pp.add_argument("--dry-run", action="store_true", help="no model calls; time everything else")
    ct = sub.add_parser(
        "confirmatory",
        help="ADR 0018 tests on confirmatory runs; refuses until tag prereg-v2 (ADR 0013)",
    )
    ct.add_argument("--snapshot", required=True)
    ct.add_argument("--runs", type=Path, required=True, help="folder of confirmatory run folders")
    ct.add_argument(
        "--test-a-all", action="store_true",
        help="test A's sensitivity run: gpt-5.1 on all clean candidates (test B stays M>=5)",
    )  # fmt: skip
    cz = sub.add_parser(
        "confirmatory-size",
        help="simulated size of the registered test from development D2 effects (no API)",
    )
    cz.add_argument("--snapshot", required=True)
    cz.add_argument("--runs", type=Path, default=Path("runs/d2"))
    cz.add_argument("--sims", type=int, default=1000)
    cf = sub.add_parser(
        "confirmatory-dryrun",
        help="ADR 0018 tests on development D2 answers (no API; a rehearsal, not a result)",
    )
    cf.add_argument("--snapshot", required=True)
    cf.add_argument("--runs", type=Path, default=Path("runs/d2"))
    pw = sub.add_parser(
        "power", help="power of the confirmatory tests from development runs (ADR 0018)"
    )
    pw.add_argument("--snapshot", required=True)
    pw.add_argument("--runs", type=Path, default=Path("runs/e3"), help="folder of LLM run folders")
    pw.add_argument("--reference", default="official", help="official or naive")
    pw.add_argument("--valid-only", action="store_true", help="sensitivity: drop invalid samples")
    pw.add_argument(
        "--from-d2", action="store_true", help="D2-style runs (v2 prompts; --runs runs/d2)"
    )
    hs = sub.add_parser(
        "hindsight", help="baselines on the as-of vs today's catalog, development cells (ADR 0016)"
    )
    hs.add_argument("--snapshot", required=True)
    cd = sub.add_parser(
        "countdist-check",
        help="log score from 9 quantiles vs full distributions, development cells (ADR 0015)",
    )
    cd.add_argument("--snapshot", required=True)
    sub.add_parser("outcome-training", help="E1b preference pairs and the ETAS recalibration fit")
    e3s = sub.add_parser("e3", help="E3 exploratory tables -> results/e3_*.csv (no API calls)")
    e3s.add_argument("--snapshot", required=True)
    e1 = sub.add_parser("e1", help="E1 adapted-model table (no API calls)")
    e1.add_argument("--snapshot", required=True)
    e1.add_argument(
        "--model", default="gpt-oss-20b-e1", help="adapted model (E1a: gpt-oss-20b-e1a)"
    )
    lt = sub.add_parser("literature", help="E2 literature exposure table (no network)")
    lt.add_argument("--snapshot", required=True)
    pr = sub.add_parser("probe", help="SPENDS MONEY (~$0.3): recall probe (prereg sec. 8)")
    pr.add_argument("--snapshot", required=True)
    lv = sub.add_parser("live", help="SPENDS MONEY (~$1.5): live Panama forecasts (prereg sec. 10)")
    lv.add_argument("--snapshot", required=True, help="snapshot holding the Panama refetch")
    lv.add_argument("--sequence", default="us6000u18k")
    lv.add_argument("--name", default="live-panama-1")
    lv.add_argument("--dry-run", action="store_true", help="build and show the items only")
    pl = sub.add_parser("pilot", help="SPENDS MONEY (<= $3): dev items only, plus count_tokens")
    pl.add_argument("--snapshot", required=True)
    pl.add_argument("--count-only", action="store_true", help="only count_tokens (free)")
    pl.add_argument("--summary", action="store_true", help="summarize a finished pilot (free)")
    a = p.parse_args(argv)

    seqs = load_sequences(a.config)
    if a.cmd == "fetch":
        from laf.usgs import fetch_sequence

        snap = a.snapshot or datetime.now(UTC).strftime(SNAPSHOT_FORMAT)
        now_ms = snapshot_ms(snap)
        for s in seqs:
            if a.only and s.id not in a.only:
                continue
            stored = fetch_sequence(a.data_dir, snap, s.id, s.catalog_min_mag, now_ms=now_ms)
            print(f"{snap} {s.id:<12} {s.name:<30} +{len(stored)} files")
    elif a.cmd == "asof":
        from laf.asof import fetch_histories

        for s in seqs:
            if a.only and s.id not in a.only:
                continue
            n = fetch_histories(
                a.data_dir,
                a.snapshot,
                [s.id],
                workers=a.workers,
                deleted=a.deleted,
                min_mag=a.min_mag,
                max_days=a.max_days,
            )
            print(f"{a.snapshot} {s.id:<12} {s.name:<30} +{n} files", flush=True)
    elif a.cmd == "tables":
        from laf.tables import build_tables, write_tables

        tables = build_tables(a.data_dir, a.snapshot, seqs)
        out = a.data_dir / "processed" / a.snapshot
        write_tables(tables, out)
        for name, df in tables.items():
            print(f"{name:<20} {len(df):>8} rows")
        bad = tables["oaf_versions"].query("not valid") if len(tables["oaf_versions"]) else []
        if len(bad):
            print(f"WARNING: {len(bad)} invalid OAF versions (see oaf_versions.error)")
    elif a.cmd == "verify":
        from laf.oaf import parse_forecast_lenient
        from laf.usgs import load_manifest, read_raw, verify_manifest

        problems = verify_manifest(a.data_dir)  # integrity: missing files, hash mismatches
        entries = load_manifest(a.data_dir)
        repaired, invalid = 0, []  # USGS data defects: recorded, excluded from scoring
        for e in entries:
            if e["path"].startswith("raw/oaf/"):
                try:
                    repaired += parse_forecast_lenient(read_raw(a.data_dir, e["path"]))[1]
                except ValueError as err:
                    first = str(err).splitlines()[1:2] or [str(err)]
                    invalid.append(f"{e['path']}: {first[0].strip()[:120]}")
        for line in problems:
            print(f"INTEGRITY {line}")
        for line in invalid:
            print(f"invalid USGS forecast (excluded) {line}")
        print(
            f"{len(entries)} files, {len(problems)} integrity problems, "
            f"{repaired} repaired JSON, {len(invalid)} invalid forecasts"
        )
        sys.exit(1 if problems else 0)
    elif a.cmd == "etas-validate":
        import pandas as pd
        from scipy import stats

        from laf import etas_validate as ev
        from laf.asof import check_observations
        from laf.generic_rj import REFERENCE_REL
        from laf.oaf import parse_forecast

        proc = a.data_dir / "processed" / a.snapshot
        out = Path("runs") / "etas_validation" / a.snapshot
        out.mkdir(parents=True, exist_ok=True)
        ref = a.data_dir / REFERENCE_REL
        if "v0" in a.parts:
            ov = pd.read_parquet(proc / "oaf_versions.parquet")
            if a.only:
                ov = ov[ov["sequence_id"].isin(a.only)]
            r = check_observations(
                a.data_dir,
                ov,
                pd.read_parquet(proc / "catalog.parquet"),
                pd.read_parquet(proc / "sequences.parquet"),
            )
            r.to_parquet(out / "v0_observations.parquet", index=False)
            c = r[r["checkable"]]
            print(
                f"V0 exact: as-of {(c['asof'] == c['official']).mean():.4f}, hindsight "
                f"{(c['hindsight'] == c['official']).mean():.4f} of {len(c)} checkable counts"
            )
            print(
                c.assign(ok=c["asof"] == c["official"])
                .groupby("sequence_id")["ok"]
                .agg(["mean", "size"])
            )
        if "v3" in a.parts:
            versions, bins = ev.run(a.data_dir, a.snapshot, only=a.only)
            versions.to_parquet(out / "v3_versions.parquet", index=False)
            bins.to_parquet(out / "v3_bins.parquet", index=False)
            golden = Path("tests/golden/oaf_us6000u18k_1791593712688.json").read_bytes()
            cmp = ev.compare(bins, parse_forecast(golden).fractileProbabilities)
            cmp.to_parquet(out / "v3_compare.parquet", index=False)
            q = cmp.groupby("sequence_id")[["d_official", "d_null"]].quantile(0.9)
            print("V3 discrepancy, 90th percentile over cells (official vs Monte Carlo null):")
            print(q.round(3))
        if "java" in a.parts:
            fits, cells = ev.java_differential(Path("runs/java_differential/out"), ref)
            fits.to_csv(out / "java_fits.csv", index=False)
            cells.to_parquet(out / "java_cells.parquet", index=False)
            same_min = int((fits["min_mag_port"].round(6) == fits["min_mag_java"].round(6)).sum())
            print(
                f"Java: MAP equal {int(fits['map_equal'].sum())}/{len(fits)}; "
                f"minMag equal {same_min}/{len(fits)}"
            )
            print(cells.groupby("mag")[["d_port_java", "d_java_java"]].median().round(3))
        if "recovery" in a.parts:
            rec = ev.recovery(ref, a.recovery_n)
            rec.to_parquet(out / "recovery.parquet", index=False)
            for t_end, g in rec.groupby("t_end"):
                cols = ["rank_ams", "rank_a", "rank_p", "rank_c", "pit_week_m5"]
                ks = {k: round(float(stats.kstest(g[k], "uniform").pvalue), 3) for k in cols}
                c90 = {k: round(float(g[k].between(0.05, 0.95).mean()), 3) for k in cols}
                print(f"recovery t_end={t_end:g} n={len(g)}: KS p {ks}; 90% coverage {c90}")
        if "decomp" in a.parts:
            its = pd.read_parquet(proc / "issue_times.parquet")
            etas_issues = its.loc[its["oaf_ams"].notna(), "issue_id"]  # official ETAS products only
            hind = pd.read_parquet(proc / "etas_forecasts_hindsight.parquet")
            asof = pd.read_parquet(proc / "etas_forecasts.parquet")
            d = ev.decomposition(
                asof[asof["issue_id"].isin(etas_issues)],
                hind,
                its,
                pd.read_parquet(proc / "forecast_fractiles.parquet"),
            )
            cols = ["d_off_asof", "d_asof_hind", "d_off_hind"]
            if (proc / "etas_forecasts_analyst.parquet").exists():  # sensitivity variant
                an = pd.read_parquet(proc / "etas_forecasts_analyst.parquet")
                da = ev.decomposition(
                    an[an["issue_id"].isin(etas_issues)],
                    asof,
                    its,
                    pd.read_parquet(proc / "forecast_fractiles.parquet"),
                )
                da = da.rename(
                    columns={"d_off_asof": "d_off_analyst", "d_asof_hind": "d_analyst_default"}
                )
                d = d.merge(
                    da[["issue_id", "window", "d_off_analyst", "d_analyst_default"]],
                    on=["issue_id", "window"],
                )
                cols += ["d_off_analyst", "d_analyst_default"]
            d.to_parquet(out / "decomposition.parquet", index=False)
            print("decomposition (mean |log ratio| of M>=5 quantiles; median over cells):")
            print(d.groupby("sequence_id")[cols].median().round(3))
        print(f"wrote {out}")
    elif a.cmd == "adaption":
        import json

        from laf import adapt

        c = adapt.client()
        adapt.RUN = Path(f"runs/{a.run}-adaption")
        rec = lambda n: json.loads((adapt.RUN / n).read_text(encoding="utf-8"))  # noqa: E731
        if a.action == "upload":
            print("dataset", adapt.upload(c, a.file, pairs=a.pairs))
        elif a.action == "recommend":
            print(
                json.dumps(
                    adapt.recommend(c, rec("dataset.json")["dataset_id"]), indent=1, default=str
                )
            )
        elif a.action == "launch":
            if a.best_from:
                src = Path(f"runs/{a.best_from}-adaption/status.json")
                hp = json.loads(src.read_text(encoding="utf-8"))["best_hyperparams"]
            elif (adapt.RUN / "recommendation.json").exists():
                hp = rec("recommendation.json").get("hyperparams")
            else:
                hp = None
            ds = rec("dataset.json")["dataset_id"]
            print(
                "run",
                adapt.launch(
                    c, ds, hyperparams=hp, max_iterations=a.max_iterations, alignment=a.pairs
                ),
            )
        elif a.action == "download":
            out = Path(f"data/interim/{a.run}-adaption/best.tar.zst")
            print(adapt.fetch_checkpoint(c, rec("run.json")["run_id"], out))
        else:
            print(json.dumps(adapt.status(c, rec("run.json")["run_id"]), indent=1, default=str))
    elif a.cmd == "training-set":
        import json

        from laf import training as T

        start = a.start
        while True:  # prereg section 11: move the start back in whole years until >= 1,000 rows
            ev = T.fetch(a.data_dir, start, a.end, a.min_mag)
            if len(ev) * 6 >= T.MIN_ROWS:
                break
            start = f"{int(start[:4]) - 1}{start[4:]}"
        items, rows, cats = T.build(a.data_dir, ev)
        data = T.dataset(a.data_dir, items, rows, cats, workers=a.workers)
        out = a.data_dir / "processed" / "training"
        out.mkdir(parents=True, exist_ok=True)
        (out / a.out).write_text(
            "".join(json.dumps(r) + "\n" for r in data), encoding="utf-8", newline="\n"
        )
        print(f"{len(ev)} sequences from {start} to {a.end}; {len(data)} rows -> {out}/{a.out}")
    elif a.cmd == "e3-select":
        from laf import e3

        sel = e3.select(a.data_dir, {s.id for s in seqs})
        e3.write_config(sel, Path("config/sequences_e3.toml"))
        print(sel.groupby("role").size().to_string())
        print(sel[["id", "mag", "role", "place"]].to_string(index=False))
    elif a.cmd == "live-score":
        from laf.live import provisional_scores

        seq = next(s for s in seqs if s.id == a.sequence)
        tab = provisional_scores(a.data_dir, a.snapshot, seq, Path("runs") / a.name, a.version)
        Path("results").mkdir(exist_ok=True)
        tab.to_csv(f"results/{a.name}_provisional.csv", index=False, lineterminator="\n")
        print(tab.round(3).to_string(index=False) if len(tab) else "no closed windows yet")
    elif a.cmd == "combined":
        from laf import extensions as X

        runs = sorted(p.parent for p in a.runs.glob("*/results.jsonl"))
        models = [f"{m}|direct|I1|high" for m in X.CLAUDE]
        tab = X.combined_table(a.data_dir / "processed" / a.snapshot, runs, models)
        Path("results").mkdir(exist_ok=True)
        tab.to_csv(f"results/combined_{a.snapshot}.csv", index=False, lineterminator="\n")
        print(tab[tab["sequence"] == "pooled"].round(3).to_string(index=False))
    elif a.cmd == "d1":
        from laf import d1
        from laf.analysis import load_tables
        from laf.items import build_items

        proc = a.data_dir / "processed" / a.snapshot
        tables = load_tables(proc)
        items = d1.probe_items(build_items(tables, d1.FLOOR), tables["sequences"])
        path = proc / "items_d1.jsonl"
        if a.action == "build":
            path.write_text(d1.items_jsonl(items), encoding="utf-8", newline="\n")
            print(f"{len(items)} probe items -> {path}")
            return
        if a.action == "analyze":  # no API calls
            import hashlib
            import json

            if not path.exists() or path.read_text(encoding="utf-8") != d1.items_jsonl(items):
                raise SystemExit(f"{path} missing or stale: run `laf d1 build`")
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            runs = []  # only answers to exactly these items
            for p in sorted(Path("runs/d1").glob("d1-*/results.jsonl")):
                rec = json.loads((p.parent / "batch.json").read_text(encoding="utf-8"))
                if rec["snapshot"] == a.snapshot and rec["items_sha256"] == sha:
                    runs.append(p.parent)
                else:
                    print(f"skipped {p.parent}: other snapshot or items")
            st = d1.answer_stats(items, tables["sequences"], runs)
            summary = d1.summarize(st, tables["sequences"])
            for name, t in (("stats", st), ("summary", summary)):
                t.to_csv(f"results/d1_{name}_{a.snapshot}.csv", index=False, lineterminator="\n")
            print(f"{len(runs)} runs; {len(st)} rows -> results/d1_stats_{a.snapshot}.csv")
            print(f"NaN means (infinite-mean tails): {st['mean'].isna().mean():.4f}")
            return
        if not path.exists() or path.read_text(encoding="utf-8") != d1.items_jsonl(items):
            raise SystemExit(f"{path} missing or stale: run `laf d1 build` and commit it")
        from laf.providers import client

        if a.action == "pilot" and a.settings:
            from laf import runner

            reqs = d1.settings_requests(items, a.settings)
            name = "d1/pilot-settings" if a.settings == "grid" else f"d1/pilot-{a.settings}"
            bound = sum(d1.bound_usd(r["params"], batch=True) for r in reqs)
            print(f"settings pilot: {len(reqs)} requests, worst case ${bound:.2f} (batch)")
            if not a.dry_run:
                batch = runner.submit(
                    client(), name, reqs, a.snapshot, estimate=bound,
                    items_file="items_d1.jsonl", prompt_set="v2",
                )  # fmt: skip
                print("batch", batch, f"-> laf status / laf collect {name}")
            return
        if a.action == "pilot":
            if a.dry_run:
                print(f"pilot: at most {len(d1.PILOT_TAGS) * len(d1.PILOT_MODELS)} calls, $0.50")
                return
            out = Path("runs/d1/pilot")
            print(f"pilot spend ${d1.pilot(client(), items, out):.3f} -> {out}/calls.jsonl")
            return
        if not a.model:
            raise SystemExit("--model is required for run")
        from laf import runner

        reqs = d1.expand(items, a.model)
        est = d1.estimate_usd(
            reqs,
            [Path("runs/d1/pilot-settings"), Path("runs/d1/pilot-sonnet-low")],
            Path("runs/d2/d2-claude-opus-5-5/results.jsonl"),
        )
        name = f"d1/d1-{a.model}"
        print(f"{name}: {len(reqs)} requests, estimate ${est:.2f} (batch)")
        if not a.dry_run:
            batch = runner.submit(
                client(), name, reqs, a.snapshot, estimate=est,
                items_file="items_d1.jsonl", prompt_set="v2",
            )  # fmt: skip
            print("batch", batch)
    elif a.cmd == "d2":
        from laf.d2 import analyze, robustness

        runs = sorted(d for d in a.runs.iterdir() if (d / "results.jsonl").exists())
        if not runs:
            raise SystemExit(f"no collected D2 runs (results.jsonl) under {a.runs}")
        df, summary = analyze(a.data_dir / "processed" / a.snapshot, runs)
        rob = robustness(df)
        for name, t in (("samples", df), ("summary", summary), ("robustness", rob)):
            t.to_csv(
                Path("results") / f"d2_{name}_{a.snapshot}.csv", index=False, lineterminator="\n"
            )
        print(summary.round(3).to_string(index=False))
        print(rob.round(3).to_string(index=False))
    elif a.cmd == "live-watch":
        from laf.live_watch import run

        run(a.out, a.live_data, a.data_dir, a.polls, a.publish, a.paid)
    elif a.cmd == "live-late":
        import pandas as pd

        from laf.live_watch import index_lags_s, late_share, version_slack_s

        cols = ["sequence_id", "update_ms", "time_start_ms", "valid", "duplicate"]
        versions = pd.concat(
            pd.read_parquet(a.data_dir / "processed" / s / "oaf_versions.parquet", columns=cols)
            for s in a.snapshot
        )
        slack, n_seq = version_slack_s(versions)
        lags = index_lags_s(a.log)
        print(f"{len(slack)} OAF versions in {n_seq} sequences; {len(lags)} dry-run index lags")
        print(f"first window opens before publication: {(slack < 0).mean():.3f}")
        rows = [
            {"poll_min": p, "forecast_min": f, "late": late_share(slack, lags, 60 * p, 60 * f)}
            for p in (2, 5, 10)
            for f in (0.5, 2, 5)
        ]
        tab = pd.DataFrame(rows)
        tab.to_csv("results/live_late_share.csv", index=False, lineterminator="\n")
        print(tab.pivot(index="poll_min", columns="forecast_min", values="late").round(3))
    elif a.cmd == "openai":
        from laf import openai_runner as O

        if a.action in ("status", "collect"):
            if not a.name:
                raise SystemExit("give the run name, e.g. openai/pilot-gpt-5.1-2025-11-13")
            c = O.client()
            if a.action == "status":
                print(O.status(c, a.name))
            else:
                print(f"{O.collect(c, a.name)} results -> runs/{a.name}/results.jsonl")
            return
        if not (a.snapshot and a.effort):
            raise SystemExit("run needs --snapshot and --effort")
        from laf.pilot import load_items

        items = load_items(a.data_dir, a.snapshot, 3.0)
        # the v2 items, written next to the registered ones and hashed into batch.json
        (a.data_dir / "processed" / a.snapshot / "items_m3.jsonl").write_text(
            "".join(i.model_dump_json() + "\n" for i in items), encoding="utf-8", newline="\n"
        )
        if a.block == "pilot":  # one request per item and effort; output capped at 16k
            sel = O.pilot_items(items)
            reqs = [r for e in a.effort for r in O.expand(
                sel, a.model, e, k=1, block="openai-pilot", max_output_tokens=16_000)]  # fmt: skip
            # outside runs/d2, so `laf d2` never pools the pilot with the experiment
            name, est = f"openai/pilot-{a.model}", O.bound_usd(reqs)
            print(f"{name}: {len(reqs)} requests, worst case ${est:.2f} (batch)")
        else:
            if len(a.effort) != 1:
                raise SystemExit("the d2 block takes one --effort")
            reqs = O.expand(items, a.model, a.effort[0])
            name = f"d2/d2-{a.model}-{a.effort[0]}"
            est = O.estimate_usd(reqs, Path(f"runs/openai/pilot-{a.model}"))
            print(f"{name}: {len(reqs)} requests, estimate ${est:.2f} (batch)")
        if not a.dry_run:
            print("batch", O.submit(O.client(), name, reqs, a.snapshot, estimate=est))
    elif a.cmd == "prospective":
        import json

        from laf.prospective import run_issue

        seq = next(s for s in seqs if s.id == a.sequence)
        out = a.out.with_name(a.out.name + "-dryrun") if a.dry_run else a.out
        if not a.dry_run and not out.resolve().is_relative_to(Path("runs").resolve()):
            raise SystemExit("a paid run writes under runs/, where the spend ledger looks")
        clients = None
        if not a.dry_run:
            from laf.openai_runner import client as openai_client
            from laf.providers import client as anthropic_client

            clients = {"claude": anthropic_client(), "openai": openai_client()}
        rec = run_issue(clients, a.data_dir, a.snapshot, seq, out, dry_run=a.dry_run)
        print(json.dumps(rec, indent=1, sort_keys=True))
    elif a.cmd == "confirmatory":
        import pandas as pd

        from laf.analysis import load_tables
        from laf.confirmatory import (
            PRIMARY,
            SECONDARY,
            confirmatory_cells,
            hierarchical,
            report,
        )
        from laf.d2 import analyze
        from laf.pilot import load_items
        from laf.splits import require_outcome_table

        proc = a.data_dir / "processed" / a.snapshot
        tables = load_tables(proc)
        require_outcome_table(tables["observed_counts"])  # first: refuses while sealed
        runs = sorted(d for d in a.runs.iterdir() if (d / "results.jsonl").exists())
        samples, _ = analyze(proc, runs)
        elapsed = {i.item_id: i.elapsed_days for i in load_items(a.data_dir, a.snapshot, 3.0)}
        widen = {PRIMARY[0]: 0.0} if a.test_a_all else None
        cells = confirmatory_cells(samples, tables["sequences"], elapsed, widen)
        descriptive = tuple(set(cells["model"]) - set(PRIMARY) - set(SECONDARY))
        t = report(cells, PRIMARY, descriptive=descriptive)
        hier = {m: hierarchical(g) for m, g in cells.groupby("model")}
        t = t.join(pd.DataFrame.from_dict(hier, orient="index"), on="model")
        tag = "_test_a_all" if a.test_a_all else ""
        path = Path("results") / f"confirmatory_{a.snapshot}{tag}.csv"
        t.to_csv(path, index=False, lineterminator="\n")
        print(t.round(3).to_string(index=False))
        print(f"-> {path}")
    elif a.cmd == "confirmatory-size":
        import pandas as pd

        from laf.confirmatory import sequence_effects, size
        from laf.power import d2_cell_differences

        runs = sorted(d for d in a.runs.iterdir() if (d / "results.jsonl").exists())
        cells = d2_cell_differences(a.data_dir / "processed" / a.snapshot, runs)
        rows = []
        for label in ("gpt-5.1-2025-11-13 medium v2A", "claude-opus-5-5 high v2A"):
            e = sequence_effects(cells[cells["model"] == label]).to_numpy()
            for n in (33, 89):
                for alpha in (0.025, 0.05):
                    for method in ("student", "percentile"):
                        rate = size(e, n, alpha=alpha, sims=a.sims, method=method)
                        rows.append(dict(effects=label, n=n, alpha=alpha, method=method,
                                         size=rate, sims=a.sims))  # fmt: skip
                        print(f"{label:<32} n={n:<3} alpha={alpha:<5} {method:<10} {rate:.3f}")
        path = Path("results") / f"confirmatory_size_d2_{a.snapshot}.csv"
        pd.DataFrame(rows).to_csv(path, index=False, lineterminator="\n")
        print(f"-> {path}")
    elif a.cmd == "confirmatory-dryrun":
        import pandas as pd

        from laf.confirmatory import report
        from laf.power import d2_cell_differences

        runs = sorted(d for d in a.runs.iterdir() if (d / "results.jsonl").exists())
        cells = d2_cell_differences(a.data_dir / "processed" / a.snapshot, runs)
        cells = cells[cells["model"].str.endswith("v2A")]
        # stand-in for the primary test A (gpt-5.1), ADR 0018 decision 15
        primary = ("gpt-5.1-2025-11-13 medium v2A",)
        t = report(cells, primary)
        from laf.confirmatory import hierarchical, stratum
        from laf.pilot import load_items

        elapsed = {i.item_id: i.elapsed_days for i in load_items(a.data_dir, a.snapshot, 3.0)}
        cells = cells.assign(
            issue_id=[c[0] for c in cells["cell"]],
            window=[c[1] for c in cells["cell"]],
            stratum=[stratum(elapsed[c[0]]) for c in cells["cell"]],
        )
        hier = {m: hierarchical(g) for m, g in cells.groupby("model")}
        t = t.join(pd.DataFrame.from_dict(hier, orient="index"), on="model")
        path = Path("results") / f"confirmatory_dryrun_d2_{a.snapshot}.csv"
        t.to_csv(path, index=False, lineterminator="\n")
        cols = ["model", "sequences", "mean", "upper", "noninferior", "holm_noninferior",
                "trimmed_mean", "median", "hier_mu", "hier_upper", "hier_noninferior"]  # fmt: skip
        print(t[cols].round(3).to_string(index=False))
        print(f"-> {path} (development data: a rehearsal of the frozen analysis, not a result)")
    elif a.cmd == "power":
        import pandas as pd

        from laf.power import cell_differences, d2_cell_differences, power_table, sequence_effects

        runs = sorted(d for d in a.runs.iterdir() if (d / "results.jsonl").exists())
        proc = a.data_dir / "processed" / a.snapshot
        if a.from_d2 and a.reference != "official":
            raise SystemExit("--from-d2 scores against the official forecast only")
        cells = (
            d2_cell_differences(proc, runs)
            if a.from_d2
            else cell_differences(proc, runs, a.reference, a.valid_only)
        )
        equivalence = a.reference != "naive"
        tables = []
        for model, g in cells.groupby("model"):
            eff = sequence_effects(g).to_numpy()
            print(f"{model}: {len(g)} cells, {len(eff)} sequences, mean dLS {g['d'].mean():+.3f}, "
                  f"between-sequence SD {eff.std(ddof=1):.3f}")  # fmt: skip
            if len(eff) < 5:
                continue
            ns, margins = (20, 40, 60, 100, 150, 194), (0.02, 0.03, 0.05, 0.1)
            # equivalence at a true difference of 0; superiority at the development estimate
            truth = 0.0 if equivalence else float(eff.mean())
            t = power_table(eff, ns, margins if equivalence else (None,), true_diff=truth)
            tables.append(t.assign(model=model, reference=a.reference))
        out = pd.concat(tables) if tables else pd.DataFrame()
        tag = "_d2" if a.from_d2 else "_validonly" if a.valid_only else ""
        path = Path("results") / f"power_{a.reference}{tag}_{a.snapshot}.csv"
        out.to_csv(path, index=False)
        if len(out):
            print(out.pivot_table(index=["model", "n_sequences"], columns="margin", values="power",
                                  dropna=False).round(2).to_string())  # fmt: skip
        print(f"-> {path}")
    elif a.cmd == "hindsight":
        from laf import analysis as A
        from laf.hindsight import compare, summary

        proc = a.data_dir / "processed" / a.snapshot
        df = compare(A.load_tables(proc), A.load_items(proc))
        table = summary(df)
        df.to_csv(Path("results") / f"hindsight_{a.snapshot}.csv", index=False)
        table.to_csv(Path("results") / f"hindsight_summary_{a.snapshot}.csv", index=False)
        print(table.round(4).to_string(index=False))
    elif a.cmd == "countdist-check":
        import numpy as np
        import pandas as pd

        from laf import analysis as A
        from laf.countdist import from_cdf_array, from_quantiles, log_score, nb_from_quantiles

        fine = np.round(np.arange(1, 400) * 0.0025, 4)
        proc = a.data_dir / "processed" / a.snapshot
        tables, items = A.load_tables(proc), A.load_items(proc)
        cell_df = A.cells(tables)  # refuses confirmatory sequences (docs/adr/0013)
        cell_df = cell_df[(cell_df["role"] != "dev") & cell_df["primary"]]
        ys = {(c["issue_id"], c["window"]): int(c["y5"]) for c in cell_df.to_dict("records")}
        rows = []
        for (name, iid, win), fc in A.baselines(tables, items, cell_df).items():
            if name not in ("official", "etas") or (iid, win) not in ys:
                continue
            if name == "official" and fc.fractiles_m5 is not None:
                levels, counts = fc.fractiles_m5
                full = from_quantiles(counts, levels).cdf
                raw = full
            elif fc.cdf_m5 is not None:  # simulated histogram: also smoothed via 399 fractiles
                raw = from_cdf_array(fc.cdf_m5)
                counts = [int(np.searchsorted(fc.cdf_m5, t - 1e-12)) for t in fine]
                full = from_quantiles(counts, fine).cdf
            else:
                continue
            y = ys[(iid, win)]
            rows.append(
                {
                    "forecaster": name, "issue_id": iid, "window": win, "y5": y,
                    "ls_raw": log_score(raw, y)[0], "ls_full": log_score(full, y)[0],
                    "ls_q9_power": log_score(from_quantiles(fc.m5).cdf, y)[0],
                    "ls_q9_nbtail": log_score(from_quantiles(fc.m5, tail="nb").cdf, y)[0],
                    "ls_q9_nb": log_score(nb_from_quantiles(fc.m5), y)[0],
                }
            )  # fmt: skip
        df = pd.DataFrame(rows)
        out = Path("results") / f"countdist_check_{a.snapshot}.csv"
        df.to_csv(out, index=False)
        for name, g in df.groupby("forecaster"):
            raw_mean, full_mean = g["ls_raw"].mean(), g["ls_full"].mean()
            print(f"{name}: {len(g)} cells, mean LS raw {raw_mean:.3f}, full {full_mean:.3f}")
            for v in ("ls_q9_power", "ls_q9_nbtail", "ls_q9_nb"):
                d = g[v] - g["ls_full"]
                corr = np.corrcoef(g[v], g["ls_full"])[0, 1]
                print(
                    f"  {v} - full: mean {d.mean():+.3f}, median {d.median():+.3f}, "
                    f"MAE {d.abs().mean():.3f}, corr {corr:.3f}"
                )
        print(f"-> {out}")
    elif a.cmd == "replicates":
        import pandas as pd

        # data: E1 = 3,090 rows (M>=6.5), E1a = 9,030 rows (M>=6.0); E1 itself had 3 iterations
        runs = {"e1": "E1", "e1r1": "E1", "e1r2": "E1", "e1a": "E1a", "e1ar2": "E1a", "e1b": "E1b"}
        e3 = pd.read_csv("results/e3_dqs_extensions.csv").query("sequence == 'pooled'")
        rows = []
        for r, data in runs.items():
            f = Path(f"results/{r}.csv")
            if not f.exists():
                continue
            t = pd.read_csv(f).query("sequence == 'pooled' and scoring == 'penalty'")
            row = {"run": r, "data": data}
            for ref in ("official", "etas"):
                x = t[t["reference"] == ref].iloc[0]
                row |= {
                    f"reg_vs_{ref}": x["dQS"],
                    f"reg_vs_{ref}_lo": x["lo"],
                    f"reg_vs_{ref}_hi": x["hi"],
                }
            for scoring, tag in (("penalty", "e3_m5"), ("m4 valid-only", "e3_m4")):
                m = e3[(e3["forecaster"] == f"laf/gpt-oss-20b-{r}|direct|I1|medium")
                       & (e3["role"] == "test-post") & (e3["scoring"] == scoring)]  # fmt: skip
                if len(m):
                    row |= {
                        tag: m["dQS"].iloc[0],
                        f"{tag}_lo": m["lo"].iloc[0],
                        f"{tag}_hi": m["hi"].iloc[0],
                    }
            rows.append(row)
        tab = pd.DataFrame(rows)
        tab.to_csv("results/replicates.csv", index=False, lineterminator="\n")
        print(tab.round(3).to_string(index=False))
    elif a.cmd == "outcome-training":
        import json

        from laf import outcome_training as O
        from laf import training as T

        out = a.data_dir / "processed" / "training"
        rows = [json.loads(x) for x in (out / "e1_train.jsonl").read_text("utf-8").splitlines()]
        ev = T.fetch(a.data_dir, "2010-01-01", "2025-07-01", 6.5)
        T.fetch_outcomes(a.data_dir, ev)
        items, _, _ = T.build(a.data_dir, ev)
        fit, dpo = O.build(rows, O.outcomes(a.data_dir, items))
        (out / "e1b_pairs.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in dpo), encoding="utf-8", newline="\n"
        )
        Path("results").mkdir(exist_ok=True)
        Path("results/etas_recal_fit.json").write_text(
            json.dumps(fit, indent=1) + "\n", encoding="utf-8", newline="\n"
        )
        print(fit, f"{len(dpo)} preference pairs")
    elif a.cmd == "e3":
        from laf import extensions as X

        Path("results").mkdir(exist_ok=True)
        for name, tab in X.e3_tables(a.data_dir / "processed" / a.snapshot).items():
            dest = "notebooks/public" if name.startswith("explorer") else "results"
            tab.to_csv(f"{dest}/{name}.csv", index=False, lineterminator="\n")
            if name.startswith("explorer"):
                continue
            pooled = tab[tab["sequence"] == "pooled"] if "sequence" in tab else tab
            print(f"== {name}\n{pooled.round(3).to_string(index=False)}")
    elif a.cmd == "e1":
        from laf import extensions as X

        runs = sorted(
            p.parent
            for p in Path("runs").glob("*/results.jsonl")
            if (p.parent / "requests.jsonl").exists()
        )
        tab, inv = X.e1_table(a.data_dir / "processed" / a.snapshot, runs, model=a.model)
        Path("results").mkdir(exist_ok=True)
        out = "e1" if a.model == "gpt-oss-20b-e1" else a.model.rsplit("-", 1)[-1]
        tab.to_csv(f"results/{out}.csv", index=False, lineterminator="\n")
        print(tab.round(3).to_string(index=False))
        print(inv.round(3).to_string())
    elif a.cmd == "literature":
        import pandas as pd

        from laf import literature as L

        pap = L.papers(a.data_dir, Path("config/literature_screen.csv"))
        issues = pd.read_parquet(a.data_dir / "processed" / a.snapshot / "issue_times.parquet")
        tab = L.exposure(pap, issues, {s.id: s.name for s in seqs})
        Path("results").mkdir(exist_ok=True)
        tab.to_csv("results/e2_literature.csv", index=False, lineterminator="\n")
        print(tab.to_string(index=False))
    elif a.cmd == "figures":
        import numpy as np
        import pandas as pd

        from laf import analysis as A
        from laf import figures as F

        proc = a.data_dir / "processed" / a.snapshot
        tables, items = A.load_tables(proc), A.load_items(proc)
        cell_df = A.cells(tables)
        cell_df = cell_df[cell_df["role"] != "dev"].reset_index(drop=True)
        runs = sorted(
            p.parent
            for p in Path("runs").glob("*/results.jsonl")
            if (p.parent / "requests.jsonl").exists()
        )
        df = A.score_all(cell_df, A.baselines(tables, items, cell_df), A.llm_samples(runs, items))
        tab = F.explorer_table(df, tables["sequences"])
        public = Path("notebooks/public")
        public.mkdir(parents=True, exist_ok=True)
        tab.to_csv(public / "explorer.csv", index=False, lineterminator="\n")
        ans = A.answer_scores(df)
        oaf = ans["primary"] & ans["oaf_cell"] & ans["role"].eq("test-post")
        h1 = pd.concat(
            [
                A.ci_table(
                    A.dqs(ans, f"{m}|direct|I1|high", "official", oaf),
                    np.random.default_rng(20261021),
                ).assign(model=m)
                for m in F.MODELS
            ]
        )
        out = Path("figures")
        out.mkdir(exist_ok=True)
        F.fig_h1(h1, out / "h1_vs_official.png")
        F.fig_coverage(df, out / "coverage.png")
        for seq, win in (("Flores Sea", "1 Week"), ("Colombia", "1 Week")):
            F.fig_fan(
                tab,
                seq,
                win,
                ["official", "etas", "claude-opus-5-5|direct|I1|high"],
                out / f"fan_{seq.split()[0].lower()}_{win.split()[1].lower()}.png",
            )
        reg = pd.concat(
            [
                A.ci_table(A.dqs(ans, f, "official", oaf), np.random.default_rng(20261021))
                .query("sequence == 'pooled'")
                .assign(forecaster=f)
                for f in F.OVERVIEW
                if f in set(ans["forecaster"])
            ]
        )
        for csv, f in (("results/e1.csv", F.OVERVIEW[5]), ("results/e1a.csv", F.OVERVIEW[6])):
            if Path(csv).exists():  # descriptive extensions, scored apart (laf e1)
                t = pd.read_csv(csv).query("sequence == 'pooled' and scoring == 'penalty'")
                reg = pd.concat([reg, t[t["reference"] == "official"].assign(forecaster=f)])
        F.fig_headline(tab, reg, out / "headline.png")
        panels = [("Preregistered test: Colombia, Flores Sea (33 windows)", reg)]
        e3 = [Path("results/e3_dqs_main.csv"), Path("results/e3_dqs_extensions.csv")]
        if all(p.exists() for p in e3):
            t = pd.concat([pd.read_csv(p) for p in e3])
            t = t.query("sequence == 'pooled' and role == 'test-post' and scoring == 'penalty'")
            panels.append(("18 more recent sequences (exploratory)", t))
        F.fig_overview(panels, out / "overview.png")
        # reader-facing summary for the explorer: difference from the official forecast
        sets = ("Preregistered", "39 more sequences (exploratory)")
        summ = pd.concat([p.assign(set=n) for n, (_, p) in zip(sets, panels, strict=False)])
        summ["forecaster"] = summ["forecaster"].map(F.display_name)
        summ[["set", "forecaster", "dQS", "lo", "hi", "cells"]].to_csv(
            public / "summary.csv", index=False, lineterminator="\n"
        )
        print(f"{len(tab)} explorer rows -> {public / 'explorer.csv'}; figures -> {out}/")
    elif a.cmd == "probe":
        import pandas as pd

        from laf.probe import run_probe
        from laf.providers import client

        seq_df = pd.read_parquet(a.data_dir / "processed" / a.snapshot / "sequences.parquet")
        print(f"{run_probe(client(), seq_df, Path('runs') / 'probe')} answers -> runs/probe/")
    elif a.cmd == "live":
        import time

        from laf.items import utc
        from laf.live import HOUR_MS, live_items, next_full_hour, run_live

        now_ms = int(time.time() * 1000)
        strict_ms = next_full_hour(now_ms + 30 * 60_000)  # next full hour after the hash
        seq = next(s for s in seqs if s.id == a.sequence)
        items, update_ms = live_items(a.data_dir, a.snapshot, seq, now_ms, strict_ms)
        print(f"newest official version {update_ms}; strict windows open {utc(strict_ms)} UTC")
        for i in items:
            ws = ", ".join(f"{w.key} {utc(w.start_ms)}-{utc(w.end_ms)}" for w in i.windows)
            print(f"{i.item_id}: issue {utc(i.issue_ms)}, {len(i.catalog)} rows; {ws}")
        if not a.dry_run:
            from laf.providers import client

            sha, spent = run_live(client(), items, Path("runs") / a.name)
            done_ms = int(time.time() * 1000)
            print(f"outputs SHA-256 {sha}; spend ${spent:.3f}; hashed {utc(done_ms)} UTC")
            if done_ms >= strict_ms - HOUR_MS // 6:
                print("WARNING: less than 10 min before the strict windows open")
    elif a.cmd == "smoke":
        from laf.pilot import smoke

        print(f"smoke spend ${smoke(Path('runs/smoke')):.4f}")
    elif a.cmd == "pilot":
        from laf.pilot import count_inputs, load_items, pilot

        items = load_items(a.data_dir, a.snapshot)
        if a.summary:
            import json

            from laf.pilot import summarize

            print(json.dumps(summarize(Path("runs/pilot"), items), indent=1))
            return
        if not a.count_only:
            print(f"pilot spend ${pilot(Path('runs/pilot'), items):.3f}")
        count_inputs(Path("runs/pilot"), items)
    elif a.cmd == "items":
        from laf.pilot import load_items

        out = a.data_dir / "processed" / a.snapshot / "items.jsonl"
        items = load_items(a.data_dir, a.snapshot)
        out.write_text(
            "".join(i.model_dump_json() + "\n" for i in items), encoding="utf-8", newline="\n"
        )
        print(f"{len(items)} items -> {out}")
    elif a.cmd == "prompts-hash":
        import json

        from laf.prompts import PROMPT_DIR, template_hashes

        for sub_dir in ("", "v2"):  # registered prompts, and the v2 (D2) prompts
            path = PROMPT_DIR / sub_dir / "HASHES.json"
            path.write_text(
                json.dumps(template_hashes(sub_dir), indent=1) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            print(f"wrote {path}")
    elif a.cmd == "spend":
        from collections import defaultdict

        from laf.runner import spend_records

        by_month: defaultdict[str, float] = defaultdict(float)
        for month, usd in spend_records():
            by_month[month] += usd
        for month in sorted(by_month):
            print(f"{month}: ${by_month[month]:.4f}")
        print(f"total ${sum(by_month.values()):.4f}")
    elif a.cmd == "batch-status":
        from laf.providers import client

        b = client().messages.batches.retrieve(a.batch_id)  # results: `laf collect` only
        print(b.processing_status, b.request_counts, b.created_at, b.ended_at)
    elif a.cmd in ("run", "status", "collect"):
        from laf import runner
        from laf.providers import client

        if a.cmd == "status":
            print(runner.status(client(), a.name))
        elif a.cmd == "collect":
            print(f"{runner.collect(client(), a.name)} results -> runs/{a.name}/results.jsonl")
        else:
            from laf.pilot import load_items

            floor = runner.BLOCKS[a.block].get("floor", 4.0)
            items = load_items(a.data_dir, a.snapshot, floor)
            items_file, prompt_set = (
                ("items.jsonl", "") if floor == 4.0 else ("items_m3.jsonl", "v2")
            )
            if floor != 4.0:  # the v2 items, written next to the registered ones and hashed
                (a.data_dir / "processed" / a.snapshot / items_file).write_text(
                    "".join(i.model_dump_json() + "\n" for i in items),
                    encoding="utf-8",
                    newline="\n",
                )
            reqs = runner.expand(items, a.block, a.model)
            est = runner.estimate_usd(reqs)
            name = a.name or f"{a.block}-{a.model}"
            print(f"{name}: {len(reqs)} requests, estimate ${est:.2f} (batch), "
                  f"spent so far ${runner.spent_usd():.2f}")  # fmt: skip
            if not a.dry_run:
                batch = runner.submit(
                    client(), name, reqs, a.snapshot, estimate=est,
                    items_file=items_file, prompt_set=prompt_set,
                )  # fmt: skip
                print("batch", batch)
    elif a.cmd == "etas":
        import time

        import pandas as pd

        from laf.etas import (
            V2_PASS,
            analyst_kwargs,
            forecast_item,
            issue_seed,
            resimulate_published,
            v2_decision,
            v2_evaluate,
        )
        from laf.etas import load_analyst_settings as _load_rules
        from laf.generic_rj import REFERENCE_REL
        from laf.pilot import load_items

        if a.validate and a.settings != "default":
            raise SystemExit("--settings analyst applies to refit forecasts, not to --validate")
        proc = a.data_dir / "processed" / a.snapshot
        rules = _load_rules(Path("config/analyst_settings.toml")) if a.settings == "analyst" else []
        # window start of each issue's matched official version, in days after the mainshock
        ov = pd.read_parquet(proc / "oaf_versions.parquet")
        ov = ov[ov["valid"] & ~ov["duplicate"].astype(bool)]
        origins = pd.read_parquet(proc / "sequences.parquet").set_index("sequence_id")["origin_ms"]
        version_days = {
            (r["sequence_id"], r["creation_ms"]): (r["time_start_ms"] - origins[r["sequence_id"]])
            / 86_400_000
            for r in ov.to_dict("records")
        }
        items = load_items(a.data_dir, a.snapshot)
        its = {
            r["issue_id"]: r
            for r in pd.read_parquet(proc / "issue_times.parquet").to_dict("records")
        }
        cats = pd.read_parquet(proc / "catalog.parquet")
        hists: dict[str, pd.DataFrame] = {}
        ref = a.data_dir / REFERENCE_REL
        rows = []
        for item in items:
            if a.only and item.item_id not in a.only:
                continue
            row = its[item.item_id]
            ams = row.get("oaf_ams")
            if a.validate and (ams is None or ams != ams):  # V2 only for ETAS products
                continue
            cat = cats[cats["sequence_id"] == item.sequence_id]
            n_fallback = 0
            if a.catalog == "asof":
                from laf.asof import as_of_or_hindsight, load_versions

                if item.sequence_id not in hists:
                    hists[item.sequence_id] = load_versions(a.data_dir, cat["id"])
                seen = row["creation_ms"] if a.validate else item.issue_ms
                after = cat[cat["id"] != item.sequence_id]  # the mainshock enters separately
                cat, fallback = as_of_or_hindsight(hists[item.sequence_id], after, int(seen))
                n_fallback = int(fallback.sum())
            t0 = time.perf_counter()
            seed = issue_seed(item.item_id) + a.seed_offset
            if a.validate:
                out, kw = resimulate_published(item, row, cat, ref, seed), {}
            else:
                vd = version_days.get((item.sequence_id, row.get("creation_ms")))
                kw = analyst_kwargs(rules, item.sequence_id, vd)
                out = forecast_item(item, row, cat, ref, seed, **kw)
            dt = time.perf_counter() - t0
            label = "analyst" if kw else "default"
            rows += [
                {**r, "runtime_s": dt, "n_hindsight_events": n_fallback, "settings": label}
                for r in out
            ]
            print(
                f"{item.item_id:<22} {dt:6.1f} s  M>=5 median by window {[r['q500'] for r in out]}",
                flush=True,
            )
        suffix = ("" if a.catalog == "asof" else "_hindsight") + (
            "_analyst" if a.settings == "analyst" else ""
        )
        name = a.out or (
            f"etas_validation{suffix}.parquet" if a.validate else f"etas_forecasts{suffix}.parquet"
        )
        df = pd.DataFrame(rows)
        if a.validate:
            df = v2_evaluate(
                df,
                pd.read_parquet(proc / "issue_times.parquet"),
                pd.read_parquet(proc / "forecast_fractiles.parquet"),
                pd.read_parquet(proc / "sequences.parquet"),
            )
        df.to_parquet(proc / name, index=False)
        print(f"wrote {proc / name}")
        if a.validate:
            cols = ["issue_id", "window", "min_mag", "q500", "off_q500", "ratio"]
            print(df[~df["ok"]][cols].round(2).to_string(index=False))
            rate, by_seq, eligible = v2_decision(df)
            print(f"V2 pass rate {rate:.3f} ({int(df['ok'].sum())}/{len(df)}), threshold {V2_PASS}")
            print("by sequence", {k: round(x, 3) for k, x in by_seq.items()})
            print("hindsight-effect sequences", eligible)
            if a.seed_offset or a.only:
                print("robustness run: the registered decision is the full run with seed offset 0")
            sys.exit(0 if rate >= V2_PASS else 1)
