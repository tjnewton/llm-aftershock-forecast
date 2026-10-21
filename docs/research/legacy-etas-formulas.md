# Legacy OAF ETAS (van der Elst GUI): exact formulas behind the published `forecast.json`

Source: `opensha/opensha-oaf` @ `08a274bde278b9de12f58a34e7f4ca8d397d0cb6` (read-only).
Prefix `etas/` = `src/main/java/org/opensha/oaf/etas/`; `GUI` = `etas/AftershockStatsGUI_ETAS.java`; `CSV` =
`src/main/resources/org/opensha/oaf/etas/resources/vdEGenericETASParams_080919.csv`.
Notation: `I(p,c,t1,t2) = Integral_{t1}^{t2} (t+c)^-p dt = ((t2+c)^(1-p) - (t1+c)^(1-p))/(1-p)` (log form if |1-p|<1e-6).
Times are days since mainshock. Writer: `etas/GraphicalForecast.java:838-850` (`ams, a, b, magMain, p, c, Mc`).

## 1. Generic prior

**Regime lookup.** `regime = TectonicRegime.forName(new TectonicRegimeTable().get_strec_name(lat, lon))`, fallback
`GLOBAL_AVERAGE` on exception or null (GUI:2245-2264, again at GUI:7004-7017). That is the same 0.05-degree Garcia/STREC table
(`rj/TectonicRegimeTable.java:242`) the RJ code uses, but RJ first checks its CAL-* special polygons and `world_region`
(`rj/OAFParameterSet.java:1020-1083`). Legacy ETAS skips that step, so the CSV row `CALIFORNIA` (mref 2.5) is reachable only if the
analyst picks it. `GenericETAS_ParametersFetch.getRegion` (STREC_DataWrapper, `:112-122`) is never called by the GUI.
Two lookups: (a) at the mainshock hypocenter in `setMainshock` (GUI:2252). This builds `genericModel`, which is the prior
(GUI:2296-2299). (b) at the aftershock-zone center in `doPostFetchCalculations` (GUI:7006). This sets `genericParams`, which
drives the grid ranges, `aSigma` and `maxMag` (GUI:7019-7027). The quick-forecast path never rebuilds `genericModel`
(`updateModelStep`, GUI:4103-4123, is not part of it, GUI:4640-4694). So if (a) and (b) disagree, the prior comes from the
hypocenter regime.

**CSV columns** (`etas/GenericETAS_ParametersFetch.java:45-85`; header row skipped):
- used: `a` (col 1), `asig` (2), `p` (4), `covaa..covcp` (5-10), `Nms` (11), `alpha` (12, only in the generic-only branching check),
  `b` (13), `mref` (14), `mmax` (15)
- ignored: `logc` (col 3, commented out at `:55`). Instead `c = 10^-2.5` for every regime (`:75`), with
  `logcValue_sigma = 0.8333` (`:79`), `pValue_sigma = sqrt(covpp*Nms)` (`:77`) and `bValue_sigma = 0.1` (`:81`).
- All rows share the global covariance: covaa=7.13e-6, covpp=7.67e-6, covcc=8.99e-4, covap=2.63e-6, covac=3.75e-5, covcp=4.5e-5,
  Nms=2099, alpha=1, b=1. mref is 4.5 (2.5 for CALIFORNIA). mmax is 9.0 for ANSR/SCR/SOR rows and 9.5 for SZ/GLOBAL rows.

**Mc conversion** (applied to both the a and ams means; `etas/ETAS_AftershockModel_Generic.java:133`, also GUI:7178):

    A0 = a_csv + log10((mmax - mref)/(mmax - Mc))        e.g. mmax 9.5, Mc 2.95: -0.117

This keeps the branching ratio `n` (section 3) unchanged. It is not a GR rescaling: with alpha=b, GR would leave a unchanged.

