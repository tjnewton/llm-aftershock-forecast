<!--
Provenance. Written by an independent reviewer (a fresh agent with no view of the project lead's
opinions), asked to act as a hostile Seismica referee of the manuscript draft
docs/manuscript/manuscript.md at commit 085fd18d, before the freeze and before any confirmatory
result. It ran no `laf` command, made no API call, wrote nothing in the repository and computed
no score on confirmatory data; its counts on the candidate snapshot use the sequence,
issue-time and forecast tables only, which docs/adr/0013-data-splits.md allows before the
freeze. The report is reproduced as returned, with two edits: the path of the reviewer's
scratch scripts is removed, and one cross-reference in section 0 is corrected (the earlier
reviews are mapped in section 8). "ms L" and "PR L" are line numbers of the manuscript and
of docs/preregistration-v2.md at that commit.

Checked afterwards by the project lead: the population counts of concern M2 (36 Alaska, 35
Marianas region, 6 Oregon; 72 on the `us` network; 19 with magnitude type mb; 35 at 35 km or
deeper and 20 at 70 km or deeper, maximum 247 km; completeness 4.6 for 39, 3.5 for 47, 3.0 for
3; 61 below M5.5, maximum M6.2), from the candidate snapshot's `sequences` table alone; the
self-contradiction in the pre-registration's prior-exposure list (section 5, item 1); and that
strict items are filtered by the on-time rule in `confirmatory.py`. Not rechecked by the lead:
the clustering count of M6, the late shares quoted from ADR 0017, and the literature list, which
the reviewer cites from memory.
-->

# Referee report: "Can general-purpose language models forecast aftershocks? A pre-registered comparison with the USGS operational aftershock forecast"

Reviewed at commit 085fd18d (branch post-submission): `docs/manuscript/manuscript.md` ("ms L…") against `docs/preregistration-v2.md` ("PR L…").

**Recommendation: major revision, and do not freeze the protocol as it stands.** The engineering is careful and the disclosure is better than most submissions. But the primary test cannot return a verdict, the reference forecast has no demonstrated advantage over a constant on this target, and the population is seismologically much narrower than the manuscript says.

## 0. What I checked and how

- **Read in full:** the manuscript, the pre-registration, the journal-rules and literature notes, ADRs 0012, 0013, 0014, 0017 and 0018, and the opening of ADRs 0010 and 0016.
- **Code read in full:** `confirmatory.py`, `d2.py`, `scoring.py`, `schemas.py`, `forecast.py`, `items.py`, `catalog.py`, `splits.py`, `analysis.baselines`, and the v3 prompt templates.
- **Code checked by search only:** `publish.py`, `live_scores.py`, `prospective.py`, `sensitivity.py`, `openai_runner.py`.
- **Not read:** `etas.py`, `generic_rj.py`, `tables.py`, `asof.py`, `live_watch.py`, `runner.py`, `cli.py`.
- **Development tables:** I compared the manuscript's size, power and dry-run figures with the `d3_20261021T2300Z` CSVs. I did not re-simulate anything.
- **Outcome-blind counts on the candidate snapshot 20261029T2000Z:** three small scripts read `sequences`, `issue_times` and `forecast_bins` only. I did not open `observed_counts`, `catalog` or `issue_catalogs`, and scored nothing.
  - `issue_times` carries `oaf_obs_m5`, `comcat_m5_at_cutoff` and `n_hindsight_m4`. The table was loaded, but those columns were never printed or used.
  - The clustering count in M6 uses only mainshock pairs more than twice the larger circle radius apart, so no cell's outcome is touched. It is reported as an aggregate.
- **Not run:** any `laf` command, any test, any network or API call. Git was used read-only (`log`, `show`, `tag -l`).
- **Not verified:** the 99.05% as-of match, the 463 of 472 and 76 of 89 official-model counts, the 71% all-zero cells, the 49%, 17% and 85% answer statistics, and the dry-run timing figures. I quote those from the project's documents.
- The two earlier reviews were read last; section 8 maps them.

## 1. What the paper claims to do

- It compares single, tool-free answers of five LLMs with the USGS operational aftershock forecast on sequences that postdate each model's documented cutoff plus three months.
- The one primary test (A) asks whether `gpt-5.1-2025-11-13` is non-inferior to the official forecast on 89 retrospective M≥5 sequences.
  - The estimand is the mean over sequences of the per-sequence mean log-score difference for P(at least one M≥5), clipped to [0.001, 0.999].
  - The margin is 0.02 nats, tested one-sided at 0.05 with a sequence-level bootstrap-t.
