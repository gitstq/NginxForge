"""Rule engine unit tests."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nginxforge.engine import (  # noqa: E402
    RULES,
    AuditOptions,
    audit,
    get_rule,
    load_default_rules,
    should_fail,
)
from nginxforge.parser import parse  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def findings_for(text: str, **settings):
    load_default_rules()
    options = AuditOptions()
    options.settings.update(settings)
    return audit([parse(text, "test.conf")], options).findings


def rule_ids(text: str, **settings) -> set:
    return {f.rule_id for f in findings_for(text, **settings)}


class RegistryTest(unittest.TestCase):
    def test_rules_are_registered(self):
        load_default_rules()
        self.assertGreaterEqual(len(RULES), 40)
        self.assertIsNotNone(get_rule("NGX101"))

    def test_ids_are_unique(self):
        load_default_rules()
        ids = [r.id for r in RULES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_rule_has_metadata(self):
        load_default_rules()
        for r in RULES:
            self.assertTrue(r.title)
            self.assertIn(r.severity, ("error", "warning", "info"))
            self.assertIn(r.category,
                          ("correctness", "security", "performance", "style"))


class CorrectnessTest(unittest.TestCase):
    def test_unknown_directive_suggests_a_fix(self):
        findings = findings_for("http { proxy_pas http://a; }")
        ids = {f.rule_id for f in findings}
        self.assertIn("NGX001", ids)
        suggestion = [f for f in findings if f.rule_id == "NGX001"][0]
        self.assertEqual(suggestion.severity, "warning")
        self.assertIn("proxy_pass", suggestion.message)

    def test_invalid_context(self):
        findings = findings_for("http { worker_connections 1024; }")
        self.assertIn("NGX002", {f.rule_id for f in findings})

    def test_arity_mismatch(self):
        findings = findings_for("http { client_max_body_size 1m 2m; }")
        self.assertIn("NGX003", {f.rule_id for f in findings})

    def test_types_block_is_not_flagged_as_unknown(self):
        findings = findings_for("http { types { text/html html; } }")
        self.assertNotIn("NGX001", {f.rule_id for f in findings})

    def test_try_files_fallback(self):
        self.assertIn("NGX005", rule_ids("server { try_files $uri $uri/; }"))
        self.assertNotIn("NGX005",
                         rule_ids("server { try_files $uri $uri/ =404; }"))

    def test_root_alias_conflict(self):
        text = "server { location /a { root /srv; alias /srv; } }"
        self.assertIn("NGX006", rule_ids(text))

    def test_duplicate_server(self):
        text = ("http { server { listen 80; server_name a.com; } "
                "server { listen 80; server_name a.com; } }")
        self.assertIn("NGX009", rule_ids(text))

    def test_upstream_server_without_port(self):
        self.assertIn("NGX010", rule_ids("http { upstream u { server 10.0.0.1; } }"))
        self.assertNotIn("NGX010",
                         rule_ids("http { upstream u { server 10.0.0.1:80; } }"))

    def test_duplicate_directive(self):
        self.assertIn("NGX012", rule_ids("http { gzip on; gzip on; }"))


class SecurityTest(unittest.TestCase):
    def test_server_tokens(self):
        self.assertIn("NGX101", rule_ids("http { server_tokens on; }"))
        self.assertNotIn("NGX101", rule_ids("http { server_tokens off; }"))

    def test_missing_security_headers(self):
        self.assertIn("NGX102", rule_ids("http { server { listen 80; } }"))

    def test_autoindex(self):
        self.assertIn("NGX103", rule_ids("http { autoindex on; }"))

    def test_obsolete_tls(self):
        self.assertIn("NGX104", rule_ids("http { ssl_protocols TLSv1; }"))
        self.assertNotIn("NGX104", rule_ids("http { ssl_protocols TLSv1.2 TLSv1.3; }"))

    def test_weak_ciphers(self):
        self.assertIn("NGX105", rule_ids("http { ssl_ciphers ALL:MD5; }"))
        # explicitly disabled tokens are fine
        self.assertNotIn("NGX105",
                         rule_ids("http { ssl_ciphers HIGH:!aNULL:!MD5; }"))

    def test_hsts_required_for_tls_servers(self):
        text = ("http { server { listen 443 ssl; ssl_certificate /etc/nginx/a.pem; "
                "ssl_certificate_key /etc/nginx/a.key; } }")
        self.assertIn("NGX106", rule_ids(text))

    def test_unsafe_key_path(self):
        text = "http { server { ssl_certificate_key /home/user/key.pem; } }"
        self.assertIn("NGX107", rule_ids(text))

    def test_sensitive_location(self):
        self.assertIn("NGX110", rule_ids("http { server { location /status { } } }"))

    def test_cors_star_with_credentials_is_an_error(self):
        text = ("http { server { add_header Access-Control-Allow-Origin '*'; "
                "add_header Access-Control-Allow-Credentials 'true'; } }")
        findings = [f for f in findings_for(text) if f.rule_id == "NGX111"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "error")

    def test_webdav(self):
        self.assertIn("NGX114",
                      rule_ids("http { server { location / { dav_methods PUT; } } }"))


class PerformanceTest(unittest.TestCase):
    def test_compression(self):
        self.assertIn("NGX201", rule_ids("http { server { listen 80; } }"))
        self.assertNotIn("NGX201", rule_ids("http { gzip on; }"))

    def test_long_keepalive(self):
        self.assertIn("NGX204", rule_ids("http { keepalive_timeout 300s; }"))
        self.assertNotIn("NGX204", rule_ids("http { keepalive_timeout 65s; }"))

    def test_settings_are_honoured(self):
        text = "http { keepalive_timeout 300s; }"
        self.assertNotIn("NGX204",
                         rule_ids(text, max_keepalive_timeout=600))

    def test_worker_processes(self):
        self.assertIn("NGX205", rule_ids("worker_processes 4;"))
        self.assertNotIn("NGX205", rule_ids("worker_processes auto;"))

    def test_upstream_keepalive(self):
        self.assertIn("NGX212",
                      rule_ids("http { upstream u { server 1.1.1.1:80; } }"))


class StyleTest(unittest.TestCase):
    def test_mixed_indentation(self):
        text = "http {\n    gzip on;\n\tsendfile on;\n}\n"
        self.assertIn("NGX301", rule_ids(text))

    def test_trailing_whitespace(self):
        self.assertIn("NGX302", rule_ids("http {\n    gzip on;   \n}\n"))

    def test_snake_case(self):
        self.assertIn("NGX305", rule_ids("http { Gzip on; }"))


class FilteringTest(unittest.TestCase):
    def test_select_category(self):
        load_default_rules()
        options = AuditOptions(select={"security"})
        result = audit([parse("http { server_tokens on; gzip off; }")], options)
        self.assertTrue(all(f.category == "security" for f in result.findings))

    def test_ignore_category(self):
        load_default_rules()
        options = AuditOptions(ignore={"security"})
        result = audit([parse("http { server_tokens on; }")], options)
        self.assertFalse([f for f in result.findings
                          if f.category == "security"])

    def test_min_severity(self):
        load_default_rules()
        options = AuditOptions(min_severity="error")
        result = audit([parse("http { server_tokens on; }")], options)
        self.assertEqual(result.findings, [])

    def test_syntax_errors_fail_the_run(self):
        load_default_rules()
        config = parse("http { server { ", "x.conf")
        result = audit([config], AuditOptions())
        self.assertFalse(result.ok)
        self.assertTrue(should_fail(result, "error"))


class FixtureTest(unittest.TestCase):
    def test_bad_fixture_has_expected_rules(self):
        from nginxforge.parser import parse_file
        load_default_rules()
        result = audit([parse_file(os.path.join(FIXTURES, "bad.conf"))],
                       AuditOptions())
        ids = {f.rule_id for f in result.findings}
        for expected in ("NGX101", "NGX102", "NGX103", "NGX104", "NGX105",
                         "NGX006", "NGX009", "NGX110", "NGX114"):
            self.assertIn(expected, ids)
        self.assertTrue(should_fail(result, "error"))

    def test_good_fixture_is_clean(self):
        from nginxforge.parser import parse_file
        load_default_rules()
        result = audit([parse_file(os.path.join(FIXTURES, "good.conf"))],
                       AuditOptions())
        self.assertEqual(result.findings, [])
        self.assertEqual(result.syntax_errors, [])


if __name__ == "__main__":
    unittest.main()
