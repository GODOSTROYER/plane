# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""PostgreSQL and routed request regressions for count-only model loading.

Unlike a query-count-only test, these also observe model construction and
queryset caches: a full SELECT followed by cached count() is still one query.
"""

from contextlib import ExitStack, contextmanager
from unittest import mock
from uuid import uuid4

import pytest
from django.db import connections
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory

from plane.app.views.issue.base import IssueViewSet
from plane.db.models import Issue, IssueLabel, Label, Project, ProjectMember, State, User, Workspace, WorkspaceMember
from plane.db.models.api import APIToken
from plane.utils.grouper import issue_on_results, issue_queryset_grouper
from plane.utils.paginator import BasePaginator, Cursor, OffsetPaginator

pytestmark = [pytest.mark.contract, pytest.mark.django_db(databases="__all__")]


@contextmanager
def capture_sql():
    """Capture all database aliases without forcing unused connections open."""
    statements = []

    def record(execute, sql, params, many, context):
        statements.append({"alias": context["connection"].alias, "sql": sql})
        return execute(sql, params, many, context)

    with ExitStack() as stack:
        for alias in connections:
            stack.enter_context(connections[alias].execute_wrapper(record))
        yield statements


@pytest.fixture
def pagination_data(workspace, create_user):
    """Persist wide issues outside measurement; use explicit fixture identities."""
    project = Project.objects.create(workspace=workspace, name="Pagination", identifier="PAG", network=0)
    ProjectMember.objects.create(project=project, workspace=workspace, member=create_user, role=20, is_active=True)
    state = State.objects.create(project=project, workspace=workspace, name="Todo", group="unstarted", default=True)
    # Bulk fixture construction deliberately bypasses Issue.save() sequence
    # allocation. These tests are read-only and set unique sequences explicitly.
    rows = Issue.objects.bulk_create([
        Issue(
            project=project,
            workspace=workspace,
            state=state,
            name=f"Pagination {i:03d}",
            sequence_id=i + 1,
            created_by=create_user,
            updated_by=create_user,
            priority="high" if i % 2 == 0 else "low",
            description_html="<p>" + "wide fixture " * 700 + "</p>",
            description_json={"text": "wide fixture " * 700},
            description_binary=b"x" * 8192,
        )
        for i in range(13)
    ])
    return project, rows


def querysets(project):
    """Use the app's actual annotation and scalar/array projection builders."""
    count_queryset = Issue.issue_objects.filter(project=project).using("default").distinct()
    rows = IssueViewSet().apply_annotations(count_queryset.all())
    rows = issue_queryset_grouper(rows, group_by=None, sub_group_by=None).order_by("sequence_id")
    return rows, count_queryset


@pytest.mark.parametrize("page_size", [1, 5, 13])
@pytest.mark.parametrize("kind", ["plain", "prefetched", "sliced", "empty", "none"])
def test_counting_never_hydrates_models(pagination_data, page_size, kind):
    project, _ = pagination_data
    rows, counts = querysets(project)
    expected = 13
    if kind == "prefetched":
        counts = counts.prefetch_related("labels")
    elif kind == "sliced":
        counts = counts.order_by("sequence_id")[:5]
        expected = 5
    elif kind == "empty":
        counts = counts.none()
        expected = 0
    elif kind == "none":
        counts = None

    with mock.patch.object(Issue, "from_db", wraps=Issue.from_db) as hydrated, capture_sql() as statements:
        result = OffsetPaginator(rows, total_count_queryset=counts).get_result(limit=page_size, cursor=Cursor(page_size))
    assert result.hits == expected
    assert hydrated.call_count == 0
    assert result.results._result_cache is None
    if counts is not None:
        assert counts._result_cache is None
    assert statements
    assert {item["alias"] for item in statements} == {"default"}
    assert all(item["sql"].lstrip().upper().startswith("SELECT COUNT(") for item in statements)


def test_previously_cached_count_remains_usable(pagination_data):
    project, _ = pagination_data
    rows, counts = querysets(project)
    list(counts)
    cached = counts._result_cache
    with mock.patch.object(Issue, "from_db", wraps=Issue.from_db) as hydrated:
        result = OffsetPaginator(rows, total_count_queryset=counts).get_result(limit=2)
    assert result.hits == len(cached) == 13
    assert counts._result_cache is cached
    assert hydrated.call_count == 0


