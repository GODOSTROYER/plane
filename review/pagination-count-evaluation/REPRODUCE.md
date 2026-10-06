# Reproduce the real-stack validation

Use the application files already applied on this fork review branch. Do not reapply the historical patches. The new `VALIDATION.md` and dated Linux evidence describe the completed run; older offline records describe earlier work.

## Setup and application checks

Requirements: Git, Python 3, Docker with Linux containers, and sufficient local disk/memory. Commands below use Bash from the repository root. PowerShell users can use equivalent absolute bind mounts. Run the validation commands sequentially; do not share the same test database between simultaneous pytest processes.

```sh
export KIT="$PWD/review/pagination-count-evaluation"
export OUT="$PWD/pagination-validation-output"
mkdir -p "$OUT"
# Only in a fresh disposable checkout with no existing local environment:
cp apps/api/.env.example apps/api/.env
python - <<'PY'
from pathlib import Path
import secrets
with Path('apps/api/.env').open('a') as f:
    f.write('\nSECRET_KEY=' + secrets.token_urlsafe(48) + '\n')
PY

docker compose -p plane-pagination-review -f docker-compose-test.yml \
  run --rm --build -v "$OUT:/verification-output" api-tests \
  pytest plane/tests --nomigrations -o addopts='' -q \
  --junitxml=/verification-output/full-backend.xml

docker compose -p plane-pagination-review -f docker-compose-test.yml \
  run --rm --entrypoint /bin/sh api-tests -ec '
    python -m ruff check plane/utils/paginator.py plane/tests/unit/utils/test_paginator_evaluation.py plane/tests/contract/test_paginator_evaluation.py plane/tests/contract/api/test_work_item_pagination_evaluation.py
    python -m ruff format --check plane/utils/paginator.py plane/tests/unit/utils/test_paginator_evaluation.py plane/tests/contract/test_paginator_evaluation.py plane/tests/contract/api/test_work_item_pagination_evaluation.py
    python manage.py check
    python manage.py makemigrations --check --dry-run
  '
```

The focused command substitutes these four test paths for `plane/tests`:

```text
plane/tests/unit/utils/test_paginator.py
plane/tests/unit/utils/test_paginator_evaluation.py
plane/tests/contract/test_paginator_evaluation.py
plane/tests/contract/api/test_work_item_pagination_evaluation.py
```

Repository-wide read-only Ruff currently finds three pre-existing unused imports. The actual API workflow's `ruff check --fix apps/api` passes by correcting them; reproduce that command only in a disposable copy, since it writes to unrelated files. The dated evidence includes the exact checks script used for this comparison.

## Baseline regression verification

```sh
git worktree add --detach ../plane-pagination-base 7466675e471efe1c96b122615f7a0d30c9b2eb05
export BASE="$(cd ../plane-pagination-base && pwd)"
for path in \
  plane/tests/unit/utils/test_paginator_evaluation.py \
  plane/tests/contract/test_paginator_evaluation.py \
  plane/tests/contract/api/test_work_item_pagination_evaluation.py; do
  cp "apps/api/$path" "$BASE/apps/api/$path"
done

# This overrides /code in an ephemeral runner, preserving both worktrees.
# It reuses only this task's disposable services, after the candidate run exits.
docker compose -p plane-pagination-review -f docker-compose-test.yml \
  run --rm -v "$BASE/apps/api:/code" -v "$OUT:/verification-output" api-tests \
  pytest plane/tests --nomigrations -o addopts='' -q \
  --junitxml=/verification-output/baseline-full.xml
```

Expected baseline exit code is 1: 33 new regression failures and 767 passes, with no errors. All 700 pre-existing tests pass. Keep this result separate from successful candidate execution.

## Performance measurements

Export the complete, verified baseline source from Git:

```sh
python "$KIT/tools/export_baseline.py" --repo "$PWD" --output "$OUT/paginator-baseline.py"
```

Run the corrected benchmark in a disposable runner. Its bind-mounted test file is not added to the application source tree or upstream contribution. This command measures one workload; repeat `PLANE_BENCH_ROWS` at 100, 1000, and 10000, each with `PLANE_BENCH_BODY_BYTES` set to 0 and 4096, without concurrent test/benchmark activity.

```sh
docker compose -p plane-pagination-review -f docker-compose-test.yml \
  run --rm -v "$OUT:/verification-output" \
  -v "$KIT/tools/test_pagination_benchmark.py:/code/plane/tests/test_pagination_benchmark.py:ro" \
  -e PLANE_RUN_PAGINATION_BENCHMARK=1 \
  -e PLANE_PAGINATION_BASELINE_FILE=/verification-output/paginator-baseline.py \
  -e PLANE_BENCH_ROWS=1000 -e PLANE_BENCH_BODY_BYTES=4096 \
  -e PLANE_BENCH_TRIALS=20 \
  -e PLANE_BENCH_OUTPUT=/verification-output/benchmark-1000-4096.json \
  api-tests pytest plane/tests/test_pagination_benchmark.py \
  --nomigrations -o addopts='' -q -s
```

The harness refuses non-test databases and requires PostgreSQL. Each workload compares the baseline, the count-source-only fix, and the combined candidate. It uses two warmups per variant/surface followed by 20 randomized trials, `DEBUG=False`, and a fixed page size of 20. Public responses use sparse `id,name` fields; app responses use their ordinary projection. The app client is force-authenticated and recent-visit dispatch is mocked. Public authentication is real; its synthetic token's rate-limit history is reset before each request outside the timed section.

The timer includes APIClient request handling and JSON parsing. It excludes TCP, SQL capture, model-construction instrumentation, allocation tracing, and EXPLAIN ANALYZE, which have separate probes. Payload hashes must agree across all variants and trials. Raw timings, medians/IQR/p95, SQL, query plans, constructed-model counts, and a separate Python-allocation peak are recorded. These are local observations, not production forecasts or statistical significance claims.

## Cleanup

```sh
docker compose -p plane-pagination-review -f docker-compose-test.yml down -v
```

This removes only the named disposable stack. Retain the output and worktrees for review. Never run this against a production project or reuse a production environment file.
