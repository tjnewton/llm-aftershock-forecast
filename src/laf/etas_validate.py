"""Emulate published legacy-ETAS forecasts end to end (docs/adr/0010 section 4).

For one official version: rebuild the catalog it saw (``laf.asof``), refit with its Mc, b and
magMain, sample the posterior, simulate with its minimum magnitude, and report its own outputs
(fractiles at every published level and the legacy ``probability``) for each window and bin.
Two seeds give the Monte Carlo null: an emulation that matches the official forecast as well as
it matches itself is as good as the port can be.
"""

import math

import numpy as np
import pandas as pd

from laf.asof import as_of_or_hindsight, load_versions
from laf.etas import (
    DAY_MS,
    LEVELS,
    N_SIMS,
    Grid,
    _poisson_quantile,
    fetched_events,
    fit_legacy,
    generic_etas,
    issue_seed,
    legacy_min_mag,
    sample_posterior,
    simulate_chunked,
)
from laf.oaf import Forecast, parse_forecast_lenient
from laf.usgs import read_raw

SCORED = ("1 Day", "1 Week", "1 Month")
MAGS = (3.0, 4.0, 5.0, 6.0, 7.0)


def legacy_fractile_values(
    n: np.ndarray, b: float, mag: float, min_mag: float, levels
) -> np.ndarray:
    """Published fractiles for M >= mag from counts n of M >= max(mag, minMag) (unrounded)."""
    q = np.quantile(n, levels, method="inverted_cdf").astype(float)
    if mag >= min_mag:
        return q
    lam = -math.log(float(np.mean(n == n.min())))
    q = np.array(
        [_poisson_quantile(lam, f) if v <= 1 else v for f, v in zip(levels, q, strict=True)]
    )
    return 10.0 ** (b * (min_mag - mag)) * q


def legacy_probability(n: np.ndarray, b: float, mag: float, min_mag: float) -> float:
    """Published ``probability``: 1 - weight at the smallest simulated count, scaled below
    minMag as 1 - (1 - P)^(10^(b (minMag - mag))) (ETAS_AftershockModel:762-782)."""
    p = 1.0 - float(np.mean(n == n.min()))
    if mag < min_mag:
        p = 1.0 - (1.0 - p) ** (10.0 ** (b * (min_mag - mag)))
    return p


