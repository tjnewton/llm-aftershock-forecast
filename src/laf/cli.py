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
    sub.add_parser("spend", help="total recorded API spend from runs/*/calls.jsonl")
    bs = sub.add_parser(
        "batch-status", help="processing status and counts of a batch id (no results)"
    )
    bs.add_argument("batch_id")
    rn = sub.add_parser("run", help="SPENDS MONEY: submit one design block as a Message Batch")
    rn.add_argument("--snapshot", required=True)
    rn.add_argument(
        "--block", required=True, choices=("core", "i0", "sonnet-low", "e3", "e3pre", "e3i0")
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
        tab = F.explorer_table(df)
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
                ["official", "etas", "claude-sonnet-5-5|direct|I1|high"],
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
        panels = [("Registered: Colombia, Flores Sea (33 cells)", reg)]
        e3 = [Path("results/e3_dqs_main.csv"), Path("results/e3_dqs_extensions.csv")]
        if all(p.exists() for p in e3):
            t = pd.concat([pd.read_csv(p) for p in e3])
            t = t.query("sequence == 'pooled' and role == 'test-post' and scoring == 'penalty'")
            panels.append(("E3 post-cutoff, 18 sequences (exploratory)", t))
        F.fig_overview(panels, out / "overview.png")
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

        (PROMPT_DIR / "HASHES.json").write_text(
            json.dumps(template_hashes(), indent=1) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"wrote {PROMPT_DIR / 'HASHES.json'}")
    elif a.cmd == "spend":
        import json

        from laf.providers import cost_usd

        total = 0.0
        for path in sorted(Path("runs").glob("*/calls.jsonl")):
            recs = [
                json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line
            ]
            usd = sum(cost_usd(r["model_requested"], r["usage"]) for r in recs if r.get("usage"))
            total += usd
            print(f"{path}: {len(recs)} calls, ${usd:.4f}")
        print(f"total ${total:.4f}")
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

            reqs = runner.expand(load_items(a.data_dir, a.snapshot), a.block, a.model)
            est = runner.estimate_usd(reqs)
            name = a.name or f"{a.block}-{a.model}"
            print(f"{name}: {len(reqs)} requests, estimate ${est:.2f} (batch), "
                  f"spent so far ${runner.spent_usd():.2f}")  # fmt: skip
            if not a.dry_run:
                print("batch", runner.submit(client(), name, reqs, a.snapshot, estimate=est))
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