@pytest.mark.parametrize("page", [0, 1, 2, 3, 8])
def test_projected_page_is_read_once_without_model_hydration(pagination_data, page):
    project, fixtures = pagination_data
    rows, counts = querysets(project)
    supplied = []

    def project_page(page_queryset):
        supplied.append(page_queryset)
        return issue_on_results(page_queryset, group_by=None, sub_group_by=None)

    request = APIRequestFactory().get("/pagination/", {"per_page": 5, "cursor": f"5:{page}:0"})
    with mock.patch.object(Issue, "from_db", wraps=Issue.from_db) as hydrated, capture_sql() as statements:
        response = BasePaginator().paginate(
            request=request, queryset=rows, total_count_queryset=counts, on_results=project_page
        )
    expected = fixtures[page * 5 : (page + 1) * 5]
    assert response.data["count"] == len(expected)
    assert response.data["total_count"] == response.data["total_results"] == 13
    assert [row["id"] for row in response.data["results"]] == [row.pk for row in expected]
    assert hydrated.call_count == 0
    assert counts._result_cache is None
    assert supplied[0]._result_cache is None
    non_counts = [item for item in statements if not item["sql"].lstrip().upper().startswith("SELECT COUNT(")]
    assert len(non_counts) == 1, statements
    assert "LIMIT 5" in non_counts[0]["sql"].upper()
    for row in response.data["results"]:
        assert row["label_ids"] == row["assignee_ids"] == row["module_ids"] == []


def test_join_duplicates_are_deduplicated_before_page_projection(pagination_data, workspace):
    project, fixtures = pagination_data
    labels = [Label.objects.create(project=project, workspace=workspace, name=f"L{i}") for i in range(2)]
    IssueLabel.objects.bulk_create([
        IssueLabel(project=project, workspace=workspace, issue=fixtures[0], label=label) for label in labels
    ])
    rows, counts = querysets(project)
    rows = rows.filter(labels__in=labels).distinct()
    counts = counts.filter(labels__in=labels).distinct()
    with mock.patch.object(Issue, "from_db", wraps=Issue.from_db) as hydrated:
        response = BasePaginator().paginate(
            request=APIRequestFactory().get("/pagination/", {"per_page": 5}),
            queryset=rows,
            total_count_queryset=counts,
            on_results=lambda page: issue_on_results(page, None, None),
        )
    assert response.data["count"] == response.data["total_count"] == 1
    assert response.data["results"][0]["id"] == fixtures[0].pk
    assert set(response.data["results"][0]["label_ids"]) == {label.pk for label in labels}
    assert hydrated.call_count == 0


def client_for(actor, surface):
    client = APIClient()
    if surface == "api":
        token = APIToken.objects.create(user=actor, label="Pagination regression", token=uuid4().hex)
        client.credentials(HTTP_X_API_KEY=token.token)
    else:
        # Session transport is outside this test; routing, permissions, queries,
        # pagination and JSON rendering all execute normally.
        client.force_authenticate(user=actor)
    return client


def list_url(workspace, project, surface):
    prefix = "/api/v1" if surface == "api" else "/api"
    suffix = "work-items" if surface == "api" else "issues"
    return f"{prefix}/workspaces/{workspace.slug}/projects/{project.pk}/{suffix}/"


@pytest.mark.parametrize("surface", ["api", "app"])
@pytest.mark.parametrize("size", [1, 5, 13])
def test_routed_list_hydrates_only_returned_models(pagination_data, workspace, create_user, surface, size):
    project, fixtures = pagination_data
    client = client_for(create_user, surface)
    params = {"per_page": size, "order_by": "sequence_id", "fields": "id,name"}
    url = list_url(workspace, project, surface)
    with mock.patch("plane.app.views.issue.base.recent_visited_task.delay"):
        warm = client.get(url, params)
        assert warm.status_code == 200, warm.data
        with mock.patch.object(Issue, "from_db", wraps=Issue.from_db) as hydrated:
            response = client.get(url, params)
            body = response.json()
    assert response.status_code == 200, body
    assert body["count"] == size
    assert body["total_count"] == body["total_results"] == 13
    assert [str(item["id"]) for item in body["results"]] == [str(row.pk) for row in fixtures[:size]]
    assert hydrated.call_count == (size if surface == "api" else 0)


@pytest.mark.parametrize("surface", ["api", "app"])
def test_routed_cursor_walk_and_previous_page(pagination_data, workspace, create_user, surface):
    project, fixtures = pagination_data
    client = client_for(create_user, surface)
    url = list_url(workspace, project, surface)
    params = {"per_page": 5, "order_by": "sequence_id", "fields": "id,name"}
    ids = []
    with mock.patch("plane.app.views.issue.base.recent_visited_task.delay"):
        for _ in range(3):
            response = client.get(url, params)
            assert response.status_code == 200, response.data
            body = response.json()
            assert body["count"] == len(body["results"])
            ids.extend(str(row["id"]) for row in body["results"])
            params["cursor"] = body["next_cursor"]
        assert body["next_page_results"] is False
        previous = client.get(url, {**params, "cursor": body["prev_cursor"]})
        assert previous.status_code == 200, previous.data
        assert [str(row["id"]) for row in previous.json()["results"]] == [str(row.pk) for row in fixtures[5:10]]
    assert ids == [str(row.pk) for row in fixtures]
    assert len(set(ids)) == len(ids)


