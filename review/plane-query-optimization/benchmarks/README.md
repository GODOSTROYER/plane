# Running the published benchmark harnesses

These are review-only tools, not part of the proposed upstream application change.
Run them only against an owned, isolated test environment and disposable checkout.
The pytest harnesses create synthetic database rows, refresh table statistics, reset
one test token's throttle history, and write JSON output. The standalone
`benchmark_project_expansion.py` is read-only and requires existing seeded data.

## Check packet packaging without Django or services

From the repository root:

```sh
python -m unittest discover -s review/plane-query-optimization/checks -p 'test_*.py' -v
```

These five checks validate benchmark import paths, Python syntax, the PR table,
and metadata terminology. They do not execute Plane's regression suite, benchmark
queries, or an archive privacy scan.

## Run database-backed checks

First configure the checkout's existing API test environment and isolated services
using the repository test documentation. Use its pinned dependencies. Run commands
from `apps/api`, with the intended `DJANGO_SETTINGS_MODULE` explicitly configured.
Do not point these commands at production. The relative paths below refer to the
host checkout; the default API test container does not mount the review packet.

```sh
# The 32 application regression cases.
python -m pytest plane/tests/contract/api/test_project_list_expansion_queries.py --reuse-db --nomigrations -q

# Refreshed-statistics join-versus-prefetch comparison; four fixture distributions.
python -m pytest ../../review/plane-query-optimization/benchmarks/test_refined_benchmark.py -c pytest.ini --reuse-db --nomigrations -q -s -p no:cacheprovider -o addopts=''

# Three final APIClient A/B scenarios and one TCP smoke test.
python -m pytest ../../review/plane-query-optimization/benchmarks/test_final_endpoint.py -c pytest.ini --reuse-db --nomigrations -q -s -p no:cacheprovider -o addopts=''
```

`test_benchmark_local.py` is the optional five-dataset exploratory comparison;
invoke it in the same way as `test_refined_benchmark.py`. Both now resolve
`benchmark_project_expansion.py` beside their own file, not through the original
local `tools/` layout. They should be run individually, without concurrent test or
benchmark activity on the services.

## Outputs and interpretation

The harnesses write generated JSON in `review/plane-query-optimization/` and may
overwrite prior generated files of the same name. They do not update the ZIP or
its checksum manifests. Review and sanitize new output before publishing it.
Keep archived evidence immutable; new scripts do not retroactively validate old
runs. A service/configuration/import error is not a reproduced N+1 failure.

The exploratory/refined strategy benchmark captures SQL during timing; do not mix
those samples with the uninstrumented final APIClient measurements. The final
harness measures `APIClient.get` plus JSON parsing, not TCP latency. Its separate
socket test is correctness coverage, not a timed benchmark.

The `api_key:<token>` eviction clears rate-limit history. It does not flush an
authentication cache or PostgreSQL buffers. New metadata calls it
`api_key_throttle_history_reset_per_request`; the historical ZIP's old
`cold_api_token_cache_per_request` label is corrected in
[QUERY_ACCOUNTING.md](../reports/QUERY_ACCOUNTING.md).

Local Docker success is not a hosted CI run. Actions can run on a fork if its
workflow triggers, branch filters and permissions allow. This correction enables
no workflows and requests no upstream review.
