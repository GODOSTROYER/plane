#!/usr/bin/env python3
"""Read-only local benchmark for Plane's project-list expansion loading strategies.

Run from apps/api in the configured Plane environment, using disposable/local
seeded data. This measures page materialization, serialization and JSON encoding;
it deliberately does NOT measure HTTP auth, middleware, pagination counts or
network transport. It is not a substitute for full endpoint benchmarks.

The legacy loading plan is the one inspected at:
7466675e471efe1c96b122615f7a0d30c9b2eb05 (project_lead joined, membership prefetched).
No database writes or HTTP requests are performed by this script.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import ExitStack, contextmanager
import gc
import hashlib
import json
import math
import os
import platform
from pathlib import Path
import random
import statistics
import subprocess
import sys
import time
import tracemalloc
from unittest import mock
from uuid import UUID


USER_FIELDS = {"created_by", "updated_by", "project_lead", "default_assignee"}
STRATEGIES = ("legacy", "users_only", "users_and_avatars", "batched_prefetch")


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, help="Slug of a disposable, seeded workspace.")
    parser.add_argument("--actor-id", required=True, type=UUID)
    parser.add_argument("--api-root", type=Path, default=Path.cwd())
    parser.add_argument("--database", choices=["default"], default="default",
                        help="Use the isolated primary; replica routing requires an HTTP request context.")
    parser.add_argument("--expand", default="created_by,updated_by")
    parser.add_argument("--sizes", default="10,50,100")
    parser.add_argument("--offset", default=0, type=int)
    parser.add_argument("--repeat", default=30, type=int)
    parser.add_argument("--warmup", default=3, type=int)
    parser.add_argument("--strategies", nargs="+", choices=STRATEGIES, default=STRATEGIES)
    parser.add_argument("--full-fields", action="store_true")
    parser.add_argument("--measure-memory", action="store_true", help="Separate tracemalloc trial; not timed.")
    parser.add_argument("--confirm-local-test-data", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.confirm_local_test_data:
        parser.error("Use only isolated local/test data and acknowledge with --confirm-local-test-data.")
    if not (args.api_root / "manage.py").is_file():
        parser.error("--api-root must be Plane's apps/api directory.")
    if not os.environ.get("DJANGO_SETTINGS_MODULE"):
        parser.error("Set DJANGO_SETTINGS_MODULE explicitly for your isolated Plane environment.")
    try:
        args.sizes = sorted(set(int(value) for value in args.sizes.split(",")))
    except ValueError:
        parser.error("--sizes must be comma-separated positive integers.")
    if not args.sizes or min(args.sizes) < 1 or max(args.sizes) > 1000:
        parser.error("Use page sizes between 1 and the inspected paginator's maximum of 1000.")
    if args.repeat < 2 or args.warmup < 0 or args.offset < 0:
        parser.error("repeat >= 2, warmup >= 0 and offset >= 0 are required.")
    args.expanded = sorted(set(value for value in args.expand.split(",") if value))
    if not args.expanded or not set(args.expanded) <= USER_FIELDS:
        parser.error("This benchmark supports only the four inspected user expansion fields.")
    return args


def main():
    args = arguments()
    sys.path.insert(0, str(args.api_root.resolve()))
    import django
    django.setup()

    from django.db import connections
    from django.conf import settings
    from django.db.models import Prefetch
    from rest_framework.renderers import JSONRenderer
    from rest_framework.test import APIRequestFactory
    from plane.api.views.project import ProjectListCreateAPIEndpoint
    from plane.db.models import User, Workspace, WorkspaceMember

    if args.database not in connections:
        raise ValueError(f"Unknown database alias: {args.database}")
    workspace = Workspace.objects.using(args.database).get(slug=args.workspace)
    actor = User.objects.using(args.database).get(pk=args.actor_id, is_active=True)
    if not WorkspaceMember.objects.using(args.database).filter(
        workspace=workspace, member=actor, is_active=True
    ).exists():
        raise ValueError("The benchmark actor must be an active workspace member.")
    params = {"expand": ",".join(args.expanded), "order_by": "name"}
    if not args.full_fields:
        params["fields"] = "id,name," + ",".join(args.expanded)
    def loading_plan(request_params):
        request = APIRequestFactory().get(f"/api/v1/workspaces/{workspace.slug}/projects/", request_params)
        request.user = actor
        view = ProjectListCreateAPIEndpoint()
        view.request = request
        view.kwargs = {"slug": workspace.slug}
        with mock.patch.object(view, "paginate", side_effect=lambda **kwargs: kwargs):
            return view.get(request, workspace.slug)

    plan = loading_plan(params)
    # An unexpanded GET retains the original membership prefetch, scoping and
    # annotations, without accidentally retaining the new expansion prefetches.
    legacy = loading_plan({key: value for key, value in params.items() if key != "expand"})["queryset"].using(args.database)
    available = legacy.count()
    if available < args.offset + max(args.sizes):
        raise ValueError(
            f"Only {available} projects are visible; need offset + largest size = "
            f"{args.offset + max(args.sizes)}. Seed data or lower --sizes."
        )

    def candidate(strategy):
        qs = legacy.all()  # Fresh result cache for EVERY trial.
        if strategy == "users_only":
            return qs.select_related(*args.expanded)
        if strategy == "users_and_avatars":
            return qs.select_related(*(field + "__avatar_asset" for field in args.expanded))
        if strategy == "batched_prefetch":
            lookups = []
            for field in args.expanded:
                if field == "project_lead":
                    # Already select_related by the legacy view. A parent Prefetch
                    # queryset could be skipped; explicitly prefetch its child.
                    lookups.append("project_lead__avatar_asset")
                else:
                    lookups.append(Prefetch(field, queryset=User._base_manager.select_related("avatar_asset")))
            return qs.prefetch_related(*lookups)
        return qs

    @contextmanager
    def capture_counts():
        counts = defaultdict(int)
        def record(execute, sql, params, many, context):
            counts[context["connection"].alias] += 1
            return execute(sql, params, many, context)
        with ExitStack() as stack:
            for alias in connections:
                stack.enter_context(connections[alias].execute_wrapper(record))
            yield counts

    def trial(strategy, size):
        qs = candidate(strategy)[args.offset:args.offset + size]
        start = time.perf_counter()
        with capture_counts() as counts:
            rows = list(qs)
            fetched = time.perf_counter()
            fetch_queries = sum(counts.values())
            data = plan["on_results"](rows)
            serialized = time.perf_counter()
            serialization_queries = sum(counts.values()) - fetch_queries
            encoded = JSONRenderer().render(data)
            done = time.perf_counter()
        if set(counts) != {args.database}:
            raise AssertionError(f"Unexpected database routing: {dict(counts)}")
        if len(rows) != size:
            raise RuntimeError("Data changed during the benchmark; retry on a stable, isolated dataset.")
        references = {
            field: sum(getattr(row, field + "_id") is not None for row in rows)
            for field in args.expanded
        }
        distinct_users = len({
            getattr(row, field + "_id")
            for row in rows for field in args.expanded
            if getattr(row, field + "_id") is not None
        })
        return {
            "strategy": strategy, "size": size,
            "fetch_ms": (fetched - start) * 1000,
            "serialization_ms": (serialized - fetched) * 1000,
            "encoding_ms": (done - serialized) * 1000,
            "total_ms": (done - start) * 1000,
            "fetch_queries": fetch_queries,
            "serialization_queries": serialization_queries,
            "queries_by_alias": dict(counts),
            "response_bytes": len(encoded),
            "sha256": hashlib.sha256(encoded).hexdigest(),
            "nonnull_references": references, "distinct_user_ids": distinct_users,
        }

    records = []
    memory = {}
    rng = random.Random(0)
    for size in args.sizes:
        for _ in range(args.warmup):
            for strategy in args.strategies:
                trial(strategy, size)
        expected_hash = None
        for _ in range(args.repeat):
            order = list(args.strategies)
            rng.shuffle(order)
            for strategy in order:
                record = trial(strategy, size)
                if expected_hash is None:
                    expected_hash = record["sha256"]
                if record["sha256"] != expected_hash:
                    raise AssertionError(
                        f"Response mismatch for {strategy}, size={size}; either semantics "
                        "changed or another process modified the benchmark data."
                    )
                records.append(record)
        if args.measure_memory:
            memory[str(size)] = {}
            for strategy in args.strategies:
                gc.collect()
                tracemalloc.start()
                trial(strategy, size)
                _, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
                memory[str(size)][strategy] = peak

    summaries = []
    for size in args.sizes:
        for strategy in args.strategies:
            rows = [row for row in records if row["size"] == size and row["strategy"] == strategy]
            times = sorted(row["total_ms"] for row in rows)
            summary = {
                "size": size, "strategy": strategy,
                "median_total_ms": statistics.median(times),
                "p95_total_ms_nearest_rank": times[math.ceil(0.95 * len(times)) - 1],
                "median_fetch_ms": statistics.median(row["fetch_ms"] for row in rows),
                "median_serialization_ms": statistics.median(row["serialization_ms"] for row in rows),
                "fetch_query_counts": sorted(set(row["fetch_queries"] for row in rows)),
                "serialization_query_counts": sorted(set(row["serialization_queries"] for row in rows)),
                "response_bytes": rows[0]["response_bytes"],
                "nonnull_references": rows[0]["nonnull_references"],
                "distinct_user_ids": rows[0]["distinct_user_ids"],
            }
            summaries.append(summary)
            print(json.dumps(summary))
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=args.api_root, text=True, capture_output=True, check=False
    ).stdout.strip()
    diff = subprocess.run(
        ["git", "diff", "HEAD", "--", "plane/api/views/project.py"],
        cwd=args.api_root, capture_output=True, check=True,
    ).stdout
    with connections[args.database].cursor() as cursor:
        cursor.execute("SELECT version()")
        postgres_version = cursor.fetchone()[0]
    result = {
        "scope": "Local ORM page fetch + serialization + JSON encoding; NOT end-to-end HTTP latency.",
        "source_commit": commit or "unknown", "django": django.get_version(),
        "production_diff_sha256": hashlib.sha256(diff).hexdigest(),
        "production_source_sha256": hashlib.sha256(
            (args.api_root / "plane/api/views/project.py").read_bytes()
        ).hexdigest(),
        "production_worktree_dirty": bool(diff), "debug": settings.DEBUG,
        "python": platform.python_version(), "platform": platform.platform(),
        "postgres": postgres_version,
        "database_vendor": connections[args.database].vendor,
        "database_alias": args.database, "request_parameters": params,
        "offset": args.offset, "repeat": args.repeat, "warmup": args.warmup,
        "summaries": summaries, "raw_trials": records,
        "separate_python_peak_traced_bytes": memory,
        "memory_caveat": "tracemalloc is Python allocations, not process RSS or database memory.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Benchmark failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
