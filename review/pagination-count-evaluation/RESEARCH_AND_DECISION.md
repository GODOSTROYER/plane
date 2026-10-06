# Research and implementation decision

## Scope and evidence boundary

This is a targeted audit of the shared pagination path and its work-item callers, not a certification of the entire repository or every open pull request. The current `preview` ref was read through the connected GitHub integration and pinned to `7466675e471efe1c96b122615f7a0d30c9b2eb05`. Relevant open paginator PR descriptions were searched again. The existing #9952 project-expansion PR is not part of this patch.

The research below distinguishes directly inspected implementation, interpretation, and work still requiring execution. No new performance measurements were available in this environment.

## Repository observations

**Count-source evaluation.** `OffsetPaginator.get_result()` chooses between a supplied count queryset and its result queryset by testing `self.total_count_queryset` in a conditional. The public work-item list supplies a full Issue queryset for that purpose. The app work-item list supplies a filtered pre-annotation queryset and applies restricted-guest scope to both its result and count paths. The Issue model has substantial rich-description fields.

**Metadata evaluation.** `BasePaginator.paginate()` invokes `on_results` and later obtains the response's `count` from `CursorResult.__len__()`. The app's `issue_on_results()` materializes a separate `.values(...)` projection. The original page can therefore remain unevaluated until its length is requested, causing a separate model fetch.

**Grouping is different.** `GroupedOffsetPaginator` and `SubGroupedOffsetPaginator` override `get_result()`, perform their own counts/window queries, and evaluate their page for an emptiness check. They are not covered by the count-source edit. This candidate does not rewrite those algorithms.

Source locations, pinned for reproduction:

