"""Temporal ETAS refit at each issue time, mirroring the USGS operational ETAS (docs/adr/0010).

Conventions: times in days after the mainshock; b = alpha = 1; no background. Productivity is
defined at the fit magnitude MREF: an event of magnitude m triggers direct aftershocks with
M >= MREF at rate 10^(a + (m - MREF)) * (t - t_i + c)^(-p); the mainshock at rate
10^(ams + (Mm - MREF)) * (t + c)^(-p). Catalog magnitudes are 0.1-binned, so "catalog M >= x"
corresponds to continuous m >= x - 0.05 in simulations (MREF = 4.95 is catalog M >= 5.0).
"""

import dataclasses
import math
import zlib
from dataclasses import dataclass

import numpy as np
from scipy import optimize, special

from laf.catalog import in_circle
from laf.oaf import Circle

MREF = 4.95
MSUP = 9.5
B = 1.0
LN10 = math.log(10.0)


def omori_integral(s0, s1, c, p):
    """Integral of (s + c)^(-p) ds from s0 to s1 (arrays broadcast, including c and p)."""
    s0, s1, c, p = (np.asarray(x, float) for x in (s0, s1, c, p))
    near1 = np.abs(p - 1.0) < 1e-9
    q = np.where(near1, 1.0, 1.0 - p)
    with np.errstate(divide="ignore", invalid="ignore"):
        power = ((s1 + c) ** q - (s0 + c) ** q) / q
    return np.where(near1, np.log((s1 + c) / (s0 + c)), power)


@dataclass(frozen=True)
class FitData:
    """Events visible at the information cutoff, split into likelihood targets and triggers."""

    mag_main: float
    t_c: float  # start of the likelihood window (catalog complete to MREF)
    t_end: float  # information cutoff
    t_trig: np.ndarray  # observed events with m >= MREF and 0 < t < t_end (triggers)
    m_trig: np.ndarray
    target: np.ndarray  # boolean mask over triggers: also a likelihood target (t >= t_c)


def kernel_terms(d: FitData, c: float, p: float):
    """Per-target mainshock kernel A_j and secondary sum S_j, and their window integrals.

    lambda(t_j) = K_ms * A_j + K_a * S_j and the integral of lambda over [t_c, t_end] is
    K_ms * IA + K_a * IS, with K_ms = 10^(ams + Mm - MREF) and K_a = 10^a.
    """
    t, w = d.t_trig, 10.0 ** (d.m_trig - MREF)
    tj = t[d.target]
    A = (tj + c) ** (-p)
    dt = tj[:, None] - t[None, :]
    with np.errstate(invalid="ignore", divide="ignore"):
        ker = np.where(dt > 0, (np.where(dt > 0, dt, 1.0) + c) ** (-p), 0.0)
    S = ker @ w
    IA = float(omori_integral(d.t_c, d.t_end, c, p))
    lo = np.maximum(d.t_c, t) - t
    IS = float(np.sum(w * omori_integral(lo, d.t_end - t, c, p)))
    return A, S, IA, IS


def log_likelihood(log10_kms, log10_ka, A, S, IA, IS):
    """Point-process log-likelihood on a grid of (K_ms, K_a); arrays broadcast elementwise."""
    kms, ka = 10.0 ** np.asarray(log10_kms, float), 10.0 ** np.asarray(log10_ka, float)
    lam = kms[..., None] * A + ka[..., None] * S
    with np.errstate(divide="ignore"):
        return np.log(lam).sum(axis=-1) - kms * IA - ka * IS


def gr_magnitudes(
    rng: np.random.Generator, n: int, mref: float = MREF, msup: float = MSUP
) -> np.ndarray:
    """Gutenberg-Richter magnitudes, b = B, truncated to [mref, msup]."""
    u = rng.random(n)
    return mref - np.log10(1.0 - u * (1.0 - 10.0 ** (-B * (msup - mref)))) / B


def omori_times(rng, s0, s1, c, p):
    """Inverse-CDF draws of s on [s0, s1] with density proportional to (s + c)^(-p)."""
    s0, s1, c, p = np.broadcast_arrays(*(np.asarray(x, float) for x in (s0, s1, c, p)))
    u = rng.random(s0.shape)
    near1 = np.abs(p - 1.0) < 1e-9
    q = np.where(near1, 1.0, 1.0 - p)
    lo, hi = (s0 + c) ** q, (s1 + c) ** q
    with np.errstate(invalid="ignore", divide="ignore"):
        power = (lo + u * (hi - lo)) ** (1.0 / q) - c
    return np.where(near1, (s0 + c) * ((s1 + c) / (s0 + c)) ** u - c, power)


