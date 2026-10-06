# Plane project-list user-expansion optimization: final review

The proposed contribution is ready for independent technical review. This packet is published on a separate branch of the contributor's public fork for review. It does not open a pull request or modify makeplane/plane.

## Change summary

The production change batches only the requested project user expansions that survive the existing fields filter. It loads each included user together with the avatar asset used by avatar_url, keeps the existing project-lead join, and leaves serializers, response fields, visibility rules, writes, schema, and dependencies unchanged.

The contribution is a follow-up to the project-list expansion N+1 work explicitly left out of [Plane PR #9717](https://github.com/makeplane/plane/pull/9717). The changed application view and regression module are also included at their normal source paths in this review branch: [project.py](https://github.com/GODOSTROYER/plane/blob/plane-query-review-20261006/apps/api/plane/api/views/project.py) and [test_project_list_expansion_queries.py](https://github.com/GODOSTROYER/plane/blob/plane-query-review-20261006/apps/api/plane/tests/contract/api/test_project_list_expansion_queries.py). The complete source diff is also available in [the patch](../patches/project-list-expansions.patch).

The prepared local contribution snapshot is c70e8050e728a9cd5cbb5549eb931b937c7e3e8c, based on makeplane/plane:preview at 7466675e471efe1c96b122615f7a0d30c9b2eb05; the same source change is published at the normal source paths on this review branch. The source change is limited to the project-list view and its regression tests.

## Verification

| Check | Result |
| --- | --- |
| Regression tests on pristine base | 21 failed and 11 passed, demonstrating the missing batching behavior |
| Focused final checks | 58 passed, including all 32 expansion regressions and adjacent endpoint/serializer tests |
| Full backend suite | 732 passed on Windows and in the repository's Linux Docker Compose test environment |
| Additional endpoint checks | 4 passed, including distinct, shared, null-user and TCP HTTP coverage |
| Ruff lint and formatting | Passed for changed files |
| Copyright check | Passed for both changed Python files |
| Django system check | No issues |
| Migration drift check | No changes detected |
| Independent code review | No blocking correctness findings |
| Hosted GitHub CI | Not run; no upstream PR has been opened |

The full suite emitted 92 warnings, with no warning-related failures: 4 came from existing factory_boy cleanup behavior and 88 from openpyxl 3.1.2 calling deprecated datetime.utcnow() while reading or writing XLSX metadata. Neither warning source is in the changed files. These dependency warnings do not block this scoped patch; dependency upgrades or warning cleanup should be handled separately.

## Measured result and its scope

The headline benchmark is a 100-project APIClient request using fields=id,name,created_by,updated_by and expand=created_by,updated_by. It includes the Django request stack through JSON parsing and excludes TCP transport. SQL capture and allocation tracing were disabled during the timing trials; statement counts were captured separately. Each variant has 20 randomized trials after two warmups, with raw samples and quartiles preserved in the [evidence archive](../evidence/plane-evidence-c70e8050e728-linux-validated.zip).

| Audit-user fixture | SQL statements before → after | Median before → after | IQR before → after |
| --- | ---: | ---: | ---: |
| Distinct users with uploaded avatars | 408 → 10 | 954.3 → 269.5 ms | 36.6 → 164.3 ms |
| Shared users with uploaded avatars | 408 → 10 | 961.5 → 250.5 ms | 62.4 → 52.0 ms |
| Null audit users | 8 → 8 | 60.8 → 66.7 ms | 4.1 → 2.0 ms |

The distinct-user median fell about 71.8%; this is distinct from the 97.5% statement reduction. The null-user median was about 6 ms higher in both local experiments. The distinct optimized distribution has a broad IQR. The measurements do not establish statistical significance, causality for the null-user difference, or production latency.

The regression tests exercise all four supported user expansions. The headline timing and SQL-count comparison exercises only the two audit fields listed above. The result should not be described as a benchmark of all four expansions or all full project-list responses.

## Scope and remaining checks

Project cover-image reads remain outside the patch. The SQL evidence uses the default-database test configuration and does not verify a real read-replica topology. Fixtures are synthetic and do not establish behavior at production workspace sizes. The all-four HTTP regressions, query accounting, raw plans, logs, and reproduction instructions are included in the review packet and evidence archive.

Before opening an upstream PR, repeat the duplicate-PR search and follow Plane's current contribution instructions. Hosted CI and maintainer review become available only after the upstream PR is opened. This publication itself is review material only.