"""Automatic fix unit tests."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nginxforge.engine import AuditOptions, audit, load_default_rules  # noqa: E402
from nginxforge.fixer import (  # noqa: E402
    apply_to_config,
    build_plan,
    total_changes,
    unified_diff,
)
from nginxforge.parser import parse  # noqa: E402


def audit_text(text: str):
    load_default_rules()
    return audit([parse(text, "test.conf")], AuditOptions())


class FixerTest(unittest.TestCase):
    def setUp(self):
        load_default_rules()

    def test_replace_fix(self):
        config = parse("http {\n    server_tokens on;\n}\n", "test.conf")
        result = audit([config], AuditOptions())
        plans = build_plan(result.findings, safe_only=True)
        self.assertIn("test.conf", plans)
        self.assertEqual(len(plans["test.conf"].changes), 1)
        change = plans["test.conf"].changes[0]
        self.assertEqual(change.mode, "replace")
        new_text = apply_to_config(config, [change])
        self.assertIn("server_tokens off;", new_text)
        self.assertNotIn("server_tokens on;", new_text)

    def test_safe_mode_skips_insertions(self):
        result = audit_text("http {\n    server { listen 80; server_name a; }\n}\n")
        safe = build_plan(result.findings, safe_only=True)
        everything = build_plan(result.findings, safe_only=False)
        self.assertLessEqual(total_changes(safe.values()),
                             total_changes(everything.values()))

    def test_rule_filter(self):
        result = audit_text("http {\n    server_tokens on;\n    autoindex on;\n}\n")
        plans = build_plan(result.findings, rule_filter={"NGX101"})
        rules = {c.rule_id for p in plans.values() for c in p.changes}
        self.assertEqual(rules, {"NGX101"})

    def test_one_change_per_line(self):
        result = audit_text("http {\n    ssl_protocols TLSv1 TLSv1.2;\n}\n")
        plans = build_plan(result.findings)
        lines = [c.line for p in plans.values() for c in p.changes]
        self.assertEqual(len(lines), len(set(lines)))

    def test_diff_is_produced(self):
        config = parse("http {\n    server_tokens on;\n}\n", "test.conf")
        result = audit([config], AuditOptions())
        plans = build_plan(result.findings, safe_only=True)
        diff = unified_diff(config, plans["test.conf"].changes)
        self.assertIn("-    server_tokens on;", diff)
        self.assertIn("+    server_tokens off;", diff)

    def test_multi_line_insert(self):
        config = parse("http {\n    server { listen 80; server_name a.com; }\n}\n",
                       "test.conf")
        result = audit([config], AuditOptions())
        plans = build_plan(result.findings)
        new_text = apply_to_config(config, plans["test.conf"].changes)
        self.assertIn("X-Content-Type-Options", new_text)
        # every inserted line must be indented inside the server block
        for line in new_text.splitlines():
            if "X-Content-Type-Options" in line:
                self.assertTrue(line.startswith("    "))

    def test_indentation_is_preserved(self):
        config = parse("http {\n        server_tokens on;\n}\n", "t.conf")
        result = audit([config], AuditOptions())
        plans = build_plan(result.findings, safe_only=True)
        new_text = apply_to_config(config, plans["t.conf"].changes)
        self.assertIn("        server_tokens off;", new_text)

    def test_fix_makes_the_rule_pass(self):
        load_default_rules()
        text = "http {\n    server_tokens on;\n}\n"
        for _ in range(3):
            config = parse(text, "t.conf")
            result = audit([config], AuditOptions())
            plans = build_plan(result.findings, safe_only=True)
            if not plans:
                break
            text = apply_to_config(config, plans["t.conf"].changes)
        self.assertNotIn("server_tokens on;", text)
        result = audit([parse(text, "t.conf")], AuditOptions())
        self.assertNotIn("NGX101", {f.rule_id for f in result.findings})


if __name__ == "__main__":
    unittest.main()
