"""Semantic diff unit tests."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nginxforge.parser import parse  # noqa: E402
from nginxforge.semdiff import (  # noqa: E402
    canonicalize,
    compare,
    render_canonical,
)

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def diff_texts(a: str, b: str):
    return compare(parse(a, "a.conf"), parse(b, "b.conf"))


class SemanticDiffTest(unittest.TestCase):
    def test_identical_text(self):
        result = diff_texts("http { gzip on; }", "http { gzip on; }")
        self.assertTrue(result.identical)
        self.assertEqual(result.change_count, 0)

    def test_sibling_order_is_ignored(self):
        a = "http { gzip on; sendfile on; server_tokens off; }"
        b = "http { server_tokens off; gzip on; sendfile on; }"
        result = diff_texts(a, b)
        self.assertTrue(result.identical, result.summary())

    def test_whitespace_and_comments_are_ignored(self):
        a = "http {\n    gzip on;\n}\n"
        b = "http {\n\tgzip   on;   # compress\n}\n"
        result = diff_texts(a, b)
        self.assertTrue(result.identical, result.summary())

    def test_added_directive(self):
        result = diff_texts("http { gzip on; }",
                            "http { gzip on; sendfile on; }")
        self.assertEqual(len(result.added), 1)
        self.assertEqual(result.added[0].name, "sendfile")
        self.assertFalse(result.identical)

    def test_removed_directive(self):
        result = diff_texts("http { gzip on; sendfile on; }",
                            "http { gzip on; }")
        self.assertEqual(len(result.removed), 1)
        self.assertEqual(result.removed[0].name, "sendfile")

    def test_changed_arguments(self):
        result = diff_texts("http { keepalive_timeout 65; }",
                            "http { keepalive_timeout 300; }")
        self.assertEqual(len(result.changed), 1)
        self.assertEqual(result.changed[0][0].args, ("65",))
        self.assertEqual(result.changed[0][1].args, ("300",))

    def test_nested_blocks_are_compared_by_path(self):
        a = "http { server { listen 80; root /a; } }"
        b = "http { server { listen 80; root /b; } }"
        result = diff_texts(a, b)
        self.assertEqual(len(result.changed), 1)
        self.assertIn("server", result.changed[0][0].path)

    def test_canonical_render_is_stable(self):
        text = "http { server { listen 80; gzip on; } }"
        first = render_canonical(parse(text))
        second = render_canonical(parse(text))
        self.assertEqual(first, second)

    def test_canonicalize_sorts(self):
        entries = canonicalize(parse("http { gzip on; autoindex on; }"))
        names = [e.name for e in entries]
        self.assertEqual(names, sorted(names))

    def test_fixture_indentation_only_change_is_identical(self):
        from nginxforge.parser import parse_file
        a = parse_file(os.path.join(FIXTURES, "good.conf"))
        b = parse_file(os.path.join(FIXTURES, "reordered.conf"))
        result = compare(a, b)
        self.assertTrue(result.identical, result.summary())

    def test_fixture_order_files(self):
        from nginxforge.parser import parse_file
        a = parse_file(os.path.join(FIXTURES, "order_a.conf"))
        b = parse_file(os.path.join(FIXTURES, "order_b.conf"))
        c = parse_file(os.path.join(FIXTURES, "order_c.conf"))
        self.assertTrue(compare(a, b).identical)
        self.assertFalse(compare(a, c).identical)

    def test_unified_text_is_produced(self):
        result = diff_texts("http { gzip on; }", "http { gzip off; }")
        self.assertIn("---", result.text)
        self.assertIn("+++", result.text)


if __name__ == "__main__":
    unittest.main()
