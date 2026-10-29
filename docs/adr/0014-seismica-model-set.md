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

OpenAI, from developers.openai.com model and deprecation pages (subagent research, to be
re-checked before pinning):

| Model ID | Knowledge cutoff | Removal from API |
|---|---|---|
| `gpt-6.1-sol` | 2026-04-30 | none listed |
| `gpt-6-astra` | 2026-04-30 | none listed |
| `gpt-5.1` | 2024-09-30 | 2027-04-01 |
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
  argues for Opus 4.6 and Sonnet 4.6, which take the same request shape as the 5.5 models.

## Open decisions (Tyler)
1. Older-cutoff Claude models for A1. My recommendation: `claude-opus-4-6`, and possibly
   `claude-sonnet-4-6` for a second size, at effort `high`.
2. The other-vendor model. For the prospective arm and a same-cutoff comparison with Claude 5.5:
   a current flagship (`gpt-6.1-sol` is the cheaper one). For A1: `gpt-5.1` (cutoff 2024-09,
   served until 2027-04). Possibly both, with OpenAI spend tracked separately.
3. Open models beyond gpt-oss-20b and Olmo-3.1-32B. Candidates: Gemma 4 31B and Phi-4.
4. Whether the 3-month buffer also applies to the Claude 5.5 models. If it does, their clean
   retrospective set starts 2026-10-01, and Colombia and Flores Sea are no longer clean; most
   of their evidence would then come from the prospective arm.
5. Whether to run models that retire before a plausible freeze outcome-blind (forecasts stored
   and hashed, scored only after the freeze). That would depart from "model runs on
   confirmatory items happen after the freeze, with frozen prompts".

## Changelog
- 2026-10-29: first version with checked Claude facts; OpenAI and open-model facts from a
  research pass, to be re-checked before pinning.
