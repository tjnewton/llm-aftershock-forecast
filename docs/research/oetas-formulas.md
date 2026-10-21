# OAF operational ETAS (oetas): exact formulas for a Python re-implementation

Source: `opensha/opensha-oaf` @ `08a274bde278b9de12f58a34e7f4ca8d397d0cb6` (read-only).
Path prefixes: `oetas/` = `src/main/java/org/opensha/oaf/oetas/`, `res/` = `src/main/resources/org/opensha/oaf/`.
Notation: `ln10 = 2.302585092994046`, `beta = b*ln10`, `v = ln10*(alpha - b)`, `W(x) = (exp(x)-1)/x` (W(0)=1),
`I(p,c,t1,t2) = Integral_{t1}^{t2} (t+c)^-p dt`. Production has b fixed at 1.0 and alpha = b, so v = 0 and all W(.) = 1.

**Key finding for Q7:** the published `forecast.json` with `"name": "Epidemic-Type aftershock model (Bayesian Combination)"`
and `parameters {ams, a, b, magMain, p, c, Mc}` (e.g. `data/raw/oaf/us6000qw60/*.json`) is NOT written by oetas. It is written
by the legacy van der Elst ETAS GUI code `src/main/java/org/opensha/oaf/etas/GraphicalForecast.java:840-848`. See section 7.

## 1. Relative zams, branch ratio, Q

`OEStatsCalc.calc_ten_a_q_from_branch_ratio(n,p,c,b,alpha,mref,mag_min,mag_max,tint)` (`oetas/OEStatsCalc.java:499`):

    (10^a)*Q = n * exp(v*(mref - mag_min)) / ( W(v*(mag_max-mag_min)) * (mag_max-mag_min) * b*ln10 * I(p,c,0,tint) )
    alpha == b:  (10^a)*Q = n / ( (mag_max-mag_min) * b*ln10 * I(p,c,0,tint) )          # mref and msup drop out

`calc_branch_ratio(a,p,c,b,alpha,mref,msup,tint)` (`:261`): `n = b*ln10 * 10^a * (msup-mref) * W(v*(msup-mref)) * I(p,c,0,tint)`.
`calc_inv_branch_ratio` (`:364`) is its inverse: `a = log10(n / (b*ln10*I*(msup-mref)*W(v*(msup-mref))))`.
Q correction (`calc_q_correction`, `:714`; comment `:100`):

    Q = exp(v*(mref - mag_min)) * W(v*(msup-mref))*(msup-mref) / ( W(v*(mag_max-mag_min))*(mag_max-mag_min) )
    alpha == b:  Q = (msup - mref)/(mag_max - mag_min)

Corrected productivity of a source of magnitude m0 (`calc_k_corr`, `:134`): `k = 10^(a + alpha*(m0-mref)) * Q`.
`I` is `OERandomGenerator.omori_rate` (`oetas/OERandomGenerator.java:377`): `w=t1+c; q=1-p; A=log1p((t2-t1)/w);`
`I = w^q * A` if `|A*q|<1e-15` else `w^q*expm1(A*q)/q`.

`calc_zams_from_br(n,p,c,b,alpha,mag_min,mag_max,tint)` (`:938`) = `log10(calc_ten_a_q_from_branch_ratio(..., mref=ZAMS_MREF=0.0, ...))`.
`OEBayPriorParams.calc_abs_to_rel_zams_offset(n,p,c,b,alpha)` (`oetas/bay/OEBayPriorParams.java:300-358`):
returns `-calc_zams_from_br(n,p,c,b,alpha, mag_min, mag_max, tint_br)` if `relative_zams` is false, else `0.0`.
`calc_rel_to_abs_zams_offset` (`:223`, duplicated in `oetas/fit/OEDisc2InitFitInfo.java:407`) returns `+calc_zams_from_br(...)` if relative, else 0.
No mref/msup are used (mref drops out; the commented-out old path used mref then converted to ZAMS_MREF).
Inputs: `mag_min, mag_max, tint_br` come from `OEDisc2InitFitInfo.make_bay_prior_params()` (`fit/OEDisc2InitFitInfo.java:628`),
i.e. the fitter's `mag_min` (= history magCat), `mag_max` (fit mag top) and `tint_br` (section 2).

