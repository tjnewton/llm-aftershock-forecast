# ADR 0005: Model set and effort levels

Status: decided by the participant.

## Decision
- Claude via the official `anthropic` Python SDK only: `claude-opus-5-5`, `claude-sonnet-5-5`,
  `claude-haiku-5-5`, exact IDs, no date suffixes. No Fable, no other vendors.
- Effort: `output_config.effort = "high"` for all three (set explicitly; defaults differ: Opus and
  Haiku default to medium, Sonnet to high). Sensitivity: Sonnet at `low` on the primary items.
- Thinking: adaptive (parameter omitted). Opus 5.5 cannot disable thinking; we never try.
- Sampling: no temperature/top_p/top_k (non-default values are rejected). Variability is
  estimated from k repeated samples.
- Tools: none declared, so no web access. Server-side refusal fallbacks: never enabled in scored
  runs (they would swap the model under test); refusals are recorded as outcomes.
- Local: two open-weight models via llama.cpp `llama-server` with JSON-schema constrained
  decoding, fixed seed and temperature. `openai/gpt-oss-20b` (documented cutoff 2024-06) and
  `allenai/Olmo-3.1-32B-Instruct` (documented cutoff Dec 2024, open training data, so
  contamination can be checked directly). Qwen3.8-27B was the original choice but
  its cutoff is undocumented and it was released 2026-08-14, so every candidate sequence except
  Panama could be in its training data.
- Spend cap: $150 total through Oct 22, using a new project key supplied by the participant.

Update (2026-10-21/22, after the freeze; docs/deviations.md): the spend cap was raised to about
$200 (guard $195). Adapted gpt-oss-20b models (E1 registered as descriptive; E1a, replicates and
E1b exploratory) are listed in docs/model-registry.md, "Adapted models".
