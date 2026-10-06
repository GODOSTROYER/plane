#!/usr/bin/env python3
"""Check syntax, patch application, and orchestration regressions offline.

The ORM, PostgreSQL, HTTP routes and production performance are NOT exercised.
All Git operations below use a newly created temporary repository.
"""
from __future__ import annotations

import ast
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

from changes import apply_changes, EDIT_A_OLD, EDIT_A_NEW

ROOT = Path(__file__).resolve().parents[1]


def invoke(command, log):
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    (ROOT / 'evidence' / log).write_text(result.stdout + result.stderr)
    return result.returncode


def main():
    source = (ROOT / 'upstream/paginator_reference.py').read_text()
    candidate = apply_changes(source)
    parsed = []
    for path in sorted(ROOT.rglob('*.py')):
        ast.parse(path.read_text(), filename=str(path))
        parsed.append(str(path.relative_to(ROOT)))
    ast.parse(candidate)
    statuses = {}
    for variant, expected in [('candidate', 0), ('upstream', 1)]:
        code = invoke([sys.executable, str(ROOT/'tools/run_offline.py'), '--variant', variant], f'offline-{variant}.txt')
        assert code == expected, (variant, code)
        suite = ET.parse(ROOT/f'evidence/offline-{variant}.xml').getroot().find('testsuite')
        statuses[variant] = {key: int(suite.attrib[key]) for key in ('tests', 'failures', 'errors', 'skipped')}
    assert statuses['candidate']['failures'] == 0
    assert statuses['upstream']['failures'] > 0
    # Mutate the tested production-method excerpt, not a separate algorithm.
    mutations = {
        'restore_count_truthiness': (EDIT_A_NEW, EDIT_A_OLD),
        'restore_metadata_hydration': ('page_count = cursor_result.results.count()', 'page_count = len(cursor_result)'),
        'count_transformed_output': ('page_count = cursor_result.results.count()', 'page_count = len(results)'),
        'drop_lock_guard': ('            and not cursor_result.results.query.select_for_update\n', ''),
        'drop_slice_guard': ('            and cursor_result.results.query.is_sliced\n', ''),
        'drop_custom_result_guard': ('            and type(cursor_result) is CursorResult\n', ''),
        'drop_passthrough_guard': ('            and results is not cursor_result.results\n', ''),
        'drop_callback_guard': ('            on_results\n            and type(cursor_result)', '            True\n            and type(cursor_result)'),
    }
    mutation_results = {}
    for name, (old, new) in mutations.items():
        assert candidate.count(old) == 1, name
        mutated = candidate.replace(old, new, 1)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'mutated.py'
            path.write_text(mutated)
            code = invoke([sys.executable, str(ROOT/'tools/run_offline.py'), '--source-file', str(path),
                           '--variant', 'upstream', '--report-name', name], f'mutation-{name}.txt')
            suite = ET.parse(ROOT/f'evidence/offline-{name}.xml').getroot().find('testsuite')
            failures, errors = int(suite.attrib['failures']), int(suite.attrib['errors'])
            assert code == 1 and failures > 0 and errors == 0, (name, code, failures, errors)
            mutation_results[name] = {'detected': True, 'failed_assertions': failures, 'collection_errors': errors}
    # Apply/reverse reviewed hunks to the complete reference. Git tolerates its
    # different line offsets; unrelated contents cannot be replaced wholesale.
    with tempfile.TemporaryDirectory() as temp:
        directory = Path(temp)
        path = directory/'apps/api/plane/utils/paginator.py'
        path.parent.mkdir(parents=True)
        path.write_text(source)
        def git(*args):
            return subprocess.run(['git', '-C', str(directory), *args], check=True, capture_output=True)
        git('init', '-q')
        git('apply', '--check', str(ROOT/'production.patch'))
        git('apply', str(ROOT/'production.patch'))
        assert path.read_text() == candidate
        git('apply', '-R', str(ROOT/'production.patch'))
        assert path.read_text() == source
        git('apply', str(ROOT/'01-count-queryset.patch'))
        git('apply', str(ROOT/'02-page-metadata.patch'))
        assert path.read_text() == candidate
        git('apply', '-R', str(ROOT/'02-page-metadata.patch'))
        git('apply', '-R', str(ROOT/'01-count-queryset.patch'))
        # Reconstruct the combined artifact from the already-published source
        # and candidate files instead of duplicating 800 lines in the packet.
        full_patch = ''.join(difflib.unified_diff(
            source.splitlines(keepends=True), candidate.splitlines(keepends=True),
            fromfile='a/apps/api/plane/utils/paginator.py',
            tofile='b/apps/api/plane/utils/paginator.py',
        ))
        for test in sorted((ROOT/'candidate').rglob('*.py')):
            relative = test.relative_to(ROOT/'candidate').as_posix()
            full_patch += ''.join(difflib.unified_diff(
                [], test.read_text().splitlines(keepends=True),
                fromfile='/dev/null', tofile='b/' + relative,
            ))
        combined = directory/'combined.patch'
        combined.write_text(full_patch)
        git('apply', '--check', str(combined))
        git('apply', str(combined))
        assert path.read_text() == candidate
        for test in (ROOT/'candidate').rglob('*.py'):
            assert (directory/test.relative_to(ROOT/'candidate')).read_bytes() == test.read_bytes()
    for stage in ('a', 'b', 'both'):
        try:
            apply_changes(apply_changes(source, stage), stage)
        except ValueError:
            pass
        else:
            raise AssertionError('Anchor application must refuse repeated edits')
    report = {
        'scope': 'OFFLINE ONLY: AST syntax, selected real method bodies with framework doubles, mutation and temporary-Git patch tests',
        'not_run': ['real Django/DRF unit tests', 'PostgreSQL ORM tests', 'HTTP request-stack tests',
                    'TCP smoke test', 'Ruff', 'full backend suite', 'benchmarks', 'hosted CI'],
        'python': sys.version, 'parsed_python_files': parsed, 'test_results': statuses,
        'mutation_results': mutation_results, 'patch_apply_reverse_and_staged_apply': 'passed_on_verified_reference',
        'full_repository_git_blob_application': 'verified full file reference; not a full application checkout',
        'source_reference_sha256': hashlib.sha256(source.encode()).hexdigest(),
        'candidate_reference_sha256': hashlib.sha256(candidate.encode()).hexdigest(),
    }
    (ROOT/'evidence/local-validation.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