Meaning (production `relative_zams: true`, grid zams values ARE relative):

    zams_abs = zams_rel + calc_zams_from_br(n,p,c,b,alpha,mag_min,mag_max,tint_br)        # zams at ZAMS_MREF = 0
    ams(mref) = zams_abs + (alpha-b)*(mref - 0)        (calc_ams_from_zams, OEStatsCalc.java:853/802)
    (10^ams)*Q_ms = 10^ams(mref), Q_ms = 1             (calc_ten_ams_q_from_zams, OEDisc2InitFitInfo.java:374)
    => zams_rel = ams(mref) - log10((10^a)*Q at the same mref)   for any common mref

So zams_rel = 0 means "mainshock as productive as an aftershock of the same magnitude"; zams_rel = log10(k_mainshock / k_aftershock at equal M).
Mainshock productivity: `k_ms = 10^(ams + alpha*(M - mref))` (no Q). Used in `OEDisc2InitStatVox.calc_likelihood` (`fit/OEDisc2InitStatVox.java:605-674`).
Sanity value (my evaluation of the formulas): n=0.5, p=1.08, c=10^-2.6, b=alpha=1, mag_min=4.6, mag_max=9.0, tint=365 gives offset = -2.3995.

## 2. Production magnitudes / times (DEFAULT regime in `res/oetas/env/EtasConfig.json`; other regimes set all `*_avail=false`, inherit)

- `mref = DEF_MREF = 3.0`, `msup = DEF_MSUP = 9.5` (`oetas/OEConstants.java:671,675`), set in `OEtasParameters.get_fmag_range` (`oetas/env/OEtasParameters.java:971`).
- `mag_min = hist_magCat` (history magnitude of completeness, see below); same value is the min simulation magnitude for the prototype catalog.
- `mag_max = mag_top`: start `hist_magCat + fmag_above_mag_cat(2.0)`; production always passes `cat_magTop > magCat`, so
  `mag_max = max(hist_magCat + 2.0, fit_rup_mag_top + 0.2, cat_magTop)` with `cat_magTop = suggest_mag_top = max(magCat + 2.0, max(Mmain, catalog_max_mag) + 0.2)`
  (`OEtasParameters.java:971-1000,1007`; `aafs/ForecastResults.java:1121-1122`). `fit_rup_mag_top` = largest mag with t > t_fitting.
- `tint_br = max(t_forecast - t_fitting, tint_br_fitting=365) + tint_br_forecast(0)` (`OEtasParameters.java:1165`; called at `oetas/env/OEExecEnvironment.java:1349`).
- Times (days from mainshock; `aafs/ForecastResults.java:1124-1127`): `t_data_begin = min_days`, `t_data_end = max_days` (fit-end inset 0),
  `t_fitting = 0` (DEFAULT_FIT_START_INSET = 0), `t_forecast = max(t_data_end, forecast start)`.
- History params (`OEtasParameters.make_hist_params` `:295`; `fit/OEDiscFGHParams.java:331-372`): `disc_delta=0.2`, `disc_base=0.005`,
  `disc_round=0.5` (nearest), `disc_gap=0.25*disc_delta=0.05`, `mag_cat_count=3000`, `eligible_count=5`, `before_max_count=50`,
  `mag_cat_int_join=1`, interval max duration `min(3.0, max(1e-5, 0.5*(t - t_split)))`, required splits at `t_fitting` and `t_data_end`.
- Fitting options: `fit_f_intervals=true`, `fit_lmr_opt=1` (LMR_OPT_MCT_INFINITY), `c_cross_intervals=c_self_intervals=1.0`.
- `gr_*` and `gs_*` keys (e.g. `gr_init_mag=4.5`) are source-GROUPING width functions (`OEtasParameters.java:584-600`), not Gutenberg-Richter.
- `eligible_*` decide whether ETAS runs at all (`check_eligible`, `OEtasParameters.java:2827`, option 2 = auto):
  skip if `Mmain - magCat < 2.0`; run if `Mmain >= 4.45` or `catalog_max_mag >= 3.95`. `eligible_small_mag=4.95` halves catalog counts for small events.