**Prior density.** `get_priorLikelihood` (`etas/ETAS_AftershockModel_Generic.java:458-493`), covariance from
`etas/GenericETAS_Parameters.java:67`. Yes: a trivariate normal on (a, p, log10 c) times an independent normal on ams with mean
A0 (not a separate ams mean) and sd asig:

    prior(ams,a,p,c) = MVN([a, p, log10 c]; mu=[A0, p_csv, -2.5], S) * N(ams; A0, asig)
    S = [[asig^2,     N*covap, N*covac],     N = Nms = 2099  ->  N*covpp=0.016099 (sd 0.1269),
         [N*covap,    N*covpp, N*covcp],                         N*covcc=1.887 (sd 1.374 in log10 c),
         [N*covac,    N*covcp, N*covcc]]                         N*covap=0.005520, N*covac=0.07871, N*covcp=0.09446

`covaa` is not used: `asig^2` replaces it. The tighter `covariance` matrix (`:66`) feeds only the unused `get_likelihood`.
In the Bayesian fit the prior is evaluated unnormalized at the grid nodes
(`get_priorLikelihoodMatrix(...,false)`, `etas/ETAS_AftershockModel_SequenceSpecific.java:237-238`).

## 2. Sequence-specific likelihood (`etas/ETAS_AftershockModel_SequenceSpecific.java:206-483`)

**Events.** `aftershockList.getRupsAboveMag(Mc)` (>=), sorted by time (`:207-229`). The list is whatever was fetched from ComCat over
[dataStart, dataEnd], with no magnitude floor and the mainshock removed (`etas/ETAS_ComcatAccessor.java:195-201,261-266`). It is
capped at the 1000 largest events (GUI:2015-2022), and dataEnd = forecastStart (section 6). There is no Page-style Mc(t) with
F/G/H and no start-time offset. Incompleteness is modeled instead by a magnitude-dependent c (`timeDepMcParam`, default **true**,
GUI:856, 1244):

    K_i = 10^(alpha*(m_i - Mc)) (aftershocks),  K_ms = 10^(alpha*(Mms - Mc))                     (:267-269)
    c_i = c0 * (10^ac * K_i)^(1/p)  if timeDepMc  else c0     (c0 = c grid value)              (:291,309-341)
    two passes: pass 1 ac = A0 (generic mean a, :137); pass 2 ac = MAP ams of pass 1 (:140-141)

Effect: from a parent the rate at t=0 is about `10^(ams-ac)/c0^p`, so the observed rate is capped near `c0^-p`.

**Intensity** of M>=Mc events at t_i (a and ams are both referenced to Mc):

    lambda_i = 10^ams * K_ms/(t_i + c_ms)^p + 10^a * Sum_{j<i} K_j/(t_i - t_j + c_j)^p           (:312,332,376-377)

Foreshocks (t_i <= 0, only possible if dataStart < 0) instead get `10^ams * K_i/(-t_i + c_i)^p` as their "mainshock" term (`:315-318`).
**Integral** and **log-likelihood** (`:295-300, 343-350, 370-384`):

    Ntot = 10^ams * K_ms * I(p, c_ms, 0, dataEnd) + 10^a * Sum_i K_i * I(p, c_i, 0, dataEnd - t_i)
    LL   = Sum_i ln(lambda_i) [terms with lambda_i > 0] - Ntot + ln prior(ams,a,p,c0)

The mainshock integral always starts at t=0, even when dataStart > 0 (`:287`). The mainshock is the conditioning event, not a data point.

## 3. Bayesian combination

**Grid** (GUI:7162-7213; vectors built at GUI:4222-4227). All ranges use `round(x,2)`, i.e. two decimals:

    ams, a :  [A0 - 4*asig, A0 + 4*asig]                     linspace
    p      :  [max(0.1, p_csv - 4*sp), p_csv + 4*sp]          sp = sqrt(covpp*2099) = 0.1269; linspace
    c0     :  [max(1e-5, round(10^-2.5/10^(4*0.8333),5)), min(1, 10^-2.5*10^(3.333))] = [1e-5, 1] for every regime
    linspace(lo,hi,n)_k = lo + k*(hi-lo)/(n-1), last = hi                     (etas/ETAS_StatsCalc.java:49-57)
    logspace(lo,hi,n)_k = 10^(log lo + k*(log hi - log lo)/n), k<n-1; last = hi  (:59-71, NOTE /n, not /(n-1))

