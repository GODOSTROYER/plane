"""Repeat the contenders after refreshing disposable fixture statistics."""

import importlib.util
import json
import sys
from pathlib import Path
from unittest import mock

import pytest
from django.db import connection
from django.test import override_settings

from plane.db.models import Cycle, DeployBoard, FileAsset, Module, Project, ProjectMember, User, Workspace
from plane.tests.contract.api.test_project_list_expansion_queries import capture_list_plan, make_expansion_project

pytest_plugins = ["plane.tests.conftest"]
EVIDENCE = Path(__file__).resolve().parents[1]


@pytest.mark.django_db
@pytest.mark.parametrize("distribution", ["distinct", "shared", "url_only", "null"])
def test_refined_comparison(distribution, workspace, create_user, make_expansion_project):
    count = 500 if distribution in {"distinct", "shared"} else 100
    shared = None
    for index in range(count):
        project, users = make_expansion_project(
            users=shared if distribution == "shared" else None,
            with_avatars=distribution != "url_only",
        )
        if distribution == "shared":
            shared = users
        update = {"name": f"Benchmark {index:04d}"}
        if distribution == "null":
            update.update(created_by=None, updated_by=None)
        Project.objects.filter(pk=project.pk).update(**update)
    models = (Project, ProjectMember, User, FileAsset, Cycle, Module, Workspace, DeployBoard)
    tables = ", ".join(connection.ops.quote_name(model._meta.db_table) for model in models)
    with connection.cursor() as cursor:
        cursor.execute(f"ANALYZE {tables}")
    print(f"Refined {distribution}: seeded {count} rows and refreshed statistics", flush=True)

    spec = importlib.util.spec_from_file_location("refined_benchmark", Path(__file__).resolve().with_name("benchmark_project_expansion.py"))
    benchmark = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(benchmark)
    output = EVIDENCE / f"refined-{distribution}.json"
    args = [
        "benchmark", "--workspace", workspace.slug, "--actor-id", str(create_user.pk),
        "--sizes", "10,100,500" if count == 500 else "10,100", "--repeat", "20", "--warmup", "2",
        "--strategies", "users_and_avatars", "batched_prefetch", "--measure-memory",
        "--confirm-local-test-data", "--output", str(output),
    ]
    with override_settings(DEBUG=False), mock.patch.object(sys, "argv", args):
        benchmark.main()
    data = json.loads(output.read_text())
    data["statistics_refreshed_on_seeded_rows"] = True
    data["workspace_size"] = count
    output.write_text(json.dumps(data, indent=2))

    plan = capture_list_plan(workspace, create_user, {
        "fields": "id,name,created_by,updated_by", "expand": "created_by,updated_by", "order_by": "name",
    })
    legacy = capture_list_plan(workspace, create_user, {
        "fields": "id,name,created_by,updated_by", "order_by": "name",
    })["queryset"]
    joined = legacy.select_related("created_by__avatar_asset", "updated_by__avatar_asset")
    plans = {
        name: json.loads(queryset[:100].explain(analyze=True, buffers=True, format="json"))
        for name, queryset in {"legacy_or_prefetch_main": legacy, "users_and_avatars": joined}.items()
    }
    (EVIDENCE / f"refined-explain-{distribution}.json").write_text(json.dumps(plans, indent=2))