- Generic Reasenberg–Jones is run through the same test, and two negative controls (a rule of thumb, a constant 0.041) are predicted not to pass.
- A prospective arm (Opus 5.5, gpt-6.1-sol) with sealed, time-stamped forecasts feeds secondary estimates without a verdict.
- The manuscript says in advance that the primary test is expected to be inconclusive.

## 2. Major concerns, ranked by damage at review

### M1. The primary test cannot return a verdict, and the reference has no demonstrated effect
Lines: ms L114–125, L356–400, L514–524.

- **Power.** It is 4% at the development estimate and 11% at a true difference of zero (ms L395–397; I confirmed 0.038 and 0.112 in the size CSV). A referee will ask why a test with that power is registered as the primary hypothesis.
- **The reference is not shown to beat a constant.** On development data the constant-probability control is +0.021 against the official forecast, with a 90% interval of −0.030 to +0.099 (PR L180–181; confirmed in the dry-run secondary table). Generic RJ is −0.009 (PR L167–168). A non-inferiority claim needs evidence that the reference has an effect on this endpoint. Here the only such evidence is a calculation that assumes the official probability is the truth (ms L366–369).
- **The margin gives away most of that assumed effect.** I recomputed the scale from the frozen official probabilities and it reproduces:

  | Forecaster, if the official probability were true | Expected loss (nats) |
  |---|---|
  | Half the official probability | 0.006 |
  | Double | 0.012 |
  | One third | 0.014 |
  | One fifth | 0.025 |
  | One tenth | 0.042 |
  | Best single constant (2.9%) | 0.031 |
  | One constant per window length | 0.028 |

  So 0.02 is about two thirds of the official forecast's entire expected advantage over a forecaster that knows nothing. PR L143–145 says so; the manuscript does not. Fixed-margin practice keeps at least half of a conservatively bounded reference effect. This margin keeps about a third of a model-assumed one.
- **Asymmetry.** The margin admits a threefold under-forecast (0.014) and rejects a threefold over-forecast (0.052). The manuscript mentions the first (ms L370–371) and not the second, which is the wrong way round for a hazard product.
- **"Assay sensitivity" is misused** (ms L379–382, citing a CONSORT extension). The term means the trial's ability to tell an effective treatment from an ineffective one, and the source is ICH E10. Testing generic RJ, which is the official product at the first issue of 76 of 89 sequences, is a different check.

**Fix.** Either (a) register the estimate and its interval as the primary outcome, with no verdict vocabulary in the title or abstract and interpretive thresholds stated in advance; or (b) register a three-arm retention-of-effect design. Option (b) first shows the official forecast superior to the constant and to generic RJ on the same cells, then asks whether the model retains a stated share of that measured advantage. In both cases report the bound at one-sided 0.025 beside 0.05. The level's looseness is conceded at PR L484–486 and missing from the manuscript.

### M2. The population and target are much narrower than the manuscript says
Lines: ms L172–196, L548–558, L574–579.

My counts on test A's 89 sequences (outcome-blind):

| Property | Count |
|---|---|
| Place: Alaska | 36 |
| Place: Guam, Northern Marianas, Micronesia, Mariana region | 35 |
| Place: Oregon and offshore Oregon | 6 |
| Located by the `us` network (NEIC) | 72 |
| Mainshock magnitude type mb | 19 |
| Depth ≥ 35 km | 35 |
| Depth ≥ 70 km (maximum 247 km) | 20 |
| Regional completeness magnitude 4.6 | 39 |
| Regional completeness magnitude 3.5 | 47 |
| Regional completeness magnitude 3.0 | 3 |
| Mainshock below M5.5 (maximum M6.2) | 61 |

The forecast circle radius is exactly 10 km from the 10th to the 90th percentile (maximum 30 km). The median first issue is about 10 minutes after the mainshock.