@dataclass(frozen=True)
class Draw:
    ams: float
    a: float
    c: float
    p: float


def simulate_counts(
    rng: np.random.Generator,
    draws: list[Draw],
    mag_main: float,
    t_obs: np.ndarray,
    m_obs: np.ndarray,
    t0: float,
    windows: list[tuple[float, float]],
    thresholds: tuple[float, ...],
    max_events: int = 200_000,
    mref: float = MREF,
    msup: float = MSUP,
) -> tuple[np.ndarray, np.ndarray]:
    """Counts of simulated events per draw, window and catalog-magnitude threshold.

    Parents are the mainshock and the observed events (t < t0); simulation runs over
    [t0, max window end], all draws at once. Returns (counts[draw, window, threshold],
    capped[draw]); a capped draw stopped generating after max_events events.
    """
    nd = len(draws)
    ams = np.array([d.ams for d in draws])
    a = np.array([d.a for d in draws])
    c = np.array([d.c for d in draws])
    p = np.array([d.p for d in draws])
    t1 = max(e for _, e in windows)
    par_t = np.concatenate([[0.0], np.asarray(t_obs, float)])
    par_m = np.concatenate([[mag_main], np.asarray(m_obs, float)])
    s0 = np.maximum(t0 - par_t, 0.0)
    # Generation 0: children of the mainshock and the observed events, born in [t0, t1].
    lk = a[:, None] + par_m[None, :] - mref
    lk[:, 0] = ams + mag_main - mref
    expected = 10.0**lk * omori_integral(s0[None, :], (t1 - par_t)[None, :], c[:, None], p[:, None])
    n = rng.poisson(expected)
    draw = np.repeat(np.repeat(np.arange(nd), par_t.size), n.ravel())
    pt = np.repeat(np.tile(par_t, nd), n.ravel())
    ps0 = np.repeat(np.tile(s0, nd), n.ravel())
    t = pt + omori_times(rng, ps0, t1 - pt, c[draw], p[draw])
    m = gr_magnitudes(rng, t.size, mref, msup)
    all_d, all_t, all_m = [draw], [t], [m]
    total = np.bincount(draw, minlength=nd)
    while t.size:
        alive = total[draw] < max_events
        draw, t, m = draw[alive], t[alive], m[alive]
        expected = 10.0 ** (a[draw] + m - mref) * omori_integral(0.0, t1 - t, c[draw], p[draw])
        n = rng.poisson(expected)
        draw, pt = np.repeat(draw, n), np.repeat(t, n)
        t = pt + omori_times(rng, np.zeros_like(pt), t1 - pt, c[draw], p[draw])
        m = gr_magnitudes(rng, t.size, mref, msup)
        all_d.append(draw)
        all_t.append(t)
        all_m.append(m)
        total += np.bincount(draw, minlength=nd)
    dd, tt, mm = np.concatenate(all_d), np.concatenate(all_t), np.concatenate(all_m)
    counts = np.zeros((nd, len(windows), len(thresholds)), dtype=np.int64)
    for w, (ws, we) in enumerate(windows):
        inside = (tt >= ws) & (tt < we)
        for h, thr in enumerate(thresholds):
            counts[:, w, h] = np.bincount(dd[inside & (mm >= thr - 0.05)], minlength=nd)
    return counts, total >= max_events


DAY_MS = 86_400_000


def fit_data_for_issue(item, seq: dict, issue_catalog) -> FitData:
    """As-of data for one issue: observed M>=5 events after the mainshock and before the cutoff.

    `item` is a laf.items.Item, `seq` a row of sequences.parquet, `issue_catalog` the rows of
    issue_catalogs.parquet for this issue. t_c follows the USGS completeness model (ADR 0009).
    """
    from laf.generic_rj import MagComp

    origin = item.mainshock.origin_ms
    rows = issue_catalog[
        (issue_catalog["time_ms"] > origin)
        & (issue_catalog["time_ms"] < item.issue_ms)
        & (issue_catalog["mag"] >= MREF - 1e-6)
    ].sort_values("time_ms")
    t = (rows["time_ms"].to_numpy() - origin) / DAY_MS
    mc = MagComp(
        seq["magcomp_region"],
        seq["magcomp_mcat"],
        seq["magcomp_F"],
        seq["magcomp_G"],
        seq["magcomp_H"],
    )
    t_end = (item.issue_ms - origin) / DAY_MS
    t_c = min(mc.complete_after_days(item.mainshock.mag, MREF), t_end)
    return FitData(
        mag_main=item.mainshock.mag,
        t_c=t_c,
        t_end=t_end,
        t_trig=t,
        m_trig=rows["mag"].to_numpy(dtype=float),
        target=t >= t_c,
    )


