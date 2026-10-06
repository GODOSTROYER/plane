# Pagination optimization — fork-only build/test packet

**Draft candidate for `GODOSTROYER/plane:preview`, on `perf/pagination-count-evaluation`. Do not modify or submit a PR to the official repository.**

Start with **[HANDOFF.md](HANDOFF.md)**. The application change and three regression files are already installed at their normal `apps/api` paths on this branch. Do not reapply the patches or run the new-branch preparation script against this branch.

## Verification boundary

The supplied candidate contains **100 authored parameterized cases**: 57 unit/orchestration, 22 ORM, and 21 request-stack/TCP. The preparation environment ran 57 offline checks with framework doubles: candidate 57 passed; original 12 failed and 45 passed; eight mutations detected. Those are not Django or PostgreSQL integration results.

During publication, the complete original paginator was verified against Git blob `2082041f1ac641ade4aa87eb9f0d9c581233e333`, the supplied combined patch applied/reversed cleanly in a file-only temporary Git repository, and the 57 offline checks passed again using that full source as input. Published candidate blob: `9909da0a627412e76d0a0ac25573517544bb9c32`. A subsequent standalone-packet run also detected all eight mutations and verified staged/combined patch application; see [publication validation](evidence/publication-validation.json).

**Still pending:** real Django/DRF tests, PostgreSQL/HTTP/TCP tests, Ruff, full backend suite, migration/system checks, hosted CI, and performance measurements. No speedup or production-memory saving is claimed.

## Important design distinction

Fork [PR #2](https://github.com/GODOSTROYER/plane/pull/2) uses an opt-in `RowPreservingList` design. This is the separate supplied **guarded SQL-count candidate**. Neither approach has been selected by real-stack performance evidence in this publication. Leave #2 untouched; compare in isolated local worktrees and do not merge both blindly.

## Contents

- [Build/test handoff](HANDOFF.md): checkout, services, real tests, fail-before proof, gates, benchmarks, and fork-only reporting.
- [Research and decisions](RESEARCH_AND_DECISION.md): inspected behavior, alternatives, guards, and scope.
- [PR draft](PR_DRAFT.md): honest validation status for this fork draft.
- [Publication record](PUBLICATION.md): base/source provenance and publication boundary.
- `candidate/`: original test inputs, duplicated from normal repository paths for offline checks only.
- `tools/`: reconstruction/export utilities, offline checker and mutation runner, opt-in real-stack benchmark.
- [Evidence guide](evidence/README.md): historical and publication validation summaries, never production benchmarks.
- `upstream/paginator_reference.py`: complete verified baseline used for offline class extraction; never overwrite candidate source with it.
- `01-count-queryset.patch`, `02-page-metadata.patch`, and `production.patch`: separable runtime patches. The branch's four-path application/test diff is the canonical combined artifact; `verify_offline.py` reconstructs and checks it without the original ZIP.

Run real tests from `apps/api` as specified in the handoff, not by recursively collecting the review directory. Use an isolated copy of the packet to rerun `python tools/verify_offline.py`; it writes reports and must not overwrite historical evidence in place.

The official PRs #9947 and #9952, old evidence branches, and the fork's `preview` are outside the write scope. Any official submission or merge requires a separate user instruction.
