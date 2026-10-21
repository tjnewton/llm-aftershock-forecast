# ADR 0004: Issue-time schedule and information cutoff

Status: Implemented in `laf.tables.select_issue_times`.

## Decision
- Targets t in {1, 3, 7, 14, 28} days after the mainshock.
- **With OAF:** the first valid archived version, plus for each target the earliest valid
  version whose information cutoff falls in [origin + t, origin + t + max(1 d, t/4)). Targets
  that select the same version merge (issue id suffix `first+1d`).
- **Without OAF:** issue times = origin + 0.3 d ("first", the median latency of the first
  archived international OAF) and origin + t exactly; windows start at the issue time and last
  1 day, 7 days and one calendar month (as OAF "1 Month" windows do: 30 or 31 days).
- **Information cutoff = min(creationTime, window timeStart).** The LLM and every refit
  baseline see only events with origin time strictly before this instant. Reason: in many
  international versions the windows start before `creationTime` (Flores up to -6 h, Venezuela
  -9 h, Kamchatka up to -7 days on a re-post), so keying on `creationTime` alone would show the
  forecaster events inside its own forecast window.
- Duplicates (same information cutoff) keep the earliest posted version.
- Versions failing validation or the event-match check are never selected.
- Primary cells: windows closed at least 21 days before the scoring snapshot (ComCat M>=5
  counts are still revised weeks later). 2-day settling is a sensitivity
  analysis. Panama cells are scored in the follow-up.

## Consequences
61 issue times over 11 sequences in snapshot 20261021T1027Z. Panama has 4 (first, 1d, 3d, 7d);
its 14d target (2026-10-23) falls after the event and is part of the prospective extension.
USGS's own data cutoff is the window start (Kamchatka v72 to v73; docs/research/
data-availability.md section 6), which supports min(creationTime, timeStart).
