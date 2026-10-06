# Build-agent handoff: Plane pagination optimization

## Objective and authorization

Finish and validate the supplied pagination optimization in this draft PR on **GODOSTROYER/plane only**. Publication to the official repository is not authorized. Do not open, update, comment on, or merge a PR in `makeplane/plane`. Do not modify existing PRs **#9947 or #9952**, their branches, evidence branches, or existing working-tree files. Never push directly to `makeplane/plane:preview`, force-push an existing branch, reset an existing checkout, or clean unrelated files/services.

New branch: **`perf/pagination-count-evaluation`**.
PR target: **`GODOSTROYER/plane:preview`**. Do not merge without a separate user instruction.
Reviewed base: **`7466675e471efe1c96b122615f7a0d30c9b2eb05`**.
Reviewed paginator blob: **`2082041f1ac641ade4aa87eb9f0d9c581233e333`**.

The source and tests are already applied on this publication branch. Continue the fork-only draft rather than reapplying patches or creating another PR. Fork PR #2 (`perf/bounded-pagination-evaluation`) is a different RowPreservingList design: leave it untouched; see `PUBLICATION.md`.

## Actual local completion

The production candidate changes only `apps/api/plane/utils/paginator.py`. Three new test files contain **100 authored parameterized cases** (static inventory included): 57 orchestration/unit, 22 database, and 21 API/request-stack/TCP.

Local execution used selected upstream method bodies with explicit framework doubles. Results: **57 pass on the candidate; 12 fail and 45 pass on original logic**. Eight targeted regressions were injected and detected, with no collection errors. Patch application, reversal, and staged application passed against the selected source excerpt in an isolated temporary Git repository. Python syntax was checked.

**None of those results establishes a real Django/DRF/PostgreSQL/HTTP test pass.** Ruff, the complete backend suite, query plans and benchmarks remain pending. During publication, the complete original source matched its Git blob, the combined patch applied/reversed successfully in a file-only temporary Git repository, and 57 offline checks passed again against its extracted candidate classes. The standalone packet also reran the baseline and eight mutations successfully; see `evidence/publication-validation.json`. That is not a full-clone or real-framework test. No speedup or production-memory claim has been measured. Read `evidence/README.md` and `RESEARCH_AND_DECISION.md` before changing this status.

## 1. Check out the published fork branch in a new clone

Do not run `prepare_branch.py` or reapply the patches to this branch: its code and tests are already installed. That preparation tool is for reconstructing the candidate from the pristine base and deliberately refuses existing branches.

```sh
git clone --branch perf/pagination-count-evaluation --single-branch \
  https://github.com/GODOSTROYER/plane.git plane-pagination-validation
cd plane-pagination-validation
git remote get-url --push origin
git branch --show-current
git rev-parse HEAD
export WORKTREE="$PWD"
export KIT="$WORKTREE/review/pagination-count-evaluation"
```

Confirm the push URL is `GODOSTROYER/plane`, the branch is `perf/pagination-count-evaluation`, and the base is the pinned revision. Use a fresh directory; do not reset an existing checkout. Keep the fork's `preview`, PR #2, #9947, #9952, and old evidence branches unchanged.

The runtime/test delta is limited to:

```text
apps/api/plane/utils/paginator.py
apps/api/plane/tests/unit/utils/test_paginator_evaluation.py
apps/api/plane/tests/contract/test_paginator_evaluation.py
apps/api/plane/tests/contract/api/test_work_item_pagination_evaluation.py
```

This fork review also intentionally includes `review/pagination-count-evaluation/` documentation/tools. The `candidate/` test copies are publication inputs, not a second backend suite. Run the files under `apps/api` for real integration validation; do not collect every Python file in the review directory as application tests.

The baseline reference in `upstream/paginator_reference.py` must never overwrite the candidate source. Obtain baseline bytes with `export_baseline.py`; source integrity remains an explicit guard. The branch's application/test diff is the canonical complete artifact; the offline verifier reconstructs the combined patch from that reference and the candidate test inputs.

## 2. Recheck existing work and review the decisions

Read current #9948 and its diff. It independently removes the next-page COUNT; this candidate **retains that probe** and does not duplicate its optimization. Check merge-order compatibility locally or explain the complementary scope in this fork PR. Also check #9906, #9486, and #9429 for edits near this code. No author has been contacted by the assistant; do not post to the official repository without separate authorization.

Review Stage A's deliberate behavior change: an explicitly supplied empty count queryset now supplies zero, rather than triggering the fallback. Normal callers must use equivalent result/count populations. Do not interpret a zero override as permission to broaden result scope.

Review Stage B particularly carefully. It preserves `CursorResult.__len__`, counts only transformed SQL-sliced non-locking QuerySets with the exact standard result type, and falls back for custom lengths, raw/pass-through/controller-only responses, locks, and unsliced grouped/custom queries. Retain the guards unless real evidence justifies a different contract. Do not replace the count with transformed-output length.

