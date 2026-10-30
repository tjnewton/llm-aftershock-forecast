# ADR 0014: Models for the Seismica phase

Status: **living document, proposed.** Facts were checked on 2026-10-29. The model list is open
(see "Open decisions") and is pinned in preregistration v2.

## Context
A forecast is clean only when the mainshock comes after the model's training data. Claude 5.5
models have a June 2026 cutoff, which leaves only a few months of sequences. Models with older
cutoffs can be tested on the whole OAF archive from November 2024 (ADR 0013). One other-vendor
frontier model, and open models from several labs, test whether the results are about Claude or
about LLMs in general.

## Contamination rule
A sequence is clean for a model if its origin is at least **3 months after the end of the
model's documented training-data cutoff month**. I use the training-data cutoff where a vendor
gives both it and a "reliable knowledge" cutoff, because it is the later one. Models without a
documented cutoff are excluded.

## Verified facts
Claude, from the Models API (`models.list`, pinned client) and the docs pages
(platform.claude.com, models overview, per-model pages, model deprecations):

| Model ID | Training-data cutoff | Clean from | `effort` | Structured outputs | Retirement |
|---|---|---|---|---|---|
| `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5` | Jun 2026 | 2026-10-01 | yes | yes | not before Sep-Oct 2027 |
| `claude-sonnet-4-6` | Jan 2026 | 2026-05-01 | yes | yes | not before 2027-02-17 |
| `claude-opus-4-6` | Aug 2025 | 2025-12-01 | yes | yes | not before 2027-02-05 |
| `claude-opus-4-5-20251101` | Aug 2025 | 2025-12-01 | yes | yes | not before 2026-11-24 |
| `claude-haiku-4-5-20251001` | Jul 2025 | 2025-11-01 | no (manual thinking budget) | yes | not before 2026-10-15 (already passed) |
| `claude-sonnet-4-5-20250929` | Jul 2025 | 2025-11-01 | no | yes | 2026-11-30 (deprecated) |

The registered models' "post-cutoff" rule (prereg v1: origin from 2026-07-01) had no buffer. The
rule above would move their clean set to 2026-10-01; I report both.

OpenAI, from developers.openai.com model and deprecation pages (the two chosen models
re-checked on 2026-10-30; the others from a research pass):

| Model ID | Knowledge cutoff | Removal from API |
|---|---|---|
| `gpt-6.1-sol` | 2026-04-30 | none listed |
| `gpt-6-astra` | 2026-04-30 | none listed |
| `gpt-5.1` (snapshot `gpt-5.1-2025-11-13`; deprecated 2026-10-01) | 2024-09-30 | 2027-04-01 |
| `gpt-4.1` | 2024-06-01 | 2027-01-14 |
| `gpt-5`, `o3` | 2024-09-30, 2024-06-01 | 2026-12-11 |

Open models that fit the 32 GB RTX 5090, with documented cutoffs:

| Model | Cutoff | License |
|---|---|---|
| gpt-oss-20b | Jun 2024 | Apache-2.0 |
| Olmo-3.1-32B-Instruct | Dec 2024 | Apache-2.0 |
| Gemma 3 27B | Aug 2024 | Gemma terms |
| Gemma 4 31B | Jan 2025 | Apache-2.0 |
| Phi-4 14B | Jun 2024 | MIT |
| Llama 3.1 8B | Dec 2023 | Llama license |

Qwen and DeepSeek distills document no cutoff, so they are excluded.

## Consequences
- **Coverage by clean window** (M>=5.0 candidates not yet used, ADR 0013): every candidate is
  clean for gpt-oss-20b, Phi-4 and gpt-4.1 (cutoff mid-2024, archive from 2024-11). Olmo is clean
  from 2025-04, Gemma 4 from 2025-05, and Opus 4.6 from 2025-12 (26 candidates).
- **Retirement risk.** Confirmatory runs happen after the freeze. Several older models retire in
  the coming weeks to months: Opus 4.5 not before 2026-11-24, Sonnet 4.5 on 2026-11-30, gpt-5
  and o3 on 2026-12-11, gpt-4.1 on 2027-01-14. A model that retires before the freeze cannot be
  in the confirmatory arm. Opus 4.6 (not before 2027-02-05), Sonnet 4.6 (not before 2027-02-17)
  and gpt-5.1 (2027-04-01) are the safer choices. Open models never retire.
