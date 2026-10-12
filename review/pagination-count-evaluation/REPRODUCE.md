# Reproduce the current validation

Use a disposable checkout of this evidence revision. Application files are already applied. Requirements: Docker with Linux containers, Git and Python 3. Commands use Bash at the repository root. Do not share the test database with concurrent pytest runs.

```sh
export KIT="$PWD/review/pagination-count-evaluation"
export OUT="$PWD/pagination-validation-output"
mkdir -p "$OUT"
# Only in a fresh checkout without an existing local .env:
cp apps/api/.env.example apps/api/.env
python - <<'PY'
from pathlib import Path
import secrets
with Path('apps/api/.env').open('a') as f:
    f.write('\nSECRET_KEY=' + secrets.token_urlsafe(48) + '\n')
PY
docker compose -p plane-pagination-review -f docker-compose-test.yml run --rm --build \
  -v "$OUT:/verification-output" api-tests pytest plane/tests --nomigrations \
  -o addopts='' -q --junitxml=/verification-output/full-backend.xml
```

Expected full result: 810 tests pass. For the focused collection, replace `plane/tests` with these four paths (115 cases):

```text
plane/tests/unit/utils/test_paginator.py
plane/tests/unit/utils/test_paginator_evaluation.py
plane/tests/contract/test_paginator_evaluation.py
plane/tests/contract/api/test_work_item_pagination_evaluation.py
```

Run checks using the exact script copied out of the archive:

```sh
python - <<'PY'
import os, zipfile
from pathlib import Path
with zipfile.ZipFile(Path(os.environ['KIT'])/'evidence/linux-20261013/linux-validation.zip') as z:
    Path(os.environ['OUT'],'checks.sh').write_bytes(z.read('run/checks.sh'))
PY
docker compose -p plane-pagination-review -f docker-compose-test.yml run --rm \
  -v "$OUT:/verification-output" --entrypoint /bin/sh api-tests /verification-output/checks.sh
```

The script checks Ruff on five files, formatting on four full files plus the changed view range, Django system checks and migration drift. It leaves unrelated existing formatting/import issues untouched. The entrypoint override does not install test requirements, so its dependency freeze describes the base check image; the archive also contains a separate full test dependency freeze.

## Reproduce the callback finding

Export pinned sources, without replacing the checkout:

```sh
git show 7466675e471efe1c96b122615f7a0d30c9b2eb05:apps/api/plane/utils/paginator.py > "$OUT/baseline-paginator.py"
git show dfebab8fa3bbb4be9bcda9703797e762d106332b:apps/api/plane/utils/paginator.py > "$OUT/submitted-paginator.py"
for variant in submitted baseline; do
  docker compose -p plane-pagination-review -f docker-compose-test.yml run --rm \
    -v "$OUT:/verification-output" \
    -v "$OUT/$variant-paginator.py:/code/plane/utils/paginator.py:ro" api-tests \
    pytest plane/tests/contract/test_paginator_evaluation.py \
    -k 'lazy_wrapped or deferred_model' --nomigrations -o addopts='' -vv \
    --junitxml="/verification-output/$variant-wrappers.xml"
done
```

Expected: submitted exits 1 with five assertion failures; baseline exits 0 with five passes. Revised code passes those five in the normal focused/full runs. Rendering is inside SQL capture. This isolates the paginator finding, not a full baseline rerun.

## Current benchmark

```sh
docker compose -p plane-pagination-review -f docker-compose-test.yml run --rm \
  -v "$OUT:/verification-output" \
  -v "$KIT/tools/test_query_shapes.py:/code/plane/tests/test_query_shapes.py:ro" \
  -e PLANE_RUN_PAGINATION_BENCHMARK=1 \
  -e PLANE_PAGINATION_BASELINE_FILE=/verification-output/baseline-paginator.py \
  -e PLANE_PAGINATION_SUBMITTED_FILE=/verification-output/submitted-paginator.py \
  -e PLANE_BENCH_ROWS=1000 -e PLANE_BENCH_BODY_BYTES=4096 -e PLANE_BENCH_TRIALS=10 \
  -e PLANE_BENCH_OUTPUT=/verification-output/query-shapes.json api-tests \
  pytest plane/tests/test_query_shapes.py --nomigrations -o addopts='' -q -s
```

This one pytest case executes 14 scenarios, each with baseline, Stage A only, submitted automatic Stage B and revised opt-in variants. Old variants strip only the new keyword from the current call site; their original paginator methods/defaults remain intact. The matrix deliberately requires 1,000 rows because offsets and expected filters are specified for that population. All timing/probe/fixture limits are documented in BENCHMARKS.md and the executable harness. Public authentication uses a random synthetic token; its throttle bucket is reset outside timings. App authentication is forced and recent-visit dispatch is mocked. DEBUG=False. The timer includes response parsing and assertions. It excludes SQL capture, allocation tracing and EXPLAIN.

## Adjacent PR compatibility

The archive includes the exact #9948 test file and the locally combined paginator source. Bind them over `plane/tests/unit/utils/test_paginator.py` and `plane/utils/paginator.py`, then run the four focused paths above. Expected: 126 cases. The archive's preparation script records the three source replacements and verifies the adjacent test Git blob. This is not a full combined-backend run or authority to include #9948 in the patch.

## Cleanup

```sh
docker compose -p plane-pagination-review -f docker-compose-test.yml down -v
```

Remove only this named disposable stack. Preserve output. Docker may create an empty host file at a new bind-mount test path; remove it only after verifying it is empty and untracked. Never reuse a production environment or database.