The production stages are separable: `01-count-queryset.patch`, then `02-page-metadata.patch`. The preparation script applies both. If Stage B fails actual SQL-plan or compatibility review, split it into a separate follow-up rather than weakening tests or overstating completion. A new remote PR still needs user authorization; local isolated comparisons do not.

## 3. Run real focused tests and existing regression tests

Use the repository's pinned Python/dependencies and real PostgreSQL stack. The inspected pins are Django 5.2.17 / DRF 3.17.2; repository CI selects Python 3.12. The assistant's Python 3.13 offline results are not a substitute.

The repository supplies `docker-compose-test.yml` with service `api-tests`. Configure **test-only** `apps/api/.env` in the new worktree from `.env.example`, including a valid test SECRET_KEY; do not copy production credentials or overwrite an existing environment. Its database/cache/broker/storage services are test-only and use tmpfs. Use a unique Compose project name.

Example Bash commands below assume KIT and WORKTREE are absolute paths. On PowerShell, use equivalent argument quoting and absolute mount paths; the Python preparation/export tools avoid shell encoding problems.

```sh
: "${KIT:?Set KIT from section 1}"
: "${WORKTREE:?Set WORKTREE from section 1}"
cd "$WORKTREE"
set -o pipefail

docker compose -p plane-pagination-validation -f docker-compose-test.yml \
  run --rm --build -v "$KIT/evidence:/verification-output" api-tests \
  pytest \
    plane/tests/unit/utils/test_paginator.py \
    plane/tests/unit/utils/test_paginator_evaluation.py \
    plane/tests/contract/test_paginator_evaluation.py \
    plane/tests/contract/api/test_work_item_pagination_evaluation.py \
    --nomigrations -o addopts='' -vv \
    --junitxml=/verification-output/real-focused.xml \
  2>&1 | tee "$KIT/evidence/real-focused.txt"
```

The TCP test uses the existing `plane_server` fixture and a real API key. The other public requests exercise API-key authentication; the app's `session_client` force-authenticates and does not test login. Only recent-visit task dispatch is mocked. Real Redis/broker services are still required for other framework edges.

The row-lock case uses a separate PostgreSQL connection with `nowait=True`, expects lock-not-available inside the owning transaction, and succeeds after release. Do not replace it with a SQL-string assertion. Investigate threading/test transaction setup if it fails; do not convert it to a vacuous mock.

## 4. Prove fail-before against the actual base

Create a **second new detached worktree** at the pinned base. Copy only the three new test files into it, leaving production source untouched. Configure its own test-only environment and Compose project name (for example `plane-pagination-baseline`). Run the same focused tests and record failures/JUnit separately.

Expected mechanism: count-queryset cache/hydration guarantees and projected-page hydration guarantees fail on the original code. Positive controls should pass. The offline “12 failures” is **not** a prediction of the real suite's exact failure count. Explicit empty-count behavior also changes by design. Distinguish those failures from missing dependencies, broker errors, fixture failures, authorization failures, or SQL incompatibilities.

Do not revert source in the candidate worktree, stash a user's changes, or mutate existing PR branches to run the baseline.

## 5. Lint, complete suite, and migration/system checks

Run changed-file Ruff lint and formatting using the real repository configuration. Formatting corrections may be needed because Ruff is unavailable in the assistant environment. Inspect every resulting change and keep unrelated files out of the patch.

Inside `apps/api`, using the configured real environment:

```sh
python -m ruff check \
  plane/utils/paginator.py \
  plane/tests/unit/utils/test_paginator_evaluation.py \
  plane/tests/contract/test_paginator_evaluation.py \
  plane/tests/contract/api/test_work_item_pagination_evaluation.py
python -m ruff format --check \
  plane/utils/paginator.py \
  plane/tests/unit/utils/test_paginator_evaluation.py \
  plane/tests/contract/test_paginator_evaluation.py \
  plane/tests/contract/api/test_work_item_pagination_evaluation.py
python manage.py check
python manage.py makemigrations --check --dry-run
```

Run the full backend suite. Review and sanitize new evidence before committing it:

```sh
cd "$WORKTREE"
docker compose -p plane-pagination-validation -f docker-compose-test.yml \
  run --rm -v "$KIT/evidence:/verification-output" api-tests \
  pytest plane/tests --nomigrations -o addopts='' \
    --junitxml=/verification-output/real-full-suite.xml \
  2>&1 | tee "$KIT/evidence/real-full-suite.txt"
```

Compare any failures with the same actual base/environment. Do not report a full pass from test collection or silently dismiss failures as pre-existing. The inspected API workflow runs `ruff check --fix apps/api`; reproduce that exact auto-fixing command only in a disposable source copy, not the preserved candidate worktree. Retain copyright headers and confirm `git diff --check`.

