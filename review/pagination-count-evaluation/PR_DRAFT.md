### Description

Offset pagination evaluates a supplied `total_count_queryset` for truthiness before calling `.count()`, constructing every matching model even when returning one page. This checks the optional source against `None` instead, including when it is an explicitly empty queryset.

The ungrouped app project work-item list also opts into SQL page counting after its eager values projection, avoiding a second fetch of raw page models. Other callers retain page-cache filling by default, including lazy callback/controller wrappers. Custom lengths, row locks, unsliced query fallbacks and direct raw-queryset responses retain their existing behavior. Count and result querysets must remain equivalently scoped.

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

- **810 backend tests passed** in Linux Docker/PostgreSQL: 700 existing plus 110 contribution cases. Covers response identities, authorization/filter scope, cursors, grouping, callback/controller cardinality, caching, DISTINCT/window queries, row locks and a real TCP API-key request.
- Five lazy-wrapper/generator cases reproduce the extra query on the previous revision and pass on pristine and revised code. Focused suite: 115 passed, a subset of the full collection.
- Ruff lint on five files, formatting of changed code, Django system checks and migration drift passed. The 92 warnings are the existing dependency deprecations. Tests use `--nomigrations`; drift checks do not validate every historical migration.
- Focused combination with #9948: 126 passed (115 focused + 11 adjacent tests), not a full combined-backend run. Its implementation is excluded.

The current benchmark checks 14 sort/filter/page-size/offset scenarios with populated relations and equal full response hashes. Example: 1,000 work items, default ordering, first page of 20, 4 KiB in **each** of four description representations. Local medians from ten randomized trials after two warmups:

| Endpoint | Baseline | Count-source fix only | Revised change |
| --- | ---: | ---: | ---: |
| Public | 231.2 ms | 56.9 ms | 58.9 ms |
| App | 245.2 ms | 58.9 ms | 55.6 ms |

Most improvement comes from the count-source fix. The opt-in additionally avoids raw-page model construction for the app projection; it does not remove a SQL statement and close timing differences vary. Timings cover APIClient handling, parsing and assertions with DEBUG=False; SQL, model, allocation and plan probes are separate. These are local observations, not production forecasts. Hosted checks and maintainer approval remain separate.

### References

- Complementary to #9948; the existing next-page count probe remains.
- [Reproduction, full results, source identities and raw evidence](VALIDATION.md). Evidence remains on my fork; this PR contains two production files and three test files.