# ---------------------------------------------------------------------------------------------
# Legacy USGS ETAS ("Epidemic-Type aftershock model (Bayesian Combination)"), the model behind
# the published international OAF products. Ported from opensha-oaf etas/ at 08a274bd; formulas
# and file:line references in docs/research/legacy-etas-formulas.md. Times in days.
# ---------------------------------------------------------------------------------------------

VDE_FILE = "etas/vdEGenericETASParams_080919.csv"
LEVELS = (0.025, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.975)
N_SIMS = 10_000  # legacy numberSimsParam
FORECAST_SPAN = 366.0  # forecastEnd = forecastStart + 366 (subcritical check)
MAX_RATE = 1e6  # Poisson-rate guard; draws reaching it also hit max_events and are flagged capped


@dataclass(frozen=True)
class GenericETAS:
    regime: str
    a: float
    asig: float
    p: float
    covpp: float
    covcc: float
    covap: float
    covac: float
    covcp: float
    nms: float
    b: float
    mref: float
    mmax: float

    def a0(self, mc: float) -> float:
        """Generic a and ams mean referenced to Mc (ETAS_AftershockModel_Generic.java:133)."""
        return self.a + math.log10((self.mmax - self.mref) / (self.mmax - mc))

    @property
    def p_sigma(self) -> float:
        return math.sqrt(self.covpp * self.nms)

    def cov(self) -> np.ndarray:
        n = self.nms
        return np.array(
            [
                [self.asig**2, n * self.covap, n * self.covac],
                [n * self.covap, n * self.covpp, n * self.covcp],
                [n * self.covac, n * self.covcp, n * self.covcc],
            ]
        )


def generic_etas(ref_dir, lat: float, lon: float, regime: str | None = None) -> GenericETAS:
    """Legacy generic ETAS parameters at a location (Garcia table, no California polygons), or
    for a named regime (an analyst's GUI override)."""
    import csv

    from laf.generic_rj import garcia_regime

    with (ref_dir / VDE_FILE).open(encoding="utf-8-sig") as f:
        rows = {r["regionName"].strip(): r for r in csv.DictReader(f)}
    regime = regime or garcia_regime(ref_dir, lat, lon)
    r = rows.get(regime) or rows["GLOBAL-AVERAGE"]
    num = {k: float(v) for k, v in r.items() if k != "regionName"}
    return GenericETAS(
        regime=r["regionName"].strip(),
        a=num["a"],
        asig=num["asig"],
        p=num["p"],
        covpp=num["covpp"],
        covcc=num["covcc"],
        covap=num["covap"],
        covac=num["covac"],
        covcp=num["covcp"],
        nms=num["Nms"],
        b=num["b"],
        mref=num["mref"],
        mmax=num["mmax"],
    )


def _round2(x: float) -> float:
    return math.floor(x * 100.0 + 0.5) / 100.0


def legacy_linspace(lo: float, hi: float, n: int) -> np.ndarray:
    return lo + np.arange(n) * (hi - lo) / (n - 1)


def legacy_logspace(lo: float, hi: float, n: int) -> np.ndarray:
    """ETAS_StatsCalc logspace: step (log hi - log lo)/n, last point forced to hi."""
    x = 10.0 ** (math.log10(lo) + np.arange(n) * (math.log10(hi) - math.log10(lo)) / n)
    x[-1] = hi
    return x


Grid = int | tuple[int, int, int, int]  # points for (ams, a, p, c); GUI 31 each, CLI (51,31,31,21)


def legacy_grids(
    g: GenericETAS, mc: float, n: Grid = 31, c_range: tuple[float, float] = (1e-5, 1.0)
):
    """Fit grids (GUI updateParameterGenericRanges, GUI:7162-7194)."""
    n_ams, n_a, n_p, n_c = (n, n, n, n) if isinstance(n, int) else n
    a0, sp = g.a0(mc), g.p_sigma
    lo, hi = _round2(a0 - 4 * g.asig), _round2(a0 + 4 * g.asig)
    ams, a = legacy_linspace(lo, hi, n_ams), legacy_linspace(lo, hi, n_a)
    p = legacy_linspace(_round2(max(0.1, g.p - 4 * sp)), _round2(g.p + 4 * sp), n_p)
    c = legacy_logspace(c_range[0], c_range[1], n_c)
    return ams, a, p, c


