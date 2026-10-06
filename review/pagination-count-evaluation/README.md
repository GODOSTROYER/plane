# Pagination count optimization — validation packet

Start with **[the completed validation report](VALIDATION.md)** and **[reproduction commands](REPRODUCE.md)**. The application and tests are already applied at their normal repository paths; do not reapply the historical patches.

## Verified on 6 October 2026

- 800 backend tests passed in the repository's Linux Docker/PostgreSQL stack, including all 100 new cases.
- Pristine production source with the same tests: 33 new regression failures, 767 passes, zero errors. All 700 existing tests passed.
- 105 focused tests passed; a separate integration with upstream #9948 passed 116 tests.
- Changed-file lint/formatting, Django system checks, and migration checks passed.
- Six benchmark workloads passed on public/app endpoints with identical responses across baseline, count-source-only, and combined implementations.

The 92 dependency warnings and three unrelated unused-import findings also occur on the pristine base. Hosted checks and maintainer review are separate. Production traffic, real replicas, concurrent throughput, and process peak RSS were not measured.

## Current evidence

- [Validation and design assessment](VALIDATION.md)
- [Reproduction commands](REPRODUCE.md)
- [Complete benchmark table](evidence/linux-20261006/BENCHMARKS.md)
- [Machine-readable summary](evidence/linux-20261006/summary.json)
- [Raw logs, trials, SQL, plans, and tested sources](evidence/linux-20261006/linux-validation.zip)
- [Source/member manifest](evidence/linux-20261006/manifest.json) and [checksums](evidence/linux-20261006/SHA256SUMS)
- [Application-only patch](evidence/linux-20261006/application.patch)
- [Upstream PR description](PR_DRAFT.md)
- [Corrected real-stack benchmark](tools/test_pagination_benchmark.py)

The official submission uses a separate application-only branch. This fork review branch retains the evidence packet. Existing upstream PRs #9947/#9952, fork PR #2, and the fork's preview were not changed.

## Historical material

[HANDOFF.md](HANDOFF.md), [RESEARCH_AND_DECISION.md](RESEARCH_AND_DECISION.md), [PUBLICATION.md](PUBLICATION.md), and the original [evidence guide](evidence/README.md) describe the initial offline preparation and earlier publication scope. Their pending-validation statements are superseded by VALIDATION.md. The subsequent explicit instruction authorizes preparing an upstream draft; no merge is authorized.

The original candidate/ copies, offline tools, source manifest, and separable patches remain available for provenance. The corrected application files and dated evidence manifest are authoritative for this validation. Do not collect the review directory as part of the backend suite or overwrite old evidence when rerunning offline tools.

Fork [PR #2](https://github.com/GODOSTROYER/plane/pull/2) uses a different RowPreservingList design. It remains unchanged and was not combined with this implementation. Read the validation report for the tradeoff; the current measurements do not compare the two designs directly.
