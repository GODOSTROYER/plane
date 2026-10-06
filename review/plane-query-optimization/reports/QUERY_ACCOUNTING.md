# What remains in the ten-statement request

The separate distinct-user SQL capture (raw/final/final-sql-distinct.json inside the evidence archive) records a real API-key request returning 100 projects with `fields=id,name,created_by,updated_by` and `expand=created_by,updated_by`. The optimized variant executes the following statements in order. Numbers are one-based positions in `captures.optimized`.

| Statement | Purpose | Relationship to this change |
| --- | --- | --- |
| 1 | Find the active API token and validate its associated user | Existing authentication |
| 2 | Update the token's `last_used` value | Existing authentication write |
| 3 | Fetch the authenticated user | Existing authentication |
| 4 | Check active workspace membership | Existing permission check |
| 5 | Count the authorized project queryset | Existing pagination total |
| 6 | Count the limited next-page probe, up to 101 IDs | Existing cursor pagination |
| 7 | Fetch the 100-project page, including annotations and the existing project-lead join | Existing main query |
| 8 | Prefetch active project memberships with their members | Existing membership prefetch |
| 9 | Batch the page's creators, joining each user's avatar asset | New bounded creator expansion fetch |
| 10 | Batch the page's editors, joining each user's avatar asset | New bounded editor expansion fetch |

The legacy request has the first eight statements followed by four relationship reads per project: creator, creator avatar, editor, editor avatar. Thus this fixture goes from `8 + 4 * 100 = 408` statements to `8 + 2 = 10`. These totals include the authentication update; they are SQL statement counts, not exclusively SELECT counts. No permission predicate or existing membership fetch was removed.

The SQL uses driver placeholders; the capture deliberately omits bound parameters and response bodies. The two related-user queries have the same SQL structure, but their role follows the sorted loading plan (`created_by`, then `updated_by`). This is the default database alias test configuration, not verification of a real read-replica topology.

The shared-user capture (raw/final/final-sql-shared.json inside the evidence archive) and null-user capture (raw/final/final-sql-null.json inside the evidence archive) are collected independently in the same harness. The latter removes audit-user references; it does not make a claim about full responses or absent project-lead/default-assignee relationships. The committed all-null regression separately sets all four user relationships to null on a populated page.

Timing samples are separate requests with SQL capture disabled. See the distinct-user timings (raw/final/final-http-uninstrumented-distinct.json inside the evidence archive), shared-user timings (raw/final/final-http-uninstrumented-shared.json inside the evidence archive), and null-user timings (raw/final/final-http-uninstrumented-null.json inside the evidence archive). Each contains the raw 20 randomized trials per variant, median, inclusive first/third quartiles, IQR, minimum and maximum. The disposable API key's rate-limit history is cleared before the clock; timing includes `APIClient.get` and JSON parsing, with `DEBUG=False`, and excludes TCP transport and allocation tracing. Response equality is asserted for every request. These are local synthetic-workload measurements, with no claim of statistical significance or production latency.

The all-four HTTP regression verifies one additional bounded fetch per populated user field: three user/avatar batches and the existing project lead's avatar batch. Query totals outside these fixtures can differ with authentication/cache state, permissions, pagination, and other selected fields. Cover-image loading and malformed non-avatar references are outside this patch.

## Metadata correction for archived results

Older raw outputs call this operation `cold_api_token_cache_per_request`. That label is inaccurate: `api_key:<token>` is the cache key returned by `ApiKeyRateThrottle.get_cache_key()`, not a token-authentication cache. The inspected `APIKeyAuthentication` queries the token, updates `last_used`, and resolves its user on each request. No authentication cache or PostgreSQL buffer cache is flushed by this harness. Current runs use `api_key_throttle_history_reset_per_request`; archived bytes, checksums and timings remain unchanged.
