"""Lexer unit tests."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nginxforge.lexer import tokenize  # noqa: E402
from nginxforge.model import (  # noqa: E402
    TK_EOF, TK_LBRACE, TK_RBRACE, TK_SEMI, TK_STRING, TK_WORD, ConfigError,
)


class LexerTest(unittest.TestCase):
    def test_simple_directive(self):
        tokens = tokenize("worker_processes auto;")
        kinds = [t.kind for t in tokens]
        self.assertEqual(kinds, [TK_WORD, TK_WORD, TK_SEMI, TK_EOF])
        self.assertEqual(tokens[0].value, "worker_processes")
        self.assertEqual(tokens[1].value, "auto")

    def test_positions(self):
        tokens = tokenize("a b;\nc d;")
        self.assertEqual(tokens[0].line, 1)
        self.assertEqual(tokens[0].col, 1)
        self.assertEqual(tokens[2].line, 1)
        third = tokens[3]
        self.assertEqual(third.line, 2)
        self.assertEqual(third.col, 1)

    def test_quoted_strings_keep_special_characters(self):
        tokens = tokenize('root "/var/www/; {weird}";')
        values = [t.value for t in tokens if t.kind == TK_STRING]
        self.assertEqual(values, ["/var/www/; {weird}"])

    def test_single_quotes(self):
        tokens = tokenize("add_header X 'a b c';")
        self.assertIn("a b c", [t.value for t in tokens])

    def test_escaped_quote(self):
        tokens = tokenize(r'add_header A "say \"hi\"";')
        values = [t.value for t in tokens if t.kind == TK_STRING]
        self.assertEqual(values[0], 'say "hi"')

    def test_comment_is_captured_with_its_line(self):
        tokens = tokenize("# hello\nworker_processes 1;")
        comments = [t for t in tokens if t.kind == "comment"]
        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0].value, "# hello")
        self.assertEqual(comments[0].line, 1)

    def test_braces(self):
        tokens = tokenize("http { }")
        self.assertEqual([t.kind for t in tokens],
                         [TK_WORD, TK_LBRACE, TK_RBRACE, TK_EOF])

    def test_unterminated_string_raises(self):
        with self.assertRaises(ConfigError):
            tokenize('root "/var/www;')

    def test_variables_are_words(self):
        tokens = tokenize("try_files $uri $uri/ =404;")
        words = [t.value for t in tokens if t.kind == TK_WORD]
        self.assertIn("$uri", words)
        self.assertIn("$uri/", words)


if __name__ == "__main__":
    unittest.main()
