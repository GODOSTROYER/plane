# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Evaluation contracts; real ORM and HTTP coverage lives in contract tests."""

import json
from types import SimpleNamespace

import pytest

from plane.utils.paginator import BadPaginationError, BasePaginator, Cursor, CursorResult, OffsetPaginator
from plane.utils import paginator as pagination

pytestmark = pytest.mark.unit


class LazyRows:
    """Refuse accidental model evaluation while allowing count/projection calls."""

    def __init__(self, rows, stats=None):
        self.rows = rows
        self.stats = stats if stats is not None else {"counts": 0, "values": [], "slices": []}

    def __bool__(self):
        raise AssertionError("A count-only queryset must not be tested for truthiness")

    def __len__(self):
        raise AssertionError("The original model page must not be materialized for metadata")

    def __iter__(self):
        raise AssertionError("The original model queryset must remain lazy")

    def __getitem__(self, key):
        assert isinstance(key, slice)
        self.stats["slices"].append(key)
        return LazyRows(self.rows[key], self.stats)

    def values(self, *fields):
        self.stats["values"].append(fields)
        return LazyRows(self.rows, self.stats)

    def count(self):
        self.stats["counts"] += 1
        return len(self.rows)


@pytest.mark.parametrize("total", [0, 1, 10, 11, 20, 21, 25])
@pytest.mark.parametrize("page", [0, 1, 2, 4])
def test_explicit_count_queryset_remains_lazy(total, page):
    rows = LazyRows(range(total))
    counts = LazyRows(range(total))
    result = OffsetPaginator(rows, total_count_queryset=counts).get_result(limit=10, cursor=Cursor(10, page))
    assert result.hits == total
    assert result.max_hits == (total + 9) // 10
    assert result.next.has_results is (total > (page + 1) * 10)
    assert result.prev.has_results is (page > 0)
    assert result.results.rows == range(total)[page * 10 : (page + 1) * 10]
    assert counts.stats["counts"] == 1
    assert counts.stats["values"] == []
    assert counts.stats["slices"] == []


def test_empty_override_is_authoritative_and_next_page_uses_result_queryset():
    result = OffsetPaginator(LazyRows(range(11)), total_count_queryset=LazyRows([])).get_result(limit=10)
    assert result.hits == 0
    assert result.max_hits == 0
    # No assumption that count and result queries describe identical populations.
    assert result.next.has_results is True


def test_none_override_uses_main_queryset():
    rows = LazyRows(range(11))
    result = OffsetPaginator(rows).get_result(limit=10)
    assert result.hits == 11
    assert result.next.has_results is True


def test_same_object_can_supply_results_and_total():
    rows = LazyRows(range(12))
    result = OffsetPaginator(rows, total_count_queryset=rows).get_result(limit=10)
    assert result.hits == 12
    assert isinstance(result.results, LazyRows)


def test_effective_limit_and_previous_cursor_are_preserved():
    result = OffsetPaginator(LazyRows(range(25)), max_limit=10).get_result(limit=50, cursor=Cursor(10, 1, True))
    assert result.results.rows == range(10, 20)
    assert str(result.prev) == "10:0:1"
    assert str(result.next) == "10:2:0"


@pytest.mark.parametrize("page,max_offset", [(-1, None), (2, 20)])
def test_invalid_offsets_fail_before_any_count(page, max_offset):
    rows = LazyRows(range(25))
    with pytest.raises(BadPaginationError):
        OffsetPaginator(rows, max_offset=max_offset).get_result(limit=10, cursor=Cursor(10, page))
    assert rows.stats["counts"] == 0


class StubPaginator:
    """Return an unevaluated source to isolate response metadata behavior."""

    def __init__(self, source):
        self.source = source
        self.grouped = False

    def get_result(self, limit, cursor):
        return CursorResult(self.source, Cursor(limit, 1, False, False), Cursor(limit, -1, True, False), 20, 2)

    def process_results(self, results):
        self.grouped = True
        return {"a": {"results": results}}


def request():
    return SimpleNamespace(GET={"per_page": "10"})


@pytest.mark.parametrize("size", [0, 1, 10])
def test_row_preserving_projection_does_not_measure_original_source(size):
    rows = [{"id": i} for i in range(size)]
    response = BasePaginator().paginate(
        request=request(),
        paginator=StubPaginator(LazyRows(rows)),
        on_results=lambda source: pagination.RowPreservingList(source.rows),
    )
    assert response.data["count"] == size
    assert response.data["results"] == rows
    assert json.loads(json.dumps(response.data["results"])) == rows


def test_count_is_captured_before_in_place_controller_mutation():
    def clear(rows):
        rows.clear()
        return {"items": rows}

    response = BasePaginator().paginate(
        request=request(),
        paginator=StubPaginator(LazyRows([1, 2, 3])),
        on_results=lambda source: pagination.RowPreservingList(source.rows),
        controller=clear,
    )
    assert response.data["count"] == 3
    assert response.data["results"] == {"items": []}


@pytest.mark.parametrize("transform", [lambda rows: [], lambda rows: rows * 2, lambda rows: {"rows": rows}])
def test_unmarked_transformations_retain_original_count(transform):
    response = BasePaginator().paginate(
        request=request(), paginator=StubPaginator([1, 2, 3]), on_results=transform
    )
    assert response.data["count"] == 3


@pytest.mark.parametrize("group,subgroup", [("priority", None), ("priority", "state_id"), (None, "state_id")])
def test_grouped_paths_ignore_projection_marker(group, subgroup):
    paginator = StubPaginator([1, 2, 3])
    response = BasePaginator().paginate(
        request=request(),
        paginator=paginator,
        on_results=lambda source: pagination.RowPreservingList([source]),
        group_by_field_name=group,
        sub_group_by_field_name=subgroup,
    )
    assert response.data["count"] == 3
    assert paginator.grouped is bool(group)


def test_no_callback_keeps_existing_source_and_count():
    source = [1, 2, 3]
    response = BasePaginator().paginate(request=request(), paginator=StubPaginator(source))
    assert response.data["results"] is source
    assert response.data["count"] == 3


def test_cursor_result_sequence_contract_is_unchanged():
    result = CursorResult([1, 2, 3], Cursor(10, 1), Cursor(10, -1))
    assert len(result) == 3
    assert list(result) == [1, 2, 3]
    assert result[1:] == [2, 3]
    assert bool(result)
    assert "results=3" in repr(result)
