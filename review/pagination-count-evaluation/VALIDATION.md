# Pagination count validation, 13 October 2026

This is the current report for upstream draft #9953. The application base remains `7466675e471efe1c96b122615f7a0d30c9b2eb05`; the independently reviewed submitted revision was `dfebab8fa3bbb4be9bcda9703797e762d106332b`. The [dated manifest](evidence/linux-20261013/manifest.json) identifies the revised application tree and exact five source files. The upstream contribution contains two production files and three test files; this evidence packet stays on the fork.

## Finding and correction

The reported lazy-wrapper regression reproduced with real Django/PostgreSQL and JSON rendering inside the SQL capture. A callback wrapping a values queryset in a mapping or list caused submitted Stage B to issue COUNT followed by the row SELECT. The baseline uses one SELECT and reuses its cache. Extending the reproduction to controller wrappers and a deferred model projection produced five failing cases on the submitted paginator; all five pass on pristine and revised implementations. These are five cases of one generic callback boundary defect, not five independent bugs or observed failures in a production endpoint.

Stage A is unchanged: select the supplied count queryset with `is not None`, then call `.count()`. This avoids hydrating every matching model and respects an explicitly empty count source. Callers must supply equivalently scoped count and page querysets.

Stage B now requires `count_page_in_database=True`. The default evaluates the original page as before, preserving its cache for lazy wrappers and generators. Only the ungrouped app project work-item list opts in: its `issue_on_results` callback eagerly materializes a values projection. The API documents this caller contract. The existing standard-result, sliced-queryset, row-lock and direct-raw-response guards remain. No recursive response inspection or transformed-output cardinality inference was added. Other endpoints retain default behavior.

## Current verification

| Check | Result |
| --- | --- |
| Full Linux backend collection | **810 passed = 700 existing + 110 contribution cases**, 92 warnings |
| Focused collection | **115 passed = 110 contribution + five existing cases**; subset of the full run |
| Lazy wrappers/generator on submitted paginator | Five expected failures, no setup/collection errors |
| Same five on pristine paginator | Five passed |
| Same five on revised paginator | Passed in focused and full collections |
| Focused combination with #9948 at `0b3afeac9c58e25c6a527ff7ffd39c9bae83f653` | **126 passed = 115 focused + 11 adjacent tests**; not an independent full combined-backend run |
| Revised query-shape benchmark | 14 cases, four variants each; response identity/count/cursor/hash checks passed |
| Ruff lint on all five contribution files | Passed |
| Formatting | Four original contribution files passed; changed view range 390-405 passed; unrelated pre-existing view formatting left unchanged |
| Django system / migration-drift checks | No issues / no changes detected |

All current tests ran in the repository's isolated Linux Docker stack with Python 3.12.5, Django 5.2.17 and PostgreSQL. The full suite used `--nomigrations`; migration-drift checks do not establish execution of every historical migration. The 92 warnings are four factory_boy save deprecations and 88 openpyxl UTC timestamp deprecations, the same categories recorded on pristine source. Existing repository-wide unused imports remain outside this patch. Hosted CI and maintainer approval are separate from local execution.

The unchanged HTTP collection includes permission/filter scope, exact page identities and cursor round trips, grouping, and a real TCP API-key request. ORM coverage retains cached/raw querysets, callback/controller cardinality, DISTINCT/window queries and cross-connection row locks. Capturing aliases does not establish a real primary/replica deployment.

## Measurements and interpretation

See the [readable table](evidence/linux-20261013/BENCHMARKS.md), [unzipped machine-readable summary and raw timing samples](evidence/linux-20261013/summary.json), and [complete evidence archive](evidence/linux-20261013/linux-validation.zip).

The new matrix uses default ordering, a sequence_id control, app priority ordering, first/middle/last/beyond-last pages, sizes 20 and 100, a selective app filter, and populated label/assignee/module relationships. It is one 1,000-row synthetic project with approximately 4 KiB in EACH of four description representations, not 4 KiB total per row. It compares pristine, Stage A only, submitted automatic Stage B and revised opt-in Stage B. Timings use ten randomized trials after two warmups; query counts, model construction, Python allocations and EXPLAIN ANALYZE are separate probes. Full payload hashes and expected ordered identities/counts/cursors match.

Most measured improvement comes from Stage A. Opted-in Stage B removes raw-page model constructions in the app projection but does not remove a SQL statement. No claim of universally faster execution, zero allocation, constant runtime, production latency or statistical significance is made. Real replicas, concurrent throughput, process RSS and production traffic remain unmeasured.

The tradeoff is visible in the fresh matrix: the app page-size-100 default case measured 78.7 ms for Stage A alone versus 61.4 ms with opt-in Stage B, while the filtered app case measured 47.6 versus 49.5 ms. These ten-trial local medians support preserving the bounded optimization, not claiming a win for every workload. SQL counts stay unchanged (nine public statements on populated pages and seven app statements in this fixture).

The initial matrix failed because its public priority expectation invented a tie-breaker absent from that endpoint. That case was removed from this deterministic-order matrix; the supported app priority case remains. A second attempt assumed high-before-low app priority; source inspection confirmed the current paginator maps priority to descending priority_order (low-before-high). Its exact expectation was corrected without changing the endpoint. Both unsuccessful harnesses/logs/XML are retained. Production code was not changed to accommodate it.

## Historical evidence and adjacent work

The [6 October report](evidence/linux-20261006/VALIDATION-HISTORICAL.md) and archive remain preserved. Their 800 total, 100 contribution, 105 focused and 116 combined-focused counts apply to the earlier revision. Its 33 baseline failures were regression cases, not 33 independent bugs. Its six datasets were three population sizes times two body widths, each exercised on both surfaces. These historical results must not be added to current totals or called fresh runs of the revised implementation.

#9948 removes a different next-page count probe; its code is not included here. The current focused combination is useful but does not replace a full test run of an eventual merged tree. Fork PR #2's RowPreservingList design remains separate and was not combined or comparatively benchmarked. Existing upstream #9947/#9952 are unchanged. This PR remains a draft.

See [reproduction commands](REPRODUCE.md), [source/member manifest](evidence/linux-20261013/manifest.json) and [checksums](evidence/linux-20261013/SHA256SUMS).