def emulate(
    f: Forecast,
    origin_ms: int,
    catalog: pd.DataFrame,
    ref_dir,
    seed: int,
    *,
    grid: Grid = 31,
    windows=SCORED,
    mags=MAGS,
    n_sims: int = N_SIMS,
    use_revealed: bool = True,
    regime: str | None = None,
    time_dep_mc: bool = True,
    mc_prior: float | None = None,
    c_range: tuple[float, float] = (1e-5, 1.0),
) -> tuple[dict, list[dict]]:
    """(version summary, rows per window x magnitude) for one official legacy-ETAS forecast."""
    par = f.model.parameters
    mc, b, mm = float(par["Mc"]), float(par["b"]), float(par["magMain"])
    # Legacy dataEnd = forecastStart = timeStart; events exist only up to the fetch (creation).
    end = min(f.time_start, f.creationTime)
    t0 = (f.time_start - origin_ms) / DAY_MS
    t, m = fetched_events(catalog, origin_ms, end, f.region)
    g = generic_etas(ref_dir, f.region.lat, f.region.lon, regime=regime)
    post = fit_legacy(
        t, m, mm, mc, b, g, t0, n=grid, time_dep_mc=time_dep_mc, mc_prior=mc_prior, c_range=c_range
    )
    rng = np.random.default_rng(seed)
    draws = sample_posterior(rng, post, n_sims)
    revealed = f.simulated_min_mag if use_revealed else None
    min_mag = (
        revealed
        if revealed is not None
        else legacy_min_mag(rng, *draws, mm, mc, b, g.mmax, t, m, t0, made_ms=f.creationTime)
    )
    sel = m >= min_mag
    wins = [f.window(w) for w in windows]
    spans = [((w.timeStart - origin_ms) / DAY_MS, (w.timeEnd - origin_ms) / DAY_MS) for w in wins]
    thr = tuple(max(x, min_mag) for x in mags)
    counts, capped = simulate_chunked(
        rng, *draws, mm, mc, b, g.mmax, t[sel], m[sel], min_mag, t0, spans, thr
    )
    sd = {}
    w = post.weight
    for k, grid_k, axis in (("ams", post.ams, 0), ("a", post.a, 1), ("p", post.p, 2)):
        marg = w.sum(axis=tuple(i for i in range(4) if i != axis))
        mean = float(np.sum(marg * grid_k))
        sd[k] = float(np.sqrt(np.sum(marg * (grid_k - mean) ** 2)))
    lc = np.log10(post.c)
    marg = w.sum(axis=(0, 1, 2))
    sd["log10c"] = float(np.sqrt(np.sum(marg * (lc - np.sum(marg * lc)) ** 2)))
    summary = {
        "n_fit_events": post.n_events,
        "n_seeds": int(sel.sum()),
        "min_mag": float(min_mag),
        "min_mag_source": "official" if revealed is not None else "rule",
        "map_ams": post.map[0],
        "map_a": post.map[1],
        "map_p": post.map[2],
        "map_c": post.map[3],
        **{f"sd_{k}": v for k, v in sd.items()},
        "capped_frac": float(capped.mean()),
    }
    rows = []
    levels = f.fractileProbabilities
    for i, win in enumerate(wins):
        for j, mag in enumerate(mags):
            try:
                official = win.bin(mag)
            except KeyError:
                continue
            n = counts[:, i, j]
            ours = legacy_fractile_values(n, b, mag, min_mag, levels)
            rows.append(
                {
                    "window": win.label,
                    "mag": mag,
                    "ours": np.floor(ours + 0.5).astype(int).tolist(),
                    "official": list(official.fractileValues),
                    "p_ours": legacy_probability(n, b, mag, min_mag),
                    "p_official": official.probability,
                }
            )
    return summary, rows


def score_levels(ours, official, levels) -> float:
    """Mean |log((ours + 1) / (official + 1))| over the nine scoring levels (cf. log-QS)."""
    idx = [int(np.argmin(np.abs(np.asarray(levels) - lv))) for lv in LEVELS]
    o, r = np.asarray(ours, float)[idx], np.asarray(official, float)[idx]
    return float(np.mean(np.abs(np.log((o + 1.0) / (r + 1.0)))))


def run(
    data_dir,
    snapshot: str,
    *,
    catalog_kind: str = "asof",
    grid: Grid = 31,
    only=None,
    regime: str | None = None,
    time_dep_mc: bool = True,
    settings=None,
):
    """``settings``: optional callable (sequence id, days of the window start) -> emulate keyword
    arguments, for analyst settings identified per session (docs/adr/0010 section 4)."""
    """Emulate every valid, non-duplicate official legacy-ETAS version with two seeds."""
    from laf.generic_rj import REFERENCE_REL

    proc = data_dir / "processed" / snapshot
    ov = pd.read_parquet(proc / "oaf_versions.parquet")
    seqs = pd.read_parquet(proc / "sequences.parquet")
    cat = pd.read_parquet(proc / "catalog.parquet")
    ref = data_dir / REFERENCE_REL
    origins = dict(zip(seqs["sequence_id"], seqs["origin_ms"], strict=True))
    ends = dict(zip(seqs["sequence_id"], seqs["catalog_end_ms"], strict=True))
    v = ov[ov["valid"] & ~ov["duplicate"].astype(bool) & ov["model"].str.startswith("Epidemic")]
    # only versions whose data window lies inside the snapshot catalog
    data_end = np.minimum(v["time_start_ms"], v["creation_ms"])
    v = v[data_end <= v["sequence_id"].map(ends)]
    if only:
        v = v[v["sequence_id"].isin(only)]
    out_v, out_b = [], []
    for seq_id, group in v.groupby("sequence_id"):
        hind = cat[(cat["sequence_id"] == seq_id) & (cat["id"] != seq_id)]
        hist = load_versions(data_dir, hind["id"]) if catalog_kind == "asof" else None
        origin = int(origins[seq_id])
        for r in group.to_dict("records"):
            f, _ = parse_forecast_lenient(
                read_raw(data_dir, f"raw/oaf/{seq_id}/{r['update_ms']}.json")
            )
            c = as_of_or_hindsight(hist, hind, f.creationTime)[0] if hist is not None else hind
            key = f"{seq_id}@{r['update_ms']}"
            for rep in (0, 1):
                kw = {"grid": grid, "regime": regime, "time_dep_mc": time_dep_mc}
                if settings is not None:
                    kw.update(settings(seq_id, (f.time_start - origin) / DAY_MS))
                summ, rows = emulate(f, origin, c, ref, issue_seed(key) + 7919 * rep, **kw)
                base = {"sequence_id": seq_id, "update_ms": r["update_ms"], "rep": rep}
                if rep == 0:
                    pub = {k: float(f.model.parameters[k]) for k in ("ams", "a", "p", "c")}
                    out_v.append(
                        {
                            **base,
                            **summ,
                            **{f"pub_{k}": x for k, x in pub.items()},
                            "elapsed_days": (min(f.time_start, f.creationTime) - origin) / DAY_MS,
                        }
                    )
                out_b += [{**base, **x} for x in rows]
            print(key, f"minMag {summ['min_mag']}", flush=True)
    return pd.DataFrame(out_v), pd.DataFrame(out_b)