def legacy_terms(t, m, mag_main, mc, c0, p, ac, t_end, alpha, time_dep_mc: bool = True):
    """Kernel sums; with timeDepMc (GUI default on) c grows with magnitude, else c = c0
    (SequenceSpecific:290-338)."""
    k = 10.0 ** (alpha * (m - mc))
    k_ms = 10.0 ** (alpha * (mag_main - mc))
    if time_dep_mc:
        ci = c0 * (10.0**ac * k) ** (1.0 / p)
        c_ms = c0 * (10.0**ac * k_ms) ** (1.0 / p)
    else:
        ci, c_ms = np.full_like(k, c0), c0
    A = k_ms * (t + c_ms) ** (-p)
    dt = t[:, None] - t[None, :]
    with np.errstate(invalid="ignore", divide="ignore"):
        ker = np.where(dt > 0, (np.where(dt > 0, dt, 1.0) + ci[None, :]) ** (-p), 0.0)
    S = ker @ k
    IA = k_ms * float(omori_integral(0.0, t_end, c_ms, p))
    IS = float(np.sum(k * omori_integral(0.0, t_end - t, ci, p)))
    return A, S, IA, IS


@dataclass
class Posterior:
    ams: np.ndarray
    a: np.ndarray
    p: np.ndarray
    c: np.ndarray
    weight: np.ndarray  # [ams, a, p, c], sums to 1; zero off the subcritical set
    map: tuple[float, float, float, float]  # (ams, a, p, c) maximizing log posterior
    ac: float
    n_events: int


def _log_prior(g: GenericETAS, mc: float, ams, a, p, c) -> np.ndarray:
    a0 = g.a0(mc)
    x = np.stack(np.broadcast_arrays(a - a0, p - g.p, np.log10(c) + 2.5), axis=-1)
    q = np.einsum("...i,ij,...j->...", x, np.linalg.inv(g.cov()), x)
    return -0.5 * q - 0.5 * ((ams - a0) / g.asig) ** 2


def fit_legacy(
    t,
    m,
    mag_main: float,
    mc: float,
    b: float,
    g: GenericETAS,
    t_end: float,
    n: Grid = 31,
    time_dep_mc: bool = True,
    mc_prior: float | None = None,
    c_range: tuple[float, float] = (1e-5, 1.0),
) -> Posterior:
    """Bayesian grid fit (ETAS_AftershockModel_SequenceSpecific): two passes with timeDepMc,
    one without. ``mc_prior``: the Mc at which the GUI last set the prior and grid ranges, when
    an analyst changed Mc afterwards (default: the fit Mc)."""
    mcp = mc if mc_prior is None else mc_prior
    alpha = min(b, 1.0)
    keep = m >= mc - 1e-6
    t, m = np.asarray(t, float)[keep], np.asarray(m, float)[keep]
    ams_g, a_g, p_g, c_g = legacy_grids(g, mcp, n, c_range)
    AM, AA, PP, CC = np.meshgrid(ams_g, a_g, p_g, c_g, indexing="ij")
    prior = _log_prior(g, mcp, AM, AA, PP, CC)
    lp = np.empty_like(prior)
    if abs(alpha - b) < 1e-12:
        mag_term = b * LN10 * (g.mmax - mc)
    else:
        mag_term = b / (alpha - b) * (10.0 ** ((alpha - b) * (g.mmax - mc)) - 1.0)

    def one_pass(ac: float):
        for ip, pv in enumerate(p_g):
            for ic, cv in enumerate(c_g):
                A, S, IA, IS = legacy_terms(
                    t, m, mag_main, mc, cv, pv, ac, t_end, alpha, time_dep_mc
                )
                lp[:, :, ip, ic] = log_likelihood(ams_g[:, None], a_g[None, :], A, S, IA, IS)
        c_star = CC * 10.0 ** (ac / PP) if time_dep_mc else CC
        integral = omori_integral(0.0, t_end + FORECAST_SPAN, c_star, PP)
        sub = 10.0**AA * integral * mag_term < 1.0  # subcritical nodes only
        lp_sub = np.where(sub, lp + prior, -np.inf)
        i = np.unravel_index(int(np.argmax(lp_sub)), lp_sub.shape)
        best = (float(ams_g[i[0]]), float(a_g[i[1]]), float(p_g[i[2]]), float(c_g[i[3]]))
        return lp_sub, best

    # Pass 1 with ac = generic mean, pass 2 with ac = pass-1 MAP ams (SequenceSpecific :137-141).
    ac = g.a0(mcp)
    lp_sub, best = one_pass(ac)
    if time_dep_mc:
        ac = best[0]
        lp_sub, best = one_pass(ac)
    rel = lp_sub - lp_sub.max()
    w = np.where(rel < -20.0, 0.0, np.exp(rel))
    return Posterior(ams_g, a_g, p_g, c_g, w / w.sum(), best, ac, int(t.size))