magCat for an international sequence: `magCat = MagCompPage_Parameters.get_magCat(Mmain) = max(magCat_regime, max(2.95, Mmain - 5.0))`
(`rj/MagCompPage_Parameters.java:83`, `rj/SearchMagFnFloor.java:50`). `res/rj/MagCompPage_ParametersFetch.json`: WORLD magCat=4.6,
F=0.5, G=0.25, H=1.0 (USA/Puerto Rico 3.5; Alaska 3.5 with F=1,G=4.5,H=0.75; California/Hawaii 3.0). The history then may RAISE magCat:
if more than 3000 ruptures after the first required split, `magCat = mag(3000th largest) - max(1e-4, tiny)` (`fit/OEMagCompFnDiscFGH.java:1753`).
Time-dependent Mc (`fit/OEMagCompFnDiscFGH.java` header): only the 5 largest ruptures are "eligible" (`:1689`);
`Mc(t) = max(magCat, max_i min(M_i, D(F*M_i - G - H*log10(t - t_i))))`, D = round-to-nearest onto `0.005 + 0.2k`, never below magCat.
Ruptures are accepted only if `m >= Mc(t^-)`; the accepted rupture stores that pre-existing Mc as its target completeness.

## 3. Log-likelihood (`oetas/fit/OEDisc2ExtFit.java` header lines 53-260; `avpr_calc_log_like` `:3695`)

Sources: every history rupture (accepted, from `min(t_early, t_data_begin)`) plus every history interval. Mainshock sources:
ruptures with `t <= t_fitting + 1e-7` (index < `i_inside_begin`, `:4348`; includes the mainshock appended by `OEExecEnvironment.java:669`)
use `ams`, Q=1. Targets: accepted ruptures strictly inside (t_fitting, t_data_end). Intervals: from t_fitting to t_data_end, each with
constant completeness `mct_j`; lmr_opt=1 means target completeness = time-dependent `mct`, upper magnitude = infinity.

    rate of M>=mct at t:  R(t; mct) = sum_{rup s<t} k_s * 10^(-b*(mct-mref)) * (t-s+c)^-p
                                    + sum_{int [s1,s2], s1<t} ks_j * 10^(-b*(mct-mref)) * Integral_{s1}^{min(t,s2)} (t-s+c)^-p ds
    k_s = (10^a)Q * 10^(alpha*(m_s-mref))   (aftershock)      k_s = 10^ams * 10^(alpha*(M-mref))  (mainshock)
    LL  = sum_{targets n} log R(t_n; mct_n)  -  sum_{intervals j} Integral_{t1j}^{t2j} R(t; mct_j) dt
    implemented as  LL = sum_n log( tenaq*S_a[n] + tenamsq*S_ms[n] ) - ( tenaq*I_a + tenamsq*I_ms )

with `tenaq = calc_ten_a_q_from_branch_ratio(n,p,c,b,alpha,mref=3,mag_min,mag_max,tint_br)` (`OEDisc2InitStatVox.java:605`) and
`tenamsq = 10^ams` (`:661-674`). No magnitude-PDF term, no log(beta) constant, b not fitted.
Unobserved events: intervals act as sources representing events with `mag_min <= m < mct_j` (events below catalog magCat never trigger).
Induced productivity density of a target interval (constant over the interval):

    kt = [source rate N] * beta * 10^(a + (alpha-b)*(mag_min-mref)) * Q * W(v, mct_j - mag_min) * Integral_{t1}^{t2} N(t)dt / (t2-t1)
    W(x,y) = (exp(x*y)-1)/x  (W(0,y)=y);  alpha==b => kt = rate * beta * tenaq * (mct_j - mag_min) * <N>

summed over prior ruptures (k_s), prior intervals (double Omori integrals) and the interval itself (self term, `c_self=1`).
Intervals with `mct == mag_min` (== magCat) have zero productivity, so most intervals far from big events contribute nothing.
Background: `zmu_range` single 0.0 => `mu = 0` (background effectively off).

## 4. Grids (`oetas/util/`) and voxel volumes