A seismologist will object on five grounds, none of which the manuscript discusses:
- **Two regions decide the result.** Eighty percent of the primary set is Alaska and the Marianas. The manuscript names neither.
- **Intermediate-depth events are aftershock-poor.** A forecaster can match or beat a generic prior on a 115 km intraslab event by knowing that. This is not skill at reading a sequence.
- **The target is not an aftershock in the usual sense.** For 61 of 89 mainshocks (M5.0–5.4), "at least one M≥5" means an event about as large as or larger than the mainshock. That is a foreshock or doublet probability, far above what Båth's law expects for the largest aftershock.
- **The catalog shown is mostly incomplete.** The prompt lists "M≥3 events" (ms L261–263), but the catalog is incomplete below 3.5 or 4.6 for 86 of 89 sequences, and the model is not told. Absence of small events is then non-informative, and the model may read it as quiescence. This gap is not among the five listed (ms L230–237).
- **The circle is the size of the location error.** A 10 km epicentral circle around an NEIC location in the Marianas is of the order of the location uncertainty. ms L575 says "the median circle … has a radius of 10 km", which understates that almost all are 10 km. Depth is ignored.

Also missing: which events receive an OAF product and whether that policy changed, and that the operational code changed during the archive (ADR 0010 section 3.5).

**Fix.**
- Add a population table (region, depth class, network, magnitude type, completeness, official model type).
- Register outcome-blind strata: depth below and above about 70 km, Alaska / Marianas / other, and first day.
- State the foreshock reading of the target.
- Tell the model the completeness magnitude, or list this as a sixth gap.
- Add M≥4 where complete (Alaska, CONUS) as a registered estimate.
- Scope the title to moderate mainshocks with automatic forecasts.

### M3. The account of what changed after development results is incomplete
Lines: ms L324–337, L372–377, L525–537.

The manuscript discloses the margin's path (0.02, then 0.05, then 0.02), the invalid-answer rule and the change of primary score. I verified that the 0.02 proposal was committed at 10:33 on 2026-11-11 (f4d525a9) and the development rerun at 14:40 (b4f70eea). The following changes are in the pre-registration or ADR 0018 and absent from the manuscript:

1. The test changed from two-sided equivalence to one-sided non-inferiority after gpt-5.1's first development run showed it beating the official forecast at M≥4 (ADR 0018 L226–227, L243–244).
2. gpt-5.1 was made sole primary, and prospective test B was demoted, after its development effects were known. ADR 0018 L186 had called B "the paper's thesis" (PR L129–130).
3. The margin was 0.10 on a different score for eleven days, when power was 0.42 to 0.45 (PR L135–136, L234–236). The manuscript names 0.10 only as a sensitivity margin.
4. The level was 0.025 at the first Holm step and became 0.05 with the justification "the power available justifies it" (PR L484–486).
5. Sonnet 4.6 was the first negative control. It was dropped when its development result stopped being bad, and replaced by controls of which one "can hardly fail" (PR L186–188, L177).
6. The informative-sequence rule was replaced; the old one kept 5 of 89 (PR L193–194).
7. The original proposal said the final margin "should be set after the development rerun gives the models' own effects" (proposal at f4d525a9, P3). ms L373–374 quotes only the first half of that.
8. The margin's restoration and the invalid-rule change were decided in the same sitting (decisions 42 and 43). Together they move the development estimate from +0.019 to +0.017 against a margin of 0.02. The manuscript reports each separately.
9. The primary model runs at effort `medium` because `high` was cut off at a 16,000-token pilot cap on three items. The study cap is 32,000 (ADR 0014 decision 6). ms L251–253 says "used up the pilot's output limit" without saying the limit was half the study's.

None of these is improper on development data. Omitting them is what lets a reader say the design was tuned.

**Fix.** One dated table of every design decision made after a development result, giving what was known at the time and the effect on the development estimate or power.

### M4. The prospective comparison selects against the informative forecasts
Lines: ms L421–443, L606–609.

- The project's own replay finds that 43% to 50% of matched items would be late at 10-minute polling, and that the window opens before publication in 30% of versions (ADR 0017 L52–61).
- The lead's note heading the first mock review records that 0 of 3 first issues in the live dry run had the matched window still closed at detection.
- First-day cells are where the official probability is largest (median 8.4% against 0.3% after day 7, PR L542–543). So test B's prospective part will consist mostly of later, near-empty cells.
- The manuscript gives no expected late share and no on-time share by slot. Its limitations list is silent on this.
- "The strict item guarantees that every forecast precedes its window" (ms L430–431) is not what the code does. Strict items are also filtered by the on-time receipt (`confirmatory.py` L714).
- The timeliness evidence is a `receipt.json` that the author's machine copies from GitHub's activity API and commits. PR L380–381 itself anticipates that GitHub's record may lapse. After that, a 30-minute claim rests on a self-archived file. OpenTimestamps bounds existence to hours, not minutes (ms L440–442 concedes this).

