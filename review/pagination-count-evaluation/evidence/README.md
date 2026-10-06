# Evidence index and limits

- `local-validation.json`: unchanged historical preparation report. It used selected source excerpts and correctly recorded fork publication as not performed at that time.
- `publication-validation.json`: new standalone-packet run using the complete byte-verified baseline reference. It records 57 candidate passes, 12 baseline failures/45 passes, all eight detected mutations, and staged/combined patch application. Framework doubles are explicit; this is not a real application or database run.
- `authored-test-inventory.json`: static count of the three test files, not collected real-stack test results.

The original supplied ZIP has SHA256 `5f4c3f80c65dce1386b9c7d60b866fb715c2ceeac1fc073d9a5b5cbeaff5a000`. Its repeated raw XML/text logs and old partial-source snapshot are not needed to run this published packet and are not duplicated here. The branch includes the documentation, complete baseline reference, tools, runtime patches, test inputs, and summarized validation records. Its application/test diff is the canonical combined artifact.

Use an isolated copy to rerun `python tools/verify_offline.py`: it writes new XML/text logs and replaces `local-validation.json` in that copy. Preserve historical records. For real validation follow `../HANDOFF.md`; add new sanitized output files rather than rewriting earlier evidence.

No PostgreSQL/HTTP/TCP tests, real-framework unit tests, full backend suite, Ruff, hosted CI, or performance measurements passed merely because the offline checks passed. No latency or memory percentage is claimed.