- **Request differences.** Haiku 4.5 and Sonnet 4.5 take no `effort` parameter. Their thinking is
  a manual token budget, so the registered settings ("explicit effort") cannot be matched. That
  argues for Opus 4.6 and Sonnet 4.6, which take the same request fields as the 5.5 models.
  One default differs: a request without `thinking` runs adaptive thinking on the 5.5 models
  but no thinking on Opus 4.6 and Sonnet 4.6 (Claude API model migration notes). See decision 5.

## Decisions (Tyler, 2026-10-30)
1. **Older-cutoff Claude models:** `claude-opus-4-6`, and `claude-sonnet-4-6` as a second model
   size, both at effort `high`.
2. **Other vendor (OpenAI), with spend tracked separately from Claude:**
   - `gpt-6.1-sol`: cutoff 2026-04-30; $2 / $10 per million tokens, half that in batch; effort
     `low` through `max`; structured outputs; no retirement date listed. Used in the
     prospective arm and the same-cutoff comparison with Claude 5.5.
   - `gpt-5.1-2025-11-13`: cutoff 2024-09-30; $1.25 / $10; effort `none` to `high`;
     structured outputs; removed from the API on 2027-04-01. Used in the older-cutoff
     retrospective arm.

   The OpenAI effort level that matches Claude's `high` is set in the D2 study before the
   freeze.
3. **Clean-period rule:** the 3-month buffer applies to every model in the paper, the Claude
   5.5 models included (clean from 2026-10-01). The unbuffered rule is a sensitivity
   analysis. The registered hackathon analysis keeps its own rule.
4. **Retiring models are dropped:** Opus 4.5, Sonnet 4.5, Haiku 4.5, gpt-5, o3 and gpt-4.1.
   Every confirmatory run happens after the freeze.
5. **Thinking and effort on the 4.6 models (Tyler, 2026-10-30), chosen by the D1 settings
   pilot** (development probe items, `runs/d1/pilot-settings`, `runs/d1/pilot-sonnet-low`):

   | Model | Setting | Valid | Mean output tokens | Batch USD per call |
   |---|---|---|---|---|
   | Opus 4.6 | adaptive, high (cap 12k) | 1 of 3 | 9,818 | 0.129 |
   | Opus 4.6 | **adaptive, medium** | 3 of 3 | 2,384 | 0.036 |
   | Opus 4.6 | thinking off, high | 3 of 3 | 652 | 0.015 |
   | Sonnet 4.6 | adaptive, high (cap 32k) | 0 of 3 | 32,000 | 0.244 |
   | Sonnet 4.6 | adaptive, medium (cap 16k) | 0 of 3 | 16,000 | 0.124 |
   | Sonnet 4.6 | **adaptive, low** (cap 16k) | 3 of 3 | 2,719 | 0.024 |
   | Sonnet 4.6 | thinking off, high | 3 of 3 | 766 | 0.010 |

   - Opus 4.6: `thinking: {"type": "adaptive"}`, effort `medium`. At `high` it often does not
     finish within 12k tokens and costs four times as much.
   - Sonnet 4.6: `thinking: {"type": "adaptive"}`, effort `low`. At `medium` and `high` it
     never finished (all answers cut off at the cap with no text).
   - Both 4.6 models reason, as the 5.5 models do by default, at different effort levels. The
     paper reports the settings as chosen by this pre-freeze pilot. The 5.5 requests stay as
     registered (no `thinking` field, effort `high`).
   - Implemented as `laf.providers.STUDY_SETTINGS`; first used by the D1 probes.

## Changelog
- 2026-10-30: decision 5 (thinking and effort on the 4.6 models, from the D1 settings pilot).
- 2026-10-30: decisions 1-4 recorded; OpenAI facts for the chosen models re-checked.
- 2026-10-29: first version with checked Claude facts; OpenAI and open-model facts from a
  research pass, to be re-checked before pinning.