**Fix.**
- State the dry-run on-time share by scheduled slot.
- Poll faster for the first version of a new sequence, or say plainly that B's prospective part will lack first-day cells.
- Add a third-party time stamp with second resolution (an RFC 3161 token, or an independent mirror of the branch).
- Replace "guarantees".

### M5. The contamination argument for the primary test rests on one vendor field, and may misname it
Lines: ms L82–87, L244–248, L559–563.

- ADR 0014 lists OpenAI's figure as a "Knowledge cutoff" (2024-09-30). It also says that where a vendor gives both, the training-data cutoff is the later one. The manuscript calls it the "documented training-data cutoff". I could not check the vendor page.
- Sixty-two of 89 sequences predate the model's release (verified). The model was released 14 months after the stated cutoff.
- The release-date subset of 27 is at a sample size where the project's own simulation shows the bound is not controlled.
- The introduction cites a method that detects recall directly (ms L84–85). The study then runs no recall probe on confirmatory mainshocks.
- The buffer is asserted, not argued.
- Contamination helps the model, which is the direction a non-inferiority test rewards.

**Fix.** Register a closed-book recall probe on the confirmatory mainshocks for the primary model (it needs no outcome to run). Register the pre- and post-release contrast with its interval. Use the vendor's exact term for the cutoff.

### M6. Sequences are treated as independent, and the size is reported selectively
Lines: ms L351–354, L390–397.

- **Clustering.** Twenty-three of the 89 sequences have another test-A mainshock 20 to 100 km away within 30 days (16 pairs, my count). The first mock review found 4 pairs with overlapping circles within 58 days; I did not recompute that, because it touches outcomes.
- The exclusion rule's context is only OAF events plus M≥6 (PR L298–299, omitted at ms L176–179). Aftershocks of an M5.5–5.9 parent without an OAF product therefore stay in as "mainshocks".
- The manuscript does not mention between-sequence dependence anywhere.
- **Size.** The quoted 0.034 is the most favorable of three registered figures: 0.047 for Opus-5.5-like effects and 0.083 for effects like the constant control's, "above its nominal 0.05" (PR L490–493, L182–183).
- All of them resample 39 development sequences in which two carry the tail. The official forecast expects about 11 event sequences in 89 (verified, 11.1). The simulation used 1,000 replicates, which the manuscript does not state.

**Fix.** Resample clusters defined by an outcome-blind rule as blocks. Report all three sizes. Add a size under a heavier, rarer tail. Simulate power from the frozen forecasts alone (outcomes drawn from the official probabilities, the model set to a multiple of them), which needs no development effects.

### M7. The clip decides the result more than the text admits
Lines: ms L315–322, L344–347, L580–583.

- "The scorer reconstructs nothing" sits next to the fact that the scorer replaces the primary model's stated probability in 49% of its development answers.
- The model is not told about the floor. I checked `prompts/v3/system_A.txt`.
- The development estimate is +0.009, +0.017 and +0.022 at clips of 0.01, 0.001 and 0.0001 (PR L59–61). It crosses the margin at the smaller clip. The manuscript omits these three numbers.
- The clip protects an overconfident under-forecaster far more often than it touches the official forecast (15% of cells).

**Fix.** Print the three numbers. Argue for 0.001 from the product's resolution. Either tell the model the floor or say that it is not told.

### M8. Baselines and information parity
Lines: ms L286–306, L215–237, L255–256.

- **The RJ refit is not a separate baseline.** It fits only M≥4.95 events with a 10-event minimum. It therefore equals generic RJ in every development cell (PR L669–670) and will in almost every test-A cell. The manuscript says "four statistical forecasts". A seismologist will also call a refit that discards all smaller aftershocks a straw version of the sequence-specific model.
- **The ETAS refit's validation is a placeholder** (ms L303–304). It is cited to an evaluation paper for the Puerto Rico sequence that the project's own literature note marks "Not read" and says is not the methods paper.
- **The introduction misdirects.** It says USGS "now uses [ETAS] for many of its public forecasts" (ms L62), while the official forecast is RJ at 463 of 472 issue times in the primary set.
- **"As a person would get from a chatbot" does not describe the request** (ms L255–256). It is an API call with a seismologist system prompt, a JSON schema, a fixed reasoning effort and a curated as-of catalog.
- **The introduction's parity sentence is absolute** (ms L110–111) where section 2.4 lists five gaps and the prospective catalog is fetched at detection.

