# Data availability: USGS OAF archive and ComCat

All numbers come from the public FDSN event service `https://earthquake.usgs.gov/fdsnws/event/1/` (service version `2.8.1`) and the product URLs it links to. Requests were sequential with a 0.5 s pause. Raw downloads (treat as untrusted) live in the session scratchpad at `<session scratch, not kept>`. "vN" means the N-th OAF version sorted by product `updateTime`.

## 1. OAF census

| Query | Retrieved (UTC) | Result |
|---|---|---|
| `count?producttype=oaf&starttime=1900-01-01` | 18:44:15Z | **254** events |
| `count?producttype=oaf&starttime=2024-11-01` | 18:55:46Z | 252 events |
| `query?producttype=oaf&starttime=1900-01-01&endtime=2024-11-01&format=geojson` | 18:55:59Z | 2: ci38457511 (2019 Ridgecrest M7.1), pr2020007007 (2020 Puerto Rico M6.4) |

In practice the ComCat OAF archive starts in November 2024. The count endpoint counts events, not versions.

**Every M≥6.5 event with an OAF product since 2024-11-01.** List: `query?producttype=oaf&minmagnitude=6.5&starttime=2024-11-01&format=geojson&orderby=time-asc` (18:44:40Z). Versions: `query?eventid=<id>&format=geojson&includesuperseded=true` (18:45:20–18:45:41Z), counting `products['oaf']`. Every version has status UPDATE, source `us`, and a single product code.

| ComCat id | Origin UTC | M | Depth km | Place | OAF versions | First updateTime | Last updateTime |
|---|---|---|---|---|---|---|---|
| nc75095651 | 2024-12-05T18:44:21Z | 7.0 mw | 10.0 | Offshore Cape Mendocino, CA | 78 | 2024-12-05T19:04:26Z | 2025-12-05T18:54:29Z |
| us7000nzf3 | 2024-12-17T01:47:25Z | 7.3 mww | 54.4 | 24 km WNW of Port-Vila, Vanuatu | 81 | 2024-12-18T23:41:36Z | 2025-12-19T17:55:38Z |
| us7000pn9s | 2025-03-28T06:20:52Z | 7.7 mww | 10.0 | 2025 Mandalay, Myanmar | 75 | 2025-03-28T17:02:18Z | 2026-04-03T18:14:47Z |
| us7000qd1y | 2025-07-16T20:37:41Z | 7.3 mww | 38.0 | 2025 Sand Point, Alaska | 77 | 2025-07-16T20:57:51Z | 2026-07-16T20:47:54Z |
| us6000qw60 | 2025-07-29T23:24:52Z | 8.8 mww | 35.0 | 2025 Kamchatka Peninsula | 80 | 2025-07-30T17:44:39Z | 2026-07-31T16:16:07Z |
| us6000rsy1 | 2025-12-06T20:41:49Z | 7.0 mww | 10.3 | 2025 Hubbard Glacier | 68 | 2025-12-06T21:58:05Z | 2026-10-17T20:52:01Z |
| us6000t7zp | 2026-06-24T22:05:04Z | 7.5 mww | 10.0 | 20 km W of Catia La Mar, Venezuela | 44 | 2026-06-25T00:20:00Z | 2026-10-12T19:58:00Z |
| us6000tjl2 | 2026-08-10T12:34:28Z | 7.4 mww | 116.1 | 4 km SSW of San José del Palmar, Colombia | 23 | 2026-08-10T19:07:30Z | 2026-10-12T20:01:22Z |
| us6000tkt2 | 2026-08-14T21:58:21Z | 7.8 mww | 10.0 | 66 km NNW of Ende, Indonesia (Flores Sea) | 33 | 2026-08-15T05:42:49Z | 2026-10-12T19:53:31Z |
| us7000ti1p | 2026-09-17T14:19:52Z | 6.5 mww | 98.0 | 177 km W of Nikolski, Alaska | 27 | 2026-09-17T14:39:59Z | 2026-10-15T14:29:55Z |
| us6000u18k | 2026-10-09T17:56:06Z | 7.7 mww | 12.6 | 12 km WSW of Pitaloza Arriba, Panama | 12 | 2026-10-10T00:55:12Z | 2026-10-19T15:52:54Z |

US-network products (nc, ak, Hubbard) ship `forecast.json` together with `forecast_data.json` and have no `review-status`. International products ship only `forecast.json` and carry `review-status=reviewed`.

## 2. Large sequences with and without OAF (M≥7.0, 2025-06-01 to now)

Query: `query?minmagnitude=7.0&starttime=2025-06-01&format=geojson&orderby=time-asc` (18:44:41Z). It returned 23 events, 7 of them with OAF. FF means a finite-fault product exists.

| id | Origin UTC | M | Place | OAF | FF |
|---|---|---|---|---|---|
| us7000qd1y | 2025-07-16T20:37:41Z | 7.3 | Sand Point, Alaska | yes | yes |
| us7000qdyl | 2025-07-20T06:49:04Z | 7.4 | Eastern Kamchatka (foreshock of M8.8) | no | yes |
| us6000qvsf | 2025-07-28T22:10:35Z | 7.0 | Macquarie Island region | no | no |
| us6000qw60 | 2025-07-29T23:24:52Z | 8.8 | Kamchatka Peninsula | yes | yes |
| us6000r2xq | 2025-08-22T02:16:18Z | 7.5 | Southern Drake Passage | no | no |
| us7000qvw5 | 2025-09-13T02:37:56Z | 7.4 | 105 km E of Petropavlovsk-Kamchatsky | no | yes |
| us7000qx2g | 2025-09-18T18:58:14Z | 7.8 | 140 km E of Petropavlovsk-Kamchatsky | no | yes |
| us6000rfwz | 2025-10-10T01:43:59Z | 7.4 | 12 km E of Santiago, Philippines | no | yes |
| us6000rgf4 | 2025-10-10T20:29:20Z | 7.6 | Drake Passage | no | no |
| us6000rsy1 | 2025-12-06T20:41:49Z | 7.0 | Hubbard Glacier | yes | yes |
| us6000rtdt | 2025-12-08T14:15:09Z | 7.6 | Aomori Prefecture, Japan | no | yes |
| us6000sasz | 2026-02-22T16:57:46Z | 7.1 | Kota Belud, Malaysia (629 km deep) | no | no |
| us7000s789 | 2026-03-24T04:37:51Z | 7.5 | W of Neiafu, Tonga (234 km) | no | no |
| us7000s8q0 | 2026-03-30T08:44:13Z | 7.3 | ENE of Luganville, Vanuatu (121 km) | no | no |
| us6000slss | 2026-04-01T22:48:13Z | 7.4 | ESE of Bitung, Indonesia | no | yes |
| us6000sri7 | 2026-04-20T07:52:58Z | 7.4 | 102 km ENE of Miyako, Japan (Sanriku) | no | yes |
| us7000srb1 | 2026-06-07T23:37:41Z | 7.8 | 25 km SW of Kablalan, Philippines (Sarangani) | no | yes |
| us6000t7zc | 2026-06-24T22:04:31Z | 7.2 | 20 km E of San Felipe, Venezuela (33 s before M7.5) | no | no |
| us6000t7zp | 2026-06-24T22:05:04Z | 7.5 | W of Catia La Mar, Venezuela | yes | yes |
| us7000t1bu | 2026-07-17T14:48:39Z | 7.3 | 60 km WSW of Puerto Madero, Mexico (offshore Chiapas) | no | yes |
| us6000tjl2 | 2026-08-10T12:34:28Z | 7.4 | San José del Palmar, Colombia | yes | yes |
| us6000tkt2 | 2026-08-14T21:58:21Z | 7.8 | NNW of Ende, Indonesia | yes | yes |
| us6000u18k | 2026-10-09T17:56:06Z | 7.7 | Pitaloza Arriba, Panama | yes | yes |

**Task-8 events: no OAF and no event-sequence.** From `query?eventid=<id>&format=geojson` (18:45:41Z). "FF fault-model length" is the finite-fault `model-length` property, which is the length of the inversion fault plane. The slipping area is smaller (see `subfault-*` and `FFM.geojson`).