Production ranges: `b` single 1.0; `alpha` null (alpha=b); `c` log 21 in [1e-4, 1]; `p` linear 37 in [0.5, 2.0];
`n` log_skew 81 in [0.025, 0.9], skew 3; `zams` (relative) linear 43 in [-2, 1]; `zmu` single 0. Voxels = (b,alpha,c,p,n); sub-voxels = zams.

    linear (OEDiscreteRangeLinear.java:89,119): d=(max-min)/(N-1); x_k=min+k*d; edges min+(k-1/2)d, k=0..N
    log    (OEDiscreteRangeLog.java:89,121):    d=(ln max-ln min)/(N-1); x_k=exp(ln min+k*d); edges exp(ln min+(k-1/2)d)
    log_skew (OEDiscreteRangeLogSkew.java:51-84,161,194):
        C = (skew-1)/(skew*max - min);  w(x) = ln(x/(1 - C*x));  x(w) = e^w/(1 + C*e^w)
        d = (w(max)-w(min))/(N-1);  x_0=min, x_{N-1}=max, x_k = x(w(min)+k*d)
        interior edges x(w(min)+(k-1/2)d), k=1..N-1;  outer edges exp(ln min - d/2*(1-C*min)), exp(ln max + d/2*(1-C*max))
        (n grid: 0.025, 0.02648, 0.02804, ..., 0.86487, 0.8826, 0.9)

`common_vox_volume` (`oetas/bay/OEBayPrior.java:182`; `util/OEValueElement.java:104,132`):

    vox_volume = width(b) * width(alpha) * ln(c_hi/c_lo) * width(p) * ln(n_hi/n_lo) * width(zams) * ln(zmu_hi/zmu_lo)
    single-value or null elements contribute 1.0

Posterior weight of a grid node (`fit/OEDisc2InitStatVox.java:725,889`):
`P_j = exp(logdens_j - max logdens) * vox_volume_j`. The prior is evaluated at node values (not integrated over the voxel).

## 5. Prior: `oetas/bay/OEMixedRNPCParams.java` via `OEBayPriorMixedRNPC.get_bay_value` (`oetas/bay/OEBayPriorMixedRNPC.java:92-107,168-204`)

`log_prior = calc_log_sel_fit_zams(zams_rel) + calc_log_sel_fit_n(n) + calc_log_sel_fit_c_p(c, p)` (`:803-833`); zams is made
relative first (offset 0 in production). Production selections: `zams_dist=1` (triangle), `n_dist=1` (skew normal), `bv_cpdist=5` (bivariate Cauchy).
Variables/units: zams_rel linear; n via `u = log10(n)`; c via `log10(c)`; p linear. Densities are normalized in (zams, log10 n, log10 c, p)
(vox_volume uses ln instead of log10; a constant factor that cancels).

Triangle with exponential tails (`calc_log_triexp`, `:578`; area `:612`; norm `:300`):

    if x < x0: r=(x-x1)/(x0-x1); log y = (x<x1) ? ln(y1) + r*(y0/y1 - 1) : ln(r*y0 + (1-r)*y1)
    else:      r=(x-x2)/(x0-x2); log y = (x>x2) ? ln(y2) + r*(y0/y2 - 1) : ln(r*y0 + (1-r)*y2)
    area = 0.5*y0*(x2-x1) + (0.5 + 1/(y0/y1-1))*y1*(x0-x1) + (0.5 + 1/(y0/y2-1))*y2*(x2-x0)
    log f_zams = log y - ln(area)      all regimes: x0=0, y0=1000, x1=-0.61, y1=339, x2=0.54, y2=105

Log-skew-normal for n (`calc_log_ulogskewnorm` `:741`, area `:759`, norm `:312`): an ordinary skew normal in `u = log10 n`,
location `log10(nzeta)`, scale `nomega`, shape `nalpha`:

    r = (log10 n - log10 nzeta)/nomega;   log f_n = ln(max(erfc(-nalpha*r/sqrt2), 1e-20)) - r^2/2 - ln(sqrt(2*pi)*nomega)
    (= ln[(2/nomega) * phi(r) * Phi(nalpha*r)])

Bivariate Cauchy in (log10 c, p) (`calc_log_bivar_cauchy_c_p` `:701`, norm `:350`):

    cr = (log10 c - log10 bv_cmu)/bv_csigma;  pr = (p - bv_pmu)/bv_psigma;  rho = bv_cpcorr
    Qf = (cr^2 + pr^2 - 2*rho*cr*pr)/(1 - rho^2)
    log f_cp = -0.5*ln(4*pi^2*bv_csigma^2*bv_psigma^2*(1-rho^2)) - 1.5*ln(1 + Qf)       # bivariate t, nu=1