def compare(bins: pd.DataFrame, levels: list[float]) -> pd.DataFrame:
    """Per version x window x magnitude: discrepancy to the official forecast (seed 0) and the
    Monte Carlo null (seed 0 vs seed 1), both as mean |log ratio| over the nine levels."""
    key = ["sequence_id", "update_ms", "window", "mag"]
    a = bins[bins["rep"] == 0].set_index(key)
    b = bins[bins["rep"] == 1].set_index(key)
    rows = []
    for k, r in a.iterrows():
        assert isinstance(k, tuple)
        idx = [int(np.argmin(np.abs(np.asarray(levels) - lv))) for lv in LEVELS]
        o = np.asarray(r["official"], float)
        rows.append(
            {
                **dict(zip(key, k, strict=True)),
                "d_official": score_levels(r["ours"], r["official"], levels),
                "d_null": score_levels(r["ours"], b.loc[k, "ours"], levels),
                "median_ours": float(np.asarray(r["ours"], float)[idx[4]]),
                "median_official": float(o[idx[4]]),
                "p_ours": r["p_ours"],
                "p_official": r["p_official"],
                "p_null": b.loc[k, "p_ours"],
            }
        )
    return pd.DataFrame(rows)


# ---- synthetic recovery (simulation-based calibration of the port's own fit and forecast) ----


def synthetic_catalog(rng, ams, a, p, c, mag_main, mc, b, mmax, t_end):
    """Plain ETAS above Mc (timeDepMc off, alpha = min(b, 1), GR magnitudes capped at Mmax):
    the model the fit assumes. Returns event times (days) and magnitudes, time-sorted."""
    from laf.etas import omori_integral, omori_times

    alpha = min(b, 1.0)
    n = rng.poisson(
        10.0 ** (ams + alpha * (mag_main - mc)) * float(omori_integral(0.0, t_end, c, p))
    )
    t = omori_times(rng, np.zeros(n), np.full(n, t_end), c, p)
    m = np.minimum(mc - np.log10(rng.random(n)) / b, mmax)
    all_t, all_m = [t], [m]
    while t.size:
        k = rng.poisson(10.0 ** (a + alpha * (m - mc)) * omori_integral(0.0, t_end - t, c, p))
        pt = np.repeat(t, k)
        t = pt + omori_times(rng, np.zeros(pt.size), t_end - pt, c, p)
        m = np.minimum(mc - np.log10(rng.random(t.size)) / b, mmax)
        all_t.append(t)
        all_m.append(m)
    t, m = np.concatenate(all_t), np.concatenate(all_m)
    order = np.argsort(t)
    return t[order], m[order]


