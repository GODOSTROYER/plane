# Fork publication record — 6 October 2026

## Authorization and destination

The user requested this supplied pagination candidate as a PR with build/test documentation **on their fork only**. Repository: `GODOSTROYER/plane`. New head: `perf/pagination-count-evaluation`. Base: the fork's `preview` at `7466675e471efe1c96b122615f7a0d30c9b2eb05`. The official repository is not a write destination, and existing PRs/branches are not modified.

The prior packet's upstream-target publication instructions have been replaced with fork-only continuation instructions. This is an authorization correction, not a change to the supplied runtime candidate or test cases.

## Existing parallel design

At publication discovery, fork PR #2 was an open draft on `perf/bounded-pagination-evaluation`, head `cdd2459637454202b8120daed9d12ef56842df64`, targeting the same fork base. It proposes `RowPreservingList` metadata reuse. This package instead proposes guarded SQL counting for transformed sliced pages. Leave PR #2 untouched and distinguish its 46-check evidence from this candidate's 57 offline checks and 100 authored cases. They are alternative metadata designs, not additive optimizations.

## Source integrity and application

The complete paginator was fetched through the GitHub connector and assembled locally from its returned content. Its computed Git blob hash matched `2082041f1ac641ade4aa87eb9f0d9c581233e333` before applying edits. The supplied application-and-tests patch applied successfully to that full verified file in an isolated file-only Git repository; reverse application was checked. New tests matched the supplied candidate bytes. The result is 24 added and 3 removed runtime lines, plus three new test files (807 additions and 3 deletions across the four application/test paths).

Candidate paginator blob: `9909da0a627412e76d0a0ac25573517544bb9c32`.
Unit test blob: `cc675bd1526ee9187db3a68c3a46312396d95c43`.
ORM test blob: `87969d9c09923feb31d0b43484157f66f8294f4c`.
Request/TCP test blob: `1f3befad5e63d7e16ecbf021ea3ef80d9ae3f7fb`.

## What was actually rerun

`run_offline.py --variant candidate --source-file <verified complete original paginator>`: **57 passed** with framework doubles. This extracts the selected classes; it is not a full application import or real database run. Historical baseline and mutation records remain historical. Pinned framework validation, PostgreSQL, HTTP/TCP, Ruff, whole-suite execution, benchmark results and hosted CI are still pending.

## Build agent requirements

Use [HANDOFF.md](HANDOFF.md). Start from this already-applied branch, retain all guards until real tests support a deliberate change, and record actual failure/pass evidence. Correct fixture or formatting problems transparently; do not convert failed integration assertions into mocks. Stage B remains subject to query-plan and latency review and can be split if not justified. Do not borrow test counts or benchmark numbers from the project-list optimization or fork PR #2.
