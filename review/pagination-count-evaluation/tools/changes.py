"""Apply the two reviewed edits; never replace unrelated paginator code."""

EDIT_A_OLD = '        total_count = self.total_count_queryset.count() if self.total_count_queryset else queryset.count()\n'
EDIT_A_NEW = '''        # QuerySet truthiness fetches every matching row. Only None means that
        # no count queryset was supplied; an explicit empty queryset counts as 0.
        count_queryset = self.total_count_queryset if self.total_count_queryset is not None else queryset
        total_count = count_queryset.count()
'''
EDIT_B_IMPORT_OLD = 'from django.db.models import Count, F, Window\n'
EDIT_B_IMPORT_NEW = 'from django.db.models import Count, F, QuerySet, Window\n'
EDIT_B_OLD = '''        # Return the response
        response = Response(
'''
EDIT_B_NEW = '''        # A callback can evaluate a projection without populating the original
        # page's cache. Count that page in SQL instead of fetching its models.
        # Do not count the transformed output: callbacks and controllers may
        # change its cardinality. Only optimize SQL-sliced pages: counting an
        # unsliced DISTINCT/GROUP BY query can discard ordering-dependent
        # columns. Keep custom lengths, row locks and raw-render cache reuse.
        if (
            on_results
            and type(cursor_result) is CursorResult
            and isinstance(cursor_result.results, QuerySet)
            and cursor_result.results.query.is_sliced
            and not cursor_result.results.query.select_for_update
            and results is not cursor_result.results
        ):
            page_count = cursor_result.results.count()
        else:
            page_count = len(cursor_result)

        # Return the response
        response = Response(
'''
EDIT_B_COUNT_OLD = '                "count": cursor_result.__len__(),\n'
EDIT_B_COUNT_NEW = '                "count": page_count,\n'


def apply_changes(source: str, stage: str = "both") -> str:
    """Fail closed when reviewed anchors have drifted or already changed."""
    if stage not in {"a", "b", "both"}:
        raise ValueError(f"Unknown stage: {stage}")
    edits = []
    if stage in {"a", "both"}:
        edits.append((EDIT_A_OLD, EDIT_A_NEW))
    if stage in {"b", "both"}:
        edits.extend([
            (EDIT_B_IMPORT_OLD, EDIT_B_IMPORT_NEW),
            (EDIT_B_OLD, EDIT_B_NEW),
            (EDIT_B_COUNT_OLD, EDIT_B_COUNT_NEW),
        ])
    for old, new in edits:
        if source.count(old) != 1:
            raise ValueError(f"Expected exactly one reviewed anchor: {old[:80]!r}")
        source = source.replace(old, new, 1)
    return source
