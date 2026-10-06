### Description

The public project-list endpoint can issue repeated user and avatar reads when a page expands project users. This follow-up to [#9717](https://github.com/makeplane/plane/pull/9717) batches the requested `created_by`, `updated_by`, `project_lead`, and `default_assignee` relations, including each user's avatar. Loading is limited to expansions that remain in `fields`; the existing project-lead join and serializer are preserved.

The change does not alter response shape, permissions, writes, or schema. Cover-image loading is outside this scope.

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

- Added 32 database-backed regression cases for sparse fields, all four expansions, bounded query growth, query-free serialization, user/avatar identity, null and inactive users, soft-deleted avatars, visibility, empty results, and cursor pagination.
- Full backend suite: **732 passed** in the repository's Linux Docker Compose test environment; the same 732 tests also passed on Windows. The regression tests reproduce the repeated reads against the pristine base.
- Changed-file lint, formatting, copyright, Django system check, and migration-drift check passed. Hosted GitHub CI has not run yet.

Local 100-project APIClient measurements with fields=id,name,created_by,updated_by and expand=created_by,updated_by (20 randomized timed trials after two warmups; SQL counts collected separately):

| Fixture | SQL statements, before → after | Median, before → after | IQR, before → after |
| --- | ---: | ---: | ---: |
| Distinct uploaded-avatar users | 408 → 10 | 954.3 → 269.5 ms | 36.6 → 164.3 ms |
| Shared uploaded-avatar users | 408 → 10 | 961.5 → 250.5 ms | 62.4 → 52.0 ms |
| Null audit-user relations | 8 → 8 | 60.8 → 66.7 ms | 4.1 → 2.0 ms |

This timing and SQL-count comparison exercises the two audit fields listed above; the four user relationships are covered by the regression tests, not by this headline timing experiment. Responses were identical in the measured comparisons. Timings cover the local Django APIClient request stack and JSON parsing; they are not production latency claims. The null-user median was about 6 ms higher locally, with no claim that this is statistically significant.

### References

Follow-up to the project-list query optimization noted in [#9717](https://github.com/makeplane/plane/pull/9717).