Default counts are analyst-editable:

| Mode | ams | a | p | c |
|---|---|---|---|---|
| GUI (GUI:822-846) | 31 | 31 | 31 | 31 |
| command line (GUI:1235-1241) | 51 | 31 | 31 | 21 |

A `-config` file can override any of these (GUI:3743-3747).
Published us6000qw60 c values (e.g. 0.0055 = 10^(-5+17*5/31), 0.0042 = 10^(-5+11*5/21)) sit on the /n logspace, which confirms the quirk.
fitMSProductivity is on by default (GUI:807, 1233). Off, ams is tied to the a MAP (`:456-461`).

**Combination.** Unweighted: `logpost = LL + ln prior` (`:384`). **Subcritical restriction** (`:387-394`):

    c* = c0 * 10^(ac/p) if timeDepMc else c0
    n  = 10^a * I(p, c*, 0, forecastEnd) * { b*ln10*(Mmax - Mc)                       if alpha == b
                                            b/(alpha-b)*(10^((alpha-b)(Mmax-Mc)) - 1)  otherwise }   (ETAS_StatsCalc.java:419-435)
    keep node only if n < 1 (else logpost = -inf); non-finite logpost -> -inf

Here forecastEnd is absolute (forecastStart + 366) and Mmax = CSV mmax.
**Normalization** (`etas/ETAS_AftershockModel.java:101-142`): `w = exp(logpost - max)`, set to 0 if `logpost - max < -20`, then
divided by Sum w over the grid. No cell volumes are used: the c grid is uniform in log10 c except its last step.

## 4. Published parameters (`etas/GraphicalForecast.java:843-849`)

`ams, a, p, c` = `getMaxLikelihood_*()` = grid values at the argmax of `logpost` over **subcritical** nodes (`:397-409`).
This is the MAP of the pass-2 fit on the 4-D (ams, a, p, c0) grid. `c` is **c0**, the bare grid value, not the time-dependent c.
`a` is referenced to Mc: the rate of M>=Mc direct aftershocks of a magnitude-m parent is `10^(a + alpha(m - Mc))*(t+c)^-p` per day
(`:269,332,377`). The same holds for `ams` with Mms.

| Key | Source | Format |
|---|---|---|
| ams, a, p | MAP grid values | `%3.2f` |
| c | MAP grid value c0 | `%5.4f` (so 0.0003 is a heavily rounded value) |
| b | `bParam` | `%3.2f` |
| magMain | mainshock magnitude | `%2.1f` |
| Mc | `magComplete` | `%2.2f` |

`bParam` is the generic b = 1.0 unless the analyst ran "Compute b" or passed `-b` (GUI:2363, 2401).
**alpha is not published:** `alpha = b if b < 1 else 1` (`link_alpha`, GUI:6960-6964).
If `bayesianModel` is null the generic model is written under the same name: its "MAP" is the middle grid index
(`etas/ETAS_AftershockModel_Generic.java:215-218`; GUI:6581-6584).

## 5. Forecast (`etas/ETAS_AftershockModel.java:319-385`, `etas/ETAScatalog.java`)

**Catalogs.** `nSims = numberSimsParam = 10000` (GUI:861, 1197; 30000 in `-prForecast`, GUI:4459), maxGenerations 100, `Mmax = mmax`.

**Parameter draws** (`etas/ETAScatalog.java:312-392`): nSims sorted U(0,1) draws are inverted on the cumulative posterior weights
over the 4-D grid, in loop order ams, a, p, c. Nodes with `n(a,p,c0,forecastEnd,Mc,Mmax) >= 1` are zeroed first, using c0 with no
time-dependent factor. The draws are then shuffled. Each catalog gets one (ams, a, p, c0) draw.