(Unused alternatives: c normal `log_norm=-0.5 ln(2 pi csigma^2)` on log10 c; p Cauchy `-ln(pi psigma) - ln(1+r^2)`; bivariate normal same norm.)
`res/oetas/bay/MixedRNPCConfig.json` GLOBAL/DEFAULT: nzeta=0.59, nomega=0.7, nalpha=-2.7, bv_cmu=0.005, bv_csigma=1.75, bv_pmu=1.07,
bv_psigma=0.24, bv_cpcorr=0.63. SZ: nzeta=0.58, nomega=0.7, nalpha=-2.4, bv_cmu=0.006, bv_csigma=1.8, bv_pmu=1.075, bv_psigma=0.27, rho=0.7;
SZ-GENERIC n: 0.55/0.71/-2.7; ANSR: 0.62/0.68/-3.4, cp 0.0035/1.6/1.08/0.19, rho 0.46; SCR: 0.31/0.35/-1.1, cp 0.07/1.5/1.065/0.26, rho 0.76.

Bayesian weight (`OEDisc2InitStatVox.java:725`; `OEtasParameters.get_bay_weight` `:1929`; applied `OEExecEnvironment.java:1469`):

    w <= 1: logdens = w*log_prior + LL        w > 1: logdens = log_prior + (2 - w)*LL
    w = early_bay_weight (2.0 = prior only, "generic") if (t_data_end - t_data_begin) <= early_bay_time (0.125 d), else bay_weight (1.0)

## 6. Posterior -> forecast (`fit/OEDisc2InitVoxSet.java:332-620,1151`; `OEDisc2InitStatVox.java:1043-1250`; `OESimulator`, `OECatalogGenerator`)

- Catalogs: `num_catalogs=500000`, `min_num_catalogs=250000` (halved if Mmain < 4.95) (`OEtasParameters.get_sim_params` `:2543`).
- Tail trim: bin sub-voxels by `-(logdens - max)` in 0.01 ln-unit bins (692 bins; last bin catch-all always dropped); keep bins until
  cumulative P reaches `(1-0.003)` of the P in the first 691 bins (`:481`).
- Systematic resampling: step = kept P / 262144; accumulator starts at -step/2; each node takes one seed slot per step the running
  accumulator crosses (`:509-560`); slot order is bit-reversal scrambled. Catalog i uses slot `i mod 262144`; a slot with n > 0.99001 is
  skipped (next slot); simulation n is capped at 0.99 (`OEConstants.java:820,825`).
- Simulation a-value: `a = calc_inv_branch_ratio(n,p,c,b,alpha, mref=3, msup=9.5, tint_br)` (`OEDisc2InitStatVox.java:1043`, `FitInfo:578`).
- Seeds: one seed rupture per source group (groups partition ALL accepted history ruptures, including the mainshock, plus interval sources):
  `k = prod_scnd_j*(10^a)Q + prod_main_j*10^ams` at the group time, equivalent mag `m0 = log10(k/10^ams)/alpha + mref` (`:1239`).
- Time: `tbegin = end of fitted data`, `tend = t_forecast + 365` (`OEExecEnvironment.java:1435-1437`).
- Per generation (`OECatalogGenerator.java:336-362,700-716`): `R = sum k_i * I(p,c, t_i -> [tbegin, tend])`; expected count
  `R * (10^(-b(m1-mref)) - 10^(-b(m2-mref)))`; Poisson size; times ~ Omori, mags ~ GR(b) truncated to [m1,m2];
  child `k = 10^(a + alpha*(m - mref)) * Q([mref,msup] -> [m1,m2])`.
- Per-catalog magnitude range (RANGING_METH_VAR_SEED_EST, `OESimulator.java:992`; `OECatalogGenerator.java:424-500`), set from seeds:
  `x = sum_{i=0}^{18} (0.9*n_cat)^i` (ran_gen_br=20, derate 0.9, n_cat = calc_branch_ratio over [tbegin,tend]);
  `m2 = mref - log10(0.02/(R*x))/b`, clipped to [-1.0, 9.9]; `m1` solves `R*(10^(-b(m1-mref)) - 10^(-b(m2-mref))) = T`, with
  T interpolated uniformly at random (u~U(0,1), in magnitude) between the solutions for T=100 and T=1000; clipped to [-3.0, 9.9]. Range then fixed.
