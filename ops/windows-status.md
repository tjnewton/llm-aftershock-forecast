# Windows task status (written by the Windows session only)

One line per event, newest last: `T<nn> running|done|failed <UTC time> <details>`.
T01 running 2026-10-22T00:01Z
T01 done 2026-10-22T04:18Z 6b08186 630 of 630 succeeded
T02 running 2026-10-22T04:21Z
T02 done 2026-10-22T07:45Z 7d4e5f1 630 of 630 succeeded
T03 running 2026-10-22T07:45Z
T04 running 2026-10-22T09:38Z
T04 done 2026-10-22T10:14Z 6a5e034 849 of 849 succeeded
T03 running 2026-10-22T10:14Z
T03 done 2026-10-22T12:31Z 43e88df 630 of 630 succeeded
T05 running 2026-10-22T13:17Z
T05 done 2026-10-22T14:01Z 8545162 777 of 777 succeeded; adapter gpt-oss-20b-e1r1-lora-f16.gguf sha256 33c916fdd70c5c34c5f92ed9ef08d8778645c18797527c0033ff3604bff3689a
T06 running 2026-10-22T13:48Z
T06 done 2026-10-22T14:25Z d1190de 777 of 777 succeeded; adapter gpt-oss-20b-e1r2-lora-f16.gguf sha256 7ec520aff551b2470a9471cd52e050b1d6f024ef80148fda8ca63839b699645d
T07 running 2026-10-22T14:19Z
T07 done 2026-10-22T14:57Z 61d5619 777 of 777 succeeded; adapter gpt-oss-20b-e1ar2-lora-f16.gguf sha256 90e868fed977697936f4da3e02ca28fee75522b9b403a2d2b4fdeba59e6d01d6
T08 running 2026-10-22T15:45Z
T08 failed 2026-10-22T22:34Z 5dc8e1b e3all finalize: json.decoder.JSONDecodeError: Unterminated string starting at: line 1 column 512 (char 511); runner._jsonl splits local_log.jsonl with str.splitlines(), which breaks on 4 U+2028 chars in model text written unescaped (ensure_ascii=False); needs a code fix, then rerun e3all to finalize (no new requests). All 630 e3all responses are in the committed local_log.jsonl (631 lines, all valid when split on 
); dev 72 of 72 and e1 147 of 147 complete; adapter gpt-oss-20b-e1b-lora-f16.gguf sha256 36c390c55be682bc5ad4729e9724abab2274df9b092a3330c4e3a4d9b26ff6d2
worker stopped 2026-10-22T22:34Z
T08 done 2026-10-22T22:54Z e54def7 849 of 849 succeeded (dev 72, e1 147, e3all 630); e3all finalized after reader fix 2405c23, no new requests; adapter gpt-oss-20b-e1b-lora-f16.gguf sha256 36c390c55be682bc5ad4729e9724abab2274df9b092a3330c4e3a4d9b26ff6d2
worker stopped 2026-10-29T19:59Z
T09 running 2026-10-30T13:45Z
T09 done 2026-10-30T13:51Z live-watch started detached, uv pid 13660 (laf.exe 32780, python 26532); first poll logged
T10 running 2026-11-01T14:48Z
T10 done 2026-11-01T14:51Z e441f00a worktree ..\laf-live-dryrun on live-dryrun; service stopped right after the 14:49Z poll (uv 13660, laf.exe 32780, python 26532/38576); 4 log files copied (the branch log.jsonl was a prefix of the local one); restarted 14:50Z writing to ..\laf-live-dryrun\runs\live-dryrun: uv pid 31616 (laf.exe 39556, python 38364/8476); pushed live-dryrun e441f00a (295 polls, 167 detections); runs/live-dryrun/ here reset to HEAD, untouched since
T11 running 2026-11-01T14:51Z
T11 done 2026-11-01T14:51Z none no second restart needed: the T10 restart at 14:50Z already ran 2bb4612b (PR #59 merged; uv rebuilt laf at start), same pids (uv 31616, laf.exe 39556, python 38364/8476); its first poll at 14:50:30Z left no traceback in stderr.log; no detection yet, so no "pipeline" line to check