def sample_posterior(rng, post: Posterior, k: int = N_SIMS):
    idx = rng.choice(post.weight.size, size=k, p=post.weight.ravel())
    i_ams, i_a, i_p, i_c = np.unravel_index(idx, post.weight.shape)
    return post.ams[i_ams], post.a[i_a], post.p[i_p], post.c[i_c]


def simulate_legacy(
    rng,
    ams,
    a,
    p,
    c,
    mag_main,
    mc,
    b,
    mmax,
    seed_t,
    seed_m,
    min_mag,
    t0,
    windows,
    thresholds,
    max_events: int = 500_000,
):
    """Legacy forward simulation (etas/ETAScatalog). Counts[draw, window, threshold], capped."""
    ams, a, p, c = (np.asarray(x, float) for x in (ams, a, p, c))
    nd, alpha = a.size, min(b, 1.0)
    a1 = a + math.log10((mmax - mc) / (mmax - min_mag))  # a' (generation 0 and >= 2 parents)
    t1 = max(e for _, e in windows)
    par_t = np.concatenate([[0.0], seed_t])
    s0 = np.maximum(t0 - par_t, 0.0)
    lk = a1[:, None] + alpha * (np.asarray(seed_m, float)[None, :] - min_mag)
    lk_ms = a1 + alpha * (mag_main + (ams - a) - min_mag)  # mainshock seeded at Mms + (ams - a)
    lk = np.concatenate([lk_ms[:, None], lk], axis=1)
    expected = 10.0**lk * omori_integral(s0[None, :], (t1 - par_t)[None, :], c[:, None], p[:, None])
    cnt = rng.poisson(np.minimum(expected, MAX_RATE)).ravel()
    draw = np.repeat(np.repeat(np.arange(nd), par_t.size), cnt)
    pt = np.repeat(np.tile(par_t, nd), cnt)
    ps0 = np.repeat(np.tile(s0, nd), cnt)

    def mags(k):
        return np.minimum(min_mag - np.log10(rng.random(k)) / b, mmax)

    t = pt + omori_times(rng, ps0, t1 - pt, c[draw], p[draw])
    m = mags(t.size)
    all_d, all_t, all_m = [draw], [t], [m]
    total, gen = np.bincount(draw, minlength=nd), 1
    while t.size:
        alive = total[draw] < max_events
        draw, t, m = draw[alive], t[alive], m[alive]
        prod = a if gen == 1 else a1  # quirk: generation-1 parents use the uncorrected a
        expected = 10.0 ** (prod[draw] + alpha * (m - min_mag)) * omori_integral(
            0.0, t1 - t, c[draw], p[draw]
        )
        cnt = rng.poisson(np.minimum(expected, MAX_RATE))
        draw, pt = np.repeat(draw, cnt), np.repeat(t, cnt)
        t = pt + omori_times(rng, np.zeros_like(pt), t1 - pt, c[draw], p[draw])
        m = mags(t.size)
        all_d.append(draw)
        all_t.append(t)
        all_m.append(m)
        total += np.bincount(draw, minlength=nd)
        gen += 1
    dd, tt, mm = np.concatenate(all_d), np.concatenate(all_t), np.concatenate(all_m)
    counts = np.zeros((nd, len(windows), len(thresholds)), dtype=np.int64)
    for w, (ws, we) in enumerate(windows):
        inside = (tt >= ws) & (tt < we)
        for h, thr in enumerate(thresholds):
            counts[:, w, h] = np.bincount(dd[inside & (mm >= thr)], minlength=nd)
    return counts, total >= max_events


# The legacy code changed its minimum simulated magnitude rule in commit 08a274bd
# (2026-10-14 19:21:40 UTC, ETAS_AftershockModel.generateStochasticCatalog):
#   before: start at 3.0; calibrate with 100 catalogs over the whole forecast (366 d)
#   after:  start at max(Mms, aftershock magnitudes) - 4; calibrate over 1 day
# In both, minMag drops by 1 until all 100 calibration catalogs contain an event (floor -3).
# With alpha = 1 and b > 1 the simulated M>=5 count depends on minMag, so the rule in force
# when a forecast was made matters (docs/adr/0010 section 3.5).
MIN_MAG_RULE_CHANGE_MS = 1_792_005_700_000


def simulate_chunked(rng, ams, a, p, c, *args, chunk: int = 500, **kwargs):
    """simulate_legacy over draws in chunks, to bound memory when minMag is low."""
    parts = [
        simulate_legacy(
            rng,
            ams[i : i + chunk],
            a[i : i + chunk],
            p[i : i + chunk],
            c[i : i + chunk],
            *args,
            **kwargs,
        )
        for i in range(0, len(a), chunk)
    ]
    return np.concatenate([x for x, _ in parts]), np.concatenate([y for _, y in parts])