**Simulation minimum magnitude** (`etas/ETAS_AftershockModel.java:328-357`):
start at `minMag = max(Mms, observed M>=Mc magnitudes) - 4`. Repeatedly run 100 calibration catalogs over
[forecastStart, forecastStart+1] and lower minMag by 1 until all 100 catalogs contain at least one event, or minMag <= -3.

*Version history of this rule* (`git log` of `ETAS_AftershockModel.java`; calibration over [forecastStart, forecastEnd] = 366 d
before 08a274bd):

| Commit (date) | Start | Loop | Below-minMag fractiles |
|---|---|---|---|
| before 8b8dfbedcb | max - 2 | test, then decrement, while any of 100 catalogs is empty; floor 3 | scaled, no Poisson step |
| 8b8dfbedcb (2025-02-07) | max - 1 | decrement, then test, until >= 95 of 100 non-empty; floor -3 | scaled with Poisson step |
| 7ecfce225f (2025-04-02) | max - 2.7 | decrement, then test, until all 100 non-empty | same |
| dd156a23ac (2025-05-08) | 3.0 | test 3.0 first, then decrement, until all 100 non-empty | not used (getDiscreteFractile) |
| 08a274bd (2026-10-14) | max - 4 | 1-day calibration, all 100 non-empty | scaled |

A product reveals its own minMag when that lies above its lowest bin: the fractiles there are `round(10^(b(minMag-M)) n)`
for integers n (`laf.oaf.Forecast.simulated_min_mag`). The 2025 Kamchatka products show 5.8 (8b8dfbedcb), the 2026 sequences
show <= 3 (dd156a23ac), and a Panama product made 3.5 h before 08a274bd was pushed shows 3.7 (docs/adr/0010 section 3.5).

**Seeds** (`etas/ETAScatalog.java:129-130,173-197`): the mainshock, with its magnitude replaced by `Mms + (ams - a)`, plus every
fetched event with `t <= forecastStart` and `M >= minMag`. That can include events below Mc and foreshocks. Seeds are generation 0
and are not counted in the forecast.

**Offspring of a parent at (t, m, generation g)** (`:236-245, 281-302`):

    a' = a + log10((Mmax - Mc)/(Mmax - minMag))   for g == 0 (seeds) and g >= 2;   a' = a   for g == 1
    mean = 10^a' * 10^(alpha*(m - minMag)) * { I(p,c0, forecastStart - t, forecastEnd - t)   if t < forecastStart
                                              I(p,c0, 0, forecastEnd - t)                    if t < forecastEnd }
    N ~ Poisson(mean) (cern.jet);  child m = minMag - log10(U)/b, set to Mmax if above it (a pile-up at Mmax, not truncation) (:400-412)
    child t: inverse CDF of (s - t + c0)^-p on [max(t, forecastStart), forecastEnd] (:414-454)

c0 is used for every parent; the time-dependent c is not used here. When alpha = 1 the shifted mainshock magnitude reproduces
`10^(ams + alpha(Mms - minMag))`. `forecastEnd = forecastStart + 366` (GUI:2158, enum GUI:228).

**Outputs.** For each window (tMin = forecastStart, tMax = tMin + {1, 7, 31, 366}) and each magnitude {3,...,8}, count the simulated
events with `tMin < t <= tMax` and `m >= M` in each catalog, giving an empirical distribution with weight 1/nSims per catalog
(`etas/ETAS_AftershockModel.java:260-289`). Then:
- **fractile f**: the smallest count whose normalized CDF is >= f (OpenSHA `getDiscreteFractile`).
  - If M < minMag: when that count is <= 1, replace it with x solving `regularizedGammaQ(x, lam) = f`, where
    `lam = -ln(weight at smallest count)`. Then scale by `10^(-b(M - minMag))` (`:647-674, 734-758`).