| id | Origin UTC | M | Depth km | FF fault-model length × width (km), strike/dip |
|---|---|---|---|---|
| us7000t1bu (offshore Chiapas) | 2026-07-17T14:48:39.881Z | 7.3 mww | 22.0 | 125 × 65, 286/27 |
| us7000srb1 (Sarangani) | 2026-06-07T23:37:41.970Z | 7.8 mww | 57.0 | two current FF codes: `_1` 90 × 90 (161/45) and `_2` 102 × 78 (357/51) |
| us6000rtdt (Aomori) | 2025-12-08T14:15:09.896Z | 7.6 mww | 40.7 | 90 × 90, 184/17 (FF `eventtime` is date-only, 00:00:00) |
| us6000sri7 (Sanriku) | 2026-04-20T07:52:58.908Z | 7.4 mww | 25.0 | 75 × 75, 193/16 (FF `eventtime` is date-only) |

## 3. Candidate sequences

Event data from the `_sup` detail queries (18:45:20Z). Forecasts were downloaded from `products['oaf'][i]['contents']['forecast.json']['url']`, for example `https://earthquake.usgs.gov/product/oaf/us6000u18k/us/1791593712688/forecast.json`. All 260 downloads returned 200, between 18:46:14Z and 18:49:53Z. The "first usable OAF" column is the first version that is not a cross-post and that belongs to this mainshock. Delays are measured from origin to creationTime.

| Sequence | id | Origin UTC (ms) | M / depth | FF length km | OAF versions (unique) | First usable OAF creationTime (delay) | Latest region (centre, R km) |
|---|---|---|---|---|---|---|---|
| Panama | us6000u18k | 2026-10-09T17:56:06.036Z | 7.7 mww / 12.6 | 150 | 12 (11) | v1 2026-10-10T00:51:02Z (6.9 h) | 7.596, −80.8184, 381.6 |
| Flores Sea | us6000tkt2 | 2026-08-14T21:58:21.561Z | 7.8 mww / 10 | 250 | 33 (30) | v2 2026-08-15T04:50Z (6.9 h); v1 is Colombia's | −8.1275, 120.7036, 227.8 |
| Kamchatka | us6000qw60 | 2025-07-29T23:24:52.483Z | 8.8 mww / 35 | 620 | 80 (67) | v1 2025-07-30T17:05:38Z (17.7 h) | 51.4135, 159.2676, 1076.8 |
| Venezuela | us6000t7zp | 2026-06-24T22:05:04.053Z | 7.5 mww / 10 | 60 | 44 (39) | v1 2026-06-24T23:56:05Z (1.9 h), but v1–v6 use magMain 7.2; first M7.5 version is v7 at 2026-06-26T12:14Z (38 h) | 10.604, −67.5488, 145.2 |
| Colombia | us6000tjl2 | 2026-08-10T12:34:28.828Z | 7.4 mww / 116 | 150 | 23 (20) | v1 2026-08-10T19:02Z (6.5 h) | 4.4721, −76.5375, 125.4 |
| Hubbard Glacier | us6000rsy1 | 2025-12-06T20:41:49.288Z | 7.0 mww / 10.3 | 87.5 | 68 (68) | v1 2025-12-06T21:47:50Z (1.1 h) | 60.4967, −139.7824, 60.0 |

**Format, as observed in all 260 files.**
- Top-level keys: `creationTime, expireTime, advisoryTimeFrame, template ('Mainshock'), injectableText, observations, model{name, reference, parameters}, fractileProbabilities, barLabels, forecast[], nextForecastTime`.
- `nextForecastTime` is missing from Kamchatka v1–v8 and v80. v80 is the final forecast, with advisory "1 Year".
- `forecast[]` has four windows: 1 Day, 1 Week, 1 Month, 1 Year. Each window has `timeStart, timeEnd, label, bins[], aboveMainshockMag{magnitude, probability}`. Each bin has `magnitude, p95minimum, p95maximum, probability, median, fractileValues[], barPercentages[]`. All four windows share one `timeStart`.
- **ETAS international** (model name "Epidemic-Type aftershock model (Bayesian Combination)", all five international sequences):
  - Parameters: `ams, a, b, magMain, p, c, Mc, regionType, regionCenterLat, regionCenterLon, regionRadius`.
  - 399 fractiles. Window lengths are 1, 7, 31 and 366 d.
  - Bins are M3–7, except Panama and Kamchatka, which have M3–8 (Kamchatka v1–v8, v10 and v11 are M3–7).
  - Observations are given at M3, 5, 6, 7 (no M4).
  - `expireTime` = creationTime + 365.4 d.
- **Reasenberg–Jones (Hubbard)**:
  - Parameters: `a, aSigma, b, c, p, pSigma, F, G, H, Mcat, magMain, region*`.
  - 197 fractiles. Window lengths are 1, 7, 30 and 365 d. Observations are given at M3, 4, 5, 6, 7.
  - Model by version: Generic for v1–v2, Bayesian Combination for 9 versions, Sequence Specific for 57.
- The magnitude of completeness is stored under the key `Mc` (ETAS) or `Mcat` (RJ). There is no `Mcat` in ETAS products.

## 4. Per-sequence version tables

Columns:
- "post lag" = updateTime − creationTime.
- "obs counts" lists `observations[].count` in the order given (ETAS: M≥3/5/6/7; RJ: M≥3/4/5/6/7).
- Panama and Flores add two columns: today's ComCat counts in the same circle, from mainshock+1 s to t, at the same magnitudes (see §6).
- The 1-week M≥5 probability column is labelled P.
- Flags are computed. "byte-identical" and "same creationTime" mark re-posts. "CROSS-POST" means the circle centre is more than 300 km from the epicentre.
- Version sources: `query?eventid=<id>&format=geojson&includesuperseded=true` (18:45Z), then each version's `forecast.json` (18:46–18:50Z).

### Panama us6000u18k
unique (non-duplicate) versions: 11; issue interval days median 1.00, max 1.0; 1-wk M≥5 median range 1–12, p95 upper range 4–38

| v | updateTime ms | update UTC | creationTime UTC | post lag h | expire | model | Mc | centre lat, lon | R km | magMain | 1-wk M≥5 median [p95] P | obs counts | ComCat now @creation | ComCat now @timeStart | flags |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1791593712688 | 2026-10-10T00:55:12Z | 2026-10-10T00:51:02Z | 0.07 | 2027-10-10 | ETAS-BC | 4.95 | 7.5735, -80.8225 | 381.6 | 7.7 | 12 [3–38] P=0.9997 | 22/11/1/0 | 26/13/1/0 | 27/13/1/0 |  |
| 2 | 1791647573143 | 2026-10-10T15:52:53Z | 2026-10-10T00:51:02Z | 15.03 | 2027-10-10 | ETAS-BC | 4.95 | 7.5735, -80.8225 | 381.6 | 7.7 | 12 [3–38] P=0.9997 | 22/11/1/0 | 26/13/1/0 | 27/13/1/0 | byte-identical to v1; posted 15 h after creation |
| 3 | 1791647732106 | 2026-10-10T15:55:32Z | 2026-10-10T15:51:37Z | 0.07 | 2027-10-11 | ETAS-BC | 4.85 | 7.5473, -80.7071 | 381.6 | 7.7 | 8 [2–23] P=0.9963 | 45/13/2/0 | 50/15/2/0 | 51/15/2/0 |  |
| 4 | 1791733873721 | 2026-10-11T15:51:13Z | 2026-10-11T15:49:59Z | 0.02 | 2027-10-12 | ETAS-BC | 4.85 | 7.5575, -80.713 | 381.6 | 7.7 | 4 [0–13] P=0.9644 | 54/14/2/0 | 55/16/2/0 | 55/16/2/0 |  |
| 5 | 1791821024407 | 2026-10-12T16:03:44Z | 2026-10-12T15:55:29Z | 0.14 | 2027-10-13 | ETAS-BC | 4.75 | 7.5687, -80.7496 | 381.6 | 7.7 | 3 [0–11] P=0.9365 | 64/14/2/0 | 65/16/2/0 | 65/16/2/0 |  |
| 6 | 1791907263622 | 2026-10-13T16:01:03Z | 2026-10-13T15:57:28Z | 0.06 | 2027-10-14 | ETAS-BC | 4.75 | 7.5908, -80.8179 | 381.6 | 7.7 | 3 [0–10] P=0.9164 | 74/15/3/0 | 77/17/3/0 | 77/17/3/0 |  |
| 7 | 1791993049353 | 2026-10-14T15:50:49Z | 2026-10-14T15:47:55Z | 0.05 | 2027-10-15 | ETAS-BC | 4.75 | 7.5933, -80.8277 | 381.6 | 7.7 | 2 [0–8] P=0.8808 | 77/15/3/0 | 78/17/3/0 | 78/17/3/0 |  |
| 8 | 1792078620533 | 2026-10-15T15:37:00Z | 2026-10-15T15:36:04Z | 0.02 | 2027-10-16 | ETAS-BC | 4.75 | 7.5919, -80.8177 | 381.6 | 7.7 | 2 [0–7] P=0.7958 | 78/16/3/0 | 79/17/3/0 | 79/17/3/0 |  |
| 9 | 1792166769933 | 2026-10-16T16:06:09Z | 2026-10-16T15:52:52Z | 0.22 | 2027-10-17 | ETAS-BC | 4.75 | 7.5938, -80.8244 | 381.6 | 7.7 | 1 [0–6] P=0.7336 | 80/16/3/0 | 81/17/3/0 | 81/17/3/0 |  |
| 10 | 1792252672761 | 2026-10-17T15:57:52Z | 2026-10-17T15:56:16Z | 0.03 | 2027-10-18 | ETAS-BC | 4.75 | 7.594, -80.8258 | 381.6 | 7.7 | 1 [0–5] P=0.6758 | 81/16/3/0 | 82/17/3/0 | 82/17/3/0 |  |
| 11 | 1792340072047 | 2026-10-18T16:14:32Z | 2026-10-18T16:11:38Z | 0.05 | 2027-10-19 | ETAS-BC | 4.75 | 7.5938, -80.8149 | 381.6 | 7.7 | 1 [0–5] P=0.6271 | 84/16/3/0 | 85/17/3/0 | 85/17/3/0 |  |
| 12 | 1792425174381 | 2026-10-19T15:52:54Z | 2026-10-19T15:45:14Z | 0.13 | 2027-10-20 | ETAS-BC | 4.75 | 7.596, -80.8184 | 381.6 | 7.7 | 1 [0–4] P=0.5857 | 86/17/3/0 | 86/17/3/0 | 86/17/3/0 |  |