**Fix.** Describe three effective baselines, or refit RJ on events above the time-dependent completeness. Write the ETAS validation and cite the model's actual source. Reword the three sentences.

### M9. Wording that will be misread
Lines: title, ms L39–44, L114–125, L361–363.

- The title asks a general question. The design answers one about a binary M≥5 event after moderate mainshocks.
- "Non-inferior" will be quoted without the margin. Given M1, the word is technically right and substantively misleading.
- "Predicted to fail" (ms L122–123) hides that the registered prediction is "not supported". That covers "inconclusive", the same label the primary model is expected to get (PR L176–177: the rule of thumb is inconclusive in about 37% of simulated studies).
- "Two forecasters with no skill" (ms L122) includes a rule of thumb that uses the sequence.
- Neither document has a pre-written sentence for superiority (PR L100–101 tests it; the table at PR L114–120 has no row).
- Neither has one for stratum or secondary intervals that lie below zero. In development the "7 days or more" stratum already has upper bounds below zero for two secondary models, in cells where the official median probability is 0.3%. That will read as "LLMs beat USGS" unless the wording is fixed now.
- The units vary: "per forecast" (ms L117), "per cell" (ms L358), and a mean of sequence means (ms L351).

**Fix.** Scope the title. In the abstract, state the deficit in nats with its probability-ratio meaning and always beside the generic and constant results. Add superiority and stratum rows to the outcome table. Use one unit.

### M10. Independence from the AI tool and reproducibility
Lines: ms L485–494, L593–595, L602–605.

- The scoring code, the protocol's only reviews and the manuscript draft come from an LLM assistant. Three of the five evaluated models are from that assistant's vendor if it is Anthropic's (ms L492, still a placeholder).
- "The frozen protocol … [is] what keep[s] the evaluation independent of the tool" does not follow. Freezing fixes the analysis; it does not verify it.
- The journal asks authors to verify AI output. The statement must say what the author personally checked.
- The primary model is withdrawn in April 2027, so test A cannot be rerun by anyone. No open-weight model is in the confirmatory set as an anchor.

**Fix.** State a human verification (for example, hand-scoring a sample of cells). Seek one outside read of the protocol before the freeze. Add one open-weight model, descriptively.

## 3. Minor concerns

1. ms L135–140: the 50 versus 49 count is left as a placeholder. ADR 0013's table resolves it: 7 registered sequences with an OAF product, 39 E3 and 3 from the E1 outcome pool.
2. ms L192–194: a secondary set of M4.0–4.9 mainshocks is defined and forecast live. I found no registered analysis that uses the prospective ones in either document, or in the code I searched (`live_scores.py`, `confirmatory.py`, `sensitivity.py`).
3. ms L202–204: the magnitude-mismatch rule omits its tolerance (0.25, ADR 0013) and that it compares with today's magnitude.
4. ms L206–211: the "first valid version" can be late. Its elapsed time has a 90th percentile of 0.56 days and a maximum of 77 days in test A. Report the distribution.
5. ms L266–268 against L329–330: the model is told its quantiles are scored with proper scoring rules, yet the secondary count score is "not a proper score". The text never connects the two (PR L262–265 does).
6. ms L269–270: averaging three answers is fine, but say that it estimates the expected score of one answer.
7. ms L275–278: say that a 3% invalid rate alone uses up the margin (PR L651).
8. ms L283–284: persistent transport failures are "listed"; the code and PR L673–674 also leave them out of the estimate. Say so, and say that a cell with no delivered answer drops out silently.
9. ms L351 and L417–419: the estimand weights a one-cell sequence and an 18-cell sequence equally, and counts the first day in three nested windows. The hierarchical model estimates a different quantity (PR L507–510). Neither point is stated.
10. ms L398–400: "the scale of the previous paragraph" points at the wrong paragraph.
11. ms L410–415: S3 to S5 give no level and no multiplicity statement (PR L88–89: 0.05 each, for four models).
12. ms L417: say that the median and trimmed mean are not hazard-relevant estimands. In development the median favors the model (−0.013) while the mean does not.
13. ms L104–106: the freeze is written in the past tense and no `prereg-v2` tag exists. That is harmless in a draft, but check every past-tense claim against the record at submission.
14. ms L78: "the search is logged in the project repository" needs an archived citation.
15. The header comment says Nandan et al. (2019) "have been read". The literature note says "Abstract only".
16. `PIT`, `FDSN`, `JSON` and `SHA-256` are used without definition.
17. The written text is already about 6,700 words (introduction 940, methods 4,380, section 4.1 1,330), before results, discussion and conclusions, against a limit of 10,000. The methods need cutting or a supplement.

