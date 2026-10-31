"""Reporter unit tests."""

from __future__ import annotations

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nginxforge.engine import AuditOptions, audit, load_default_rules  # noqa: E402
from nginxforge.parser import parse  # noqa: E402
from nginxforge.reporters import MACHINE_FORMATS, formats, render  # noqa: E402
from nginxforge.reporters.text import set_color  # noqa: E402


class ReporterTest(unittest.TestCase):
    def setUp(self):
        load_default_rules()
        set_color(False)
        self.result = audit(
            [parse("http {\n    server_tokens on;\n    ssl_protocols TLSv1;\n}\n",
                   "demo.conf")],
            AuditOptions(),
        )

    def test_all_formats_render(self):
        self.assertGreaterEqual(len(self.result.findings), 2)
        for fmt in formats():
            with self.subTest(format=fmt):
                out = render(fmt, self.result)
                self.assertIsInstance(out, str)
                self.assertTrue(out.strip())

    def test_json_is_valid_and_structured(self):
        payload = json.loads(render("json", self.result))
        self.assertEqual(payload["tool"]["name"], "nginxforge")
        self.assertIn("findings", payload)
        self.assertIn("summary", payload)
        self.assertEqual(payload["summary"]["total"], len(self.result.findings))
        self.assertEqual(payload["summary"]["by_severity"]["error"],
                         sum(1 for f in self.result.findings
                             if f.severity == "error"))

    def test_sarif_structure(self):
        payload = json.loads(render("sarif", self.result))
        self.assertEqual(payload["version"], "2.1.0")
        run = payload["runs"][0]
        self.assertEqual(run["tool"]["driver"]["name"], "nginxforge")
        self.assertTrue(run["results"])
        first = run["results"][0]
        self.assertIn("ruleId", first)
        self.assertIn("locations", first)
        self.assertTrue(run["tool"]["driver"]["rules"])

    def test_markdown_has_a_table(self):
        out = render("markdown", self.result)
        self.assertIn("## 🛡️ NginxForge audit", out)
        self.assertIn("| Severity | Rule |", out)
        for finding in self.result.findings:
            self.assertIn(finding.rule_id, out)

    def test_html_is_self_contained(self):
        out = render("html", self.result)
        self.assertIn("<!DOCTYPE html>", out)
        self.assertIn("<style>", out)
        self.assertNotIn("http://", out.split("<style>")[1].split("</style>")[0])
        self.assertIn("demo.conf", out)

    def test_text_lists_every_finding(self):
        out = render("text", self.result)
        for finding in self.result.findings:
            self.assertIn(finding.rule_id, out)
        self.assertIn("summary", out)

    def test_text_reports_a_clean_run(self):
        clean = audit([parse("http {\n}\n", "clean.conf")], AuditOptions())
        clean.findings = []
        out = render("text", clean)
        self.assertIn("no findings", out)

    def test_machine_formats_are_flagged(self):
        self.assertIn("json", MACHINE_FORMATS)
        self.assertIn("sarif", MACHINE_FORMATS)
        self.assertNotIn("text", MACHINE_FORMATS)

    def test_unknown_format_raises(self):
        with self.assertRaises(KeyError):
            render("yaml", self.result)


if __name__ == "__main__":
    unittest.main()
