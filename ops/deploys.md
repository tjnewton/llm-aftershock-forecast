# Deploys of the service worktree ..\laf-service (runbook section 0.4)

2026-11-04T11:27:57Z 22c337e9 dry run moved into the service worktree under the startup task (T16)
2026-11-04T17:40:02Z 7329a4c7 pre-freeze review fixes (#98-#102): 40-day poll lookback, receipts from the branch, live-status; first step crashed on the hand-made seal check/mac-2026-11-01 (no items), stopped at 17:41:13Z by adding it to receipts_missing in the dry run's state.json; code fix in #104
2026-11-04T23:22:26Z f09a30fa receipt and release housekeeping never stop the detector, a seal without items gets its receipt (#104); check/mac-2026-11-01 taken off receipts_missing while stopped, its receipt came on the first poll (live-test 60ad5823)