## 4. Specific attention points, in brief

- **Hypothesis, margin and decision rules.** They are stated clearly and fixed before any confirmatory score. A reader can still accuse the author of post hoc choice on the primary model, the test direction, the level and the control set (M3). The final margin is the strictest of those considered, which helps.
- **"Non-inferior" and the outcome wording.** The pre-registration's outcome table is honest. The manuscript carries two of its five rows into the abstract note and has no wording for superiority (M9).
- **Statistical unit, bootstrap, power.** The sequence-level bootstrap-t is implemented as described. Dependence between sequences and the selective size are open (M6). The power is not defensible for a primary test (M1).
- **Contamination.** Only the prospective arm is clean by construction, and the retrospective argument is thin (M5).
- **Information parity.** Honest in section 2.4, overstated in the introduction, and missing the completeness gap (M2, M8).
- **Prospective timeliness.** The rule is sound. The selection it causes and the weakness of the evidence are unstated (M4).
- **Missing literature:**
  - ICH E10 and the fixed-margin literature (Schumi and Wittes 2011; Pigeot et al. 2003 is in the bibliography, uncited).
  - Diebold and Mariano (1995), for comparing forecasts under dependence.
  - Foreshock probabilities and Båth's law (Jones 1985; Agnew and Jones 1991; Felzer et al. 2004).
  - Productivity by depth and setting (Wetzler et al. 2016; Dascher-Cousineau et al. 2020).
  - Teleseismic location accuracy (Bondár et al. 2004).
  - Pseudo-prospective aftershock evaluations (Savran et al. 2020 and Mizrahi et al. 2024 are in the bibliography, uncited; Omi et al. 2013).
  - Pre-registration of analyses of existing data.
  - LLM forecasting (Halawi et al. 2024, in the bibliography, uncited).
  - I cite these from memory; verify each.

## 5. Manuscript against pre-registration: disagreements and omissions

1. **Prior exposure, exclusions.**
   - ms L158–159: "(4) Only aggregate counts of the foreshock and aftershock exclusions were viewed."
   - PR L610–613: "They were identified on 2026-11-01 with Tyler's approval: nc75094976 (M4.23, 2024-12-04), us7000q8wx (M4.40, 2025-06-26) and us7000s2bn (M5.50, 2026-03-05), each followed within a year by a larger event whose circle holds it."
   - PR L740 and L305–306 repeat the aggregate-only claim, so the pre-registration contradicts itself. For us7000s2bn the author knows a larger event occurred in its circle.
2. **The forward-excluded sensitivity analysis.**
   - ms L180–182: "three events were excluded for that reason alone … the three are added back in a sensitivity analysis".
   - PR L613–615: "Only us7000s2bn is in a tested model's clean M>=5 set".
   - The analysis adds one sequence, not three.
3. **Prior exposure, revision counts.**
   - ms L161–163 lists "the official model type, the circle radii and the dates of the mainshocks".
   - PR L741–747 lists none of these. Neither lists the mainshock magnitudes used at ms L551 and PR L106–107.
4. **Level.**
   - ms L357–358: "in a one-sided test at 0.05".
   - PR L484–486: "looser than the usual one-sided 0.025 for non-inferiority; the power available justifies it." Omitted.
5. **Margin's share of the reference effect.**
   - ms L369–372: the margin "keeps out a forecaster that knows nothing about the sequence".
   - PR L143–145: "It is about two thirds of the official forecast's expected advantage over that constant." Omitted.
6. **Earlier margin and power.** PR L135–136, "it replaces 0.10 on the count score", and PR L234–236, power "0.42 for A and 0.64 for B". Omitted.
7. **Size.**
   - ms L393–395: "is 0.034 at a nominal 0.05".
   - PR L490–493: "0.034 (gpt-5.1-like effects) and 0.047 (Opus-5.5-like effects) … For effects like the constant control's it is 0.083".
8. **Size for B.**
   - ms L408–409: "about 0.14".
   - PR L495: "At N = 33: 0.165 and 0.144 at 0.05."
9. **Generic RJ's expected result.**
   - ms L381: "if generic RJ also passes".
   - PR L168–169: "generic RJ is supported in every simulated study of 89 sequences, so the clause will apply".
   - ms L522 says "expected to pass", but only in the limitations. The most likely joint outcome (PR L122–124) is not stated as such.