def _prior_draw(rng, g, mc, grids, t_end: float):
    """(ams, a, p, c) from the generic prior, inside the fit grid box and subcritical."""
    from laf.etas import omori_integral

    a0 = g.a0(mc)
    lo = [float(x.min()) for x in grids]
    hi = [float(x.max()) for x in grids]
    for _ in range(10_000):
        ams = rng.normal(a0, g.asig)
        a, p, lc = rng.multivariate_normal([a0, g.p, -2.5], g.cov())
        th = (ams, a, p, 10.0**lc)
        if not all(lo[i] <= th[i] <= hi[i] for i in range(4)):
            continue
        n = (
            10.0**a
            * float(omori_integral(0.0, t_end + 366.0, th[3], p))
            * g.b
            * math.log(10)
            * (g.mmax - mc)
        )
        if n < 1.0:
            return th
    raise RuntimeError("no subcritical prior draw")


def _marginal_cdf(post, k: int, x: float) -> float:
    """Posterior marginal CDF of parameter k at x, linear between grid nodes (log10 for c)."""
    grid = [post.ams, post.a, post.p, np.log10(post.c)][k]
    x = math.log10(x) if k == 3 else x
    w = post.weight.sum(axis=tuple(i for i in range(4) if i != k))
    cdf = np.cumsum(w) - 0.5 * w  # mass up to each node's centre
    return float(np.interp(x, grid, cdf, left=0.0, right=1.0))


def recovery_one(args) -> dict:
    """One synthetic sequence: fit at t_end, posterior ranks of the truth, and the PIT of the
    next week's M>=5 count under the port's posterior-predictive simulation."""
    from laf.etas import fit_legacy, legacy_grids, sample_posterior, simulate_chunked

    seed, g, mag_main, mc, t_end, n_pred = args
    rng = np.random.default_rng(seed)
    grids = legacy_grids(g, mc, 31)
    th = _prior_draw(rng, g, mc, grids, t_end)
    b = 1.0
    t, m = synthetic_catalog(rng, *th, mag_main, mc, b, g.mmax, t_end + 7.0)
    seen = t < t_end
    post = fit_legacy(t[seen], m[seen], mag_main, mc, b, g, t_end, n=31, time_dep_mc=False)
    future = (t >= t_end) & (t < t_end + 7.0) & (m >= 5.0)
    draws = sample_posterior(rng, post, n_pred)
    counts, _ = simulate_chunked(
        rng,
        *draws,
        mag_main,
        mc,
        b,
        g.mmax,
        t[seen],
        m[seen],
        mc,
        t_end,
        [(t_end, t_end + 7.0)],
        (5.0,),
    )
    y, n = int(future.sum()), counts[:, 0, 0]
    pit = float(np.mean(n < y) + rng.random() * np.mean(n == y))  # randomized PIT
    return {
        "seed": seed,
        "n_fit": post.n_events,
        "y_week_m5": y,
        "pit_week_m5": pit,
        **{
            f"rank_{k}": _marginal_cdf(post, i, th[i]) for i, k in enumerate(("ams", "a", "p", "c"))
        },
        **{f"true_{k}": th[i] for i, k in enumerate(("ams", "a", "p", "c"))},
    }


# ---- differential test against the USGS Java code (archived runs) ----


def java_catalog(path) -> pd.DataFrame:
    """Catalog file written for the USGS Java command line (times truncated to seconds)."""
    from datetime import UTC, datetime

    rows = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if line.strip() and not line.startswith("#"):
            y, mo, d, h, mi, s, lat, lon, dep, mag = line.split()
            t = datetime(int(y), int(mo), int(d), int(h), int(mi), int(float(s)), tzinfo=UTC)
            rows.append(
                {
                    "id": f"e{i}",
                    "time_ms": int(t.timestamp() * 1000),
                    "latitude": float(lat),
                    "longitude": float(lon),
                    "depth": float(dep),
                    "mag": float(mag),
                }
            )
    return pd.DataFrame(rows)


