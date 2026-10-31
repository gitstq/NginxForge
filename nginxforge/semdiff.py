"""
Semantic diff between two nginx configurations.

A plain ``diff`` on nginx files is almost useless: re-ordering two independent
directives, re-indenting a block or moving a comment all change the bytes while
leaving the *meaning* untouched. This module compares the parsed trees instead.

Two things are deliberately ignored:

* whitespace, indentation and comments
* the order of sibling directives (nginx only cares about a handful of
  overlapping rules, and those are reported separately by the audit)

What *is* compared:

* the block hierarchy (``http > server > location``)
* directive names and their arguments
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Tuple

from .model import ConfigFile, Directive


@dataclass(frozen=True)
class Entry:
    """A single canonicalised directive."""

    path: str          # e.g. "http > server[example.com] > location /api"
    name: str
    args: Tuple[str, ...]
    line: int = 0

    @property
    def signature(self) -> Tuple[str, str, Tuple[str, ...]]:
        return (self.path, self.name, self.args)

    @property
    def identity(self) -> Tuple[str, str]:
        """Identity ignoring the arguments - used to detect *changed* lines."""
        return (self.path, self.name)

    def render(self) -> str:
        args = " ".join(self.args)
        return f"{self.path} :: {self.name} {args}".rstrip()


def _block_label(node: Directive) -> str:
    """Stable label for a block, including its key arguments when obvious."""
    if not node.args:
        return node.name
    if node.name in ("location", "upstream", "if", "map", "geo", "limit_except"):
        return f"{node.name}[{' '.join(node.args)}]"
    if node.name == "server":
        server_name = node.find_first("server_name")
        label = server_name.args[0] if (server_name and server_name.args) else "_"
        return f"server[{label}]"
    return node.name


def _canonical_path(node: Directive) -> str:
    chain: List[str] = []
    current: Optional[Directive] = node.parent
    while current is not None:
        chain.append(_block_label(current))
        current = current.parent
    chain.reverse()
    return " > ".join(chain) if chain else "main"


def canonicalize(config: ConfigFile) -> List[Entry]:
    """Flatten a configuration into a deterministic, order-independent list."""
    entries: List[Entry] = []

    def visit(node: Directive) -> None:
        path = _canonical_path(node)
        if node.block is None:
            entries.append(Entry(path, node.name, tuple(node.args), node.line))
        else:
            entries.append(Entry(path, node.name, tuple(node.args), node.line))
            for child in node.block:
                visit(child)

    for node in config.tree:
        visit(node)
    # Sorting by (path, name, args) removes sibling ordering noise.
    entries.sort(key=lambda e: (e.path, e.name, e.args))
    return entries


def render_canonical(config: ConfigFile) -> str:
    """Render the canonical form as text (useful for eyeballing a diff)."""
    return "\n".join(entry.render() for entry in canonicalize(config))


@dataclass
class DiffResult:
    """Outcome of comparing two configurations."""

    added: List[Entry] = field(default_factory=list)
    removed: List[Entry] = field(default_factory=list)
    changed: List[Tuple[Entry, Entry]] = field(default_factory=list)
    text: str = ""
    left_label: str = "a"
    right_label: str = "b"

    @property
    def identical(self) -> bool:
        return not (self.added or self.removed or self.changed)

    @property
    def change_count(self) -> int:
        return len(self.added) + len(self.removed) + len(self.changed)

    def summary(self) -> str:
        if self.identical:
            return "configurations are semantically identical"
        return (f"{len(self.added)} added, {len(self.removed)} removed, "
                f"{len(self.changed)} changed")


def compare(left: ConfigFile, right: ConfigFile,
            left_label: Optional[str] = None,
            right_label: Optional[str] = None) -> DiffResult:
    """Compare two parsed configurations semantically."""
    a = canonicalize(left)
    b = canonicalize(right)

    left_label = left_label or (left.path or "a")
    right_label = right_label or (right.path or "b")

    by_id_a: Dict[Tuple[str, str], List[Entry]] = {}
    by_id_b: Dict[Tuple[str, str], List[Entry]] = {}
    for entry in a:
        by_id_a.setdefault(entry.identity, []).append(entry)
    for entry in b:
        by_id_b.setdefault(entry.identity, []).append(entry)

    result = DiffResult(left_label=left_label, right_label=right_label)

    keys = sorted(set(by_id_a) | set(by_id_b), key=lambda k: (k[0], k[1]))
    for key in keys:
        left_entries = by_id_a.get(key, [])
        right_entries = by_id_b.get(key, [])
        left_args = [e.args for e in left_entries]
        right_args = [e.args for e in right_entries]
        common = min(len(left_entries), len(right_entries))

        for idx in range(common):
            if left_args[idx] != right_args[idx]:
                # Try to pair the closest argument list instead of a blind
                # positional match, so re-ordered siblings do not look changed.
                best = _best_match(left_entries[idx], right_entries[common:])
                if best is not None:
                    result.changed.append((left_entries[idx], best))
                else:
                    result.changed.append((left_entries[idx], right_entries[idx]))

        for entry in left_entries[common:]:
            result.removed.append(entry)
        for entry in right_entries[common:]:
            result.added.append(entry)

    result.text = "\n".join(difflib.unified_diff(
        [e.render() for e in a],
        [e.render() for e in b],
        fromfile=left_label,
        tofile=right_label,
        lineterm="",
        n=2,
    ))
    return result


def _best_match(target: Entry, candidates: List[Entry]) -> Optional[Entry]:
    """Pick the candidate with the most arguments in common with ``target``."""
    if not candidates:
        return None
    target_set = set(target.args)
    best = max(candidates, key=lambda c: len(target_set & set(c.args)))
    return best


def iter_entries(config: ConfigFile) -> Iterator[Entry]:
    for entry in canonicalize(config):
        yield entry