10. **Control history.** PR L186–188: "Sonnet 4.6 was first chosen as a control … It is not one". Omitted.
11. **Informative-sequence set.** PR L198–199: "49 of test A's 89 sequences qualify. Seven lie between 0.101 and 0.103, so the set is sensitive to the threshold's value". The earlier rule is at PR L193–194. All omitted at ms L386–388.
12. **Co-primary history.** PR L129–130: "B was co-primary with a Holm correction." Omitted at ms L362–363.
13. **Clip sensitivity.** PR L59–61: "+0.009, +0.017 and +0.022 at clips of 0.01, 0.001 and 0.0001". Omitted at ms L344–347 and L580–583.
14. **The scoring promise.** PR L262–265: "For the quantiles that promise refers to the log-scale quantile score … a sensitivity analysis here". Omitted.
15. **Baselines.**
    - ms L288: "Four statistical forecasts".
    - PR L669–670: "RJ-MLE … equals generic RJ in every development cell."
16. **Retries.**
    - ms L283–284: "retried up to ten times and then listed".
    - PR L673–674: "up to 10 attempts. Persistent failures are listed and left out."
17. **Invalid answers.** Omitted: PR L647–648, "if the verdict differs between the two rules the paper reports the result as depending on how invalid answers are handled"; PR L664–668, the Brier and strict-item rules.
18. **Secondary levels.** PR L88–89 and L131, "superiority, alpha 0.05 … at 0.05 each". Not given at ms L410–415.
19. **Descriptive analyses.** PR L91 registers "D1 behavioral probes; hindsight effect (ADR 0016)" as descriptive. The manuscript mentions neither, yet ms L465–466 says anything not listed is exploratory.
20. **Exclusion context.** PR L298–299: "The context is the OAF events plus ComCat M>=6 from 2023-11-01". Omitted at ms L176–179.
21. **Hierarchical model.** PR L507–510: fixed effects, and "not the mean of sequence means". Omitted at ms L417–419.
22. **Abstract.** ms L41–44 fixes two clauses. PR L116–120 has five rows, including "No claim" when a control passes and the inferior row.
23. **Control prediction.** ms L122–123 says "predicted to fail it"; PR L83–84 says "predicted result: not supported".
24. **Cutoff term.** ms L244–246 says "documented training-data cutoff". PR L240 heads the column "Training cutoff", but ADR 0014 lists OpenAI's as a "Knowledge cutoff".

## 6. Described method against code

No substantive difference was found in the primary path. The following match the text:
- the score and clip (`scoring.log_score_binary`, `P_CLIP = 1e-3`);
- the stated probability and the looser validity rule (`schemas.stated_p5`);
- the per-answer log 2 penalty and the per-cell mean over samples (`confirmatory_cells`);
- the sequence means, the bootstrap-t with 10,000 resamples and a fixed seed, and the five status labels (`noninferiority`, `decide`, `_status`);
- the bound and the p-value, which agree at the boundary by my arithmetic;
- the informative rule, the constant 0.041, the rule of thumb, generic RJ's productivity spread, the RJ refit and its fallback, and the outcome count with its tolerance.

Differences and silences:
1. Strict items are filtered by on-time in code (`confirmatory.py` L714). The text says "guarantees" (ms L430–431).
2. Transport errors are excluded from the estimate, not only listed (`confirmatory_cells`, first line).
3. A set of identical sequence effects returns an infinite bound. This is an edge case the text does not state.
4. The trimmed mean and median carry 95% percentile intervals (`robust`). The text is silent.
5. The RJ refit also fits b when it has 50 or more events, and bounds c and p. The text is silent.
6. Retries run from `-retry2` to `-retry10`, which is ten attempts, not ten retries.
7. The `tier` label "secondary" is assigned in `prospective.py`. I found no consumer in the scoring modules I searched (minor 2).

Not checked: the issue schedule in `tables.py`, the as-of rebuild, the ETAS port, the detector, and the release path.

## 7. Journal rules

