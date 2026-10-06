# Loading strategy decision

The supplied research recommended starting with conditional joins and selecting the final strategy using measurements. The implementation uses **conditional batched prefetching**, based on those measurements.

## What changed from the supplied patch

The four-field allowlist and `fields`/`expand` intersection are unchanged. Instead of adding user and avatar columns to the annotated, distinct project query, the handler prefetches each included user using a queryset that joins its avatar. The existing project-lead join remains; for that cached parent, the handler prefetches its avatar directly.

`User._base_manager` matches ordinary forward foreign-key lookup semantics. There are no new active-user filters, database-alias overrides, serializer changes, or schema changes. Missing users stay null. Unexpanded or excluded fields add no new relation-fetch queries.

## Evidence

Five exploratory datasets covered distinct users, shared users, URL-only avatars, null audit fields, and full responses with cover images. Four additional comparisons refreshed PostgreSQL statistics on the seeded rows before measuring the two contenders. All strategies produced identical response hashes. The comparison used fresh queryset caches, randomized strategy order, 20 timed trials per strategy/page size, two warmups, and separate Python allocation measurements. These historical strategy comparisons captured SQL during timing; final endpoint measurements below separate SQL capture from timing.

With refreshed statistics, median page-fetch/serialization/encoding times were:

| Dataset | Page size | User/avatar joins | Batched prefetch |
| --- | ---: | ---: | ---: |
| Distinct users with uploaded avatars | 10 | 141.2 ms | 65.8 ms |
| Distinct users with uploaded avatars | 100 | 495.4 ms | 459.0 ms |
| Distinct users with uploaded avatars | 500 | 1812.9 ms | 1767.8 ms |
| Shared users with uploaded avatars | 10 | 127.2 ms | 62.5 ms |
| Shared users with uploaded avatars | 100 | 606.4 ms | 432.7 ms |
| Shared users with uploaded avatars | 500 | 1947.8 ms | 1969.9 ms |
| Null audit users | 100 | 117.9 ms | 46.9 ms |

Large-page timings are close; these medians alone do not establish a statistically reliable difference or show that prefetching always wins. The local evidence favors prefetching for smaller pages, empty relationships, and shared-user allocations. One 500-row shared-user workload slightly favored joins.

For the distinct-user 100-row page, refreshed query plans estimated and returned 100 rows. PostgreSQL planning took about 106 ms for the widened join query versus 4 ms for the original main query; execution was about 29 versus 12 ms. These are individual plan observations, not end-to-end request latencies. Raw plans retain row estimates, buffers, loops, and sort details.

At 500 projects sharing two audit users, separate traced Python peak allocations were about 20.5 MB with joins and 16.5 MB with prefetching. This measures Python allocations, not process RSS or database memory.

## Tradeoffs and limits

For two populated audit fields, prefetching adds two bounded fetch statements instead of adding joins to the main project query. Supported user/avatar expansions in the regression suite issue no additional statements after loading the page. Empty audit relationships need no extra queries. The original lazy-loading behavior already used multiple database statements; this change does not introduce a transactional snapshot guarantee.

Measurements used local Windows Python 3.12.6, Django 5.2.17, PostgreSQL 15.19 and Redis 8.0.5 with `DEBUG=False` for timings. Timings vary on this machine and are not production latency claims. Fixtures cover at most 500 projects per workspace, not a production-scale workspace. Replica lag and malformed avatar references are not benchmarked.

Full responses with cover assets still perform one cover-image read per row. The exploratory `benchmark-covers.json` measures that full response. Its corresponding `http-stack-covers.json` and EXPLAIN artifacts deliberately use sparse fields, so they do not establish full-cover HTTP performance.

The exploratory and refined comparisons were run while the initial join implementation was present. Their scripts explicitly construct both candidates; the recorded source hashes identify that stage. The final endpoint measurements and regression suite exercise the final prefetch implementation. Benchmark tools remain outside the proposed upstream patch.

## Final endpoint measurements without SQL tracing

The final prefetch implementation was measured again after test strengthening, with SQL capture in separate requests and no allocation tracing during timing. Each dataset has 20 randomized trials per variant after two warmups; inclusive quartiles and every raw duration are retained. APIClient timings include JSON parsing and exclude TCP transport. This final experiment did not rerun the historical join comparison.

| Audit users, 100 projects | SQL statements before → after | Median before → after | IQR before → after |
| --- | ---: | ---: | ---: |
| Distinct uploaded-avatar users | 408 → 10 | 954.3 → 269.5 ms | 36.6 → 164.3 ms |
| Shared uploaded-avatar users | 408 → 10 | 961.5 → 250.5 ms | 62.4 → 52.0 ms |
| Null audit users | 8 → 8 | 60.8 → 66.7 ms | 4.1 → 2.0 ms |

The null-user median was about 6 ms higher in both the older and this new local experiment. Additional Python loading-plan work and system variability are possible contributors; no causal attribution or statistical significance is established. Do not describe the patch as having no latency regression. The optimized distinct-user timing also has a broad IQR; the raw distributions remain available.

See [the ten-statement accounting](QUERY_ACCOUNTING.md) for the remaining authentication, permission, pagination, membership and expansion work. The portable evidence bundle includes the scripts, raw trials, representative plans and final validation logs. The strengthened tests pass (732 across the backend suite, including 32 expansion cases; four additional endpoint checks). The full backend suite also passed under Linux in the repository's disposable Docker Compose test stack; hosted GitHub CI remains pending until a PR is published.

## Evidence files

- `benchmark-*.json`: exploratory four-strategy comparisons.
- `refined-*.json`: comparisons after refreshing statistics, including raw repeated trials and source provenance.
- `refined-explain-*.json`: refreshed PostgreSQL plans.
- `final-http-uninstrumented-*.json`: latest final implementation through the complete Django HTTP stack, with SQL capture disabled during timings and quartiles/raw trials retained.
- `final-sql-*.json`: separate untimed captures; driver SQL with bound values omitted.
- `final-http-{distinct,shared,null}.json`: historical final-implementation HTTP timings with SQL capture inside the timer; not combined with the newer measurements.
- `logs/`: baseline failures, final tests, benchmark runs and repository gates.
