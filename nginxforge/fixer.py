"""
Automatic, reviewable fixes.

Every fix is expressed as a line oriented patch against the original file, so
the result can always be shown as a unified diff *before* anything is written
to disk. Nothing is ever applied implicitly.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set

from .model import (
    FIX_DELETE,
    FIX_INSERT_AFTER,
    FIX_INSERT_BEFORE,
    FIX_REPLACE,
    ConfigFile,
    Finding,
)

#: Modes that only rewrite an existing line (never add or remove content).
SAFE_MODES = frozenset({FIX_REPLACE})


@dataclass
class Change:
    """One pending edit, resolved to absolute 1-based line numbers."""

    line: int
    mode: str
    text: str            # may contain embedded newlines for multi-line inserts
    rule_id: str
    summary: str
    severity: str

    def lines(self) -> List[str]:
        return self.text.split("\n") if self.text else []


@dataclass
class FixPlan:
    """All pending edits for a single file."""

    file: str
    changes: List[Change] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.changes)


def build_plan(findings: Sequence[Finding],
               safe_only: bool = False,
               rule_filter: Optional[Set[str]] = None) -> Dict[str, FixPlan]:
    """Group applicable fixes per file.

    ``safe_only`` drops insertions/deletions and keeps pure rewrites, which is
    the conservative default for unattended runs.
    """
    plans: Dict[str, FixPlan] = {}
    used_lines: Dict[str, Set[int]] = {}

    for finding in sorted(findings, key=lambda f: (f.file or "", f.line, f.rule_id)):
        if finding.fix is None or not finding.line:
            continue
        if rule_filter and finding.rule_id not in rule_filter:
            continue
        if safe_only and finding.fix.mode not in SAFE_MODES:
            continue
        key = finding.file or "<stdin>"
        if finding.line in used_lines.setdefault(key, set()):
            continue  # one edit per line keeps the result predictable
        used_lines[key].add(finding.line)
        plan = plans.setdefault(key, FixPlan(file=key))
        plan.changes.append(Change(
            line=finding.line,
            mode=finding.fix.mode,
            text=finding.fix.new_line,
            rule_id=finding.rule_id,
            summary=finding.fix.summary,
            severity=finding.severity,
        ))
    return plans


def _apply_to_text(text: str, changes: Sequence[Change]) -> str:
    lines = text.splitlines()
    # Work bottom-up so earlier line numbers stay valid.
    for change in sorted(changes, key=lambda c: c.line, reverse=True):
        idx = change.line - 1
        if not (0 <= idx < len(lines)):
            continue
        original = lines[idx]
        indent = original[: len(original) - len(original.lstrip())]
        payload = [indent + part.strip() for part in change.lines()] or [""]
        if change.mode == FIX_REPLACE:
            lines[idx: idx + 1] = payload
        elif change.mode == FIX_DELETE:
            del lines[idx]
        elif change.mode == FIX_INSERT_BEFORE:
            lines[idx: idx] = payload
        elif change.mode == FIX_INSERT_AFTER:
            lines[idx + 1: idx + 1] = payload
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def apply_plan(source: str, changes: Sequence[Change]) -> str:
    """Apply ``changes`` to ``source`` and return the new text."""
    return _apply_to_text(source, changes)


def apply_to_config(config: ConfigFile, changes: Sequence[Change]) -> str:
    return _apply_to_text(config.text, changes)


def unified_diff(config: ConfigFile, changes: Sequence[Change],
                 label: Optional[str] = None) -> str:
    """Render the pending edits as a unified diff (dry-run output)."""
    before = config.text.splitlines()
    after = _apply_to_text(config.text, changes).splitlines()
    return "\n".join(difflib.unified_diff(
        before, after,
        fromfile=f"{label or config.path or 'config'} (before)",
        tofile=f"{label or config.path or 'config'} (after)",
        lineterm="",
        n=2,
    ))


def total_changes(plans: Iterable[FixPlan]) -> int:
    return sum(plan.count for plan in plans)
