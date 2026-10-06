"""Final implementation: full HTTP stack A/B measurements and a TCP smoke test."""

import hashlib
import json
import platform
import random
import statistics
import time
from pathlib import Path
from unittest import mock

import django
import pytest
import requests
from django.core.cache import cache
from django.db import connection
from django.test import override_settings
from plane.api.views.project import ProjectListCreateAPIEndpoint
from plane.db.models import (
    Cycle,
    DeployBoard,
    FileAsset,
    Module,
    Project,
    ProjectMember,
    User,
    Workspace,
)
from plane.tests.contract.api.test_project_list_expansion_queries import capture_sql

pytest_plugins = [
    "plane.tests.conftest",
    "plane.tests.contract.api.test_project_list_expansion_queries",
]
EVIDENCE = Path(__file__).resolve().parents[1]


@pytest.mark.django_db
@pytest.mark.parametrize("distribution", ["distinct", "shared", "null"])
def test_final_http_stack(
    distribution, workspace, create_user, make_expansion_project, api_key_client
):
    users = None
    for index in range(100):
        project, new_users = make_expansion_project(
            users=users if distribution == "shared" else None
        )
        users = new_users
        update = {"name": f"Benchmark {index:04d}"}
        if distribution == "null":
            update.update(created_by=None, updated_by=None)
        Project.objects.filter(pk=project.pk).update(**update)
    models = (
        Project,
        ProjectMember,
        User,
        FileAsset,
        Cycle,
        Module,
        Workspace,
        DeployBoard,
    )
    with connection.cursor() as cursor:
        cursor.execute(
            "ANALYZE "
            + ", ".join(
                connection.ops.quote_name(model._meta.db_table) for model in models
            )
        )

    original = ProjectListCreateAPIEndpoint.paginate

    def legacy_paginate(view, *args, **kwargs):
        queryset = kwargs["queryset"]
        membership = [
            lookup
            for lookup in queryset._prefetch_related_lookups
            if getattr(lookup, "prefetch_to", lookup) == "project_projectmember"
        ]
        kwargs["queryset"] = queryset.prefetch_related(None).prefetch_related(
            *membership
        )
        return original(view, *args, **kwargs)

    url = f"/api/v1/workspaces/{workspace.slug}/projects/"
    params = {
        "fields": "id,name,created_by,updated_by",
        "expand": "created_by,updated_by",
        "order_by": "name",
        "per_page": 100,
    }
    variants = ["legacy", "optimized"] * 20
    random.Random(0).shuffle(variants)
    results = []
    expected = None
    query_counts = {}
    captures = {}
    with override_settings(DEBUG=False):
        # Count SQL separately: execute wrappers must not affect latency samples.
        for variant in ("legacy", "optimized"):
            cache.delete("api_key:test-api-token-12345")
            handler = legacy_paginate if variant == "legacy" else original
            with (
                mock.patch.object(ProjectListCreateAPIEndpoint, "paginate", handler),
                capture_sql() as queries,
            ):
                response = api_key_client.get(url, params)
                payload = response.json()
            assert response.status_code == 200, payload
            assert len(payload["results"]) == 100
            if expected is None:
                expected = payload
            assert payload == expected
            assert {query["alias"] for query in queries} == {"default"}
            query_counts[variant] = len(queries)
            captures[variant] = queries
        for variant in ["legacy", "optimized"] * 2 + variants:
            cache.delete("api_key:test-api-token-12345")
            handler = legacy_paginate if variant == "legacy" else original
            with mock.patch.object(ProjectListCreateAPIEndpoint, "paginate", handler):
                started = time.perf_counter()
                response = api_key_client.get(url, params)
                payload = response.json()
                milliseconds = (time.perf_counter() - started) * 1000
            assert response.status_code == 200, payload
            assert len(payload["results"]) == 100
            assert payload == expected
            results.append({"variant": variant, "milliseconds": milliseconds})
    results = results[4:]
    summary = {}
    for variant in ("legacy", "optimized"):
        samples = [row["milliseconds"] for row in results if row["variant"] == variant]
        q1, _, q3 = statistics.quantiles(samples, n=4, method="inclusive")
        summary[variant] = {
            "median_ms": statistics.median(samples),
            "q1_ms": q1,
            "q3_ms": q3,
            "iqr_ms": q3 - q1,
            "minimum_ms": min(samples),
            "maximum_ms": max(samples),
            "query_count_separately_captured": query_counts[variant],
        }
    assert query_counts["legacy"] == (8 if distribution == "null" else 408)
    assert query_counts["optimized"] == (8 if distribution == "null" else 10)
    output = {
        "scope": "Full Django HTTP stack through APIClient, no TCP; only expansion prefetches removed for legacy comparison",
        "rows": 100,
        "workspace_rows": 100,
        "debug": False,
        "statistics_refreshed": True,
        "repeats_per_variant": 20,
        "warmup_per_variant": 2,
        "parameters": params,
        "python": platform.python_version(),
        "platform": platform.system(),
        "django": django.get_version(),
        "postgresql_version": connection.pg_version,
        "sql_capture_during_timing": False,
        "allocation_tracing_during_timing": False,
        "quantile_method": "statistics.quantiles(n=4, method='inclusive')",
        "clock_scope": "APIClient.get plus response.json; token-cache eviction outside clock",
        "cold_api_token_cache_per_request": True,
        "summary": summary,
        "trials": results,
        "production_source_sha256": hashlib.sha256(
            Path("plane/api/views/project.py").read_bytes()
        ).hexdigest(),
    }
    (EVIDENCE / f"final-http-uninstrumented-{distribution}.json").write_text(
        json.dumps(output, indent=2)
    )
    (EVIDENCE / f"final-sql-{distribution}.json").write_text(
        json.dumps(
            {
                "scope": "Separate untimed requests; parameterized SQL only, bound values omitted",
                "distribution": distribution,
                "query_counts": query_counts,
                "captures": captures,
                "production_source_sha256": output["production_source_sha256"],
            },
            indent=2,
        )
    )
    print(distribution, summary, flush=True)


@pytest.mark.django_db(transaction=True)
def test_socket_project_expansions(
    plane_server, workspace, make_expansion_project, api_token
):
    project, users = make_expansion_project()
    cache.delete("api_key:test-api-token-12345")
    response = requests.get(
        f"{plane_server.url}/api/v1/workspaces/{workspace.slug}/projects/",
        headers={"X-API-Key": api_token.token},
        params={
            "fields": "id,name,created_by,updated_by,project_lead,default_assignee",
            "expand": "created_by,updated_by,project_lead,default_assignee",
        },
        timeout=30,
    )
    assert response.status_code == 200, response.text
    rows = response.json()["results"]
    assert len(rows) == 1 and rows[0]["id"] == str(project.pk)
    for field, user in users.items():
        assert rows[0][field]["id"] == str(user.pk)
        assert (
            rows[0][field]["avatar_url"]
            == f"/api/assets/v2/static/{user.avatar_asset_id}/"
        )
    print("TCP HTTP 200: all four expanded users and avatar URLs correct", flush=True)
