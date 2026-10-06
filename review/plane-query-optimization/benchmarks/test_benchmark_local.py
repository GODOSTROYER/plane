"""Disposable evidence harness; deliberately kept outside the upstream patch."""

import importlib.util
import json
import random
import statistics
import sys
import time
from pathlib import Path
from unittest import mock

import pytest
from django.core.cache import cache
from django.db import connection
from django.test import override_settings

from plane.api.views.project import ProjectListCreateAPIEndpoint
from plane.db.models import FileAsset, Project
from plane.tests.contract.api.test_project_list_expansion_queries import (
    capture_list_plan,
    capture_sql,
    make_expansion_project,
)

pytest_plugins = ["plane.tests.conftest"]
EVIDENCE = Path(__file__).resolve().parents[1]


@pytest.mark.django_db
@pytest.mark.parametrize("distribution", ["distinct", "shared", "url_only", "null", "covers"])
def test_benchmark(distribution, workspace, create_user, make_expansion_project, api_key_client):
    """Seed real rows, compare four read strategies, and roll back all fixtures."""
    count = 500 if distribution in {"distinct", "shared"} else 100
    shared_users = None
    for index in range(count):
        project, users = make_expansion_project(
            users=shared_users if distribution == "shared" else None,
            with_avatars=distribution != "url_only",
        )
        if distribution == "shared":
            shared_users = users
        Project.objects.filter(pk=project.pk).update(name=f"Benchmark {index:04d}")
        if distribution == "null":
            Project.objects.filter(pk=project.pk).update(created_by=None, updated_by=None)
        if distribution == "covers":
            asset = FileAsset.objects.create(
                asset=f"benchmark-cover/{index}.png", project=project, workspace=workspace,
                entity_type=FileAsset.EntityTypeContext.PROJECT_COVER, is_uploaded=True,
            )
            Project.objects.filter(pk=project.pk).update(cover_image_asset=asset)

    specification = importlib.util.spec_from_file_location("project_benchmark", EVIDENCE / "tools/benchmark_project_expansion.py")
    benchmark = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(benchmark)
    arguments = [
        "benchmark_project_expansion.py", "--workspace", workspace.slug,
        "--actor-id", str(create_user.pk), "--sizes", "10,100,500" if count == 500 else "10,100",
        "--repeat", "20", "--warmup", "2", "--measure-memory", "--confirm-local-test-data",
        "--output", str(EVIDENCE / f"benchmark-{distribution}.json"),
    ]
    if distribution == "covers":
        arguments.append("--full-fields")
    with override_settings(DEBUG=False), mock.patch.object(sys, "argv", arguments):
        benchmark.main()

    params = {"fields": "id,name,created_by,updated_by", "expand": "created_by,updated_by", "order_by": "name"}
    plan = capture_list_plan(workspace, create_user, params)
    legacy = capture_list_plan(workspace, create_user, {
        key: value for key, value in params.items() if key != "expand"
    })["queryset"]
    plans = {}
    for strategy, queryset in {
        "legacy": legacy,
        "users_only": legacy.select_related("created_by", "updated_by"),
        "users_and_avatars": legacy.select_related("created_by__avatar_asset", "updated_by__avatar_asset"),
    }.items():
        plans[strategy] = json.loads(queryset[:100].explain(analyze=True, buffers=True, format="json"))
    (EVIDENCE / f"explain-{distribution}.json").write_text(json.dumps(plans, indent=2))

    # The complete HTTP stack runs via Django's API client (no TCP). Reconstruct
    # only the legacy loading paths at the paginator boundary for A/B comparison.
    original_paginate = ProjectListCreateAPIEndpoint.paginate
    def legacy_paginate(view, *args, **kwargs):
        queryset = kwargs["queryset"]
        membership = [lookup for lookup in queryset._prefetch_related_lookups
                      if getattr(lookup, "prefetch_to", lookup) == "project_projectmember"]
        kwargs["queryset"] = queryset.select_related(None).select_related("project_lead").prefetch_related(None).prefetch_related(*membership)
        return original_paginate(view, *args, **kwargs)

    endpoint_trials = []
    url = f"/api/v1/workspaces/{workspace.slug}/projects/"
    expected = None
    variants = ["legacy", "optimized"] * 10
    random.Random(0).shuffle(variants)
    with override_settings(DEBUG=False):
        for variant in variants:
            # Isolate only this disposable token's rate-limit history, outside timing.
            cache.delete("api_key:test-api-token-12345")
            handler = legacy_paginate if variant == "legacy" else original_paginate
            with mock.patch.object(ProjectListCreateAPIEndpoint, "paginate", handler):
                start = time.perf_counter()
                with capture_sql() as queries:
                    response = api_key_client.get(url, {**params, "per_page": 100})
                    payload = response.json()
                duration = (time.perf_counter() - start) * 1000
            assert response.status_code == 200, payload
            if expected is None:
                expected = payload
            assert payload == expected
            assert len(payload["results"]) == 100
            endpoint_trials.append({"variant": variant, "queries": len(queries), "milliseconds": duration})
    summary = {
        variant: {
            "median_ms": statistics.median(t["milliseconds"] for t in endpoint_trials if t["variant"] == variant),
            "query_counts": sorted({t["queries"] for t in endpoint_trials if t["variant"] == variant}),
        } for variant in ("legacy", "optimized")
    }
    (EVIDENCE / f"http-stack-{distribution}.json").write_text(json.dumps({
        "scope": "Django HTTP stack via APIClient, no TCP; legacy joins reconstructed at pagination boundary",
        "debug": False, "page_size": 100, "workspace_size": count,
        "summary": summary, "trials": endpoint_trials,
    }, indent=2))
    print(distribution, summary)