- **Structure.** Research Article form with three heading levels: compliant. If the result is inconclusive as expected, the null-results Report type may fit better; decide after the analysis.
- **Length.** About 6,700 words are written before results. There is a real risk of exceeding 10,000. Eight display items are planned, within the limit of ten.
- **Abstract and non-technical summary.** Placeholders.
- **Use of AI.** Correctly placed in Methods (ms L485–494), but it holds four placeholders and does not yet say what the author verified.
- **Data and code availability.** Placeholder. It must give a Zenodo DOI, a license and a readme. It must say that results reproduce from archived answers, since the primary model will be gone. It should cite the contributing networks (us, ak, nc, ci, nn, tx, pr), as the journal asks for network data.
- **Author contributions, competing interests, acknowledgments.** Placeholders. The competing-interests statement must cover vendor credits and the assistant's vendor.
- **ORCID.** Absent.
- **References.** All 60 entries carry a DOI. Eighteen are uncited and must be removed or cited. Cited keys all resolve.
- **Style.** Magnitude notation, date format and American spelling are consistent. "Forecast", never "prediction", is respected (ms L127–129).

## 8. The earlier reviews

Points they already made, and whether the manuscript answers them:

| Earlier finding | Manuscript now |
|---|---|
| No assay sensitivity; generic RJ passes (design 1) | Disclosed (ms L119–122, L522–524). Not fixed. The constant-control evidence in M1 is new. |
| Score through nine quantiles degenerate (design 2) | Answered: probability score. |
| Margin set with power in view; fixed-margin construction (design 3, revision 1) | Partly: the path is disclosed. The two-thirds share and the earlier 0.10 are omitted. |
| Power, size, level (design 4; revision 2) | Partly: "expected inconclusive" is stated. The level's looseness and the other sizes are omitted. |
| Population is small earthquakes (design 5) | Partly (ms L548–558). Region, depth and completeness are not given; the title is unscoped. |
| On-time rule selects against first issues (design 6) | Not answered. |
| Contamination rests on the vendor; no recall probe (design 7) | Limitation stated; no probe. |
| Invalid-answer rule (design 8; revision 5) | Answered and disclosed. |
| Informative estimand (design 9) | Answered. Threshold sensitivity is omitted. |
| Multiplicity in secondary tests (design 10) | Not answered. |
| Hindsight in prompt and version matching; parity overstated (design 11, 12) | Answered in section 2.4. The introduction is still absolute. |
| No open-weight anchor or mainshock-only arm (design 13) | Not answered. |
| Model identity (design 14) | Answered as a limitation. |
| Retrospective arm is a plan for public data (design 15) | Answered (ms L564–568). |
| Independence between sequences (design 16) | Not mentioned at all. |
| Outcome noise at 10 km and M5.0 (design 18) | Answered as a limitation, understated. |
| Live operations (design 19) | Answered as a limitation. |
| Clip (revision 6) | Partly: shares are given, the three means are not. |
| Three nulls as the modal outcome (revision 2) | Partly. |
| RJ refit equals generic RJ (revision 11) | Not answered. |

Points I did not find in either review:
- the regional and depth composition and the completeness of the shown catalog (M2);
- the foreshock reading of the target (M2);
- the official forecast's lack of a demonstrated advantage over the constant, and the misuse of "assay sensitivity" (M1);
- the wider clustering count (M6);
- the knowledge-cutoff wording (M5);
- the verifiability of the timeliness receipt (M4);
- the full design-history omissions, including the effort pilot's cap (M3);
- the prior-exposure contradiction and the one-of-three sensitivity set (section 5, items 1 and 2);
- the unused prospective secondary set (minor 2);
- the missing superiority and stratum wording (M9).

## 9. Three changes I would require before accepting

1. **Replace the primary analysis or its vocabulary (M1, M9).** Either register the estimate with its interval as the primary outcome and remove "non-inferior" from the title and abstract; or adopt a retention-of-effect design that first shows the official forecast beats the constant and the generic model on the same cells. In both cases report the bound at 0.025 and write the superiority and stratum wording in advance.
2. **Make the population and the unit seismologically explicit (M2, M6).** Add the region, depth, network and completeness table. Register depth, region and first-day strata. Resample outcome-blind clusters as blocks. State the foreshock reading of the target and the completeness gap. Scope the title.
3. **Complete the record and the evidence for the two cleanliness claims (M3, M4, M5).** Add a full dated design-history table. Correct the prior-exposure list. Register a recall probe and the release-date contrast for the primary model. Report the on-time share by slot, with a fix or a plain statement about first issues, and a third-party time stamp.

**Recommendation for the design as it stands: major revision.** If it were submitted unchanged with the expected inconclusive result, I would not support publication as a Research Article with this title.
