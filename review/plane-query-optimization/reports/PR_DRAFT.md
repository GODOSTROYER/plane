### Description

The public project-list endpoint performs repeated user and avatar reads when a page expands user relationships. For example, `fields=id,name,created_by,updated_by&expand=created_by,updated_by` on 100 projects with uploaded-avatar audit users issued 408 SQL statements in the local request-stack benchmark.

This follow-up to #9717 batches included `created_by`, `updated_by`, `project_lead`, and `default_assignee` expansions together with their avatar assets. It intersects `expand` with `fields`, allowlists the supported relationships, and retains the existing project-lead join. Other users use their base manager to preserve ordinary foreign-key lookup semantics, including inactive historical users.

The change is confined to the list GET handler and regression tests. Serialization, permissions, ordering, pagination, writes, and schema remain unchanged. Cover-image loading is outside this scope.

### Type of Change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] Feature (non-breaking change which adds functionality)
- [ ] Improvement (change that would cause existing functionality to not work as expected)
- [ ] Code refactoring
- [x] Performance improvements
- [ ] Documentation update

### Screenshots and Media (if applicable)

Not applicable.

### Test Scenarios

- **732 backend tests passed** in the repository's Linux Docker Compose stack and Windows test environment, including **32 new regression cases**. The final regression file against the pristine base produced 21 failures and 11 passes, demonstrating the missing loading guarantees.
- Coverage includes all four expansions, sparse fields, exact user/avatar identity, shared users across roles, null/inactive users, soft-deleted avatars, bounded HTTP query growth, query-free serialization after page loading, visibility, empty results, and cursor pagination.
- Changed-file Ruff lint/formatting, copyright, Django system checks, and migration-drift checks passed. The 92 full-suite warnings are existing factory_boy/openpyxl deprecations; none originate in the changed files.
- Local validation is separate from hosted GitHub checks and maintainer review.

6 October 2026 rerun of the corrected published harness: local 100-project audit-user measurements (20 randomized trials per variant after two warmups; SQL counts captured separately from timing):

| Fixture | SQL statements, before → after | Median, before → after | IQR, before → after |
| --- | ---: | ---: | ---: |
| Distinct uploaded-avatar users | 408 → 10 | 1245.3 → 464.4 ms | 325.0 → 172.5 ms |
| Shared uploaded-avatar users | 408 → 10 | 1538.7 → 396.9 ms | 654.3 → 250.6 ms |
| Null audit-user relations | 8 → 8 | 112.0 → 124.2 ms | 45.4 → 62.8 ms |

Responses were identical. These measurements cover `APIClient.get` plus JSON parsing for `fields=id,name,created_by,updated_by&expand=created_by,updated_by`, rather than TCP or production traffic. The A/B harness reconstructs legacy loading by removing only the new expansion prefetches at pagination; the pristine-base regression run is separate. The null-user median increased by about 12 ms, and the distinct-user optimized IQR is broad; no statistical-significance or universal latency claim is made. Real replica routing and production-scale workspaces were not exercised. Earlier 5 October measurements are preserved unchanged in the historical evidence archive; the table above uses the latest replay.

### References

- Follow-up to the project-list N+1 work explicitly deferred in #9717.
- [Reproduction commands, strategy decision, raw trials, SQL accounting, and validation logs](https://github.com/GODOSTROYER/plane/tree/ac453a0783f0774b196d44d665afafb2b5fcbc39/review/plane-query-optimization). The evidence packet is hosted separately on my fork; this PR contains only the application change and regression tests.