def legacy_min_mag(
    rng, ams, a, p, c, mag_main, mc, b, mmax, seed_t, seed_m, t0, made_ms: int
) -> float:
    """Minimum simulated magnitude under the rule in force at `made_ms` (epoch ms)."""
    if made_ms < MIN_MAG_RULE_CHANGE_MS:
        mm, span = 3.0, FORECAST_SPAN
    else:
        observed = seed_m[seed_m >= mc - 1e-6]
        mm, span = max([mag_main, *observed.tolist()]) - 4.0, 1.0
    while mm > -3.0:
        sel = seed_m >= mm
        counts, _ = simulate_chunked(
            rng,
            ams[:100],
            a[:100],
            p[:100],
            c[:100],
            mag_main,
            mc,
            b,
            mmax,
            seed_t[sel],
            seed_m[sel],
            mm,
            t0,
            [(t0, t0 + span)],
            (-10.0,),
        )
        if (counts[:, 0, 0] > 0).all():
            return mm
        mm -= 1.0
    return mm


SEED = 20261021
MC_DEFAULT, B_DEFAULT = 4.95, 1.0


def issue_seed(issue_id: str) -> int:
    """Per-issue seed, independent of which other items a snapshot holds (ADR 0010 section 3.7)."""
    return SEED + zlib.crc32(issue_id.encode())


MAX_FETCHED = 1000  # legacy maxCatalogNumberParam (GUI:2015-2021): ties at the cut are kept


def fetched_events(
    cat, origin_ms: int, cutoff_ms: int, circle: Circle
) -> tuple[np.ndarray, np.ndarray]:
    """Events in the forecast circle after the mainshock and before the cutoff.

    The legacy code fetches the forecast region and keeps the 1,000 largest; the circle is also
    what the LLM sees (ADR 0010 section 3.2).
    """
    rows = cat[(cat["time_ms"] > origin_ms) & (cat["time_ms"] < cutoff_ms) & in_circle(cat, circle)]
    if len(rows) > MAX_FETCHED:  # legacy keeps every event at or above the 1,000th magnitude
        rows = rows[rows["mag"] >= rows["mag"].nlargest(MAX_FETCHED).iloc[-1]]
    rows = rows.sort_values("time_ms")
    t = (rows["time_ms"].to_numpy() - origin_ms) / DAY_MS
    return t, rows["mag"].to_numpy(dtype=float)


def _poisson_quantile(lam: float, fractile: float) -> float:
    """Continuous Poisson quantile: x in [0, 20] with Q(x, lam) = fractile (legacy poissQuantile).

    Q increases in x, so the legacy minimisation of |fractile - Q| is this root, clamped. For
    lam = 0 the legacy objective is flat and its answer arbitrary; 0 is returned.
    """
    if lam <= 0.0:
        return 0.0
    f = lambda x: special.gammaincc(x, lam) - fractile  # noqa: E731
    lo, hi = 1e-12, 20.0
    if f(lo) >= 0.0:
        return 0.0
    if f(hi) <= 0.0:
        return hi
    root: float = optimize.brentq(f, lo, hi, xtol=1e-9)  # type: ignore[assignment]  # stub: full_output tuple
    return root


def legacy_fractiles(n: np.ndarray, b: float, mag: float, min_mag: float) -> np.ndarray:
    """Count fractiles at LEVELS for M >= mag, from simulated counts n of M >= min_mag.

    At or above the simulated minimum: the discrete fractiles. Below it (Kamchatka 2025, minMag
    5.8), the legacy code reports 10^(b (minMag - mag)) times the discrete fractile, replacing a
    fractile <= 1 by a continuous Poisson quantile whose rate comes from the probability of the
    smallest simulated count (ETAS_AftershockModel.scaledNumDistributionFunc, 8b8dfbedcb). The
    published values are rounded to integers.
    """
    q = np.quantile(n, LEVELS, method="inverted_cdf")
    if mag >= min_mag:
        return q.astype(int)
    lam = -math.log(float(np.mean(n == n.min())))  # legacy num_DistributionFunc.getY(0)
    q = np.array(
        [_poisson_quantile(lam, f) if v <= 1 else v for f, v in zip(LEVELS, q, strict=True)]
    )
    return np.floor(10.0 ** (b * (min_mag - mag)) * q + 0.5).astype(int)