def java_differential(out_dir, ref_dir, seed: int = 20261021) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Port vs USGS Java on the Java runs' own inputs (runs/java_differential/out/<issue>/).

    Returns (fits: MAP and minMag per issue, cells: per window x magnitude discrepancy of the
    port to Java run 1 and of Java run 2 to run 1, the Java Monte Carlo null)."""
    import json
    import re

    fits, cells = [], []
    for issue in sorted(out_dir.glob("*@*")):
        runs = sorted(issue.glob("official_circle_run*"))
        meta = json.loads((runs[0] / "meta.json").read_text(encoding="utf-8"))
        js = [
            parse_forecast_lenient(next((r / "Forecasts").glob("*/*.json")).read_bytes())[0]
            for r in runs
        ]
        log = (runs[0] / "run.log").read_text(encoding="utf-8")
        java_map = [
            float(re.findall(rf"getMaxLikelihood_{k}\(\)=(\S+)", log)[-1])
            for k in ("ams", "a", "p", "c")
        ]
        summ, ours = emulate(
            js[0], meta["origin_used_ms"], java_catalog(runs[0] / "catalog.txt"), ref_dir, seed,
            grid=(51, 31, 31, 21), use_revealed=False,
        )  # fmt: skip
        port_map = [summ[f"map_{k}"] for k in ("ams", "a", "p", "c")]
        fits.append(
            {
                "issue": issue.name,
                "map_equal": bool(np.allclose(port_map, java_map, rtol=1e-9, atol=1e-12)),
                **{f"java_{k}": v for k, v in zip(("ams", "a", "p", "c"), java_map, strict=True)},
                **{f"port_{k}": v for k, v in zip(("ams", "a", "p", "c"), port_map, strict=True)},
                "min_mag_port": summ["min_mag"],
                "min_mag_source": summ["min_mag_source"],
                "min_mag_java": float(re.findall(r"minSimMag=(\S+)", log)[-1]),
                "n_fit_events": summ["n_fit_events"],
            }
        )
        levels = js[0].fractileProbabilities
        for r in ours:
            jb = [j.window(r["window"]).bin(r["mag"]) for j in js]
            cells.append(
                {
                    "issue": issue.name,
                    "window": r["window"],
                    "mag": r["mag"],
                    "d_port_java": score_levels(r["ours"], jb[0].fractileValues, levels),
                    "d_java_java": score_levels(jb[1].fractileValues, jb[0].fractileValues, levels),
                    "p_port": r["p_ours"],
                    "p_java": jb[0].probability,
                    "p_java2": jb[1].probability,
                }
            )
    return pd.DataFrame(fits), pd.DataFrame(cells)


def recovery(ref_dir, n: int, t_ends=(1.0, 3.0, 7.0), workers: int = 8, n_pred: int = 2000):
    """Synthetic recovery over n sequences per fit time (SZ-GENERIC prior, M7.5, Mc 4.95)."""
    from concurrent.futures import ProcessPoolExecutor

    g = generic_etas(ref_dir, 7.587, -80.769)  # SZ-GENERIC (Panama hypocentre)
    jobs = [
        (20261021 + 100_000 * k + i, g, 7.5, 4.95, t, n_pred)
        for k, t in enumerate(t_ends)
        for i in range(n)
    ]
    with ProcessPoolExecutor(workers) as pool:
        rows = list(pool.map(recovery_one, jobs, chunksize=8))
    return pd.DataFrame(rows).assign(t_end=[j[4] for j in jobs])


# ---- sensitivity of the refit to fixed settings ----

VARIANTS = {
    "base": {},
    "seed2": {"_seed": 1},  # Monte Carlo null
    "grid21": {"grid": 21},
    "grid41": {"grid": 41},
    "sims30k": {"n_sims": 30_000},
    "mmax-0.5": {"mmax_shift": -0.5},
    "mmax+0.5": {"mmax_shift": 0.5},
    "noTDM": {"time_dep_mc": False},
    "minmag=Mc": {"_min_mag_mc": True},
}


def _sens_job(args):
    from laf.etas import MC_DEFAULT, forecast_item

    item, row, cat, ref, seed, name, kw = args
    kw = dict(kw)
    seed += 7919 * kw.pop("_seed", 0)
    if kw.pop("_min_mag_mc", False):
        has_oaf = row.get("oaf_mc") is not None and row["oaf_mc"] == row["oaf_mc"]
        kw["min_mag"] = float(row["oaf_mc"]) if has_oaf else MC_DEFAULT
    return [{**r, "variant": name} for r in forecast_item(item, row, cat, ref, seed, **kw)]


def sensitivity(data_dir, snapshot: str, workers: int = 8, variants=VARIANTS) -> pd.DataFrame:
    """Refit every benchmark item under each variant (hindsight catalog)."""
    from concurrent.futures import ProcessPoolExecutor

    from laf.generic_rj import REFERENCE_REL
    from laf.pilot import load_items

    proc = data_dir / "processed" / snapshot
    its = {
        r["issue_id"]: r for r in pd.read_parquet(proc / "issue_times.parquet").to_dict("records")
    }
    cats = pd.read_parquet(proc / "catalog.parquet")
    ref = data_dir / REFERENCE_REL
    jobs = []
    for item in load_items(data_dir, snapshot):
        cat = cats[cats["sequence_id"] == item.sequence_id]
        for name, kw in variants.items():
            jobs.append((item, its[item.item_id], cat, ref, issue_seed(item.item_id), name, kw))
    with ProcessPoolExecutor(workers) as pool:
        rows = [r for out in pool.map(_sens_job, jobs) for r in out]
    return pd.DataFrame(rows)


def sensitivity_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Per variant: discrepancy of the M>=5 quantiles to the base variant (mean |log ratio|
    over the nine levels, median and 90th percentile over cells) and max |dP(M>=6)|."""
    qcols = [f"q{round(lv * 1000):03d}" for lv in LEVELS]
    base = df[df["variant"] == "base"].set_index(["issue_id", "window"])
    out = []
    for name, g in df[df["variant"] != "base"].groupby("variant"):
        g = g.set_index(["issue_id", "window"])
        q, q0 = g[qcols].to_numpy(float), base.loc[g.index, qcols].to_numpy(float)
        d = np.mean(np.abs(np.log((q + 1.0) / (q0 + 1.0))), axis=1)
        dp = np.abs(g["p_m6"].to_numpy() - base.loc[g.index, "p_m6"].to_numpy())
        out.append(
            {
                "variant": name,
                "d_median": float(np.median(d)),
                "d_p90": float(np.quantile(d, 0.9)),
                "d_max": float(d.max()),
                "dp6_p90": float(np.quantile(dp, 0.9)),
                "dp6_max": float(dp.max()),
            }
        )
    return pd.DataFrame(out).sort_values("d_p90")


