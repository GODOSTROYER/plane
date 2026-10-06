# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Opt-in, synthetic PostgreSQL request-stack benchmark; never production.

Copy into plane/tests/ only in a disposable benchmark worktree, then run:
PLANE_RUN_PAGINATION_BENCHMARK=1 pytest plane/tests/test_pagination_benchmark.py -s

PLANE_PAGINATION_BASELINE_FILE must point to paginator.py exported with
`git show <reviewed-base>:apps/api/plane/utils/paginator.py` from the REAL clone.
Output contains no credentials. Timings exclude SQL/hydration/tracemalloc probes.
"""

from contextlib import ExitStack, contextmanager
import gc
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import statistics
import time
import tracemalloc
import types
from unittest import mock
from uuid import uuid4

import django
from django.core.cache import cache
from django.db import connections
import pytest
from rest_framework.test import APIClient

from plane.db.models import Issue, Project, ProjectMember, State, User, Workspace, WorkspaceMember
from plane.db.models.api import APIToken
from plane.utils import paginator as live

pytestmark = [
    pytest.mark.django_db(databases="__all__"),
    pytest.mark.skipif(os.environ.get("PLANE_RUN_PAGINATION_BENCHMARK") != "1", reason="Opt-in synthetic benchmark"),
]


@contextmanager
def capture_sql():
    records = []

    def record(execute, sql, params, many, context):
        records.append((context["connection"].alias, sql, params))
        return execute(sql, params, many, context)

    with ExitStack() as stack:
        for alias in connections:
            stack.enter_context(connections[alias].execute_wrapper(record))
        yield records


def load_variant(name, source):
    module = types.ModuleType(name)
    exec(compile(source, f"<{name}>", "exec"), module.__dict__)
    return module.BasePaginator.paginate


def quantile(values, fraction):
    values = sorted(values)
    index = (len(values) - 1) * fraction
    low = int(index)
    high = min(low + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (index - low)


def test_pagination_request_stack_benchmark():
    count = int(os.environ.get("PLANE_BENCH_ROWS", "1000"))
    body_bytes = int(os.environ.get("PLANE_BENCH_BODY_BYTES", "4096"))
    trials = int(os.environ.get("PLANE_BENCH_TRIALS", "20"))
    assert 0 <= count <= 100_000
    assert 0 <= body_bytes <= 65_536
    assert 5 <= trials <= 100
    assert connections["default"].vendor == "postgresql"
    database_name = str(connections["default"].settings_dict["NAME"])
    assert "test" in database_name.lower(), "Refusing to benchmark outside a pytest test database"
    baseline_path = Path(os.environ["PLANE_PAGINATION_BASELINE_FILE"])
    baseline = baseline_path.read_text()
    original_expression = "        total_count = self.total_count_queryset.count() if self.total_count_queryset else queryset.count()"
    assert baseline.count(original_expression) == 1, "Baseline must contain the reviewed original defect"
    count_only = baseline.replace(
        original_expression,
        "        count_queryset = self.total_count_queryset if self.total_count_queryset is not None else queryset\n"
        "        total_count = count_queryset.count()",
    )
    variants = {
        "baseline": load_variant("benchmark_baseline", baseline),
        "count_only": load_variant("benchmark_count_only", count_only),
        "candidate": live.BasePaginator.paginate,
    }
    token = uuid4().hex
    actor = User.objects.create(email=f"bench-{token}@example.test", username=f"bench-{token}")
    workspace = Workspace.objects.create(name="Pagination benchmark", slug=f"bench-{token}", owner=actor)
    WorkspaceMember.objects.create(workspace=workspace, member=actor, role=20, is_active=True)
    project = Project.objects.create(workspace=workspace, name="Benchmark", identifier="BM")
    ProjectMember.objects.create(project=project, member=actor, role=20, is_active=True)
    state = State.objects.create(workspace=workspace, project=project, name="Todo", group="backlog", default=True)
    rng = random.Random(20261006)
    body = "".join(rng.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=body_bytes))
    for start in range(0, count, 250):
        Issue.objects.bulk_create(
            [
                Issue(
                    workspace=workspace, project=project, state=state, name=f"Work item {index:07}",
                    sequence_id=index + 1, created_by=actor, updated_by=actor,
                    description_html=f"<p>{body}</p>", description_json={"text": body},
                    description_stripped=body, description_binary=body.encode(),
                )
                for index in range(start, min(start + 250, count))
            ],
            batch_size=250,
        )
    with connections["default"].cursor() as cursor:
        cursor.execute("ANALYZE " + connections["default"].ops.quote_name(Issue._meta.db_table))
        cursor.execute("SELECT version()")
        postgres = cursor.fetchone()[0]
    api_token = APIToken.objects.create(user=actor, token=uuid4().hex, label="Synthetic pagination benchmark")
    public_client, app_client = APIClient(), APIClient()
    public_client.credentials(HTTP_X_API_KEY=api_token.token)
    app_client.force_authenticate(user=actor)
    result = {
        "scope": "Synthetic APIClient.get + JSON parsing; no TCP or production traffic",
        "seed": 20261006, "rows": count, "body_bytes_per_representation": body_bytes,
        "page_size": 20, "trials": trials, "python": platform.python_version(),
        "django": django.get_version(), "postgresql": postgres,
        "baseline_sha256": hashlib.sha256(baseline.encode()).hexdigest(),
        "candidate_sha256": hashlib.sha256(Path(live.__file__).read_bytes()).hexdigest(),
        "surfaces": {},
    }
    with mock.patch("plane.app.views.issue.base.recent_visited_task.delay"):
        for surface, client in (("public", public_client), ("app", app_client)):
            url = f"/api{'/v1' if surface == 'public' else ''}/workspaces/{workspace.slug}/projects/{project.pk}/issues/"
            params = {"per_page": 20, "order_by": "name"}
            if surface == "public":
                params["fields"] = "id,name"

            def call():
                response = client.get(url, params)
                data = response.json()
                assert response.status_code == 200, data
                assert data["count"] == min(count, 20)
                assert data["total_count"] == count
                return data

            def prepare():
                # Delete only this synthetic token's bucket, outside timings.
                if surface == "public":
                    cache.delete(f"api_key:{api_token.token}")

            timings = {name: [] for name in variants}
            payload_hashes = {name: set() for name in variants}
            for name, function in variants.items():
                with mock.patch.object(live.BasePaginator, "paginate", function):
                    for _ in range(2):
                        prepare()
                        call()
            schedule = list(variants) * trials
            rng.shuffle(schedule)
            for name in schedule:
                gc.collect()
                prepare()
                with mock.patch.object(live.BasePaginator, "paginate", variants[name]):
                    start = time.perf_counter_ns()
                    data = call()
                    elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
                timings[name].append(elapsed_ms)
                payload_hashes[name].add(hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest())
            assert len(set.union(*payload_hashes.values())) == 1, "A/B response payloads differ"
            surface_result = {}
            for name, function in variants.items():
                with mock.patch.object(live.BasePaginator, "paginate", function):
                    gc.collect()
                    prepare()
                    tracemalloc.start()
                    try:
                        call()
                        _, peak = tracemalloc.get_traced_memory()
                    finally:
                        tracemalloc.stop()
                    prepare()
                    with capture_sql() as sql, mock.patch.object(Issue, "from_db", wraps=Issue.from_db) as hydrate:
                        call()
                    plans = []
                    for alias, statement, parameters in sql:
                        table = connections[alias].ops.quote_name(Issue._meta.db_table)
                        if statement.lstrip().upper().startswith("SELECT") and f"FROM {table}" in statement:
                            with connections[alias].cursor() as cursor:
                                cursor.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + statement, parameters)
                                plans.append(cursor.fetchone()[0])
                    values = timings[name]
                    surface_result[name] = {
                        "raw_ms": values, "median_ms": statistics.median(values),
                        "iqr_ms": quantile(values, 0.75) - quantile(values, 0.25),
                        "p95_ms": quantile(values, 0.95),
                        "python_peak_bytes_one_separate_probe": peak,
                        "issue_models_constructed_separate_probe": hydrate.call_count,
                        "sql_count_separate_probe": len(sql),
                        "parameterized_sql_no_credentials": [{"alias": alias, "sql": statement} for alias, statement, _ in sql],
                        "issue_select_plans": plans,
                        "payload_sha256": next(iter(payload_hashes[name])),
                    }
            result["surfaces"][surface] = surface_result
    output = Path(os.environ.get("PLANE_BENCH_OUTPUT", "/tmp/plane-pagination-benchmark.json"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, default=str) + "\n")
    print(f"Synthetic benchmark saved to {output}")
