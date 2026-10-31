"""
Core data model for the NginxForge configuration AST.

The whole toolkit is built on top of a very small, dependency-free object model:

    ConfigFile   -> one parsed ``*.conf`` file
      Directive  -> ``name args... ;``  or  ``name args... { ... }``
        Token    -> the raw lexical unit, always carrying line/column info

Every node keeps its source position so that auditors, fixers and reporters can
point the user at an exact line without re-scanning the original text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Sequence

# --------------------------------------------------------------------------
# Lexical layer
# --------------------------------------------------------------------------

#: Token kinds produced by :mod:`nginxforge.lexer`.
TK_WORD = "word"          # bare word / variable / number
TK_STRING = "string"      # single or double quoted literal
TK_LBRACE = "{"
TK_RBRACE = "}"
TK_SEMI = ";"
TK_EOF = "eof"


@dataclass
class Token:
    """A single lexical unit with full source position information."""

    kind: str
    value: str            # decoded value (quotes stripped)
    raw: str              # exact source text
    line: int             # 1-based line number
    col: int              # 1-based column number

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"Token({self.kind!r}, {self.value!r} @ {self.line}:{self.col})"


class ConfigError(Exception):
    """Raised when the configuration cannot be lexed or parsed."""

    def __init__(self, message: str, file: Optional[str] = None,
                 line: Optional[int] = None, col: Optional[int] = None) -> None:
        super().__init__(message)
        self.message = message
        self.file = file
        self.line = line
        self.col = col

    def __str__(self) -> str:
        head = self.message
        if self.file:
            head = f"{self.file}: {head}"
        if self.line is not None:
            head += f" (line {self.line}"
            if self.col is not None:
                head += f", column {self.col}"
            head += ")"
        return head


# --------------------------------------------------------------------------
# Syntactic layer
# --------------------------------------------------------------------------

#: Context name of the top-level (pseudo) block.
ROOT_CONTEXT = "main"


@dataclass
class Directive:
    """One nginx directive, optionally owning a nested block."""

    name: str
    args: List[str] = field(default_factory=list)
    line: int = 1
    col: int = 1
    block: Optional[List["Directive"]] = None
    parent: Optional["Directive"] = None
    file: Optional[str] = None
    #: Comment lines immediately preceding this directive (best effort).
    comment: Optional[str] = None

    # -- structural helpers -------------------------------------------------

    @property
    def is_block(self) -> bool:
        return self.block is not None

    @property
    def context(self) -> str:
        """The *owning* context name, e.g. ``http``, ``server``, ``location``."""
        if self.parent is None:
            return ROOT_CONTEXT
        return self.parent.name

    def context_path(self) -> List[str]:
        """Full chain of block names from the root down to this directive."""
        chain: List[str] = []
        node: Optional[Directive] = self.parent
        while node is not None:
            chain.append(node.name)
            node = node.parent
        chain.reverse()
        return chain or [ROOT_CONTEXT]

    def path_label(self) -> str:
        """Human readable location, e.g. ``http > server > location /api``."""
        chain: List[str] = []

        def label_of(node: "Directive") -> str:
            text = node.name
            if node.args:
                text += " " + " ".join(node.args)
            return text

        node: Optional[Directive] = self
        while node is not None:
            chain.append(label_of(node))
            node = node.parent
        chain.reverse()
        return " > ".join(chain) if chain else ROOT_CONTEXT

    def ancestors(self) -> Iterator["Directive"]:
        node = self.parent
        while node is not None:
            yield node
            node = node.parent

    def ancestor_named(self, name: str) -> Optional["Directive"]:
        for node in self.ancestors():
            if node.name == name:
                return node
        return None

    def in_context(self, *names: str) -> bool:
        """True when any ancestor block is named one of ``names``."""
        return any(node.name in names for node in self.ancestors())

    # -- traversal ----------------------------------------------------------

    def walk(self) -> Iterator["Directive"]:
        """Depth-first pre-order traversal including ``self``."""
        yield self
        if self.block:
            for child in self.block:
                yield from child.walk()

    def children(self, name: Optional[str] = None) -> List["Directive"]:
        if not self.block:
            return []
        if name is None:
            return list(self.block)
        return [d for d in self.block if d.name == name]

    def find_all(self, name: str) -> Iterator["Directive"]:
        for node in self.walk():
            if node.name == name:
                yield node

    def find_first(self, name: str) -> Optional["Directive"]:
        for node in self.find_all(name):
            return node
        return None

    def has(self, name: str) -> bool:
        return self.find_first(name) is not None

    # -- rendering ----------------------------------------------------------

    def source_line(self) -> str:
        """Best effort reconstruction of the directive as written."""
        args = " ".join(_quote_if_needed(a) for a in self.args)
        head = f"{self.name} {args}".strip()
        if self.block is None:
            return f"{head};"
        return f"{head} {{"

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Directive {self.name} {self.args} @{self.line}>"


def _quote_if_needed(value: str) -> str:
    if value == "" or any(ch in value for ch in " \t\r\n;{}\"'\\"):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


@dataclass
class ConfigFile:
    """A parsed nginx configuration file."""

    path: Optional[str]
    text: str
    tree: List[Directive]
    errors: List[ConfigError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def walk(self) -> Iterator[Directive]:
        for node in self.tree:
            yield from node.walk()

    def find_all(self, name: str) -> Iterator[Directive]:
        for node in self.walk():
            if node.name == name:
                yield node

    def find_first(self, name: str) -> Optional[Directive]:
        for node in self.find_all(name):
            return node
        return None

    def line_text(self, line: int) -> str:
        lines = self.text.splitlines()
        if 1 <= line <= len(lines):
            return lines[line - 1]
        return ""


# --------------------------------------------------------------------------
# Findings
# --------------------------------------------------------------------------

#: Severity levels, ordered from most to least severe.
SEVERITIES = ("error", "warning", "info")
SEVERITY_RANK = {name: idx for idx, name in enumerate(SEVERITIES)}


#: How a :class:`Fix` should be applied to the source text.
#: ``replace`` rewrites the line, ``delete`` drops it and the ``insert_*``
#: modes add a brand new line relative to the reported line.
FIX_REPLACE = "replace"
FIX_DELETE = "delete"
FIX_INSERT_BEFORE = "insert_before"
FIX_INSERT_AFTER = "insert_after"


@dataclass
class Fix:
    """A machine applicable, reversible patch on the source text."""

    #: One of the ``FIX_*`` constants above.
    mode: str
    #: Replacement/inserted text (indentation of the target line is reused).
    new_line: str
    #: Short human description of what the fix does.
    summary: str


@dataclass
class Finding:
    """A single audit result."""

    rule_id: str
    title: str
    severity: str
    category: str
    message: str
    file: Optional[str] = None
    line: int = 0
    col: int = 0
    snippet: str = ""
    path: str = ""
    remediation: str = ""
    fix: Optional[Fix] = None
    #: Extra structured payload (used by JSON/SARIF reporters).
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def location(self) -> str:
        if self.file and self.line:
            return f"{self.file}:{self.line}"
        if self.file:
            return str(self.file)
        return f"line {self.line}" if self.line else "-"

    def to_dict(self, include_fix: bool = True) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "rule_id": self.rule_id,
            "title": self.title,
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
            "file": self.file,
            "line": self.line,
            "col": self.col,
            "snippet": self.snippet,
            "path": self.path,
            "remediation": self.remediation,
        }
        if include_fix and self.fix is not None:
            data["fix"] = {
                "summary": self.fix.summary,
                "new_line": self.fix.new_line,
            }
        return data


def sort_findings(findings: Sequence[Finding]) -> List[Finding]:
    """Deterministic ordering: severity, then file, then line, then rule."""
    return sorted(
        findings,
        key=lambda f: (
            SEVERITY_RANK.get(f.severity, len(SEVERITIES)),
            f.file or "",
            f.line,
            f.col,
            f.rule_id,
        ),
    )