- [Paginator](https://github.com/makeplane/plane/blob/7466675e471efe1c96b122615f7a0d30c9b2eb05/apps/api/plane/utils/paginator.py)
- [Public work-item list](https://github.com/makeplane/plane/blob/7466675e471efe1c96b122615f7a0d30c9b2eb05/apps/api/plane/api/views/issue.py)
- [App work-item list](https://github.com/makeplane/plane/blob/7466675e471efe1c96b122615f7a0d30c9b2eb05/apps/api/plane/app/views/issue/base.py)
- [Projection callback](https://github.com/makeplane/plane/blob/7466675e471efe1c96b122615f7a0d30c9b2eb05/apps/api/plane/utils/grouper.py)
- [Issue model](https://github.com/makeplane/plane/blob/7466675e471efe1c96b122615f7a0d30c9b2eb05/apps/api/plane/db/models/issue.py)
- [Dependency pins](https://github.com/makeplane/plane/blob/7466675e471efe1c96b122615f7a0d30c9b2eb05/apps/api/requirements/base.txt)

## External research

[Django 5.2's QuerySet reference](https://docs.djangoproject.com/en/5.2/ref/models/querysets/) documents evaluation through truthiness and length, cached counts, lazy slicing, and the interaction between ordering and DISTINCT projections. These explain why a small SQL-statement count does not establish small application memory use.

The relevant version's implementation was also inspected, rather than relying only on generic guidance:

- [`QuerySet.__bool__`, `_fetch_all`, and `count` in Django 5.2.17](https://github.com/django/django/blob/5.2.17/django/db/models/query.py)
- [`Query.get_aggregation` and `get_count` in Django 5.2.17](https://github.com/django/django/blob/5.2.17/django/db/models/sql/query.py)

Aggregation handles sliced and distinct queries using an inner query. Its ordering and locking adjustments matter: blindly replacing every sequence length with COUNT is not the selected design.

[PostgreSQL 15 aggregate documentation](https://www.postgresql.org/docs/15/functions-aggregate.html) explicitly notes the work involved in an exact table count. Eliminating Python model construction does **not** make the database count constant-time. [PostgreSQL EXPLAIN guidance](https://www.postgresql.org/docs/15/using-explain.html) informs the proposed plan/buffer measurements; EXPLAIN ANALYZE executes its statement and belongs only on isolated test data here.

## Options considered

| Option | Decision and reasoning |
|---|---|
| Explicit `is not None` selection | Chosen. Distinguishes absence of an override without reading its rows. |
| `supplied_queryset or queryset` | Rejected. Reintroduces the same boolean evaluation. |
| `.exists()` before `.count()` | Rejected. Existence is not the optional-argument contract and adds a separate operation. |
| `.iterator()`, `.only()`, or `.defer()` for counting | Rejected. Still transfers rows merely to count; also risks callback/field interactions. |
| Global `len(serialized_results)` | Rejected. Python filtering, deduplication, mappings, grouping, and controllers can change output cardinality. |
| Global `CursorResult.__len__ = queryset.count` | Rejected. Alters sequence/cache semantics and custom result behavior beyond this response construction. |
| Derive page size from total minus offset | Not chosen. Requires equivalent populations and timing assumptions; adjacent to #9948's independent next-page proposal. |
| Reuse `.values("id")` probe as universal page count | Not chosen. Changing projected fields can affect DISTINCT behavior; it also couples this work to #9948's probe removal. |
| Always SQL-count the raw page | Rejected. Can add work for pass-through rendering, affect unsliced ordering-sensitive counts, and omit row locks. |
| Conservatively count transformed SQL-sliced pages | Chosen as Stage B, pending real query-plan validation. Retains original queryset cardinality and avoids its model hydration. |
| Redis cache, new index, approximate totals, keyset pagination | Not needed for the immediate defects. Introduces invalidation, migration, or API decisions without measured justification. |

There is no claim that this is the universally fastest SQL plan. Stage A has a direct evaluation defect. Stage B's resource/latency tradeoff must be measured for Plane's annotated and DISTINCT queries before being presented as a performance win.

## Exact compatibility decisions

Stage A preserves queryset choice except for a supplied empty override: **zero now remains zero** instead of falling back to a different queryset. This deliberate edge-case change is tested and disclosed. Normal callers should provide equally scoped count and result populations. Their authorization and filters are not changed.

Stage B leaves `CursorResult.__len__` intact. It uses `.count()` only when all of the following are true: a callback was supplied; the result is exactly the standard CursorResult; the raw page is a Django QuerySet; it has a SQL slice; it is not a `select_for_update` query; and final output is not the raw page itself. Otherwise the existing length path runs.

This preserves custom length overrides, non-queryset sequences, pass-through/controller-only behavior, row-lock acquisition, and the unsliced grouped/custom path. Sliced DISTINCT and window-filtered queries have explicit ORM regression candidates. The query flags are Django internals, so retain version-specific tests during dependency upgrades; do not describe them as a stable public introspection API.

No snapshot-isolation guarantee is added. Counts and data already execute in separate statements. An insert/delete racing between them can still produce changing pagination metadata. This change must not claim to solve concurrent-update pagination consistency.

## Existing-work overlap

[#9948](https://github.com/makeplane/plane/pull/9948), by shivsin25, removes an independent next-page COUNT. Its inspected patch leaves count-queryset truthiness unchanged. This candidate retains its existing probe and does not copy that optimization. Coordinate merge order and credit the adjacent work.

Other returned paginator proposals include #9906 (page parameter), #9486 (cursor bounds), #9429 (nonpositive per_page), #9852 (archive counts), #9767 (public grouping), #9469 (page search), and #8588 (workspace layouts). Recheck current diffs before publication. Their existence is not proof that all interactions have been integration-tested.

## Performance experiment and acceptance

Use `tools/test_pagination_benchmark.py` against the real pinned base and candidate. It compares original, count-source-only, and combined variants using the actual request stack. Use fixed page size 20 while varying matching populations (100, 1,000, 10,000) and description sizes (0, 4 KiB, then larger only when safe). Run each workload in a fresh isolated process/test run. Two warmups and randomized trial order precede medians/IQRs; allocations, SQL, model construction, and EXPLAIN probes are separate from timings.

Acceptance: payload/metadata equivalence for normal inputs; explicit empty-override semantics documented; no count-only full-population hydration; no extra raw-page model hydration for the targeted projection path; preserved authorization/grouped behavior; no material representative latency regression. Do not gate ordinary CI on millisecond thresholds. Extend with RSS and controlled concurrency measurements before making deployment-level memory claims.

The benchmark emits raw data, versions, source hashes, response hashes, parameterized SQL, and plans. It is **authored but unexecuted** here. It does not benchmark production traffic or TCP latency. A separate real-TCP smoke test is included in the contract candidate.

## Unfinished or intentionally excluded

Full repository tests, actual Git-blob application, Ruff, real PostgreSQL/HTTP/TCP execution, runtime query plans, and publication require the build agent. Burndown algorithm changes, grouped-paginator eager evaluation, cursor validation, deep-offset/keyset redesign, and #9952 are outside this candidate. Split Stage B out if measured plans or maintainer feedback do not justify it; do not weaken a correctness test just to retain a larger diff.

## Fork publication addendum — 6 October 2026

This package is published only to `GODOSTROYER/plane`, on `perf/pagination-count-evaluation`, targeting that fork's `preview`. The official repository is not an authorized write target. The complete paginator source was subsequently verified against blob `2082041f1ac641ade4aa87eb9f0d9c581233e333` and the supplied patch applied successfully; real-stack tests and performance measurements remain pending.

An existing fork draft #2 uses a different opt-in `RowPreservingList` strategy for metadata. This publication preserves the supplied SQL-count candidate for side-by-side build/test review and leaves that draft unchanged. Neither strategy has been established as superior by the offline checks. Do not merge both or conflate their test counts/results.