def decomposition(asof: pd.DataFrame, hind: pd.DataFrame, issue_times, fractiles) -> pd.DataFrame:
    """Outcome-free split of refit-vs-official differences on OAF issues: distance official to
    refit(as-of) (code and analyst settings), refit(as-of) to refit(hindsight) (catalog), and
    official to refit(hindsight) (both), as mean |log ratio| over the nine M>=5 levels."""
    qcols = [f"q{round(lv * 1000):03d}" for lv in LEVELS]
    f = fractiles[fractiles["magnitude"] == 5.0].set_index(
        ["sequence_id", "info_cutoff_ms", "window", "p"]
    )["count"]
    its = issue_times.set_index("issue_id")
    h = hind.set_index(["issue_id", "window"])
    rows = []
    for r in asof.to_dict("records"):
        issue, window = r["issue_id"], r["window"]
        it = its.loc[issue]
        off = [f.get((it["sequence_id"], it["issue_ms"], window, lv)) for lv in LEVELS]
        qa = np.array([r[c] for c in qcols], float)
        qh = h.loc[(issue, window), qcols].to_numpy(float)
        d = lambda x, y: float(np.mean(np.abs(np.log((x + 1.0) / (y + 1.0)))))  # noqa: E731
        row = {
            "issue_id": issue,
            "sequence_id": it["sequence_id"],
            "window": window,
            "d_asof_hind": d(qa, qh),
            "median_asof": qa[4],
            "median_hind": qh[4],
        }
        if all(x is not None for x in off):
            qo = np.asarray(off, float)
            row.update({"d_off_asof": d(qa, qo), "d_off_hind": d(qh, qo), "median_official": qo[4]})
        rows.append(row)
    return pd.DataFrame(rows)