- Accumulation (`OEAccumRateTimeMag`, option 433 = CATLEN_ENTIRE / OUTFILL_PDF_DIRECT / MAGFILL_PDF_HYBRID, param 0.25):
  per catalog and per cumulative (time window from t_forecast, M >= Mbin) bin, a shifted Poisson: shift = simulated count, mean = expected
  count from analytic rates for magnitudes below m1 ("downfill") or above m2 ("upfill", secondary productivity reduced by 25%) and after
  catalog stop; distributions are summed over catalogs -> probabilities and fractiles. Only catalogs that reached `tend` count.

## 7. Published `model.parameters`

oetas product (`OEForecastGrid.java:129-132`, `OEDisc2InitVoxSet.get_display_params` `:1454`, `OESimulator.java:349-363`): name
"ETAS (Ogata, 1988) aftershock model (...)"; params `b, alpha, c, p, n, zams, zmu` of the MAP node (argmax of `logdens` WITHOUT vox_volume),
`zams` is the raw RELATIVE grid value; plus `simCount, simDuration[, simMagMin, simMagMax]` and `Mcat, F, G, H` + region. No `a`/`ams`/`Mc` keys.

The `ams, a, b, magMain, p, c, Mc` product is legacy `etas/GraphicalForecast.java:840-848`: values from
`ETAS_AftershockModel.getMaxLikelihood_*()` = argmax over a 4-D grid (ams, a, p, c; defaults 51x31x31x21) of
`LL + ln(prior)` restricted to subcritical sets (`etas/ETAS_AftershockModel_SequenceSpecific.java:380-406`). Convention there:

    rate of M>=Mc:  lambda(t) = 10^ams*10^(alpha(Mms-Mc))*(t+c)^-p + sum_i 10^a*10^(alpha(m_i-Mc))*(t-t_i+c)^-p   (:267-269)
    LL = sum log lambda(t_i) - [10^ams*N_ms + 10^a*N_as]  over [dataStart, dataEnd], events with m >= Mc
    prior: MVN on (a, p, log10 c) x N(ams; mean_a, sigma_a), mean_a += log10((maxMag-refMag)/(maxMag-Mc))   (Generic.java:133,458)
    n = 10^a * I(p,c,0,forecastMaxDays) * b*ln10*(maxMag - Mc)   (alpha==b; ETAS_StatsCalc.java:419)

So `a`, `ams` are log10 productivity for M >= Mc events with magnitudes referenced to Mc; `Mc` is the analyst's (GUI) completeness.
With alpha = b the oetas quantities map exactly: `a_legacy = log10((10^a)Q)` (mag_min=Mc, mag_max=maxMag, tint_br=forecastMaxDays),
`ams_legacy = ams_oetas = zams_abs`, and `zams_rel = ams - a` (us6000qw60: -2.34 - (-2.44) = +0.10).

## Uncertain / not found

- How a mainshock location maps to a MixedRNPC regime (`OEMixedRNPCConfig.get_params(Location)`, OAF tectonic regions) was not traced.
- `disc_gap` handling and the skyline algorithm in `OEMagCompFnDiscFGH` were read only at header level; split/join details may matter for exact Mc(t).
- Interval double-Omori integrals (`OEOmoriCalc`) and the self-interval term were not transcribed line by line.
- Source-grouping widths (`OEDisc2Grouping` span/rup width functions) not traced; they affect seeding only, not the likelihood.
- Downfill/upfill/outfill internals of `OEAccumRateTimeMag` summarized, not transcribed; forecast window/mag-bin lists come from `USGS_ForecastInfo` (not read).
- Legacy model's grid bounds, time-dependent-Mc option (`c = c0*(10^ac*prod)^(1/p)`), refMag and maxMag come from GUI/analyst inputs and
  `GenericETAS_Parameters`; not resolved for any specific published forecast.
- Whether the dither assigns exactly round(P/step) slots per node (code reads like systematic resampling; edge handling at `:560-610` not read).
