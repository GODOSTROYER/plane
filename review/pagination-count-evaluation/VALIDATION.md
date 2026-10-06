# Pagination count validation — 6 October 2026

This report records real Linux/Django/PostgreSQL validation of the candidate originally published in fork PR #3 at `b8a8da65124432ea7758a1afbc3f2c263eb69872`. It supersedes the earlier packet's pending-validation status. The original offline records remain historical evidence, not database test results.

The application baseline is upstream `7466675e471efe1c96b122615f7a0d30c9b2eb05`. Production changes remain confined to `apps/api/plane/utils/paginator.py`; the other three contribution files are regression tests. The upstream contribution excludes this review packet.

## Corrections made during validation

The first real focused run produced 98 passes and seven failures. The new HTTP fixtures requested `order_by=name`, which is not in `ISSUE_ORDER_BY_ALLOWLIST`; the endpoint correctly substituted its default ordering. The tests' expected insertion order was therefore wrong. The tests and benchmark now request the supported `sequence_id` ordering. Exact response identity assertions were retained. Three test files were formatted with the repository's Ruff configuration. No production-code correction was necessary.

The benchmark explicitly sets `DEBUG=False` and records it. SQL capture, model-construction instrumentation, allocation tracing, and EXPLAIN probes are separate from timing. Resetting the synthetic API key's throttle history is correctly described as a throttle operation, not an authentication-cache reset.

## Real-stack results

| Check | Result |
| --- | --- |
| Focused suite: 100 new cases and five existing paginator tests | 105 passed |
| Complete backend suite with the candidate | 800 passed; 92 warnings |
| Complete backend suite on pristine production source, with the same new tests copied in | 767 passed; 33 expected regression failures; 92 warnings; zero errors |
| Existing tests on the pristine base | All 700 passed |
| Isolated compatibility run with upstream #9948's next-page optimization and its tests | 116 passed |
| Changed-file Ruff lint and formatting | Passed |
| Django system check | No issues |
| Migration drift | No changes detected |
| Exact API workflow lint command in a disposable source copy | Exit 0; fixed three existing unused imports in that copy |

The 33 baseline failures are confined to the new suites: 12 orchestration, 13 ORM, and eight HTTP cases. They expose count-queryset evaluation, unnecessary model hydration, and the explicitly empty count-source fallback. There were no baseline collection, setup, or infrastructure errors. The candidate passes the same cases.

The 92 warnings occur on both revisions: four `factory_boy` post-generation-save deprecations and 88 `openpyxl` UTC timestamp deprecations. None originates in the new tests or paginator. Read-only repository lint on both revisions reports the same three unused imports in `app/views/issue/sub_issue.py` and `app/views/project/invite.py`; those unrelated files are excluded from the contribution.

Coverage includes page boundaries and cursor round trips, exact returned identities, permission/filter scope, empty results, grouping/subgrouping, custom callback/controller cardinality, cached/raw querysets, sliced and unsliced DISTINCT, window queries, and cross-connection PostgreSQL row-lock acquisition/release. Public requests use API-key authentication; app requests use the existing force-authenticated test client and do not validate login. A public request also runs over a real TCP socket. Only recent-visit task dispatch is mocked in the new request tests.

## Performance decision

Retain both production changes. Six workloads (100, 1,000, and 10,000 matching work items, each with empty or 4-KiB description payloads per representation) passed response-equivalence checks on both public and app endpoints. Each uses a fixed 20-item page and 20 randomized trials per variant after two warmups. [The complete table](evidence/linux-20261006/BENCHMARKS.md) includes medians and IQRs for baseline, count-source-only, and combined implementations.

At 1,000 items with 4-KiB descriptions, public median duration was 242.1 / 52.7 / 53.2 ms; app median was 243.5 / 48.4 / 43.9 ms. SQL statements stayed at nine and seven respectively. Baseline constructed 1,020 issue models on either endpoint; count-source-only constructed 20; the combined implementation constructed 20 for the public serializer and zero for the app projection. This is reduced hydration, not reduced statement count.

The count-source correction supplies most of the gain and removes work proportional to the matching population. The page-metadata change additionally avoids the app's 20 raw-page model constructions and their allocation cost. It is not consistently faster in every small case: for 100 items with empty descriptions, app medians were 33.9 ms for count-source-only and 34.7 ms combined, with overlapping IQRs. These trials do not establish statistical significance for close differences. Both stages preserve measured responses, while regression tests protect the intended loading behavior.

At 10,000 items with 4-KiB descriptions, combined medians were 110.6 ms public and 825.1 ms app, versus 2,380.5 and 2,345.9 ms baseline. The app still performs substantial database/projection work as the population grows; bounded model hydration must not be described as constant request cost. Existing annotation, sorting, and filtering costs are outside this patch.

Raw trials, parameterized SQL, representative EXPLAIN ANALYZE plans, dependency versions, source files, original failed-fixture logs, corrected test logs, and JUnit results are in [the 38-member evidence archive](evidence/linux-20261006/linux-validation.zip). [The manifest](evidence/linux-20261006/manifest.json) and [SHA256 checksums](evidence/linux-20261006/SHA256SUMS) identify the artifacts. Logs/source are normalized to LF for portability; the manifest records both canonical and tested runtime-byte hashes. Archive CRCs and member hashes were verified. The publication check uses an explicit file allowlist plus credential/path pattern checks; this is not a guarantee against every possible sensitive string.

## Environment and evidence boundaries

Python 3.12.5, Django 5.2.17, Ruff 0.9.7, and PostgreSQL 15.7, using the repository's Linux Docker Compose stack on Docker Desktop. Docker reported 22 CPUs and 16,459,132,928 bytes of memory. All fixtures are synthetic and services are disposable. Exact installed dependency versions are recorded with the evidence.

The benchmark compares the complete exported baseline method, the same method with only count-source selection corrected, and the combined candidate. This is an in-process controlled comparison, not three deployed environments. The pristine-base test run above is a separate experiment.

The patch removes unnecessary model construction; it does not make total runtime constant, remove every database statement, or provide a transactionally consistent response snapshot. Actual replica routing/lag, production traffic, concurrent throughput, and process peak RSS are not measured. Python allocation probes are not RSS measurements. Hosted CI and maintainer approval are separate from these local results.

## Alternative and adjacent work

Fork PR #2 uses a `RowPreservingList` callback marker instead of the count-based metadata strategy. That approach avoids an additional count after projection but changes the callback contract and the grouper. It has not been combined with this candidate or benchmarked here; no claim of universal superiority over that alternative is made.

Upstream #9948 independently removes the existing next-page COUNT. This candidate retains that probe and addresses separate evaluation costs. An isolated runner combined that change from `0b3afeac9c58e25c6a527ff7ffd39c9bae83f653` with this candidate and its 11 additional tests: all 116 focused cases passed. The submitted implementation does not incorporate #9948's code. Other nearby proposals (#9906, #9486, #9429) concern page/cursor input handling rather than these count paths. The targeted open-PR search found #9948 as adjacent work, not a direct duplicate; unpublished work cannot be ruled out.

See `REPRODUCE.md` for runnable commands and the evidence manifest for exact source identities and raw results.