def _summaries(counts: np.ndarray, windows, keys, b: float, min_mag: float) -> list[dict]:
    """Per-window M>=5 fractiles, mean and histogram, and P(M>=6).

    counts[:, w, 0] counts M >= max(5, minMag); below minMag the histogram is of the scaled
    counts round(10^(b (minMag - 5)) n), the distribution the legacy fractiles summarise.
    """
    scale = 10.0 ** (b * max(min_mag - 5.0, 0.0))
    out = []
    for w, key in enumerate(keys):
        n5, n6 = counts[:, w, 0], counts[:, w, 1]
        q = legacy_fractiles(n5, b, 5.0, min_mag)
        out.append(
            {
                "window": key,
                "time_start_ms": windows[w][0],
                "time_end_ms": windows[w][1],
                **{f"q{round(lv * 1000):03d}": int(v) for lv, v in zip(LEVELS, q, strict=True)},
                "mean_m5": float(scale * n5.mean()),
                "p_m6": float((n6 >= 1).mean()),
                "hist_m5": np.bincount(np.floor(scale * n5 + 0.5).astype(int)).tolist(),
            }
        )
    return out


def _thresholds(min_mag: float) -> tuple[float, float]:
    if min_mag > 6.0:  # P(M>=6) would need the legacy below-minMag probability; never seen
        raise ValueError(f"simulated minimum magnitude {min_mag} above 6")
    return max(5.0, min_mag), 6.0


def _circle(it_row: dict) -> Circle:
    return Circle(it_row["region_lat"], it_row["region_lon"], it_row["region_radius_km"])


def _min_mag(rng, it_row: dict, draws, mag_main, mc, b, mmax, t, m, t0, made_ms: int):
    """(minMag, source): the matched official version's own simulated minimum where its
    fractiles reveal one (oaf_sim_min_mag), else the legacy rule in force at made_ms."""
    revealed = it_row.get("oaf_sim_min_mag")
    if revealed is not None and not np.isnan(revealed):
        return float(revealed), "official"
    ams, a, p, c = draws
    return legacy_min_mag(
        rng, ams, a, p, c, mag_main, mc, b, mmax, t, m, t0, made_ms=made_ms
    ), "rule"


def load_analyst_settings(path) -> list[dict]:
    """Rules of config/analyst_settings.toml (inferred analyst settings, ADR 0010 section 4.1)."""
    import tomllib

    with open(path, "rb") as f:
        return tomllib.load(f).get("rule", [])


def analyst_kwargs(rules: list[dict], sequence_id: str, version_days: float | None) -> dict:
    """forecast_item keyword arguments for an issue whose matched official version starts its
    windows ``version_days`` after the mainshock; {} when no rule applies."""
    if version_days is None:
        return {}
    for r in rules:
        if r["sequence"] == sequence_id and r["from_days"] <= version_days < r["to_days"]:
            kw: dict = {"regime": r["regime"], "time_dep_mc": r.get("time_dep_mc", True)}
            if "c_fixed" in r:
                kw.update(c_range=(r["c_fixed"], r["c_fixed"]), grid=(31, 31, 31, 1))
            return kw
    return {}


def forecast_item(
    item,
    it_row: dict,
    cat,
    ref_dir,
    seed: int,
    *,
    grid: Grid = 31,
    n_sims: int = N_SIMS,
    time_dep_mc: bool = True,
    mmax_shift: float = 0.0,
    min_mag: float | None = None,
    regime: str | None = None,
    c_range: tuple[float, float] = (1e-5, 1.0),
) -> list[dict]:
    """Legacy-ETAS refit forecast for one benchmark item (ADR 0010). The keyword arguments
    are for sensitivity analyses; the defaults are the registered refit."""
    origin, cutoff = item.mainshock.origin_ms, item.issue_ms
    mm = item.mainshock.mag
    has_oaf = it_row.get("oaf_mc") is not None and not np.isnan(it_row["oaf_mc"])
    mc = float(it_row["oaf_mc"]) if has_oaf else MC_DEFAULT
    b = float(it_row["oaf_b"]) if has_oaf else B_DEFAULT
    t, m = fetched_events(cat, origin, cutoff, _circle(it_row))
    t0 = (cutoff - origin) / DAY_MS
    g = generic_etas(ref_dir, item.mainshock.lat, item.mainshock.lon, regime=regime)
    if mmax_shift:
        g = dataclasses.replace(g, mmax=g.mmax + mmax_shift)
    post = fit_legacy(t, m, mm, mc, b, g, t0, n=grid, time_dep_mc=time_dep_mc, c_range=c_range)
    rng = np.random.default_rng(seed)
    draws = sample_posterior(rng, post, n_sims)
    if min_mag is None:
        min_mag, source = _min_mag(rng, it_row, draws, mm, mc, b, g.mmax, t, m, t0, made_ms=cutoff)
    else:
        source = "override"
    sel = m >= min_mag
    windows = [((w.start_ms - origin) / DAY_MS, (w.end_ms - origin) / DAY_MS) for w in item.windows]
    counts, capped = simulate_chunked(
        rng, *draws, mm, mc, b, g.mmax, t[sel], m[sel], min_mag, t0, windows, _thresholds(min_mag)
    )
    info = {
        "issue_id": item.item_id,
        "sequence_id": item.sequence_id,
        "mc": mc,
        "b": b,
        "regime": g.regime,
        "min_mag": min_mag,
        "min_mag_source": source,
        "n_fit_events": post.n_events,
        "ac": post.ac,
        "map_ams": post.map[0],
        "map_a": post.map[1],
        "map_p": post.map[2],
        "map_c": post.map[3],
        "post_mean_a": float(np.mean(draws[1])),
        "post_mean_p": float(np.mean(draws[2])),
        "capped_frac": float(capped.mean()),
        "n_sims": n_sims,
        "seed": seed,
    }
    ms_windows = [(w.start_ms, w.end_ms) for w in item.windows]
    rows = _summaries(counts, ms_windows, [w.label for w in item.windows], b, min_mag)
    return [{**info, **r} for r in rows]


