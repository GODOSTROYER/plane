# Pagination count validation packet

Start with **[VALIDATION.md](VALIDATION.md)**, the authoritative current report, and [REPRODUCE.md](REPRODUCE.md). Application code is already applied at its normal paths. Do not apply historical patches over it.

Validated 13 October 2026: **810 backend tests passed**, including 110 contribution cases. The lazy-wrapper regression is reproduced and fixed by making raw-page SQL counting an explicit opt-in for the known eager app projection. A bounded 14-case query-shape matrix passed, with four variants and identical response hashes.

- [Current benchmark table](evidence/linux-20261013/BENCHMARKS.md)
- [Machine-readable results and raw timing samples](evidence/linux-20261013/summary.json)
- [Raw logs, plans, SQL, sources and harness](evidence/linux-20261013/linux-validation.zip)
- [Manifest](evidence/linux-20261013/manifest.json) and [checksums](evidence/linux-20261013/SHA256SUMS)
- [Application-only patch](evidence/linux-20261013/application.patch)
- [Change since submitted revision](evidence/linux-20261013/review-fix.patch)
- [Current upstream draft description](PR_DRAFT.md)

The full collection used --nomigrations; migration-drift checks, hosted CI and maintainer review are distinct. The 115 focused cases are a subset of 810. The 126-case adjacent-PR check is focused combination evidence, not another full backend run.

## Historical material

The 6 October evidence and [previous report](evidence/linux-20261006/VALIDATION-HISTORICAL.md) are historical. HANDOFF.md, RESEARCH_AND_DECISION.md, PUBLICATION.md, original candidate copies and offline tools describe earlier revisions and are superseded by the current report where they differ. Preserve their provenance; do not use them to overwrite current code or infer current test results. Fork PR #2 is a separate design, unchanged.

The official draft contains only application code and regression tests. This fork branch contains the evidence. Nothing is merged.