- **probability** = `1 - (weight at the smallest observed count)`. This is P(N>=1) only if some catalog had 0 events.
  If M < minMag: `P = 1-(1-P)^(10^(-b(M-minMag)))` (`:762-782`).
- **JSON fields** (`etas/GraphicalForecast.java:222-235, 778-779, 888-893, 929-936`):
  - `median = round(F(0.5))`, `p95minimum = (int)F(0.025)`, `p95maximum = (int)F(0.975)` (truncation toward zero)
  - `fractileValues = round(F(f))` for f = 0.0025, 0.0050, ..., 0.9975 (399 values); `barPercentages` are derived from these
  - `aboveMainshockMag.probability` uses M = Mms
  - `observations` count fetched data-window events with M >= 2.99, 4.99, 5.99 and 6.99 (`:803-806`)
  - `timeStart` = forecastStart = dataEnd, so the window starts exactly at the data end time

## 6. Analyst inputs

**Mc.**
- Default rule (`setMagComplete`, GUI:2351-2399; `etas/OgataMagFreqDist.java:94-170`):
  - Scan mc on a 0.1 grid of half-bins, from `round(min(Mmin,1)/0.1)*0.1 - 0.05` upward.
  - Stop at the first mc where the GR log-likelihood with fixed b = b_csv beats both b ± 0.1 (with a N(b_csv, 0.1) prior).
    Call the result `Mc_raw = mc + 0.5`.
  - Then `Mc = floor(Mc_raw/0.1)*0.1 - 0.05`, so a .x5 value drops by 0.1 (e.g. 2.95 -> 2.85).
- `-mc X` (GUI:7743-7746): goes through the same floor, so `-mc 3.0` gives 2.95.
- `validateMcParam` (GUI:7404-7416) then caps Mc at `Mms - 0.05` and snaps it to a .x5 value.
- The analyst can also type Mc or run "Compute b" (Ogata-Katsura b and Mc, GUI:4051-4081).

**Times.**
- dataStart default 0 (GUI:625, 1188-1191). `-dataStart X` sets it, and negative values add foreshocks.
- `dataEnd = forecastStart` (linked, GUI:2133-2147). forecastStart is "now" in the GUI (`nowBoolean` true, GUI:587, 2115-2121)
  or `-forecastStartTime` on the command line (GUI:1183, 1268).
- There is no other time-after-mainshock offset. The command-line output is
  `Forecasts/<id>/<id>_t<dataEnd>.json` (GUI:4481-4483).

**Other.**
- b defaults to 1 (`-b` sets it); alpha is linked to b; Mmax comes from the CSV (7.05 in `-prForecast`, GUI:2285).
- `-rj` fixes a = -9 (GUI:4416-4425).

**Re-simulating a published forecast from (ams, a, b, p, c, Mc, magMain)**:
1. Set `alpha = min(b,1)` and `Mmax = mmax(regime at regionCenterLat/Lon)`.
2. Take forecastStart = (timeStart - mainshock_time)/86400000.
3. Refetch the catalog over [dataStart(=0?), forecastStart] (all magnitudes, 1000 largest) and rebuild minMag by the calibration rule.
4. Seed the mainshock with magnitude `magMain + ams - a`, then run section 5 with the fixed (a, p, c).

A fixed MAP set leaves out the posterior parameter spread the published fractiles include, and the published c has only four decimals.

## 7. Running the Java code, and what the products reveal
**Command line** (opensha-oaf 08a274bde278 with opensha e2ece620c9bf; needs JDK 21; built with
`./gradlew appOAF_ETAS_Jar`; archived runs and scripts in `runs/java_differential/`):
- `-eventID X -forecastStartTime T` (days after the mainshock) starts command-line mode; data end
  = forecast start; data start 0. `AftershockStatsGUI_ETAS` extends `JFrame`, so it needs an AWT
  display even without a window (`-Djava.awt.headless=true` throws).
