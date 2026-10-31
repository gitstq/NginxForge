"""Generator unit tests - the generated configs must always audit clean."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nginxforge.engine import AuditOptions, audit, load_default_rules  # noqa: E402
from nginxforge.generator import (  # noqa: E402
    TEMPLATES,
    generate,
    get_template,
    list_templates,
)
from nginxforge.parser import parse  # noqa: E402


class GeneratorTest(unittest.TestCase):
    def setUp(self):
        load_default_rules()

    def test_all_templates_are_registered(self):
        names = {t.name for t in list_templates()}
        self.assertGreaterEqual(len(names), 8)
        self.assertIn("reverse-proxy", names)

    def test_every_template_audits_clean(self):
        for tpl in list_templates():
            with self.subTest(template=tpl.name):
                text = generate(tpl.name, domain="demo.example.com",
                                upstream="10.0.0.10:9000")
                result = audit([parse(text, f"{tpl.name}.conf")], AuditOptions())
                self.assertEqual(result.syntax_errors, [],
                                 f"{tpl.name}: syntax errors")
                self.assertEqual(
                    [(f.rule_id, f.message) for f in result.findings], [],
                    f"{tpl.name}: {[f.rule_id for f in result.findings]}")

    def test_unknown_template_raises(self):
        with self.assertRaises(KeyError):
            generate("does-not-exist")

    def test_parameters_are_applied(self):
        text = generate("reverse-proxy", domain="shop.example.org",
                        upstream="10.1.2.3:5000", name="shop")
        self.assertIn("server_name shop.example.org;", text)
        self.assertIn("server 10.1.2.3:5000", text)
        self.assertIn("upstream shop {", text)
        self.assertIn("proxy_pass http://shop;", text)

    def test_tls_can_be_disabled(self):
        text = generate("reverse-proxy", tls="off")
        self.assertNotIn("ssl_certificate", text)
        self.assertIn("listen      80;", text)

    def test_static_template_uses_root(self):
        text = generate("static", root="/srv/site")
        self.assertIn("root /srv/site;", text)
        self.assertIn("try_files $uri $uri/ =404;", text)

    def test_output_is_parseable_and_structured(self):
        text = generate("api-gateway")
        config = parse(text, "api.conf")
        http = config.find_first("http")
        self.assertIsNotNone(http)
        self.assertTrue(any(n.name == "server" for n in http.block))
        self.assertIsNotNone(config.find_first("upstream"))

    def test_no_trailing_whitespace_or_tabs(self):
        for tpl in list_templates():
            with self.subTest(template=tpl.name):
                text = generate(tpl.name)
                for number, line in enumerate(text.splitlines(), 1):
                    self.assertEqual(line, line.rstrip(),
                                     f"{tpl.name}:{number} trailing space")
                    self.assertNotIn("\t", line, f"{tpl.name}:{number} tab")

    def test_get_template_metadata(self):
        tpl = get_template("spa")
        self.assertIsNotNone(tpl)
        self.assertTrue(tpl.title)
        self.assertIn("root", tpl.params)

    def test_templates_registry_is_a_dict_of_templates(self):
        for name, tpl in TEMPLATES.items():
            self.assertEqual(name, tpl.name)
            self.assertTrue(callable(tpl.build))


if __name__ == "__main__":
    unittest.main()
