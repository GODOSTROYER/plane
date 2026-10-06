# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Dependency-free publication checks, not replacements for Plane's DB tests."""

import ast
import importlib.util
from pathlib import Path
import re
import unittest


PACKET = Path(__file__).resolve().parents[1]
BENCHMARKS = PACKET / "benchmarks"


class PacketTests(unittest.TestCase):
    """Keep the published reproduction entry points and descriptions usable."""

    def assert_loader_resolves(self, filename):
        """Evaluate the harness's actual path expression without importing Django."""
        script = BENCHMARKS / filename
        tree = ast.parse(script.read_text(encoding="utf-8"), filename=str(script))
        calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "spec_from_file_location"
        ]
        self.assertEqual(len(calls), 1)
        expression = ast.Expression(body=calls[0].args[1])
        target = eval(
            compile(expression, str(script), "eval"),
            {"__builtins__": {}, "Path": Path, "__file__": str(script), "EVIDENCE": PACKET},
        )
        self.assertTrue(target.is_file(), f"Missing benchmark target: {target}")
        self.assertEqual(target, BENCHMARKS / "benchmark_project_expansion.py")
        spec = importlib.util.spec_from_file_location("packet_benchmark_check", target)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertTrue(callable(module.main))

    def test_exploratory_harness_loads_published_benchmark(self):
        self.assert_loader_resolves("test_benchmark_local.py")

    def test_refined_harness_loads_published_benchmark(self):
        self.assert_loader_resolves("test_refined_benchmark.py")

    def test_pr_table_header_matches_delimiter(self):
        lines = (PACKET / "reports" / "PR_DRAFT.md").read_text(encoding="utf-8").splitlines()
        delimiters = 0
        for index, line in enumerate(lines):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if not line.startswith("|") or not all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                continue
            delimiters += 1
            header = [cell.strip() for cell in lines[index - 1].strip().strip("|").split("|")]
            self.assertEqual(len(header), len(cells), f"Table delimiter at line {index + 1}")
        self.assertGreater(delimiters, 0, "The benchmark table must remain present")

    def test_endpoint_metadata_describes_throttle_reset(self):
        script = BENCHMARKS / "test_final_endpoint.py"
        tree = ast.parse(script.read_text(encoding="utf-8"))
        outputs = [
            node.value for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "output" for target in node.targets)
            and isinstance(node.value, ast.Dict)
        ]
        self.assertEqual(len(outputs), 1)
        values = {ast.literal_eval(key): value for key, value in zip(outputs[0].keys, outputs[0].values)}
        self.assertNotIn("cold_api_token_cache_per_request", values)
        self.assertIs(ast.literal_eval(values["api_key_throttle_history_reset_per_request"]), True)
        self.assertIn("throttle-history reset", ast.literal_eval(values["clock_scope"]))

    def test_harnesses_compile_without_running_workloads(self):
        for filename in ("test_benchmark_local.py", "test_refined_benchmark.py", "test_final_endpoint.py"):
            with self.subTest(filename=filename):
                script = BENCHMARKS / filename
                compile(script.read_text(encoding="utf-8"), str(script), "exec")


if __name__ == "__main__":
    unittest.main()
