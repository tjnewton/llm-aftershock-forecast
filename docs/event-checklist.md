# Event checklist (OSI Hackathon, Oct 21-22, 2026)

> Historical: the event-day runbook as written on Oct 20-21. The work it lists is done;
> boxes were not ticked. Outcomes: README.md, docs/writeup.md, docs/deviations.md.

Hour-by-hour runbook: docs/PLAN.md section 8. Times are ET.
Slack and social posts are made by the participant only.

## Morning of Oct 21 (07:30-08:15): re-checks
- [ ] Slack: 2026 submission route, rubric, tracks, prizes, rules on prior work or proprietary
      APIs, write-up template, whether Earth science counts. Note anything that changes the plan.
- [ ] https://llmhackathon.github.io/agenda/ deadline still Oct 22 19:00 CT; NC State 18:00 ET.
- [ ] New large earthquakes: `curl -s "https://earthquake.usgs.gov/fdsnws/event/1/query?format=csv&starttime=2026-10-19&minmagnitude=6.5"`.
      A new M>=7 does NOT join the test set (prereg section 4); log it for the prospective set.
- [ ] Panama: newest OAF version time and any M>=6 aftershock.
- [ ] `uv run laf fetch` (new snapshot S21; rerun with `--snapshot S21` after 5xx errors).
- [ ] Event histories for new events (as-of catalog, ADR 0011; ComCat allows 500
      requests per 5 minutes, the fetcher paces itself; run ONE fetch at a time):
      `uv run laf asof --snapshot S21 --only us6000tjl2 us6000t7zp us6000tkt2 us6000u18k --workers 16`,
      `uv run laf asof --snapshot S21 --only us6000qw60 --workers 16 --min-mag 4.9` and
      `--min-mag 2.9 --max-days 16`, and for each other sequence `--min-mag 2.9 --max-days
      <last issue day + 1>` (values in ADR 0011).
- [ ] `uv run laf tables --snapshot S21`; `uv run laf verify`; `uv run laf items --snapshot S21`.
- [ ] Regenerate data-card counts for S21; check `query_covers_x1_5` is all true and
      `catalog_source` is `asof` for every issue.
- [ ] `uv run laf etas --snapshot S21` (as-of, registered), `--catalog hindsight` (catalog
      effect) and `--settings analyst` (labelled sensitivity variant), about 2 min each, and `uv run laf etas --snapshot S21 --validate` (seed offset 0:
      exit 1 means V2 < 0.80, so the refit becomes exploratory; log it).
- [ ] `issue_times.n_hindsight_m4` is 0 for every issue (else refetch histories, rebuild tables).
- [ ] `uv run laf etas-validate --snapshot S21 --parts v0 v3 decomp` (V0 misses only +-1, ADR 0011;
      results into ADR 0010 section 4).
- [ ] Novelty spot check: arXiv listing for "LLM aftershock" / "language model earthquake
      forecast" (docs/research/novelty-and-literature.md queries A1, A14).
- [ ] Claude models overview: IDs and cutoffs unchanged; pricing unchanged.
- [ ] `.env` present (do not print it); Console workspace limit $150; spend so far `uv run laf spend`.
- [ ] Windows 5090: `llama-server` starts with both models; one request each returns valid JSON.

## Freeze (08:15-09:00)
1. `git status` review; `uv run pre-commit run --all-files`; first commits (small, by topic:
   scaffold, data layer, data snapshot, docs, prompts).
2. Fill prereg placeholders: snapshot id, `shasum -a 256 data/manifest.jsonl`,
   `shasum -a 256 data/processed/S21/items.jsonl data/processed/S21/etas_forecasts*.parquet`,
   `prompts/HASHES.json`,
   `find src/laf -name '*.py' | sort | xargs shasum -a 256 | shasum -a 256`.
3. Commit; `shasum -a 256 docs/preregistration.md`; `git tag -a prereg-v1 -m "<sha256>"`.
4. Participant: `gh repo edit --visibility public` (confirm), then `git push --follow-tags`.
5. Participant posts tag, commit SHA and file SHA-256 in Slack.

## Day 1 and Day 2 runbook
See docs/PLAN.md section 8. Gates: Haiku canary valid by 14:00 ET Oct 21 (else T0); Opus back
by 08:00 ET Oct 22 (else ladder); results not retrieved before `scoring-v1` unless scoring was
frozen at `prereg-v1`; submit by 16:00 ET Oct 22.

## Video storyboard (aim 2:00, hard limit 4:00)
| Time | Shot | Narration (key line) |
|---|---|---|
| 0:00-0:15 | Panama M7.7 map, aftershock animation | "Ten days ago an M7.7 hit Panama. People ask chatbots: how many more, how big?" |
| 0:15-0:35 | USGS forecast page next to a chatbot answer | "USGS publishes calibrated forecasts. We scored LLMs against them, on earthquakes after the models' training cutoff." |
| 0:35-0:55 | Pipeline diagram: ComCat + OAF versions to items to models to scores | "Same information USGS had at each issue time. No tools, no web. Every prompt, model ID and response logged and hashed." |
| 0:55-1:30 | Headline figure: per-sequence log-QS vs official; fan chart for Flores | "Result: ..." (per-sequence; same catalog USGS saw) |
| 1:30-1:45 | Calibration/coverage figure; invalid-output rates | "Calibration ..." |
| 1:45-1:55 | Live Panama: hashed forecast vs what happened in the first day | "A preregistered live forecast, hashed before the window opened." |
| 1:55-2:00 | Repo URL, licence, "pilot; negative results are results" | "Open benchmark; it grows with every new forecast USGS issues." |

## One-page write-up outline (2025 collective-paper template; prose, no bullets)
- **Title and team:** "Do LLMs forecast aftershocks like the USGS? A contamination-aware
  benchmark"; solo; CRediT: conceptualization, data curation, software, formal analysis,
  visualization, writing (all T. Newton).
- **Introduction (2-3 lines):** chatbots are asked hazard questions; USGS operational forecasts
  give calibrated numbers; no study has scored LLMs as aftershock forecasters with proper
  scoring rules on post-cutoff sequences.
- **Results (with 1 figure):** design in two sentences (sequences, issue times, arms, models,
  scoring, baselines); the headline per-sequence comparison with CIs; calibration; invalid
  rates; caveats (pilot scale, as-of catalog rebuilt from ComCat histories; official
  P(M>=6) scored as published, slightly below 1 in near-certain cells).
- **Future work (1-2 sentences):** prospective preregistered extension over every new OAF
  sequence; more models; tool-using arm.
- **Open-source materials:** GitHub repo, frozen benchmark, video link.
- **References (6):** Reasenberg & Jones 1989; Page et al. 2016; Gneiting & Raftery 2007;
  Bracher et al. 2021; Karger et al. 2025 (ForecastBench); QuakeGen 2026 (DOIs in
  docs/research/novelty-and-literature.md section D).

## Submission checklist
- [ ] Social post (platform per Slack), with video link and write-up.
- [ ] Video <= 4 min (aim 2 min), captions, repo URL on screen.
- [ ] One-page write-up (PDF and Markdown).
- [ ] Repo public; README results; tags `prereg-v1`, `live-panama-1`, `v0.1-submission`.
- [ ] Global (Luma) registration confirmed (required to reach judges).
- [ ] Calendar reminder: collective-paper write-up request (2025 write-ups arrived up to
      4.5 months after the event).
