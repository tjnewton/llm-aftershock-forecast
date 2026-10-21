# ADR 0002: Region definitions

Status: proposed.

## Decision
- **Sequences with an OAF product:** each issue time is scored inside the circle stated in that
  forecast version (`model.parameters.regionCenterLat/Lon/regionRadius`). Prompts state the same
  circle, so every forecaster predicts the same quantity.
- **Sequences without OAF:** a circle around the ComCat epicentre of radius
  max(10 km, 1.5 * 10^(-2.44 + 0.59 M)) km (1.5 x the Wells & Coppersmith 1994 subsurface rupture
  length, all slip types). This reproduces the research-note radii (Chiapas 110.4 km).
- Catalog queries use a circle centred on the epicentre with radius 1.5 x max over valid
  versions of (radius + centre offset), so every scoring circle scaled x1.5 lies inside it and
  the region sensitivity analyses need no new download (`issue_times.query_covers_x1_5`).
- Distances: great circle on a 6371 km sphere. ComCat's own circle test differs slightly; counts
  are filtered locally so every forecaster is scored on identical events.

## Evidence
- The OAF JSON carries the circle; verified on Panama v1 (7.5735N, 80.8225W, 381.6 km).
- Some OAF versions are filed under the wrong event (Kamchatka's first product is a Myanmar
  forecast; Flores' first is a Colombia forecast). Versions are rejected when the circle centre
  is more than max(50 km, half the radius) from the epicentre, when `magMain` differs from the
  event magnitude by more than 0.3, or when they were created before the mainshock
  (`Forecast.event_mismatch`). Four Venezuela versions fail the centre test (about 142 km off);
  they are excluded and listed in the data card.