- `-Mc X` is floored to a .x5 value (`floor(X/0.1)*0.1 - 0.05`; pass X + 0.06 to get X).
  `-b` fixes b. `-catalog <file>` (relative to `user.home`) replaces the ComCat fetch.
- Fixed: grids ams 51, a 31, p 31, c 21; 10,000 simulations; unseeded `Math.random()`;
  timeDepMc on; region a circle of 10 km + 3 x WC94 rupture length around the aftershock
  centroid (`-aftershockRadius` and `-config` have no effect); output
  `<user.home>/Forecasts/<id>/<id>_t<dataEnd>.json` (the directory must exist).
- The Java fetcher swallows IO errors: an HTTP 429 from ComCat silently yields an empty catalog.
- **Port vs Java on identical inputs** (5 issues): the grid MAP is the same node to full
  precision, minMag is identical, and forecast fractiles differ by no more than the Java code's
  own run-to-run noise (`tests/test_etas.py::test_fit_reproduces_the_usgs_java_map_exactly`;
  `laf etas-validate --parts java`).

**Settings evidenced by the published products** (refit on the as-of catalog, ADR 0011, with
each product's Mc, b and magMain; exact = all four MAP values equal after `%3.2f`/`%5.4f`):
| Sequence | Exact MAP under GUI defaults (hypocentre regime, 31-point grids, timeDepMc) | Reading |
|---|---|---|
| Panama | 12/12 (and no other regime/grid/timeDepMc combination matches) | GUI defaults |
| Flores Sea | 1/30; most values one or two grid steps off | custom ranges or grids |
| Colombia | 1/21 | c pinned at 0.003 (days 1-8) and 0.1 (days 35-42); regime alternating SZ-ONSHORE / GLOBAL-AVERAGE / SZ-INLBACK (ADR 0010 section 4.1) |
| Venezuela | 0/36 (9/24 exact with the identified settings) | regime overridden to SZ-GENERIC until day ~33, c range [1e-5, 0.9998], ranges set at Mc 4.25/4.75 (ADR 0010 section 4.1) |
| Kamchatka | at most 7/61 over six grid configurations (21, 31, 41 points; 51/31/31/21, 41/41/41/21, 41/41/41/31 for ams/a/p/c); c values on both 21- and 31-point grids | mixed GUI and command-line runs; 41-point a and p grids suggested by spacing |

The full forecast distributions nevertheless agree with the official ones to within Monte Carlo
noise where tested (ADR 0010 section 4, V3): the posterior averages over these grid-step
differences.

## Uncertain / not found
- The grids, Mc, b and config file behind any specific published forecast are not recorded in the JSON. In us6000qw60, the a and p
  spacings (about 8*asig/40 and 8*sp/40) suggest 41-point grids, not the defaults. This is an inference only.
- OpenSHA library semantics (`getDiscreteFractile`, additive `ArbDiscrEmpiricalDistFunc.set`, `getRupsAboveMag` >=) were read from
  `opensha/opensha` master, not a pinned commit. `TectonicRegime.forName` and the behavior for STREC names missing from the CSV
  were not traced.
- Whether analysts re-ran `updateModelStep` (rebuilding the prior after a regime or Mc change) varies from run to run.
- Code quirks, reported as written (intent unknown):
  - the generation-1 productivity is uncorrected while all others use a'
  - the probability uses `getY(0)`
  - foreshock intensity term
  - the p=1 branch in `calculateProductivity` uses `log(t+c)` (`etas/ETAScatalog.java:293`)
  - `uRand /= cumSum` (`:369`) is harmless only if no posterior mass is supercritical
  - the braceless `if` at `etas/ETAS_AftershockModel_SequenceSpecific.java:326-332` gives tied event times a stale c
- `ETAS_USGS_AftershockForecast.java`, `ETAS_RateModel2D.java` and the GMPE/shaking code were not read. They do not feed
  `forecast.json` model parameters.
