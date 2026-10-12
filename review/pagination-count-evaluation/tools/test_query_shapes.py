# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Opt-in, synthetic PostgreSQL request-stack benchmark; never production.

Copy into plane/tests/ only in a disposable benchmark worktree, then run:
PLANE_RUN_PAGINATION_BENCHMARK=1 pytest plane/tests/test_query_shapes.py -s

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
from django.conf import settings
from django.core.cache import cache
from django.db import connections
from django.test import override_settings
import pytest
from rest_framework.test import APIClient

from plane.db.models import (
    Issue,
    IssueAssignee,
    IssueLabel,
    Label,
    Module,
    ModuleIssue,
    Project,
    ProjectMember,
    State,
    User,
    Workspace,
    WorkspaceMember,
)
from plane.db.models.api import APIToken
from plane.utils import paginator as live

pytestmark = [
    pytest.mark.django_db(databases="__all__"),
    pytest.mark.skipif(
        os.environ.get("PLANE_RUN_PAGINATION_BENCHMARK") != "1",
        reason="Opt-in synthetic benchmark",
    ),
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

    def invoke(self, *args, **kwargs):
        # Only the new internal opt-in is removed. Old implementations and
        # their original OffsetPaginator defaults otherwise run unchanged.
        kwargs.pop("count_page_in_database", None)
        return module.BasePaginator.paginate(self, *args, **kwargs)

    return invoke


def quantile(values, fraction):
    values = sorted(values)
    index = (len(values) - 1) * fraction
    low = int(index)
    high = min(low + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (index - low)


@override_settings(DEBUG=False)
def test_pagination_request_stack_benchmark():
    count = int(os.environ.get("PLANE_BENCH_ROWS", "1000"))
    body_bytes = int(os.environ.get("PLANE_BENCH_BODY_BYTES", "4096"))
    trials = int(os.environ.get("PLANE_BENCH_TRIALS", "10"))
    assert 0 <= count <= 100_000
    assert 0 <= body_bytes <= 65_536
    assert 5 <= trials <= 100
    assert connections["default"].vendor == "postgresql"
    database_name = str(connections["default"].settings_dict["NAME"])
    assert "test" in database_name.lower(), (
        "Refusing to benchmark outside a pytest test database"
    )
    baseline_path = Path(os.environ["PLANE_PAGINATION_BASELINE_FILE"])
    baseline = baseline_path.read_text()
    original_expression = "        total_count = self.total_count_queryset.count() if self.total_count_queryset else queryset.count()"
    assert baseline.count(original_expression) == 1, (
        "Baseline must contain the reviewed original defect"
    )
    count_only = baseline.replace(
        original_expression,
        "        count_queryset = self.total_count_queryset if self.total_count_queryset is not None else queryset\n"
        "        total_count = count_queryset.count()",
    )
    variants = {
        "baseline": load_variant("benchmark_baseline", baseline),
        "count_only": load_variant("benchmark_count_only", count_only),
        "submitted": load_variant(
            "benchmark_submitted",
            Path(os.environ["PLANE_PAGINATION_SUBMITTED_FILE"]).read_text(),
        ),
        "candidate": live.BasePaginator.paginate,
    }
    token = uuid4().hex
    actor = User.objects.create(
        email=f"bench-{token}@example.test", username=f"bench-{token}"
    )
    workspace = Workspace.objects.create(
        name="Pagination benchmark", slug=f"bench-{token}", owner=actor
    )
    WorkspaceMember.objects.create(
        workspace=workspace, member=actor, role=20, is_active=True
    )
    project = Project.objects.create(
        workspace=workspace, name="Benchmark", identifier="BM"
    )
    ProjectMember.objects.create(project=project, member=actor, role=20, is_active=True)
    state = State.objects.create(
        workspace=workspace, project=project, name="Todo", group="backlog", default=True
    )
    rng = random.Random(20261006)
    body = "".join(rng.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=body_bytes))
    for start in range(0, count, 250):
        Issue.objects.bulk_create(
            [
                Issue(
                    workspace=workspace,
                    project=project,
                    state=state,
                    name=f"Work item {index:07}",
                    sequence_id=index + 1,
                    created_by=actor,
                    updated_by=actor,
                    priority="high" if index % 5 == 0 else "low",
                    description_html=f"<p>{body}</p>",
                    description_json={"text": body},
                    description_stripped=body,
                    description_binary=body.encode(),
                )
                for index in range(start, min(start + 250, count))
            ],
            batch_size=250,
        )
    related_user = User.objects.create(
        email=f"related-{token}@example.test", username=f"related-{token}"
    )
    ProjectMember.objects.create(
        workspace=workspace,
        project=project,
        member=related_user,
        role=20,
        is_active=True,
    )
    labels = [
        Label.objects.create(workspace=workspace, project=project, name=f"Label {i}")
        for i in range(2)
    ]
    module = Module.objects.create(
        workspace=workspace, project=project, name="Benchmark module"
    )
    issue_rows = list(Issue.objects.filter(project=project).order_by("sequence_id"))
    IssueLabel.objects.bulk_create(
        [
            IssueLabel(
                workspace=workspace, project=project, issue=row, label=labels[i % 2]
            )
            for i, row in enumerate(issue_rows)
        ]
    )
    IssueAssignee.objects.bulk_create(
        [
            IssueAssignee(
                workspace=workspace,
                project=project,
                issue=row,
                assignee=actor if i % 2 == 0 else related_user,
            )
            for i, row in enumerate(issue_rows)
        ]
    )
    ModuleIssue.objects.bulk_create(
        [
            ModuleIssue(workspace=workspace, project=project, issue=row, module=module)
            for row in issue_rows
        ]
    )
    with connections["default"].cursor() as cursor:
        cursor.execute(
            "ANALYZE " + connections["default"].ops.quote_name(Issue._meta.db_table)
        )
        cursor.execute("SELECT version()")
        postgres = cursor.fetchone()[0]
    api_token = APIToken.objects.create(
        user=actor, token=uuid4().hex, label="Synthetic pagination benchmark"
    )
    public_client, app_client = APIClient(), APIClient()
    public_client.credentials(HTTP_X_API_KEY=api_token.token)
    app_client.force_authenticate(user=actor)
    result = {
        "scope": "Synthetic APIClient.get + JSON parsing; no TCP or production traffic",
        "seed": 20261006,
        "rows": count,
        "body_bytes_per_representation": body_bytes,
        "trials": trials,
        "python": platform.python_version(),
        "relationship_rows_per_kind": count,
        "django": django.get_version(),
        "postgresql": postgres,
        "debug": settings.DEBUG,
        "sql_capture_during_timings": False,
        "api_key_throttle_history_reset_before_public_requests": True,
        "baseline_sha256": hashlib.sha256(baseline.encode()).hexdigest(),
        "candidate_sha256": hashlib.sha256(
            Path(live.__file__).read_bytes()
        ).hexdigest(),
        "cases": {},
    }
    with mock.patch("plane.app.views.issue.base.recent_visited_task.delay"):
        scenarios = [
            ("default-first", None, 20, 0, False),
            ("sequence-control", "sequence_id", 20, 0, False),
            ("default-middle", None, 20, 25, False),
            ("default-last", None, 20, 49, False),
            ("default-beyond", None, 20, 50, False),
            ("default-large", None, 100, 3, False),
            ("priority-large", "priority", 100, 0, False),
            ("filtered-related", None, 20, 2, True),
        ]
        assert count == 1000, (
            "This bounded matrix's offsets are specified for 1000 rows"
        )
        for surface, client, scenario in [
            (s, c, case)
            for s, c in (("public", public_client), ("app", app_client))
            # Public priority ordering has no deterministic tie-breaker.
            for case in scenarios
            if not (s == "public" and (case[4] or case[0] == "priority-large"))
        ]:
            case_name, ordering, page_size, page, filtered = scenario
            print(f"Starting {surface}/{case_name}", flush=True)
            url = f"/api{'/v1' if surface == 'public' else ''}/workspaces/{workspace.slug}/projects/{project.pk}/issues/"
            params = {"per_page": page_size, "cursor": f"{page_size}:{page}:0"}
            if ordering is not None:
                params["order_by"] = ordering
            if surface == "public":
                params["fields"] = "id,name"
            rows = issue_rows
            if filtered:
                params.update(
                    priority="high", labels=str(labels[0].pk), assignees=str(actor.pk)
                )
                rows = [row for i, row in enumerate(rows) if i % 10 == 0]
            expected_total = len(rows)
            if ordering == "sequence_id":
                ordered = rows
            elif ordering == "priority":
                # Existing app mapping passes -priority_order to OffsetPaginator;
                # preserve that behavior (low before high), then newest first.
                ordered = sorted(
                    rows,
                    key=lambda row: (
                        0 if row.priority == "low" else 1,
                        -row.created_at.timestamp(),
                    ),
                )
            else:
                ordered = sorted(rows, key=lambda row: row.created_at, reverse=True)
            expected_page = ordered[page * page_size : (page + 1) * page_size]
            expected_ids = [str(row.pk) for row in expected_page]

            def call():
                response = client.get(url, params)
                data = response.json()
                assert response.status_code == 200, data
                assert data["count"] == len(expected_ids)
                assert data["total_count"] == data["total_results"] == expected_total
                assert [str(row["id"]) for row in data["results"]] == expected_ids, (
                    surface,
                    case_name,
                )
                assert data["next_page_results"] is (
                    expected_total > (page + 1) * page_size
                )
                assert data["prev_page_results"] is (page > 0)
                if surface == "app":
                    for row in data["results"]:
                        assert (
                            len(row["label_ids"])
                            == len(row["assignee_ids"])
                            == len(row["module_ids"])
                            == 1
                        )
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
                payload_hashes[name].add(
                    hashlib.sha256(
                        json.dumps(data, sort_keys=True).encode()
                    ).hexdigest()
                )
            assert len(set.union(*payload_hashes.values())) == 1, (
                "A/B response payloads differ"
            )
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
                    with (
                        capture_sql() as sql,
                        mock.patch.object(
                            Issue, "from_db", wraps=Issue.from_db
                        ) as hydrate,
                    ):
                        call()
                    plans = []
                    for alias, statement, parameters in sql:
                        table = connections[alias].ops.quote_name(Issue._meta.db_table)
                        if (
                            statement.lstrip().upper().startswith("SELECT")
                            and f"FROM {table}" in statement
                        ):
                            with connections[alias].cursor() as cursor:
                                cursor.execute(
                                    "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) "
                                    + statement,
                                    parameters,
                                )
                                plans.append(cursor.fetchone()[0])
                    values = timings[name]
                    surface_result[name] = {
                        "raw_ms": values,
                        "median_ms": statistics.median(values),
                        "iqr_ms": quantile(values, 0.75) - quantile(values, 0.25),
                        "p95_ms": quantile(values, 0.95),
                        "python_peak_bytes_one_separate_probe": peak,
                        "issue_models_constructed_separate_probe": hydrate.call_count,
                        "sql_count_separate_probe": len(sql),
                        "parameterized_sql_no_credentials": [
                            {"alias": alias, "sql": statement}
                            for alias, statement, _ in sql
                        ],
                        "issue_select_plans": plans,
                        "payload_sha256": next(iter(payload_hashes[name])),
                    }
            result["cases"][surface + "/" + case_name] = {
                "surface": surface,
                "request": params,
                "matching_count": expected_total,
                "returned_count": len(expected_ids),
                "variants": surface_result,
            }
            print(f"Completed {surface}/{case_name}", flush=True)
    output = Path(
        os.environ.get("PLANE_BENCH_OUTPUT", "/tmp/plane-pagination-benchmark.json")
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, default=str) + "\n")
    print(f"Synthetic benchmark saved to {output}")
