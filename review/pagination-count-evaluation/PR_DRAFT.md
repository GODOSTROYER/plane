# Fork-only PR description

Target: **GODOSTROYER/plane:preview**. Head: **perf/pagination-count-evaluation**. This candidate is separate from fork #2's RowPreservingList approach; leave that draft unchanged. Do not submit this packet to the official repository.

[Build/test agent handoff](HANDOFF.md) · [Research](RESEARCH_AND_DECISION.md) · [Publication record](PUBLICATION.md)

### Description

**Draft: real database/request-stack validation and performance measurements are pending.**

This addresses two unnecessary model-materialization paths in pagination:

1. `OffsetPaginator.get_result()` tests `total_count_queryset` for truthiness before calling `.count()`. For Django QuerySets that can fetch all matching models just to obtain a total. Choose the optional source with `is not None` instead.
2. `BasePaginator.paginate()` can evaluate a callback's `.values(...)` projection and subsequently fetch the original page's models again for response metadata. Count transformed SQL-sliced, non-locking QuerySets without that second model hydration, while retaining the original raw-page cardinality.

The metadata optimization is deliberately guarded. `CursorResult.__len__` is unchanged. Custom result lengths, non-queryset sequences, pass-through/controller-only behavior, row locks, and unsliced grouped/custom queries retain their existing path. No permissions, serializer fields, models, migrations, write handlers, or cursor formats change.

**Explicit edge-case behavior change:** an explicitly supplied empty count queryset now supplies zero; previously it fell back to the result queryset's count. Normal callers must supply equivalently scoped result and count querysets.

The metadata change replaces a redundant model-fetch query with a COUNT where applicable. It does not claim to remove every additional SQL query, make database counting constant-time, or provide snapshot consistency between separate statements.

### Relationship to existing work

Complementary to #9948 by @shivsin25, which removes the independent next-page COUNT. This patch retains that existing probe and does not duplicate that optimization. Merge-order coordination/rebase may be necessary. Independent of #9952; no project-list expansion code is changed.

### Type of Change

- [x] Performance improvements
- [ ] Feature
- [ ] Documentation update

### Tests and validation

Three new test files contain 100 authored parameterized cases:

- 57 unit/orchestration cases: optional count sources, empty overrides, page boundaries, lazy slicing, callback/controller cardinality, pass-through cache behavior, custom lengths, locking and unsliced-query guards.
- 22 ORM cases: SQL and model-construction evidence, cold/warm queryset caches, empty/last/out-of-range pages, DISTINCT/window queries, aliases, and actual cross-connection PostgreSQL row locking.
- 21 API/request-stack/TCP cases: public/app work-item lists, cursor round trips, filters, hidden/foreign records, guest/member scope, grouped/subgrouped metadata, and a real-TCP API-key smoke test.

**Executed in the preparation environment:** 57 offline orchestration checks passed using selected production-method bodies with explicit Django/DRF doubles. Original logic produced 12 failures and 45 passes. Eight deliberate regressions were detected. Syntax and patch application/reversal checks originally passed against selected source excerpts. Publication additionally verified the complete original Git blob and applied the supplied combined patch, and reran 57 offline checks using the full source as input.

**Not executed there:** real Django/DRF unit tests, PostgreSQL/HTTP/TCP tests, Ruff, full backend suite, migration/system checks, and benchmark measurements. The offline results must not be read as an integration-test pass.

A separate opt-in benchmark harness compares the real baseline, count-source-only change, and combined candidate with randomized trials, response hashes, SQL/model-construction accounting, allocations, and query plans. No latency or memory improvement percentage is claimed before running it.

### Before ready for review

Replace this section with actual test commands/results, baseline failures, measured tradeoffs, source SHA, and a link to the evidence. Keep any remaining limitations explicit. Stage B should be split or revised if representative query plans do not justify it.