def resimulate_published(item, it_row: dict, cat, ref_dir, seed: int) -> list[dict]:
    """V2: simulate an official version from its own published parameters (MAP only)."""
    origin, cutoff = item.mainshock.origin_ms, item.issue_ms
    mm, mc, b = item.mainshock.mag, float(it_row["oaf_mc"]), float(it_row["oaf_b"])
    draws = tuple(np.full(N_SIMS, float(it_row[f"oaf_{k}"])) for k in ("ams", "a", "p", "c"))
    t, m = fetched_events(cat, origin, cutoff, _circle(it_row))
    t0 = (cutoff - origin) / DAY_MS
    g = generic_etas(ref_dir, item.mainshock.lat, item.mainshock.lon)
    rng = np.random.default_rng(seed)
    made = int(it_row["creation_ms"])  # rule in force when the official forecast was made
    min_mag, source = _min_mag(rng, it_row, draws, mm, mc, b, g.mmax, t, m, t0, made_ms=made)
    sel = m >= min_mag
    windows = [((w.start_ms - origin) / DAY_MS, (w.end_ms - origin) / DAY_MS) for w in item.windows]
    counts, _ = simulate_chunked(
        rng, *draws, mm, mc, b, g.mmax, t[sel], m[sel], min_mag, t0, windows, _thresholds(min_mag)
    )
    ms_windows = [(w.start_ms, w.end_ms) for w in item.windows]
    rows = _summaries(counts, ms_windows, [w.label for w in item.windows], b, min_mag)
    return [
        {"issue_id": item.item_id, "min_mag": min_mag, "min_mag_source": source, **r} for r in rows
    ]


# V2 acceptance (ADR 0010 sections 4 and 6): per (version, window) pair, the M>=5 median of the
# re-simulation against the official one; the run passes when at least V2_PASS of pairs do, and
# the hindsight effect is reported for sequences whose own pass rate is at least V2_PASS.
V2_RATIO = (0.75, 1 / 0.75)  # bounds on (ours + 1) / (official + 1), inclusive
V2_PASS = 0.80


def v2_evaluate(val, issue_times, fractiles, sequences):
    """V2 rows joined to the official M>=5 fractiles (2.5/50/97.5%), with ratio and ok."""
    f = fractiles[fractiles["magnitude"] == 5.0].set_index(
        ["sequence_id", "info_cutoff_ms", "window", "p"]
    )["count"]
    v = val.merge(issue_times[["issue_id", "sequence_id", "issue_ms"]], on="issue_id")
    for p, col in ((0.025, "off_q025"), (0.5, "off_q500"), (0.975, "off_q975")):
        v[col] = [f.get((r.sequence_id, r.issue_ms, r.window, p)) for r in v.itertuples()]
    if v["off_q500"].isna().any():
        raise ValueError("V2 pair without an official M>=5 median")
    v["ratio"] = (v["q500"] + 1) / (v["off_q500"] + 1)
    v["ok"] = v["ratio"].between(*V2_RATIO)
    return v.merge(sequences[["sequence_id", "name"]], on="sequence_id")


def v2_decision(v) -> tuple[float, dict[str, float], list[str]]:
    """(overall pass rate, pass rate by sequence name, sequences eligible for the hindsight
    effect)."""
    by_seq = v.groupby("name")["ok"].mean()
    return float(v["ok"].mean()), by_seq.to_dict(), sorted(by_seq[by_seq >= V2_PASS].index)
