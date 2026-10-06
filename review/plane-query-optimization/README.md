# Plane project-list user-expansion review packet

This packet collects the proposed performance follow-up for the public project-list API, following the deferred query work noted in [Plane PR #9717](https://github.com/makeplane/plane/pull/9717).

**This is a review packet on the contributor's public fork, not a pull request to Plane.** It is isolated on a review branch and does not change the fork's default branch or the upstream repository.

## Start here

1. [Final review report](reports/FINAL_REVIEW.md)
2. [Implementation decision and benchmark comparison](reports/DECISION.md)
3. [Annotated SQL accounting](reports/QUERY_ACCOUNTING.md)
4. [Prepared upstream PR description](reports/PR_DRAFT.md)
5. [Open critique and scope limits](reports/CRITIQUE.md)
6. [Complete patch against the pinned upstream base](patches/project-list-expansions.patch)
7. [Regression test source](tests/test_project_list_expansion_queries.py)
8. [Sanitized evidence archive](evidence/plane-evidence-c70e8050e728-linux-validated.zip)
9. [Evidence redaction and integrity audit](evidence/PUBLICATION_AUDIT.md)

The review branch also includes the changed application view and regression test at their normal source paths for direct code review. The archive includes raw final and historical benchmark trials, SQL captures, PostgreSQL plans, the Linux Docker Compose test transcript, validation logs, scripts, source hashes, a sanitization manifest, and a SHA256 manifest. Its own README contains reproduction instructions and explains which evidence is historical. The archive SHA256 is 553d5caf5624f4dbc6f179c92ff8c18fa2d7a21dae3da4dbe7ddef4a3d144e19.

## Snapshot and validation

- Prepared local contribution snapshot: c70e8050e728a9cd5cbb5549eb931b937c7e3e8c; the same source change is published at the normal source paths on this review branch.
- Production implementation commit: 9227478e0cdb08165ba55e8189872cdb9b99b5e6
- Upstream base: makeplane/plane preview at 7466675e471efe1c96b122615f7a0d30c9b2eb05
- The prepared contribution snapshot lists Arnav Bule as its sole author. Review-packet and source-publication commits are separate; no upstream PR was created.
- Backend suite: 732 passed in both the repository's Linux Docker Compose environment and the Windows test environment; all 32 expansion regression cases passed. Four additional endpoint checks passed. Changed-file lint, formatting, copyright, Django system check, and migration-drift checks passed.
- The full run emitted 92 pre-existing dependency warnings: 4 from factory_boy cleanup behavior and 88 from openpyxl's deprecated datetime.utcnow() usage. Neither source is in the changed files, and no warning caused a test failure.
- Hosted GitHub CI and maintainer approval are still pending; no PR to makeplane/plane has been opened.

## What the headline benchmark establishes

The headline request used 100 projects with fields=id,name,created_by,updated_by and expand=created_by,updated_by. With distinct audit users and uploaded avatars, SQL statements fell from 408 to 10; the median APIClient request time changed from 954.3 ms to 269.5 ms. Timings used 20 randomized trials after two warmups, with SQL capture performed separately.

The expanded HTTP query-bound regression also covers all four user relationships. The 100-project timing result does not benchmark all four expansions or every default project-list field combination. Null audit-user requests retained an 8-statement count, while the measured median changed from 60.8 ms to 66.7 ms. Results are local synthetic-workload measurements, not production latency claims.

## Known limits

- Project cover-image loading remains outside this change.
- The current SQL capture uses the default database test configuration; real read-replica routing was not exercised.
- The distinct-user optimized timing distribution has a broad IQR; no statistical-significance or production-scale claim is made.
- Hosted CI has not run because there is no upstream PR awaiting maintainer approval.

See the [historical initial research report](reports/INITIAL_RESEARCH_HISTORICAL.md) for the earlier investigation. Its proposed join-first approach and unrun-test status were superseded by the final benchmark decision and validation documented above.