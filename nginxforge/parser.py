"""
Recursive-descent parser turning a token stream into a directive tree.

Design goals
------------
1. **Fault tolerant.** A syntax error must never abort the whole audit: the
   parser records a :class:`~nginxforge.model.ConfigError` and resynchronises so
   that every remaining directive is still inspected by the rule engine.
2. **Position preserving.** Every directive keeps line/column and the raw source
   line, which the reporters and the fixer rely on.
3. **Deterministic.** Same input => byte-identical tree, which makes the
   semantic diff reproducible.
"""

from __future__ import annotations

from typing import List, Optional

from .directives import BLOCK_DIRECTIVES, arity
from .lexer import tokenize
from .model import (
    TK_EOF,
    TK_LBRACE,
    TK_RBRACE,
    TK_SEMI,
    TK_STRING,
    TK_WORD,
    ConfigError,
    ConfigFile,
    Directive,
    ROOT_CONTEXT,
    Token,
)


class Parser:
    """Build a :class:`ConfigFile` out of raw nginx configuration text."""

    def __init__(self, text: str, file: str | None = None) -> None:
        self.text = text
        self.file = file
        self.tokens: List[Token] = tokenize(text, file)
        self.idx = 0
        self.errors: List[ConfigError] = []
        self._pending_comment: Optional[str] = None

    # -- token access -------------------------------------------------------

    def _cur(self) -> Token:
        return self.tokens[self.idx]

    def _advance(self) -> Token:
        tok = self.tokens[self.idx]
        if tok.kind != TK_EOF:
            self.idx += 1
        return tok

    def _at(self, kind: str) -> bool:
        return self._cur().kind == kind

    # -- parsing ------------------------------------------------------------

    def parse(self) -> ConfigFile:
        tree = self._parse_block_body(terminator=TK_EOF, parent=None)
        if self._cur().kind != TK_EOF:  # pragma: no cover - defensive
            tok = self._cur()
            self._error("unexpected trailing token %r" % tok.raw, tok)
        return ConfigFile(path=self.file, text=self.text, tree=tree,
                          errors=self.errors)

    def _parse_block_body(self, terminator: str,
                          parent: Optional[Directive]) -> List[Directive]:
        out: List[Directive] = []
        while True:
            tok = self._cur()
            if tok.kind == TK_EOF:
                break
            if tok.kind == terminator:
                break
            if tok.kind == "comment":
                self._pending_comment = tok.value.lstrip("#").strip()
                self._advance()
                continue
            if tok.kind == TK_RBRACE and terminator != TK_RBRACE:
                self._error("unexpected '}' - no matching block is open", tok)
                self._advance()
                continue
            if tok.kind in (TK_SEMI, TK_LBRACE):
                self._error(f"unexpected '{tok.raw}' - a directive name was expected",
                            tok)
                self._advance()
                continue
            node = self._parse_directive(parent)
            if node is not None:
                out.append(node)
            self._pending_comment = None
        return out

    def _parse_directive(self, parent: Optional[Directive]) -> Optional[Directive]:
        head = self._cur()
        if head.kind not in (TK_WORD, TK_STRING):
            self._error(f"unexpected token {head.raw!r}", head)
            self._advance()
            return None

        name = head.value
        line, col = head.line, head.col
        self._advance()

        args: List[str] = []
        while True:
            tok = self._cur()
            if tok.kind in (TK_SEMI, TK_LBRACE, TK_RBRACE, TK_EOF):
                break
            if tok.kind == "comment":
                # A comment trailing the arguments is not part of them.
                self._advance()
                continue
            args.append(tok.value)
            self._advance()

        node = Directive(
            name=name, args=args, line=line, col=col,
            parent=parent, file=self.file,
            comment=self._pending_comment,
        )

        tok = self._cur()
        if tok.kind == TK_LBRACE:
            self._advance()
            if self._cannot_take_a_block(node):
                self._error(
                    f"directive '{name}' is missing a ';' before '{{'", head,
                )
            node.block = self._parse_block_body(TK_RBRACE, node)
            if self._at(TK_RBRACE):
                self._advance()
            else:
                self._error(
                    f"unterminated block '{name}' - missing '}}'", head,
                )
        elif tok.kind == TK_SEMI:
            self._advance()
        elif tok.kind in (TK_EOF, TK_RBRACE):
            self._error(
                f"directive '{name}' is missing a terminating ';'", head,
            )
        return node

    # -- diagnostics --------------------------------------------------------

    @staticmethod
    def _cannot_take_a_block(node: Directive) -> bool:
        """Heuristic for the very common "forgot the semicolon" mistake.

        ``server_tokens off { ... }`` parses fine token-wise, but nginx would
        reject it: the directive simply cannot own a block.
        """
        if node.name in BLOCK_DIRECTIVES:
            return False
        spec = arity(node.name)
        if spec is None:
            return False  # unknown directive - stay quiet
        low, high = spec
        return len(node.args) >= low

    def _error(self, message: str, tok: Token) -> None:
        self.errors.append(
            ConfigError(message, file=self.file, line=tok.line, col=tok.col)
        )


def parse(text: str, file: str | None = None) -> ConfigFile:
    """Parse ``text`` into a :class:`ConfigFile` (never raises on bad input)."""
    return Parser(text, file).parse()


def parse_file(path: str, encoding: str = "utf-8") -> ConfigFile:
    """Parse a configuration file from disk."""
    with open(path, "r", encoding=encoding, errors="replace") as handle:
        return parse(handle.read(), path)


def render(tree: List[Directive], indent: str = "    ", level: int = 0) -> str:
    """Pretty-print a directive tree back into nginx syntax."""
    out: List[str] = []
    pad = indent * level
    for node in tree:
        out.append(pad + node.source_line())
        if node.block is not None:
            out.append(render(node.block, indent, level + 1))
            out.append(pad + "}")
    return "\n".join(out)


__all__ = [
    "Parser", "parse", "parse_file", "render", "ROOT_CONTEXT",
]
