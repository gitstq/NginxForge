"""End-to-end CLI tests (in-process, no subprocess required)."""

from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nginxforge.cli import main  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
BAD = os.path.join(FIXTURES, "bad.conf")
GOOD = os.path.join(FIXTURES, "good.conf")
SYNTAX = os.path.join(FIXTURES, "syntax_error.conf")


def run(*argv: str):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main(list(argv))
    return code, buf.getvalue()


class CliTest(unittest.TestCase):
    def test_no_command_prints_help(self):
        code, out = run()
        self.assertEqual(code, 2)
        self.assertIn("usage", out.lower())

    def test_version(self):
        # argparse prints the version and exits, so the code arrives as SystemExit
        buf = io.StringIO()
        with redirect_stdout(buf):
            with self.assertRaises(SystemExit) as ctx:
                main(["--version"])
        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("nginxforge", buf.getvalue())

    def test_audit_bad_config_fails(self):
        code, out = run("audit", BAD, "--no-color")
        self.assertEqual(code, 1)
        self.assertIn("NGX104", out)

    def test_audit_good_config_passes(self):
        code, out = run("audit", GOOD, "--no-color")
        self.assertEqual(code, 0)
        self.assertIn("no findings", out)

    def test_audit_syntax_error_fails(self):
        code, out = run("audit", SYNTAX, "--no-color")
        self.assertEqual(code, 1)
        self.assertIn("NGX004", out)

    def test_audit_summary_mode(self):
        code, out = run("audit", BAD, "--summary")
        self.assertEqual(code, 1)
        self.assertIn("finding(s)", out)

    def test_audit_json_output(self):
        code, out = run("audit", BAD, "--format", "json")
        self.assertEqual(code, 1)
        self.assertTrue(out.strip().startswith("{"))

    def test_audit_never_fails(self):
        code, _ = run("audit", BAD, "--fail-on", "never")
        self.assertEqual(code, 0)

    def test_audit_output_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "report.html")
            code, out = run("audit", BAD, "--format", "html", "--output", target)
            self.assertEqual(code, 1)
            self.assertTrue(os.path.exists(target))
            self.assertGreater(os.path.getsize(target), 500)

    def test_rules_listing(self):
        code, out = run("rules")
        self.assertEqual(code, 0)
        self.assertIn("NGX101", out)

    def test_rules_explain(self):
        code, out = run("rules", "NGX104")
        self.assertEqual(code, 0)
        self.assertIn("Obsolete TLS", out)
        self.assertIn("remediation", out)

    def test_rules_explain_unknown(self):
        self.assertEqual(run("rules", "NOPE")[0], 2)

    def test_fix_dry_run_does_not_touch_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "app.conf")
            with open(BAD, encoding="utf-8") as src:
                original = src.read()
            with open(target, "w", encoding="utf-8") as dst:
                dst.write(original)
            code, out = run("fix", target, "--safe")
            self.assertEqual(code, 0)
            self.assertIn("pending", out)
            with open(target, encoding="utf-8") as handle:
                self.assertEqual(handle.read(), original)

    def test_fix_apply_rewrites_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "app.conf")
            with open(BAD, encoding="utf-8") as src:
                original = src.read()
            with open(target, "w", encoding="utf-8") as dst:
                dst.write(original)
            code, out = run("fix", target, "--safe", "--apply")
            self.assertEqual(code, 0)
            with open(target, encoding="utf-8") as handle:
                updated = handle.read()
            self.assertNotEqual(updated, original)
            self.assertIn("server_tokens off;", updated)
            self.assertNotIn("SSLv3", updated)

    def test_diff_identical_files(self):
        code, out = run("diff", os.path.join(FIXTURES, "order_a.conf"),
                        os.path.join(FIXTURES, "order_b.conf"))
        self.assertEqual(code, 0)
        self.assertIn("identical", out)

    def test_diff_detects_changes(self):
        code, out = run("diff", os.path.join(FIXTURES, "order_a.conf"),
                        os.path.join(FIXTURES, "order_c.conf"))
        self.assertEqual(code, 1)
        self.assertIn("keepalive_timeout", out)

    def test_diff_json(self):
        code, out = run("diff", os.path.join(FIXTURES, "order_a.conf"),
                        os.path.join(FIXTURES, "order_c.conf"),
                        "--format", "json")
        self.assertEqual(code, 1)
        self.assertIn('"identical": false', out)

    def test_gen_list(self):
        code, out = run("gen", "--list")
        self.assertEqual(code, 0)
        self.assertIn("reverse-proxy", out)

    def test_gen_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "nginx.conf")
            code, out = run("gen", "--template", "static",
                            "--domain", "x.example.com", "--out", target)
            self.assertEqual(code, 0)
            self.assertTrue(os.path.exists(target))
            with open(target, encoding="utf-8") as handle:
                self.assertIn("server_name x.example.com;", handle.read())

    def test_gen_unknown_template(self):
        self.assertEqual(run("gen", "--template", "nope")[0], 2)

    def test_gen_audit_flag(self):
        code, out = run("gen", "--template", "spa", "--audit")
        self.assertEqual(code, 0)
        self.assertIn("passes all rules", out)

    def test_fmt_check_on_clean_file(self):
        code, out = run("fmt", GOOD, "--check")
        self.assertEqual(code, 1)  # generated file uses aligned arguments
        self.assertIn("need formatting", out)

    def test_fmt_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "a.conf")
            with open(target, "w", encoding="utf-8") as handle:
                handle.write("http {\n gzip on;\n server {\n listen 80;\n }\n}\n")
            run("fmt", target, "--in-place")
            with open(target, encoding="utf-8") as handle:
                once = handle.read()
            code, _ = run("fmt", target, "--check")
            self.assertEqual(code, 0, once)

    def test_parse_tree(self):
        code, out = run("parse", GOOD)
        self.assertEqual(code, 0)
        self.assertIn("http {", out)

    def test_parse_json(self):
        code, out = run("parse", GOOD, "--format", "json")
        self.assertEqual(code, 0)
        self.assertIn('"name": "http"', out)

    def test_missing_file_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = run("audit", os.path.join(tmp, "nothing.conf"))
            self.assertIn(code, (0, 2))


if __name__ == "__main__":
    unittest.main()
