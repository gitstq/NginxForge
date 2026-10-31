"""
Dependency-free lexer for the nginx configuration language.

The nginx grammar is deliberately tiny, which makes a hand written scanner both
faster and more robust than a generated one:

* directives are ``name arg arg ...;`` or ``name arg arg ... { ... }``
* ``#`` starts a comment that runs to end of line
* ``'...'`` and ``"..."`` quote arbitrary bytes, including ``;`` and ``{``
* inside quotes a ``\\`` escapes the next character

The scanner keeps every token's exact line/column so downstream consumers can
produce precise diagnostics.
"""

from __future__ import annotations

from typing import List

from .model import (
    TK_EOF,
    TK_LBRACE,
    TK_RBRACE,
    TK_SEMI,
    TK_STRING,
    TK_WORD,
    ConfigError,
    Token,
)

#: Characters that terminate a bare word.
_WORD_STOP = set(" \t\r\n;{}")


class Lexer:
    """Convert raw configuration text into a flat token stream."""

    def __init__(self, text: str, file: str | None = None) -> None:
        self.text = text
        self.file = file
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens: List[Token] = []

    # -- position helpers ---------------------------------------------------

    def _advance(self, count: int = 1) -> None:
        for _ in range(count):
            if self.pos >= len(self.text):
                return
            if self.text[self.pos] == "\n":
                self.line += 1
                self.col = 1
            else:
                self.col += 1
            self.pos += 1

    def _peek(self, offset: int = 0) -> str:
        idx = self.pos + offset
        if idx >= len(self.text):
            return ""
        return self.text[idx]

    def _skip_ignorable(self) -> None:
        """Skip whitespace and comments, recording the latter as trivia."""
        while self.pos < len(self.text):
            ch = self.text[self.pos]
            if ch in " \t\r\n":
                self._advance()
                continue
            if ch == "#":
                start_line, start_col = self.line, self.col
                while self.pos < len(self.text) and self.text[self.pos] != "\n":
                    self._advance()
                # Comments are retained so the parser can attach them to the
                # directive that follows them.
                self.tokens.append(
                    Token("comment", _slice_line(self.text, start_line),
                          "", start_line, start_col)
                )
                continue
            break

    # -- public API ---------------------------------------------------------

    def tokenize(self) -> List[Token]:
        while self.pos < len(self.text):
            self._skip_ignorable()
            if self.pos >= len(self.text):
                break
            ch = self.text[self.pos]
            start_line, start_col = self.line, self.col
            if ch == ";":
                self.tokens.append(Token(TK_SEMI, ";", ";", start_line, start_col))
                self._advance()
            elif ch == "{":
                self.tokens.append(Token(TK_LBRACE, "{", "{", start_line, start_col))
                self._advance()
            elif ch == "}":
                self.tokens.append(Token(TK_RBRACE, "}", "}", start_line, start_col))
                self._advance()
            elif ch in ('"', "'"):
                self.tokens.append(self._read_quoted(ch, start_line, start_col))
            else:
                self.tokens.append(self._read_word(start_line, start_col))
        self.tokens.append(Token(TK_EOF, "", "", self.line, self.col))
        return self.tokens

    # -- token readers ------------------------------------------------------

    def _read_quoted(self, quote: str, line: int, col: int) -> Token:
        start = self.pos
        self._advance()  # opening quote
        buf: List[str] = []
        closed = False
        while self.pos < len(self.text):
            ch = self.text[self.pos]
            if ch == "\\" and self._peek(1):
                buf.append(self._peek(1))
                self._advance(2)
                continue
            if ch == quote:
                self._advance()
                closed = True
                break
            if ch == "\n":
                # nginx actually tolerates multi-line quoted strings; keep the
                # newline so re-rendering preserves the original layout.
                buf.append(ch)
                self._advance()
                continue
            buf.append(ch)
            self._advance()
        if not closed:
            raise ConfigError(
                "unterminated quoted string",
                file=self.file, line=line, col=col,
            )
        raw = self.text[start:self.pos]
        return Token(TK_STRING, "".join(buf), raw, line, col)

    def _read_word(self, line: int, col: int) -> Token:
        start = self.pos
        while self.pos < len(self.text):
            ch = self.text[self.pos]
            if ch in _WORD_STOP or ch in ('"', "'"):
                # A quote glued to a bare word (``root"/var/www"``) is legal in
                # nginx only when separated; stop the word so the parser can
                # surface a precise error instead of silently merging them.
                break
            self._advance()
        raw = self.text[start:self.pos]
        if not raw:
            # Defensive: never consume zero characters, otherwise we loop.
            raw = self.text[self.pos]
            self._advance()
        return Token(TK_WORD, raw, raw, line, col)


def _slice_line(text: str, line_no: int) -> str:
    lines = text.splitlines()
    if 1 <= line_no <= len(lines):
        return lines[line_no - 1].strip()
    return ""


def tokenize(text: str, file: str | None = None) -> List[Token]:
    """Convenience wrapper around :class:`Lexer`."""
    return Lexer(text, file).tokenize()
