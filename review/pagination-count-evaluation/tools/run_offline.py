#!/usr/bin/env python3
"""Execute unit orchestration tests with explicit framework doubles.

This does NOT load Django, PostgreSQL, DRF, or Plane's HTTP stack. It is an
additional offline gate, never a substitute for the repository test suites.
"""
from __future__ import annotations

import argparse
import ast
from collections.abc import Sequence
import math
from pathlib import Path
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[1]


class QuerySetDouble:
    query = None

    def count(self):
        raise NotImplementedError

    def __len__(self):
        raise NotImplementedError


class ResponseDouble:
    def __init__(self, data):
        self.data = data


class ParseErrorDouble(Exception):
    def __init__(self, detail=None):
        super().__init__(detail)


def load_core(source: str) -> types.ModuleType:
    """Compile the selected production classes verbatim at the AST level."""
    tree = ast.parse(source)
    names = {"Cursor", "CursorResult", "BadPaginationError", "OffsetPaginator", "BasePaginator"}
    tree.body = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name in names]
    if {node.name for node in tree.body} != names:
        raise ValueError("Unexpected paginator source")
    module = types.ModuleType("plane.utils.paginator")
    module.__dict__.update(
        math=math, Sequence=Sequence, QuerySet=QuerySetDouble, MAX_LIMIT=1000,
        Response=ResponseDouble, ParseError=ParseErrorDouble,
        ISSUE_GROUP_BY_ALLOWLIST={"priority", "state_id"},
    )
    exec(compile(tree, "<AST-extracted paginator: framework doubles>", "exec"), module.__dict__)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=["upstream", "candidate"], required=True)
    parser.add_argument("--source-file", type=Path)
    parser.add_argument("--report-name")
    args = parser.parse_args()
    from changes import apply_changes
    source = (args.source_file or ROOT / "upstream" / "paginator_reference.py").read_text()
    if args.variant == "candidate":
        source = apply_changes(source)
    module = load_core(source)
    for name in ("django", "django.db", "django.db.models", "plane", "plane.utils"):
        sys.modules[name] = types.ModuleType(name)
    sys.modules["django.db.models"].QuerySet = QuerySetDouble
    sys.modules["plane.utils.paginator"] = module
    print("OFFLINE ONLY: AST-extracted production orchestration + framework doubles.")
    print("Django/DRF/PostgreSQL and HTTP integration are NOT exercised.")
    return pytest.main([
        str(ROOT / "candidate/apps/api/plane/tests/unit/utils/test_paginator_evaluation.py"),
        "-c", str(ROOT / "tests/offline/pytest.ini"),
        "--confcutdir", str(ROOT), "-q", "--tb=short",
        "--junitxml", str(ROOT / f"evidence/offline-{args.report_name or args.variant}.xml"),
        "-p", "no:cacheprovider",
    ])


if __name__ == "__main__":
    raise SystemExit(main())