@pytest.mark.parametrize("surface", ["api", "app"])
def test_count_and_results_keep_project_and_active_issue_scope(pagination_data, workspace, create_user, surface):
    project, fixtures = pagination_data
    other = Workspace.objects.create(owner=create_user, name="Foreign", slug=f"other-{uuid4().hex}")
    foreign = Project.objects.create(workspace=other, name="Foreign", identifier="FOR")
    Issue.objects.bulk_create([Issue(workspace=other, project=foreign, name="Foreign secret", sequence_id=1)])
    sibling = Project.objects.create(workspace=workspace, name="Sibling", identifier="SIB")
    Issue.objects.bulk_create([Issue(workspace=workspace, project=sibling, name="Sibling secret", sequence_id=1)])
    Issue.objects.filter(pk=fixtures[0].pk).update(is_draft=True)
    Issue.objects.filter(pk=fixtures[1].pk).update(archived_at=timezone.now().date())
    Issue.objects.filter(pk=fixtures[2].pk).update(deleted_at=timezone.now())
    with mock.patch("plane.app.views.issue.base.recent_visited_task.delay"):
        response = client_for(create_user, surface).get(
            list_url(workspace, project, surface), {"per_page": 100, "order_by": "sequence_id", "fields": "id,name"}
        )
    assert response.status_code == 200, response.data
    body = response.json()
    assert body["count"] == body["total_count"] == 10
    assert [str(item["id"]) for item in body["results"]] == [str(row.pk) for row in fixtures[3:]]


def test_restricted_guest_count_contains_only_their_issues(pagination_data, workspace):
    project, fixtures = pagination_data
    guest = User.objects.create(email=f"{uuid4().hex}@example.test", username=uuid4().hex)
    WorkspaceMember.objects.create(workspace=workspace, member=guest, role=5, is_active=True)
    ProjectMember.objects.create(project=project, workspace=workspace, member=guest, role=5, is_active=True)
    Project.objects.filter(pk=project.pk).update(guest_view_all_features=False)
    Issue.objects.filter(pk=fixtures[0].pk).update(created_by=guest)
    with mock.patch("plane.app.views.issue.base.recent_visited_task.delay"):
        response = client_for(guest, "app").get(list_url(workspace, project, "app"), {"per_page": 5})
    assert response.status_code == 200, response.data
    body = response.json()
    assert body["count"] == body["total_count"] == 1
    assert str(body["results"][0]["id"]) == str(fixtures[0].pk)


def test_app_legacy_filter_applies_to_both_rows_and_total(pagination_data, workspace, create_user):
    project, fixtures = pagination_data
    with mock.patch("plane.app.views.issue.base.recent_visited_task.delay"):
        response = client_for(create_user, "app").get(
            list_url(workspace, project, "app"), {"per_page": 100, "priority": "high", "order_by": "sequence_id"}
        )
    assert response.status_code == 200, response.data
    body = response.json()
    assert body["count"] == body["total_count"] == 7
    assert [str(item["id"]) for item in body["results"]] == [str(row.pk) for row in fixtures[::2]]


@pytest.mark.parametrize("surface", ["api", "app"])
def test_nonmember_cannot_obtain_rows_or_counts(pagination_data, workspace, surface):
    project, _ = pagination_data
    outsider = User.objects.create(email=f"{uuid4().hex}@example.test", username=uuid4().hex)
    response = client_for(outsider, surface).get(list_url(workspace, project, surface), {"per_page": 5})
    assert response.status_code == 403, response.data
    assert "results" not in response.data
    assert "total_count" not in response.data


@pytest.mark.parametrize("subgroup", [None, "state_id"])
def test_grouped_response_counts_rows_not_groups(pagination_data, workspace, create_user, subgroup):
    project, fixtures = pagination_data
    params = {"per_page": 2, "group_by": "priority", "order_by": "sequence_id"}
    if subgroup:
        params["sub_group_by"] = subgroup
    with mock.patch("plane.app.views.issue.base.recent_visited_task.delay"):
        response = client_for(create_user, "app").get(list_url(workspace, project, "app"), params)
    assert response.status_code == 200, response.data
    body = response.json()
    returned = []
    for group in body["results"].values():
        if subgroup:
            for sub in group["results"].values():
                returned.extend(sub["results"])
        else:
            returned.extend(group["results"])
    assert body["count"] == len(returned) == 4
    assert body["total_count"] == 13
    assert {str(row["id"]) for row in returned} == {str(row.pk) for row in fixtures[:4]}
    assert body["next_page_results"] is True
