"""Parser unit tests."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nginxforge.model import ConfigError  # noqa: E402
from nginxforge.parser import parse, parse_file, render  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


class ParserTest(unittest.TestCase):
    def test_flat_directives(self):
        cfg = parse("worker_processes auto;\npid /run/nginx.pid;\n")
        self.assertEqual(len(cfg.tree), 2)
        self.assertEqual(cfg.tree[0].name, "worker_processes")
        self.assertEqual(cfg.tree[0].args, ["auto"])
        self.assertTrue(cfg.ok)

    def test_nested_blocks(self):
        cfg = parse("http {\n server {\n  listen 80;\n }\n}\n")
        http = cfg.tree[0]
        self.assertTrue(http.is_block)
        server = http.block[0]
        self.assertEqual(server.name, "server")
        self.assertEqual(server.context, "http")
        self.assertEqual(server.context_path(), ["http"])
        self.assertEqual(server.children("listen")[0].args, ["80"])

    def test_context_path_is_deep(self):
        cfg = parse("http {\n server {\n  location / {\n   root /var/www;\n  }\n }\n}\n")
        root = list(cfg.find_all("root"))[0]
        self.assertEqual(root.context_path(), ["http", "server", "location"])
        self.assertEqual(
            root.path_label(),
            "http > server > location / > root /var/www",
        )

    def test_quoted_arguments_with_semicolons(self):
        cfg = parse('add_header X "a;b" always;')
        node = cfg.tree[0]
        self.assertEqual(node.args, ["X", "a;b", "always"])

    def test_missing_semicolon_before_brace_is_reported(self):
        # Exactly what nginx complains about: a non-block directive that
        # swallows the following '{' because its ';' is missing.
        cfg = parse("http {\n server_tokens off\n server {\n }\n}\n")
        self.assertFalse(cfg.ok)
        self.assertTrue(any("missing a ';'" in e.message for e in cfg.errors))

    def test_missing_semicolon_merges_arguments_like_nginx(self):
        # nginx's lexer treats newlines as plain whitespace, so the next
        # directive's tokens simply become extra arguments. The arity rule
        # (NGX003) is what surfaces this to the user.
        cfg = parse("worker_processes 2\npid /run/nginx.pid;\n")
        self.assertEqual(cfg.tree[0].args, ["2", "pid", "/run/nginx.pid"])

    def test_unclosed_block_is_reported(self):
        cfg = parse("http {\n server { listen 80; }\n")
        self.assertFalse(cfg.ok)
        self.assertTrue(any("missing '}'" in e.message for e in cfg.errors))

    def test_unexpected_closing_brace_recovers(self):
        cfg = parse("}\nworker_processes 1;\n")
        self.assertFalse(cfg.ok)
        self.assertIn("worker_processes", [n.name for n in cfg.tree])

    def test_comments_are_attached_to_the_next_directive(self):
        cfg = parse("# tune me\nworker_processes auto;\n")
        self.assertEqual(cfg.tree[0].comment, "tune me")

    def test_fixture_good_parses_cleanly(self):
        cfg = parse_file(os.path.join(FIXTURES, "good.conf"))
        self.assertTrue(cfg.ok, cfg.errors)
        self.assertIsNotNone(cfg.find_first("http"))

    def test_fixture_syntax_error_has_errors(self):
        cfg = parse_file(os.path.join(FIXTURES, "syntax_error.conf"))
        self.assertFalse(cfg.ok)
        self.assertGreaterEqual(len(cfg.errors), 1)

    def test_render_roundtrip(self):
        cfg = parse_file(os.path.join(FIXTURES, "good.conf"))
        text = render(cfg.tree)
        reparsed = parse(text)
        self.assertTrue(reparsed.ok, reparsed.errors)
        self.assertEqual(
            [n.name for n in cfg.walk()],
            [n.name for n in reparsed.walk()],
        )

    def test_types_block_is_parsed(self):
        cfg = parse("http {\n types {\n  text/html html;\n }\n}\n")
        types = list(cfg.find_all("types"))[0]
        self.assertEqual(len(types.block), 1)
        self.assertEqual(types.block[0].name, "text/html")

    def test_if_block(self):
        cfg = parse("server {\n if ($slow) {\n  limit_rate 10k;\n }\n}\n")
        node = list(cfg.find_all("if"))[0]
        self.assertEqual(node.args, ["($slow)"])
        self.assertEqual(node.block[0].name, "limit_rate")

    def test_empty_and_whitespace_input(self):
        self.assertEqual(parse("").tree, [])
        self.assertEqual(parse("\n\n  \n").tree, [])


if __name__ == "__main__":
    unittest.main()
