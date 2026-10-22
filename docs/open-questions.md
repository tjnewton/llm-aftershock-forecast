# Open questions (resolved)

Every question raised before the event is answered; kept for the record.

- **Windows RTX 5090 setup:** done (llama.cpp b11739, gpt-oss-20b MXFP4 and Olmo-3.1-32B Q4_K_M;
  docs/model-registry.md, "Local serving").
- **ORCID for CITATION.cff:** optional, not added.
- **Reasoning tokens at effort `high`:** recorded per call in each run's `results.jsonl` (`usage`).
- **Batch turnaround:** about one hour for every batch on Oct 21-22.
- **Local throughput on the 5090:** gpt-oss-20b 15-30 s per request (long reasoning), Olmo 7-19
  s, adapted gpt-oss about 2.4 s (it answers without long reasoning).
- **Grammar-constrained decoding with gpt-oss reasoning:** works (`response_format` JSON schema
  through llama-server); invalid answers come from content, not from the grammar.
