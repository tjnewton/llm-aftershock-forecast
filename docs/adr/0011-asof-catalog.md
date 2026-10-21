# ADR 0011: ComCat catalog as it stood at each issue time

Status: **accepted.** Living document: the method below is the
current one; the changelog at the end records how it got here.

## Decision
Rebuild, for every issue time T, the catalog an operational forecast fetching ComCat at T would
have seen, from ComCat's own product histories, and use it

1. for the LLM prompts (`issue_catalogs`, so the LLM sees what USGS saw, not today's revisions);
2. for the legacy-ETAS validation and refit decomposition (ADR 0010 section 4).

Outcomes (`observed_counts`) stay on the snapshot's current ComCat: the final, revised catalog
is the best estimate of what happened.

## Method (`src/laf/asof.py`)
- **Histories.** `laf asof --snapshot S` fetches, for every catalog event from 7 days before the
  mainshock to 90 days after it (optionally above a magnitude floor and up to a day limit), the
  ComCat event document with `includesuperseded=true`, which lists every version of every
  product. Stored once per event as `raw/events/<id>.geojson.gz` with a manifest entry; versions
  older than the fetch never change, so all snapshots share these files.
- **Origin versions.** Each version of each `origin` product gives source, code, status,
  `updateTime` (set by the source), `indexTime` (when ComCat indexed it), `preferredWeight`, and
  the origin's time, location, depth and magnitude.
- **As of T.** A version is available at T if its `indexTime <= T`. For each product (source,
  code), take its latest available version; drop products whose latest version is a deletion;
  the event's preferred origin at T is the remaining product with the highest
  `preferredWeight` (ties: the latest). The mainshock's own history comes from its event
  document in the snapshot.
- **Rate.** ComCat allows 500 requests per 5 minutes per client; the fetcher paces itself at
  1 request/s across threads and waits the requested 5 minutes on HTTP 429.
- **Missing histories never drop events.** `as_of_or_hindsight` adds the hindsight row of every
  event without a history (below a fetch floor, or a failed request); `issue_catalogs` marks
  such rows `from_hindsight` and `issue_times.n_hindsight_m4` counts those a forecaster would see
  (M >= 4). The freeze requires 0.

## Validation (V0): the official products' own observation counts
Each legacy-ETAS `forecast.json` records how many fetched events it had above M3, M5, M6 and M7
in its data window (`observations`). Counting the as-of catalog at the product's creationTime
with the port's own event selection (forecast circle, after the mainshock, before the data end,
1,000 largest with ties; `laf etas-validate --parts v0`) must reproduce them.

| Sequence | Checkable counts | Exact, as-of | Exact, hindsight |
|---|---|---|---|
| Colombia | 84 | 100% | 76% |
| Flores Sea | 120 | 99.2% | 52% |
| Kamchatka | 84 | 95.2% | 31% |
| Panama | 48 | 100% | 52% |
| Venezuela | 128 | 100% | 69% |
| Sand Point (RJ) | 105 | 100% | 93% |
| Hubbard Glacier (RJ) | 105 | 73.3% | 97% |
| **All** | **674** | **95.1%** | **69.1%** |

A count is checkable when every hindsight event within 0.5 magnitude units of its threshold has
a history and the version's data window lies inside the snapshot catalog. Misses are all +-1:
Hubbard's +1 at M>=5 is one early aftershock whose Alaska origin (ml 5.11) and NEIC origin
(us6000rsy4, mb 5.0) were one ComCat event at the time and were split into two events about two
months later (`us7000rpbv`); Kamchatka (4) and Flores (1) are single M>=3 events. Flores' first
version: 56 M>=3 events in today's catalog, 19 then.

## Limitations
- **Deleted events** are not reconstructed: ComCat's `includedeleted=true` queries timed out
  (HTTP 504 after 60 s, even one day worldwide at M>=4). Events that existed at T and
  were later deleted are missing. V0's exact agreement bounds their effect on these sequences.
- **Association changes**: events are keyed by today's ComCat ids, so origins associated into one
  event then and split later (Hubbard's us7000rpbv), or separate then and merged later, are
  counted as they are associated today.
- **Magnitude floors.** Histories were fetched for all events of the ETAS sequences, for
  Kamchatka above current M2.9 up to one day after its last issue time and above M4.9 to day 90
  (the fit uses M >= 5.15, simulations start at 5.8), and for the other sequences above current
  M2.9 up to one day after their last issue time (prompts show M >= 4.0). Below those floors the as-of catalog is incomplete; the refit's as-of variant is
  reported only where it is complete.
- Availability uses `indexTime`; a product re-indexed later than its first availability would
  appear late. V0 shows no such case.
- A history fetched at time F answers "as of T" only for T <= F; histories are fetched after the
  last issue time of every sequence in the benchmark, but a later snapshot with new issue times
  must refetch the affected events.

## Changelog
- built, with pacing at 1 request/s and 429 handling.
- events without a history fall back to their current origin (`as_of_or_hindsight`), counted
  by `n_hindsight_m4`.
- snapshot 20261021T1027Z: all histories fetched (4,691 events, 0 failures); `n_hindsight_m4` =
  0 for all 61 issues; V0 379/380 on the four 2026 ETAS sequences and 95.1% over 674 counts
  including Kamchatka and the RJ sequences. Prompts and the registered refit use the as-of
  catalog.
