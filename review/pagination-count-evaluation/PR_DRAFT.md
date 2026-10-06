### Description

Offset pagination currently evaluates a supplied `total_count_queryset` for truthiness before calling `.count()`, constructing every matching model even when only one page is returned. A projection callback can then trigger a second fetch of the raw page when response metadata calls `len(cursor_result)`.

This change checks the optional count source against `None` and uses SQL counting for transformed, sliced, non-locking querysets with the standard `CursorResult`. It preserves custom length behavior, row locks, grouped-query behavior, and raw-response cache reuse. An explicitly supplied empty count queryset now correctly supplies zero instead of falling back to the page queryset. Callers must continue to supply equivalently scoped count and result querysets.

### Type of Change

- [x] Bug fix (non-breaking change which fixes an issue)
- [ ] Feature (non-breaking change which adds functionality)
- [ ] Improvement (change that would cause existing functionality to not work as expected)
- [ ] Code refactoring
- [x] Performance improvements
- [ ] Documentation update

### Screenshots and Media (if applicable)

Not applicable.

### Test Scenarios

- **800 backend tests passed** in the repository's Linux Docker/PostgreSQL stack, including 100 new cases. The same tests against pristine production source produced **33 regression failures and 767 passes**; all 700 pre-existing tests passed.
- Coverage includes exact page identities, cursors, authorization/filter scope, grouping, callback/controller cardinality, queryset caching, DISTINCT/window queries, PostgreSQL row locks, and a real TCP API-key request.
- Changed-file Ruff lint/formatting, Django system checks, and migration checks passed. The 92 dependency deprecation warnings and three repository-wide unused imports also occur on the pristine base. The API workflow's auto-fixing lint command passed in a disposable copy.
- A separate compatibility run with #9948 passed **116 tests**. Its implementation is not included here.

Representative local workload: 1,000 matching work items, page size 20, 4-KiB description payload per representation. Medians from 20 randomized trials after two warmups:

| Endpoint | Baseline | Count-source fix only | Combined change |
| --- | ---: | ---: | ---: |
| Public API, `fields=id,name` | 242.1 ms | 52.7 ms | 53.2 ms |
| App API, ordinary projection | 243.5 ms | 48.4 ms | 43.9 ms |

Constructed work-item models fell from 1,020 to 20 for the public response and from 1,020 to zero for the app projection. SQL statement counts remained 9 and 7 respectively. Responses matched across all variants. Timings cover APIClient request handling plus JSON parsing with `DEBUG=False`; SQL, allocation, and query-plan probes were separate. Smaller-workload timing differences vary; these are local observations, not production or universal speedup claims. Hosted checks and maintainer review remain separate.

### References

- Complementary to #9948: this retains its existing next-page COUNT probe and removes separate model-evaluation costs.
- [Reproduction instructions, full measurements, source identities, and raw evidence](VALIDATION.md). The review packet stays on my fork; this PR contains only the paginator change and three regression-test files.