### Flores Sea us6000tkt2
unique (non-duplicate) versions: 30; issue interval days median 1.01, max 7.1; 1-wk M≥5 median range 0–10, p95 upper range 2–33

| v | updateTime ms | update UTC | creationTime UTC | post lag h | expire | model | Mc | centre lat, lon | R km | magMain | 1-wk M≥5 median [p95] P | obs counts | ComCat now @creation | ComCat now @timeStart | flags |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1786772569293 | 2026-08-15T05:42:49Z | 2026-08-10T19:02:32Z | 106.67 | 2027-08-11 | ETAS-BC | 4.95 | 4.8704, -76.3141 | 125.4 | 7.4 | 1 [0–7] P=0.6902 | 1/1/0/0 | 0/0/0/0 | 0/0/0/0 | CROSS-POST: centre 18027 km from epicentre (another event's forecast); posted 107 h after creation |
| 2 | 1786772769588 | 2026-08-15T05:46:09Z | 2026-08-15T04:50:30Z | 0.93 | 2027-08-15 | ETAS-BC | 4.95 | -8.2546, 121.0701 | 195.8 | 7.7 | 10 [2–33] P=0.9982 | 19/10/1/0 | 57/16/1/0 | 56/16/1/0 | magMain/R/model change |
| 3 | 1786820790984 | 2026-08-15T19:06:30Z | 2026-08-15T18:56:46Z | 0.16 | 2027-08-16 | ETAS-BC | 4.85 | -8.2288, 120.9862 | 195.8 | 7.7 | 8 [2–23] P=0.9974 | 34/15/1/0 | 94/21/1/0 | 94/21/1/0 |  |
| 4 | 1786910357229 | 2026-08-16T19:59:17Z | 2026-08-16T19:53:42Z | 0.09 | 2027-08-17 | ETAS-BC | 4.85 | -8.15, 120.8806 | 195.8 | 7.7 | 9 [2–22] P=0.9989 | 52/22/1/0 | 141/26/1/0 | 140/26/1/0 |  |
| 5 | 1786993005429 | 2026-08-17T18:56:45Z | 2026-08-17T18:49:58Z | 0.11 | 2027-08-18 | ETAS-BC | 4.95 | -8.1785, 120.903 | 195.8 | 7.7 | 5 [1–14] P=0.9872 | 69/28/1/0 | 184/34/1/0 | 184/34/1/0 |  |
| 6 | 1787077819231 | 2026-08-18T18:30:19Z | 2026-08-18T18:25:51Z | 0.07 | 2027-08-19 | ETAS-BC | 4.95 | -8.1704, 120.8737 | 195.8 | 7.7 | 4 [0–11] P=0.9532 | 75/28/1/0 | 207/34/1/0 | 208/34/1/0 |  |
| 7 | 1787167221541 | 2026-08-19T19:20:21Z | 2026-08-19T19:17:01Z | 0.06 | 2027-08-20 | ETAS-BC | 4.95 | -8.1721, 120.8951 | 195.8 | 7.7 | 3 [0–10] P=0.9492 | 85/30/1/0 | 242/36/1/0 | 241/36/1/0 |  |
| 8 | 1787251414752 | 2026-08-20T18:43:34Z | 2026-08-20T18:40:11Z | 0.06 | 2027-08-21 | ETAS-BC | 4.95 | -8.1812, 120.855 | 195.8 | 7.7 | 5 [1–12] P=0.9806 | 101/37/1/0 | 277/44/1/0 | 277/44/1/0 |  |
| 9 | 1787340000386 | 2026-08-21T19:20:00Z | 2026-08-21T19:15:58Z | 0.07 | 2027-08-22 | ETAS-BC | 4.95 | -8.1837, 120.8328 | 195.8 | 7.7 | 4 [0–10] P=0.963 | 114/39/1/0 | 302/46/1/0 | 302/46/1/0 |  |
| 10 | 1787424315607 | 2026-08-22T18:45:15Z | 2026-08-22T18:44:25Z | 0.01 | 2027-08-23 | ETAS-BC | 4.95 | -8.1726, 120.8153 | 195.8 | 7.7 | 3 [0–10] P=0.9512 | 128/40/1/0 | 312/48/1/0 | 312/48/1/0 |  |
| 11 | 1787514618779 | 2026-08-23T19:50:18Z | 2026-08-23T19:49:45Z | 0.01 | 2027-08-24 | ETAS-BC | 4.95 | -8.1748, 120.8225 | 195.8 | 7.7 | 3 [0–9] P=0.9287 | 132/40/1/0 | 313/48/1/0 | 313/48/1/0 |  |
| 12 | 1787593597080 | 2026-08-24T17:46:37Z | 2026-08-24T17:43:21Z | 0.05 | 2027-08-25 | ETAS-BC | 4.95 | -8.1738, 120.8136 | 195.8 | 7.7 | 3 [0–8] P=0.9125 | 138/41/1/0 | 323/49/1/0 | 323/49/1/0 |  |
| 13 | 1787691378387 | 2026-08-25T20:56:18Z | 2026-08-25T20:48:14Z | 0.13 | 2027-08-26 | ETAS-BC | 4.95 | -8.175, 120.8006 | 195.8 | 7.7 | 2 [0–8] P=0.891 | 145/42/1/0 | 329/50/1/0 | 329/50/1/0 |  |
| 14 | 1787775236134 | 2026-08-26T20:13:56Z | 2026-08-26T20:13:24Z | 0.01 | 2027-08-27 | ETAS-BC | 4.95 | -8.1708, 120.7875 | 195.8 | 7.7 | 2 [0–7] P=0.8627 | 156/42/1/0 | 348/51/1/0 | 343/50/1/0 |  |
| 15 | 1787857148593 | 2026-08-27T18:59:08Z | 2026-08-27T18:58:27Z | 0.01 | 2027-08-28 | ETAS-BC | 4.95 | -8.18, 120.7745 | 195.8 | 7.7 | 2 [0–7] P=0.8609 | 166/44/1/0 | 352/52/1/0 | 352/52/1/0 |  |
| 16 | 1787937124164 | 2026-08-28T17:12:04Z | 2026-08-27T18:58:27Z | 22.23 | 2027-08-28 | ETAS-BC | 4.95 | -8.18, 120.7745 | 195.8 | 7.7 | 2 [0–7] P=0.8609 | 166/44/1/0 | 352/52/1/0 | 352/52/1/0 | byte-identical to v15; posted 22 h after creation |
| 17 | 1787937269787 | 2026-08-28T17:14:29Z | 2026-08-28T17:11:48Z | 0.04 | 2027-08-29 | ETAS-BC | 4.95 | -8.1788, 120.7748 | 195.8 | 7.7 | 2 [0–6] P=0.8383 | 168/44/1/0 | 354/52/1/0 | 354/52/1/0 |  |
| 18 | 1788222729652 | 2026-09-01T00:32:09Z | 2026-09-01T00:15:57Z | 0.27 | 2027-09-01 | ETAS-BC | 4.95 | -8.1772, 120.7023 | 227.8 | 7.8 | 2 [0–6] P=0.8078 | 212/46/1/0 | 367/53/1/0 | 367/53/1/0 | magMain/R/model change |
| 19 | 1788291854295 | 2026-09-01T19:44:14Z | 2026-09-01T19:43:00Z | 0.02 | 2027-09-02 | ETAS-BC | 4.95 | -8.1784, 120.702 | 227.8 | 7.8 | 1 [0–6] P=0.7706 | 217/49/1/0 | 369/53/1/0 | 369/53/1/0 |  |
| 20 | 1788385175892 | 2026-09-02T21:39:35Z | 2026-09-02T21:38:33Z | 0.02 | 2027-09-03 | ETAS-BC | 4.95 | -8.1667, 120.7067 | 227.8 | 7.8 | 1 [0–5] P=0.7356 | 233/50/1/0 | 370/53/1/0 | 370/53/1/0 |  |
| 21 | 1788460444347 | 2026-09-03T18:34:04Z | 2026-09-03T18:32:55Z | 0.02 | 2027-09-04 | ETAS-BC | 4.95 | -8.1657, 120.704 | 227.8 | 7.8 | 1 [0–5] P=0.7076 | 238/50/1/0 | 371/53/1/0 | 371/53/1/0 |  |
| 22 | 1788543064229 | 2026-09-04T17:31:04Z | 2026-09-04T17:30:20Z | 0.01 | 2027-09-05 | ETAS-BC | 4.95 | -8.164, 120.7107 | 227.8 | 7.8 | 1 [0–5] P=0.6885 | 251/50/1/0 | 372/53/1/0 | 372/53/1/0 |  |
| 23 | 1788808310821 | 2026-09-07T19:11:50Z | 2026-09-07T19:11:11Z | 0.01 | 2027-09-08 | ETAS-BC | 4.95 | -8.143, 120.7132 | 227.8 | 7.8 | 1 [0–5] P=0.6271 | 308/50/1/0 | 382/53/1/0 | 382/53/1/0 |  |
| 24 | 1788885627467 | 2026-09-08T16:40:27Z | 2026-09-07T19:16:36Z | 21.40 | 2027-09-08 | ETAS-BC | 4.95 | -8.143, 120.7132 | 227.8 | 7.8 | 1 [0–5] P=0.6271 | 308/50/1/0 | 382/53/1/0 | 382/53/1/0 | posted 21 h after creation |
| 25 | 1788989092836 | 2026-09-09T21:24:52Z | 2026-09-09T21:23:56Z | 0.02 | 2027-09-10 | ETAS-BC | 4.95 | -8.13, 120.7086 | 227.8 | 7.8 | 1 [0–4] P=0.6302 | 328/53/1/0 | 387/55/1/0 | 387/55/1/0 |  |
| 26 | 1789069993990 | 2026-09-10T19:53:13Z | 2026-09-10T19:52:57Z | 0.00 | 2027-09-11 | ETAS-BC | 4.95 | -8.1301, 120.7071 | 227.8 | 7.8 | 1 [0–4] P=0.6167 | 338/53/1/0 | 388/55/1/0 | 388/55/1/0 |  |
| 27 | 1789157285889 | 2026-09-11T20:08:05Z | 2026-09-10T19:52:57Z | 24.25 | 2027-09-11 | ETAS-BC | 4.95 | -8.1301, 120.7071 | 227.8 | 7.8 | 1 [0–4] P=0.6167 | 338/53/1/0 | 388/55/1/0 | 388/55/1/0 | byte-identical to v26; posted 24 h after creation |
| 28 | 1789157424933 | 2026-09-11T20:10:24Z | 2026-09-11T20:07:08Z | 0.05 | 2027-09-12 | ETAS-BC | 4.95 | -8.1239, 120.7084 | 227.8 | 7.8 | 1 [0–4] P=0.6038 | 343/53/1/0 | 388/55/1/0 | 388/55/1/0 |  |
| 29 | 1789423698867 | 2026-09-14T22:08:18Z | 2026-09-14T22:00:51Z | 0.12 | 2027-09-15 | ETAS-BC | 4.95 | -8.1213, 120.7077 | 227.8 | 7.8 | 1 [0–4] P=0.5688 | 351/54/1/0 | 394/56/1/0 | 394/56/1/0 |  |
| 30 | 1790012997820 | 2026-09-21T17:49:57Z | 2026-09-21T17:43:07Z | 0.11 | 2027-09-22 | ETAS-BC | 4.95 | -8.1222, 120.6999 | 227.8 | 7.8 | 1 [0–4] P=0.5284 | 377/57/1/0 | 400/58/1/0 | 400/58/1/0 |  |
| 31 | 1790613950145 | 2026-09-28T16:45:50Z | 2026-09-28T16:42:01Z | 0.06 | 2027-09-29 | ETAS-BC | 4.95 | -8.1249, 120.6978 | 227.8 | 7.8 | 0 [0–3] P=0.4461 | 390/58/1/0 | 406/58/1/0 | 406/58/1/0 |  |
| 32 | 1791223286054 | 2026-10-05T18:01:26Z | 2026-10-05T17:53:14Z | 0.14 | 2027-10-06 | ETAS-BC | 4.95 | -8.1586, 120.7353 | 445.6 | 7.8 | 0 [0–3] P=0.4529 | 421/61/1/0 | 436/62/1/0 | 436/62/1/0 | magMain/R/model change |
| 33 | 1791834811999 | 2026-10-12T19:53:31Z | 2026-10-12T19:53:29Z | 0.00 | 2027-10-13 | ETAS-BC | 4.85 | -8.1275, 120.7036 | 227.8 | 7.8 | 0 [0–2] P=0.3691 | 413/60/1/0 | 421/61/1/0 | 421/61/1/0 | magMain/R/model change; obs M3 count decreased |

### Colombia us6000tjl2
unique (non-duplicate) versions: 20; issue interval days median 1.05, max 7.7; 1-wk M≥5 median range 0–1, p95 upper range 1–7 (table shows v1–v3, flagged rows and last; 9 of 23)

| v | updateTime ms | update UTC | creationTime UTC | post lag h | expire | model | Mc | centre lat, lon | R km | magMain | 1-wk M≥5 median [p95] P | obs counts | flags |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1786388850023 | 2026-08-10T19:07:30Z | 2026-08-10T19:02:32Z | 0.08 | 2027-08-11 | ETAS-BC | 4.95 | 4.8704, -76.3141 | 125.4 | 7.4 | 1 [0–7] P=0.6902 | 1/1/0/0 |  |
| 2 | 1786388975779 | 2026-08-10T19:09:35Z | 2026-08-10T19:02:32Z | 0.12 | 2027-08-11 | ETAS-BC | 4.95 | 4.8704, -76.3141 | 125.4 | 7.4 | 1 [0–7] P=0.6902 | 1/1/0/0 | same creationTime as v1 |
| 3 | 1786461085116 | 2026-08-11T15:11:25Z | 2026-08-11T14:52:00Z | 0.32 | 2027-08-12 | ETAS-BC | 4.45 | 4.8704, -76.3141 | 125.4 | 7.4 | 0 [0–3] P=0.3569 | 1/1/0/0 |  |
| 6 | 1786773063590 | 2026-08-15T05:51:03Z | 2026-08-14T15:51:27Z | 13.99 | 2027-08-15 | ETAS-BC | 4.15 | 4.8819, -76.3303 | 125.4 | 7.4 | 0 [0–2] P=0.1668 | 3/1/0/0 | posted 14 h after creation |
| 15 | 1787592270318 | 2026-08-24T17:24:30Z | 2026-08-24T17:08:35Z | 0.27 | 2027-08-25 | ETAS-BC | 4.15 | 4.8361, -76.4112 | 125.4 | 7.4 | 0 [0–1] P=0.0646 | 5/1/0/0 | same creationTime as v14 |
| 19 | 1789424929632 | 2026-09-14T22:28:49Z | 2026-09-14T22:17:16Z | 0.19 | 2027-09-15 | ETAS-BC | 4.15 | 4.6331, -76.6048 | 125.4 | 7.4 | 0 [0–1] P=0.092 | 16/1/0/0 | byte-identical to v18 |
| 21 | 1790617076725 | 2026-09-28T17:37:56Z | 2026-09-28T17:27:45Z | 0.17 | 2027-09-29 | ETAS-BC | 4.65 | 4.3997, -76.4427 | 200.0 | 7.4 | 0 [0–1] P=0.0988 | 46/1/0/0 | magMain/R/model change |
| 22 | 1791224184600 | 2026-10-05T18:16:24Z | 2026-10-05T18:12:01Z | 0.07 | 2027-10-06 | ETAS-BC | 4.65 | 4.3985, -76.4253 | 240.7 | 7.4 | 0 [0–1] P=0.0936 | 51/1/0/0 | magMain/R/model change |
| 23 | 1791835282045 | 2026-10-12T20:01:22Z | 2026-10-12T20:01:20Z | 0.00 | 2027-10-13 | ETAS-BC | 4.55 | 4.4721, -76.5375 | 125.4 | 7.4 | 0 [0–1] P=0.1392 | 51/1/0/0 | magMain/R/model change |

### Venezuela us6000t7zp
unique (non-duplicate) versions: 39; issue interval days median 1.09, max 7.7; 1-wk M≥5 median range 0–6, p95 upper range 0–17 (table shows v1–v4, flagged rows and last; 14 of 44)

| v | updateTime ms | update UTC | creationTime UTC | post lag h | expire | model | Mc | centre lat, lon | R km | magMain | 1-wk M≥5 median [p95] P | obs counts | flags |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1782346800899 | 2026-06-25T00:20:00Z | 2026-06-24T23:56:05Z | 0.40 | 2027-06-25 | ETAS-BC | 4.95 | 10.4202, -68.517 | 145.2 | 7.2 | 6 [1–17] P=0.9815 | 1/1/1/1 |  |
| 2 | 1782346981516 | 2026-06-25T00:23:01Z | 2026-06-24T23:56:05Z | 0.45 | 2027-06-25 | ETAS-BC | 4.95 | 10.4202, -68.517 | 145.2 | 7.2 | 6 [1–17] P=0.9815 | 1/1/1/1 | same creationTime as v1 |
| 3 | 1782356359389 | 2026-06-25T02:59:19Z | 2026-06-24T23:56:05Z | 3.05 | 2027-06-25 | ETAS-BC | 4.95 | 10.4202, -68.517 | 145.2 | 7.2 | 6 [1–17] P=0.9815 | 1/1/1/1 | same creationTime as v1 |
| 4 | 1782366027304 | 2026-06-25T05:40:27Z | 2026-06-25T05:30:50Z | 0.16 | 2027-06-25 | ETAS-BC | 4.95 | 10.4356, -68.4996 | 145.2 | 7.2 | 3 [0–11] P=0.9401 | 1/1/1/1 |  |
| 5 | 1782390518552 | 2026-06-25T12:28:38Z | 2026-06-25T12:13:15Z | 0.26 | 2027-06-25 | ETAS-BC | 4.45 | 10.4978, -67.5555 | 250.0 | 7.2 | 3 [0–9] P=0.8896 | 3/1/1/1 | magMain/R/model change |
| 7 | 1782477199743 | 2026-06-26T12:33:19Z | 2026-06-26T12:14:11Z | 0.32 | 2027-06-26 | ETAS-BC | 4.45 | 10.5023, -67.5137 | 250.0 | 7.5 | 1 [0–4] P=0.5238 | 3/0/0/0 | magMain/R/model change |
| 13 | 1782878189358 | 2026-07-01T03:56:29Z | 2026-06-30T04:22:36Z | 23.56 | 2027-06-30 | ETAS-BC | 4.45 | 10.5982, -67.6507 | 250.0 | 7.5 | 0 [0–3] P=0.4173 | 8/0/0/0 | byte-identical to v12; posted 24 h after creation |
| 24 | 1783699378347 | 2026-07-10T16:02:58Z | 2026-07-10T15:18:56Z | 0.73 | 2027-07-11 | ETAS-BC | 4.45 | 10.6466, -67.6123 | 200.0 | 7.5 | 0 [0–1] P=0.132 | 11/1/0/0 | magMain/R/model change |
| 25 | 1783704373007 | 2026-07-10T17:26:13Z | 2026-07-10T15:18:56Z | 2.12 | 2027-07-11 | ETAS-BC | 4.45 | 10.6466, -67.6123 | 200.0 | 7.5 | 0 [0–1] P=0.132 | 11/1/0/0 | same creationTime as v24 |
| 33 | 1785167863714 | 2026-07-27T15:57:43Z | 2026-07-27T15:49:32Z | 0.14 | 2027-07-28 | ETAS-BC | 4.55 | 10.6502, -67.7173 | 199.9 | 7.5 | 0 [0–1] P=0.0572 | 13/1/0/0 | same creationTime as v32 |
| 36 | 1787003291744 | 2026-08-17T21:48:11Z | 2026-08-17T21:45:51Z | 0.04 | 2027-08-18 | ETAS-BC | 4.55 | 10.6574, -67.6237 | 145.2 | 7.5 | 0 [0–1] P=0.0271 | 16/1/0/0 | magMain/R/model change |
| 37 | 1787591056747 | 2026-08-24T17:04:16Z | 2026-08-24T17:01:41Z | 0.04 | 2027-08-25 | ETAS-BC | 4.55 | 10.6352, -67.7572 | 200.0 | 7.5 | 0 [0–0] P=0.0238 | 17/1/0/0 | magMain/R/model change |
| 41 | 1790015526290 | 2026-09-21T18:32:06Z | 2026-09-21T18:31:10Z | 0.02 | 2027-09-22 | ETAS-BC | 4.25 | 10.6042, -67.5477 | 145.2 | 7.5 | 0 [0–1] P=0.0308 | 19/1/0/0 | magMain/R/model change |
| 44 | 1791835080877 | 2026-10-12T19:58:00Z | 2026-10-12T19:57:59Z | 0.00 | 2027-10-13 | ETAS-BC | 4.25 | 10.604, -67.5488 | 145.2 | 7.5 | 0 [0–1] P=0.0251 | 19/1/0/0 |  |

### Kamchatka us6000qw60
unique (non-duplicate) versions: 67; issue interval days median 6.74, max 53.1; 1-wk M≥5 median range 0–130, p95 upper range 3–320 (table shows v1–v5, flagged rows and last; 24 of 80)

| v | updateTime ms | update UTC | creationTime UTC | post lag h | expire | model | Mc | centre lat, lon | R km | magMain | 1-wk M≥5 median [p95] P | obs counts | flags |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1753897479941 | 2025-07-30T17:44:39Z | 2025-07-30T17:05:38Z | 0.65 | 2026-07-31 | ETAS-BC | 5.25 | 51.3264, 159.1253 | 1076.8 | 8.8 | 95 [31–265] P=1.0 | 126/80/3/0 | no nextForecastTime |
| 2 | 1753897487444 | 2025-07-30T17:44:47Z | 2025-07-28T18:57:23Z | 46.79 | 2026-07-29 | ETAS-BC | 4.55 | 21.8592, 95.9414 | 499.9 | 7.7 | 0 [0–1] P=0.0799 | 92/6/1/0 | CROSS-POST: centre 6370 km from epicentre (another event's forecast); posted 47 h after creation; no nextForecastTime; magMain/R/model change; obs M3 count decreased |
| 3 | 1753897493966 | 2025-07-30T17:44:53Z | 2025-07-30T17:05:38Z | 0.65 | 2026-07-31 | ETAS-BC | 5.25 | 51.3264, 159.1253 | 1076.8 | 8.8 | 95 [31–265] P=1.0 | 126/80/3/0 | byte-identical to v1; no nextForecastTime; magMain/R/model change |
| 4 | 1753920685013 | 2025-07-31T00:11:25Z | 2025-07-31T00:00:30Z | 0.18 | 2026-07-31 | ETAS-BC | 5.25 | 51.2758, 159.1098 | 1076.8 | 8.8 | 130 [46–320] P=1.0 | 162/101/3/0 | malformed JSON (trailing comma); no nextForecastTime |
| 5 | 1753920949270 | 2025-07-31T00:15:49Z | 2025-07-30T17:05:38Z | 7.17 | 2026-07-31 | ETAS-BC | 5.25 | 51.3264, 159.1253 | 1076.8 | 8.8 | 95 [31–265] P=1.0 | 126/80/3/0 | byte-identical to v1; posted 7 h after creation; no nextForecastTime; obs M3 count decreased |
| 6 | 1753921181051 | 2025-07-31T00:19:41Z | 2025-07-31T00:00:30Z | 0.32 | 2026-07-31 | ETAS-BC | 5.25 | 51.2758, 159.1098 | 1076.8 | 8.8 | 130 [46–320] P=1.0 | 162/101/3/0 | same creationTime as v4; no nextForecastTime |
| 7 | 1753979341652 | 2025-07-31T16:29:01Z | 2025-07-31T16:25:22Z | 0.06 | 2026-08-01 | ETAS-BC | 5.25 | 51.1847, 159.0264 | 1076.8 | 8.8 | 94 [31–220] P=1.0 | 220/125/5/0 | malformed JSON (trailing comma); no nextForecastTime |
| 8 | 1753979390868 | 2025-07-31T16:29:50Z | 2025-07-31T16:25:22Z | 0.07 | 2026-08-01 | ETAS-BC | 5.25 | 51.1847, 159.0264 | 1076.8 | 8.8 | 94 [31–220] P=1.0 | 220/125/5/0 | same creationTime as v7; no nextForecastTime |
| 15 | 1754096084561 | 2025-08-02T00:54:44Z | 2025-08-02T00:53:10Z | 0.03 | 2026-08-02 | ETAS-BC | 5.25 | 51.2219, 159.077 | 1076.8 | 8.8 | 82 [24–190] P=1.0 | 346/160/6/0 | byte-identical to v14 |
| 18 | 1754335814586 | 2025-08-04T19:30:14Z | 2025-08-03T21:57:02Z | 21.55 | 2026-08-04 | ETAS-BC | 5.25 | 51.2374, 159.1313 | 1076.8 | 8.8 | 48 [13–130] P=1.0 | 453/178/8/0 | byte-identical to v17; posted 22 h after creation |
| 20 | 1754508075437 | 2025-08-06T19:21:15Z | 2025-08-05T20:49:49Z | 22.52 | 2026-08-06 | ETAS-BC | 5.25 | 51.2289, 159.1065 | 1076.8 | 8.8 | 31 [7–87] P=1.0 | 511/190/9/0 | byte-identical to v19; posted 23 h after creation |
| 21 | 1754508171096 | 2025-08-06T19:22:51Z | 2025-08-05T20:49:49Z | 22.55 | 2026-08-06 | ETAS-BC | 5.25 | 51.2289, 159.1065 | 1076.8 | 8.8 | 31 [7–87] P=1.0 | 511/190/9/0 | byte-identical to v19; posted 23 h after creation |
| 23 | 1754508745936 | 2025-08-06T19:32:25Z | 2025-08-06T19:29:56Z | 0.04 | 2026-08-07 | ETAS-BC | 5.15 | 51.2311, 159.1051 | 1076.8 | 8.8 | 33 [8–90] P=1.0 | 542/195/9/0 | byte-identical to v22 |
| 38 | 1756841815130 | 2025-09-02T19:36:55Z | 2025-08-19T18:08:15Z | 337.48 | 2026-08-20 | ETAS-BC | 5.15 | 51.2645, 159.1301 | 1076.8 | 8.8 | 13 [1–41] P=1.0 | 944/261/12/0 | byte-identical to v35; posted 337 h after creation; obs M3 count decreased |
| 41 | 1759165412412 | 2025-09-29T17:03:32Z | 2025-09-22T17:25:38Z | 167.63 | 2026-09-23 | ETAS-BC | 5.15 | 51.3721, 159.2634 | 1076.8 | 8.8 | 9 [1–31] P=0.9988 | 1223/354/19/2 | byte-identical to v40; posted 168 h after creation |
| 42 | 1759165484245 | 2025-09-29T17:04:44Z | 2025-09-22T17:25:38Z | 167.65 | 2026-09-23 | ETAS-BC | 5.15 | 51.3721, 159.2634 | 1076.8 | 8.8 | 9 [1–31] P=0.9988 | 1223/354/19/2 | byte-identical to v40; posted 168 h after creation |
| 49 | 1766855223617 | 2025-12-27T17:07:03Z | 2025-12-27T17:06:52Z | 0.00 | 2026-12-28 | ETAS-BC | 5.15 | 51.4632, 159.3129 | 1076.8 | 8.8 | 4 [0–15] P=0.8369 | 1223/436/24/2 | window start 1.0 d before creation |
| 56 | 1771095649816 | 2026-02-14T19:00:49Z | 2026-02-14T18:59:51Z | 0.02 | 2027-02-15 | ETAS-BC | 5.15 | 51.456, 159.2738 | 1076.8 | 8.8 | 1 [0–5] P=0.6318 | 1003/466/26/2 | window start 1.1 d before creation; obs M3 count decreased |
| 57 | 1771870045243 | 2026-02-23T18:07:25Z | 2026-02-23T18:07:18Z | 0.00 | 2027-02-24 | ETAS-BC | 5.15 | 51.4514, 159.2748 | 1076.8 | 8.8 | 3 [0–15] P=0.7499 | 1006/468/28/2 | window start 3.0 d before creation |
| 65 | 1776732097950 | 2026-04-21T00:41:37Z | 2026-04-21T00:41:27Z | 0.00 | 2027-04-21 | ETAS-BC | 5.15 | 51.4284, 159.2474 | 1076.8 | 8.8 | 3 [0–12] P=0.6256 | 1052/485/27/2 | window start 3.3 d before creation |
| 66 | 1777308647111 | 2026-04-27T16:50:47Z | 2026-04-27T16:50:34Z | 0.00 | 2027-04-28 | ETAS-BC | 5.15 | 51.4268, 159.2395 | 1076.8 | 8.8 | 3 [0–12] P=0.614 | 1061/489/27/2 | window start 3.0 d before creation |
| 68 | 1778527186296 | 2026-05-11T19:19:46Z | 2026-05-11T13:29:57Z | 5.83 | 2027-05-11 | ETAS-BC | 5.15 | 51.4265, 159.242 | 1076.8 | 8.8 | 1 [0–4] P=0.5004 | 1066/491/27/2 | window start 2.9 d before creation |
| 72 | 1781280473453 | 2026-06-12T16:07:53Z | 2026-06-12T16:07:47Z | 0.00 | 2027-06-13 | ETAS-BC | 5.15 | 51.4252, 159.2685 | 1076.8 | 8.8 | 0 [0–4] P=0.4706 | 1075/493/27/2 | window start 7.0 d before creation |
| 80 | 1785514567057 | 2026-07-31T16:16:07Z | 2026-07-31T16:13:11Z | 0.05 | 2027-08-01 | ETAS-BC | 5.15 | 51.4135, 159.2676 | 1076.8 | 8.8 | 0 [0–3] P=0.4809 | 1103/515/29/2 | no nextForecastTime |

### Hubbard Glacier us6000rsy1
unique (non-duplicate) versions: 68; issue interval days median 7.00, max 7.0; 1-wk M≥5 median range 0–2, p95 upper range 0–19 (table shows v1–v3, flagged rows and last; 5 of 68)

| v | updateTime ms | update UTC | creationTime UTC | post lag h | expire | model | Mc | centre lat, lon | R km | magMain | 1-wk M≥5 median [p95] P | obs counts | flags |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1765058285666 | 2025-12-06T21:58:05Z | 2025-12-06T21:47:50Z | 0.17 | 2026-12-06 | RJ-Gen | 4.2 | 60.4133, -139.6604 | 60.0 | 7.0 | 2 [0–19] P=0.7387 | 9/8/2/0/0 |  |
| 2 | 1765061516609 | 2025-12-06T22:51:56Z | 2025-12-06T22:41:49Z | 0.17 | 2026-12-06 | RJ-Gen | 4.2 | 60.4192, -139.6795 | 60.0 | 7.0 | 2 [0–18] P=0.7167 | 20/14/2/0/0 |  |
| 3 | 1765068723788 | 2025-12-07T00:52:03Z | 2025-12-07T00:41:49Z | 0.17 | 2026-12-07 | RJ-BC | 4.2 | 60.4334, -139.723 | 60.0 | 7.0 | 1 [0–5] P=0.6535 | 44/21/2/0/0 | magMain/R/model change |
| 12 | 1765485474709 | 2025-12-11T20:37:54Z | 2025-12-11T20:27:35Z | 0.17 | 2026-12-11 | RJ-SS | 4.0 | 60.4823, -139.7895 | 60.0 | 7.0 | 0 [0–3] P=0.4688 | 262/52/5/0/0 | magMain/R/model change |
| 68 | 1792270321801 | 2026-10-17T20:52:01Z | 2026-10-17T20:41:49Z | 0.17 | 2027-10-17 | RJ-SS | 4.0 | 60.4967, -139.7824 | 60.0 | 7.0 | 0 [0–0] P=0.005836 | 409/72/8/0/0 |  |

## 5. Region definition

- **The forecast JSON carries its own region.** It lives in `model.parameters`: `regionType` (always `circle`), `regionCenterLat`, `regionCenterLon` and `regionRadius` (km). There is no polygon and no time window, and nothing outside `model.parameters`. The centre is not the epicentre: it moves between versions, for example Panama 7.5735,−80.8225 → 7.596,−80.8184, while the epicentre is 7.5868,−80.769.
- **The radius also changes between versions.** Flores: 195.8 → 227.8 (when magMain went 7.7 → 7.8), a one-off 445.6 in v32, then back to 227.8. Venezuela: 145.2 → 250 → 200 → 145.2. Colombia: 125.4 → 200 → 240.7 → 125.4. Panama, Kamchatka and Hubbard keep a constant radius.
- **The `event-sequence` product.** Its properties are `circle-latitude, circle-longitude, circle-radiuskm, region-type=circle, sequence-type=sequence, starttime, endtime, eventtime, minimum/maximum-latitude/longitude` (bounding box), `generated-by` ("USGS Aftershock Forecasting System 1.05.1848"; Hubbard also has 1.06.1866 and 1.06.1876), `review-status` and `title`.
  - `starttime` = eventtime − 30 d.
  - `endtime` = the paired OAF `expireTime`.
  - Each event-sequence version is published alongside an OAF version.
  - Source: the `_sup` detail queries (18:45Z).
- **Panama:** 12 event-sequence versions, all equal to the paired OAF centre and radius, with endtime equal to expireTime.
  - First version (2026-10-10T00:55:12Z): centre 7.5735, −80.8225, R 381.6; start 2026-09-09T17:56:06.036Z; end 2027-10-10T11:17:45.962Z.
  - Last version: centre 7.596, −80.8184, R 381.6; end 2027-10-20T02:11:58.101Z; bounding box lat 4.1619 to 11.0301, lon −84.2830 to −77.3538.
- **Flores:** 34 event-sequence versions for 33 OAF versions. All agree with the nearest OAF version, including the first one (2026-08-15T05:42:49Z), which carries Colombia's circle (4.8704, −76.3141, R 125.4). The cross-post therefore hit both products.
  - Last version: centre −8.1275, 120.7036, R 227.8; start 2026-07-15T21:58:21.561Z; end 2027-10-13T06:20:12.960Z; bounding box lat −10.1775 to −6.0775, lon 118.6328 to 122.7744.
  - `eventtime` milliseconds vary across versions (.564/.505/.561) as the origin was revised.
- **Venezuela:** early event-sequence versions have eventtime 22:05:12.092. ComCat now says 22:05:04.053.
- **Older sequences:** Kamchatka has event-sequence versions only from 2026-05-01 (14 versions), and Hubbard only from 2026-03-07 (33). For earlier issues, `forecast.json` is the only source of the region.
- **Hubbard event-sequence precision:** latitude and longitude have 7 decimals, while `forecast.json` rounds to 4. `endtime` keeps the origin time of day, while `expireTime` is rounded to the hour. These are rounding differences, not real disagreements.

## 6. Observations versus ComCat: data cutoff and catalog revision

**Method.** One superset catalog per sequence, counted locally with a haversine circle (R = 6371 km) for each version's circle:
- Panama: `query?format=csv&eventtype=earthquake&latitude=7.5868&longitude=-80.769&maxradiuskm=500&starttime=2026-10-09T17:56:07&minmagnitude=3&orderby=time-asc` (19:01:44Z).
- Flores: `…latitude=-8.3358&longitude=121.3446&maxradiuskm=700&starttime=2026-08-14T21:58:22&endtime=2026-10-13T00:00:00…` (19:01:57Z).

Server cross-check, from `count?eventtype=earthquake&latitude=7.5735&longitude=-80.8225&maxradiuskm=381.6&starttime=…&endtime=2026-10-10T00:51:02.216&minmagnitude={3,4,5,6}` (18:53:25–18:53:39Z):
- The server returned 27/27/14/2, which includes the mainshock (see §7, sub-second trap). Without the mainshock that is 26/26/13/1, the same as the local count.
- Panama v12 (`…latitude=7.596&longitude=-80.8184…endtime=2026-10-19T15:45:14.355`): server 87/87/18/4, i.e. 86/86/17/3 without the mainshock.
- ComCat M≥3 equals M≥4 here. No M3.x events are catalogued near Panama, so the OAF "M≥3" count is in effect an M≥4 count.

**Catalog revision since issue.**

| Version | OAF obs M≥3/5/6/7 | ComCat now @creation | Difference |
|---|---|---|---|
| Panama v1 | 22/11/1/0 | 26/13/1/0 | +4 at M≥3, +2 at M≥5 |
| Panama v12 | 86/17/3/0 | 86/17/3/0 | exact |
| Flores v2 | 19/10/1/0 | 57/16/1/0 | 3× more events now |
| Flores v33 | 413/60/1/0 | 421/61/1/0 | +8 at M≥3, +1 at M≥5 |

- Panama v1: one example is us6000u2t1 (M5.1 mb, 2026-10-09T18:16:47Z). Its id sits far later in the `us` sequence than its neighbours (u18t…u1bg), which suggests a late addition.
- Flores v2: ComCat backfill is heavy. us6000u2w8 (M5.5, 2026-08-14T22:18:48Z) was last updated 2026-10-16, and Flores counts are still growing two months after the mainshock.
- **Consequence:** scoring against today's ComCat measures more than the forecast. Early-sequence observed counts can be 1.2–3× what USGS saw at issue time.

**Cutoff test: is the data cutoff creationTime or window timeStart?**
- **Comparing totals does not settle it.** Backfill is far larger than the gap between the two cutoffs.
  - Panama: in v1–v3, timeStart falls 9 min after creationTime and one event lies in that gap. That event happened after the forecast was created, so it could never have been counted. The other versions show no difference between the cutoffs.
  - Flores: only v2, v4, v6, v7 and v14 have events between the two times. The "closer match" always picks the earlier of the two times, which is what an undercount does, so it is uninformative.
- **The increment test is the better check** (Δobs between consecutive versions with the same region against ΔComCat). On Flores' cleanest pair, v13→v14→v15 at M≥3 and M≥5, the timeStart cutoff predicts (14, 0, 9, 2) against observed (11, 0, 10, 2), total error 4. The creationTime cutoff predicts (19, 1, 4, 1), total error 16. This **supports cutoff = timeStart**.
- **Kamchatka v71/v72/v73 is decisive.** v72 was created 2026-06-12T16:07:47Z with timeStart 2026-06-05T17:00:32Z, and v73 was created six minutes later, at 16:13:01Z.
  - Query: `count?eventtype=earthquake&latitude=51.4252&longitude=159.2685&maxradiuskm=1076.8&starttime=<a>&endtime=<b>&minmagnitude={3,5,6}` (19:04:16–19:09:24Z).
  - ComCat now counts these M≥3/5/6 events in each window:

    | Window | M≥3/5/6 events |
    |---|---|
    | v71 timeStart → v72 timeStart | 33/2/0 |
    | v72 timeStart → v72 creation | 37/7/1 |
    | v72 creation → v73 creation | 1/0/0 |

  - The OAF observations moved +5/+1/0 from v71 to v72, then +9/+6/+1 from v72 to v73, a six-minute span.
  - Under cutoff = creationTime, v72→v73 should be about 0. The observed +6 M≥5 and +1 M≥6 match the events between v72's timeStart and its creationTime.
  - **Conclusion:** `observations` are counted up to the window `timeStart`, and data cutoff = min(timeStart, creationTime). When timeStart > creationTime (common at Panama, by +3 to +24 min) the cutoff cannot exceed creationTime.
  - Therefore an LLM given "the catalog up to issue time" should be given it up to timeStart, and the scoring window should start at timeStart.
  - Caution: timeStart can be up to 7 days before creationTime (Kamchatka v72). Those forecasts were issued "late", so their 1-Day and 1-Week windows partly or wholly lie in the past at issue time.

## 7. ComCat API practicalities

- **Result limit: 20000 events per query.** application.json (18:44:44Z) does not state it; it lists only catalogs, contributors, producttypes, eventtypes and magnitudetypes. The docs page `https://earthquake.usgs.gov/fdsnws/event/1/` (18:54:00Z) says `limit` must be in [1, 20000] and that larger requests get HTTP 400. Confirmed with `query?format=csv&starttime=2026-10-01&limit=20001` (18:54:00Z), which returned HTTP 400 "Bad limit value "20001". Valid values are 0 <= limit <= 20000". Use `offset` or time-splitting to page.
- **Formats.** `query` supports csv, geojson, kml, quakeml (alias of xml), text and xml; the default is quakeml. `count` supports text (default), geojson and xml. `orderby` accepts time, time-asc, magnitude, magnitude-asc.
- **CSV columns:** `time,latitude,longitude,depth,mag,magType,nst,gap,dmin,rms,net,id,updated,place,type,horizontalError,depthError,magError,magNst,status,locationSource,magSource`. **magType is included**, and so is `updated`, which helps detect revisions. `format=text` also has MagType and MagAuthor but no `updated`.
- **Magnitude rounding.** International (`us`) magnitudes have 1 decimal and drop trailing zeros: "5", not "5.0" (10 of 87 Panama rows, 26 of 391 Flores rows). Latitude and longitude have up to 4 decimals. US regional networks publish unrounded values, e.g. ci41292687 `mag` 4.31762677888687, nc75305736 4.18. Bin with a tolerance, as in `mag >= m - 1e-9`, or round to 0.1 first.
- **magType mix in the 30-day M≥4 catalogs** (`query?format=csv&eventtype=earthquake&latitude=<c>&longitude=<c>&maxradiuskm=<R>&starttime=<origin>&endtime=<origin+30 d>&minmagnitude=4&orderby=time-asc`, 18:53:55–18:53:58Z, using the latest OAF circle):

  | Sequence | Rows | mb | mww | Notes |
  |---|---|---|---|---|
  | Panama (to now, day 10) | 87 | 78 | 9 | all net `us`, reviewed |
  | Flores | 391 | 376 | 15 | |

  Rows average 185–187 bytes. Mixed mb/mww is the norm, so an M≥5 threshold mostly means mb ≥ 5.
- **Sub-second times are ignored in starttime.** `starttime=2026-10-09T17:56:06.999` still returned the mainshock at 06.036 (count 27). `starttime=…T17:56:07` returned 26 (18:54:54–55Z). To exclude the mainshock, use whole seconds (mainshock+1 s) or filter by id.
- **includesuperseded detail responses are large.** They are 0.7–7.1 MB per event (Myanmar 7.1 MB; 34 MB for the 11 events), so cache them.
- **Count requests can fail.** A 1076.8 km-radius count took about 10–35 s each and once returned HTTP 502 from nginx. Retry with backoff.
- **updatedafter reflects any product change.** It also catches routine OAF re-issues on small events, so it is not a "new event" filter.

## 8. Size estimate

`forecast.json` totals are bytes on disk and equal the sum of `contents['forecast.json'].length`. ComCat counts come from `count?eventtype=earthquake&latitude=<latest OAF centre>&longitude=…&maxradiuskm=<latest R>&starttime=<origin−365 d>&minmagnitude=<m>` with no endtime (now), retrieved 18:55:10–18:55:14Z.

| Sequence | OAF files | forecast.json bytes | ComCat cut | Count | CSV est. (×200 B) |
|---|---|---|---|---|---|
| Panama | 12 | 383,568 | M≥4.0 | 134 | 26.8 kB |
| Flores | 33 | 937,678 | M≥4.0 | 473 | 94.6 kB |
| Kamchatka | 80 | 2,864,054 | M≥4.0 | 5,022 | 1.00 MB |
| Venezuela | 44 | 1,101,421 | M≥4.0 | 20 | 4.0 kB |
| Colombia | 23 | 561,419 | M≥4.0 | 67 | 13.4 kB |
| Hubbard (US) | 68 | 1,062,007 (+3,600,192 forecast_data.json, not downloaded) | M≥2.5 | 1,118 | 223.6 kB |
| **Total** | 260 | **6,910,147** | | 6,834 | ≈1.37 MB |

Each sequence fits in a single query under the 20000 limit.

## 9. New events

- **M≥6.5:** none. `query?minmagnitude=6.5&starttime=2026-10-19T00:00:00&format=geojson` (18:44:42Z) returned count 0.
- **New OAF products today.** Found with `query?producttype=oaf&updatedafter=2026-10-19T00:00:00&starttime=2024-01-01&format=geojson` (18:44:43Z), which matched 16 events. Each event's current OAF updateTime was then checked with `query?eventid=<id>&format=geojson` (18:55:32–18:55:45Z). All 16 have a new OAF version today:
  - Panama v12, updateTime 2026-10-19T15:52:54Z (only the Panama sequence among the candidates).
  - 15 routine daily or weekly re-issues for M4.0–6.1 events: aka2026msxacu, aka2026ukynnb, ci41292687, nc75305736, nn00924954, tx2026burunl, tx2026uacobs, us6000sayv (M6.0), us6000sgk0, us6000t8yt, us6000tzna, us6000u1cd, us7000srjx (M6.1 Cuba), us7000td35, us7000tesi.
  - Each re-issue lands about 10 min after its origin's time of day.
- **No new Flores, Venezuela or Colombia version** as of 18:56Z. Their last weekly issues were 2026-10-12 around 19:53–20:01Z, so on the weekly cadence the next one is due later today. Re-check before freezing.

## 10. Anomalies and traps

1. **Cross-posted forecasts.**
   - Flores v1 is byte-identical to Colombia v2: magMain 7.4, Colombia's circle, created 2026-08-10, posted to Flores 2026-08-15T05:42Z.
   - Kamchatka v2 is a Myanmar forecast: magMain 7.7, centre 21.86, 95.94, R 499.9, created 2025-07-28.
   - The Myanmar archive has two versions at 2025-07-30T17:41–17:42Z whose length (37,181) equals Kamchatka v1's, which suggests the reverse cross-post (not downloaded).
   - **Validate** magMain and the distance from the circle centre to the epicentre before using any version.
2. **Re-posts.** Byte-identical copies and same-creationTime versions: Panama 1, Flores 2, Kamchatka 12, Venezuela 5, Colombia 3, Hubbard 0. Some were re-posted long after creation: Kamchatka v38 after 337 h (copy of v35), v41/v42 after 168 h, Panama v2 after 15 h. **Issue time is `creationTime`, never `updateTime`.** De-duplicate on creationTime.
3. **The window start differs from creationTime**, from −7.0 d (Kamchatka v72) to +14.6 h (Colombia v7). ETAS window starts fall on round clock times plus a constant offset per sequence: Panama hh:00:28.116, Flores hh:00:31, Kamchatka 17:00:32 weekly. `observations` stop at timeStart (§6).
4. **Malformed JSON.** Kamchatka v4 and v7 (2025-07-31) contain `},]` trailing commas, so a strict `json.loads` fails.
5. **Non-monotone fractiles.** In Kamchatka v19–v23, v45 and v51, `fractileValues` are not monotone; for example v19's 1-Month M≥3 bin starts [2331, 2856, 2735]. Sort the fractiles or reject the version before deriving quantiles.
6. **Venezuela doublet.** us6000t7zc (M7.2, 22:04:31Z, −68.556) came 33 s before us6000t7zp (M7.5) and has no OAF of its own.
   - OAF v1–v6 (to 2026-06-25T18:50Z) use magMain 7.2, centre near the M7.2, and obs M≥7 = 1 (the M7.5 counted as an aftershock).
   - From v7 the forecasts use magMain 7.5 and the observations reset.
   - The Venezuela sequence is small: 20 M≥4 events within 145 km over a year.
7. **Kamchatka sequence.**
   - There is a 53-day gap with no new forecast: from 2025-09-22 (or the 2025-09-29 re-post) to 2025-11-14.
   - Three separate M≥7 events with no OAF of their own (M7.4 2025-07-20 foreshock, M7.4 2025-09-13, M7.8 2025-09-18) sit inside the 1076.8 km circle.
   - Observed counts drop between versions (M≥3 1293 → 1003 at v56) because of catalog revision.
   - The Flores v1 and Kamchatka v2 cross-posts also show "count decreased".
8. **Hubbard.** The model changes (RJ Generic → Bayesian → Sequence-specific) and observed M≥3 drops 411 → 408. The radius is only 60 km and Mcat is 4.0–4.2.
9. **FDSN ignores sub-second time in starttime** (§7). ComCat is still being backfilled two months after a large international mainshock (§6).
10. **advisoryTimeFrame** switches from "1 Week" to "1 Month" during a sequence, and Kamchatka v80 says "1 Year". It is display text, not a window selector.
