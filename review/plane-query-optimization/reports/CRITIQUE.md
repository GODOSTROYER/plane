# Final critique and reviewer prompts

This is a candid review aid for the proposed Plane project-list user/avatar batching change. No blocking production-code correctness defect was identified in the final diff. The remaining items define the evidence boundary and identify useful independent checks.

## Review these claims precisely

1. **The performance benchmark is deliberately narrow.** Its 100-project request uses fields=id,name,created_by,updated_by and expands only created_by,updated_by. The regression module also exercises project_lead and default_assignee, but the 954.3-to-269.5 ms headline must not be presented as a four-expansion benchmark.
2. **The null-user latency median is higher.** The SQL count stays at 8, while the local median changed from 60.8 to 66.7 ms. The samples do not establish a reliable latency regression or its cause. The distinct-user optimized timing IQR is also broad (164.3 ms). Preserve that qualification in any public summary.
3. **A separate N+1 remains.** Project cover-image assets can still cause per-row reads for full responses. This work only addresses requested user/avatar expansions.
4. **Replica routing is not verified.** The captured SQL and query tests use the default database test configuration. They do not prove behavior when a real read-replica router is active.
5. **The 92 warnings are unrelated but visible.** They come from existing factory_boy cleanup behavior and openpyxl's deprecated datetime.utcnow() calls. No changed-file warning or warning-caused test failure was reported. Do not hide or claim they were fixed.
6. **Hosted CI is pending.** Local Windows and Linux Docker Compose suites passed, but hosted GitHub checks and maintainer review cannot be claimed until an upstream PR exists.

## Test-design maintainability note

The loading-plan tests inspect Django's private queryset state (_prefetch_related_lookups and query.select_related), and the HTTP query-bound assertion encodes the current loading plan's per-field statement increment. These tests provide a useful guard for this optimization, but may need adjustment if the ORM plan changes while observable response and bounded-query behavior remain correct. An independent reviewer should judge whether that coupling is intentional and proportionate.

## What is strong

The diff has a narrow production surface, preserves the serializer and project-lead join, conditions loading on the fields that will actually be serialized, and covers nested avatar assets. The final suite includes exact per-project identity checks, shared and single-user role cases, nulls, inactive users, soft-deleted avatars, visibility, pagination, and query-free serialization after loading. The test suite passed against both final code and the Linux Docker Compose path.

The [decision report](DECISION.md) records why the measured implementation uses batched prefetching instead of simply widening the main query. The [annotated accounting](QUERY_ACCOUNTING.md) explains the ten statements in the audit-user workload. The raw trials and SQL/plan evidence are in the sanitized archive.