Run the focused suite against compatible changes from #9948 in a separate temporary integration worktree if useful, after reviewing its current diff. Do not merge someone else's unreviewed branch into the candidate merely to obtain a larger combined improvement.

## 6. Measure the real performance tradeoff

First export the **actual Git blob**, not a selected-method snapshot:

```sh
python "$KIT/tools/export_baseline.py" \
  --repo "$WORKTREE" --output "$KIT/evidence/paginator-baseline.py"
```

Do not use Windows PowerShell redirection that may transcode `git show` output to UTF-16. The export tool writes verified raw bytes and refuses to overwrite an existing export.

Use a third **disposable benchmark worktree** containing the validated candidate. Copy `tools/test_pagination_benchmark.py` only into that worktree's `apps/api/plane/tests/`, never into a production-code commit. Configure a unique test-only Compose project/environment there. Example from that benchmark worktree:

```sh
docker compose -p plane-pagination-benchmark -f docker-compose-test.yml \
  run --rm --build -v "$KIT:/verification-kit" \
  -e PLANE_RUN_PAGINATION_BENCHMARK=1 \
  -e PLANE_PAGINATION_BASELINE_FILE=/verification-kit/evidence/paginator-baseline.py \
  -e PLANE_BENCH_ROWS=1000 \
  -e PLANE_BENCH_BODY_BYTES=4096 \
  -e PLANE_BENCH_TRIALS=20 \
  -e PLANE_BENCH_OUTPUT=/verification-kit/evidence/benchmark-1000-4096.json \
  api-tests pytest plane/tests/test_pagination_benchmark.py \
  --nomigrations -o addopts='' -q -s
```

Repeat at 100 / 1,000 / 10,000 matching issues, page size 20, with empty and 4-KiB descriptions. Increase workload only within safe local resource limits. The harness also bounds inputs and requires a PostgreSQL test database; do not disable its opt-in or test-database checks.

It compares baseline, Stage A only, and combined candidate using actual models/views/serializers, two warmups, randomized variant order, and raw trials. Time includes APIClient request handling and JSON parsing, **not TCP**. SQL capture, model-construction counts, Python allocation probes, and EXPLAIN ANALYZE are separate from timings. Payload hashes must match.

Record source commits/hashes, dependency/database versions, workload, warmup policy, trials, median, IQR, and raw observations. Stage A should eliminate full-population count-only hydration. Stage B should eliminate the second raw-page hydration on the app projection path. Neither automatically reduces the number of SQL statements.

**Additional measurements still to implement/run:** per-process peak RSS using isolated workers and a controlled concurrent-read workload; representative distinct/annotation-heavy query plans; optional separately reported TCP timings; and actual replica routing/lag behavior if claiming support for those deployments. Do not infer production savings from `tracemalloc` or call a loop-based synthetic orchestration test a database benchmark.

The harness may need environmental or fixture corrections when first run. Keep those corrections separate from the production proposal and rerun baseline/candidate fairly. Do not replace failed response-equivalence assertions with weaker checks.

## 7. Report and update this fork draft only

Before committing, verify `origin`'s push URL and the current branch. Review every changed path and sanitize evidence. Do not publish credentials, real user payloads, database URLs, tokens, personal paths, or production SQL parameters. Use the user's existing verified Git identity; do not invent a sign-off, co-author, or approval.

Keep the runtime proposal and evidence changes clear in separate commits where practical. Stage only reviewed files. Existing historical evidence is a record of earlier offline execution, not a claim that it was rerun after later changes. Put new results in new files and update the verification table with exact commands and outcomes.

```sh
git diff --check
git status --short
# Stage reviewed runtime/test/doc files explicitly, then:
git diff --cached --check
git diff --cached --stat
git commit -m "test: validate pagination candidate and record fork-only evidence"
git push origin HEAD:refs/heads/perf/pagination-count-evaluation

gh pr list --repo GODOSTROYER/plane \
  --head perf/pagination-count-evaluation --state all
```

Do not force-push, merge, close the other fork draft, or create an upstream PR. If the remote branch advanced, inspect the changes and coordinate rather than overwrite. Update the existing fork draft's body only after identifying its number from the command above. Keep it draft until real integration/performance evidence and human review justify readiness.

Report the fork PR URL, validated head SHA, exact diff, passed checks, failures, and unexecuted checks. Compare Stage B with fork PR #2 only in separate local worktrees; do not combine incompatible metadata strategies. Ask the user for a separate instruction before any official-repository publication or merge.

## Cleanup and final status

Stop only this task's uniquely named Compose projects. Remove volumes only for those explicitly disposable test projects. Leave existing Plane services/data/branches untouched. Preserve logs and handoff outputs. Do not delete a worktree with uncommitted changes.

A truthful final result may be “draft PR created, database checks pending” if execution is blocked. It may not be “end-to-end verified” unless those real tests and checks ran successfully.
