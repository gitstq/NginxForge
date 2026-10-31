"""
Human readable terminal reporter.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from ..engine import AuditResult
from ..model import Finding

_USE_COLOR = True

_RESET = "\033[0m"
_STYLES = {
    "error": "\033[1;31m",
    "warning": "\033[1;33m",
    "info": "\033[1;36m",
    "dim": "\033[2m",
    "bold": "\033[1m",
    "ok": "\033[1;32m",
}

_GLYPHS = {
    "error": "✖",
    "warning": "⚠",
    "info": "ℹ",
}


def set_color(enabled: bool) -> None:
    """Enable or disable ANSI colour globally."""
    global _USE_COLOR
    _USE_COLOR = enabled


def _style(text: str, name: str) -> str:
    if not _USE_COLOR:
        return text
    return f"{_STYLES.get(name, '')}{text}{_RESET}"


def render(result: AuditResult, version: str = "1.0.0",
           show_fix_hint: bool = True) -> str:
    out: List[str] = []
    counts = result.counts()

    out.append(_style(f"nginxforge {version}", "bold") +
               " - nginx configuration audit")
    out.append(_style(
        f"scanned {len(result.files)} file(s) · "
        f"{len(result.rules_run)} rule(s) · "
        f"{len(result.findings)} finding(s)", "dim"))
    out.append("")

    for error in result.syntax_errors:
        out.append(_style(f"✖ syntax error: {error}", "error"))
    if result.syntax_errors:
        out.append("")

    grouped: Dict[Optional[str], List[Finding]] = {}
    for finding in result.findings:
        grouped.setdefault(finding.file, []).append(finding)

    for file_name in sorted(grouped, key=lambda k: (k is None, k or "")):
        findings = grouped[file_name]
        out.append(_style(f"── {file_name or '<stdin>'} " + "─" * 8, "bold"))
        for finding in findings:
            glyph = _GLYPHS.get(finding.severity, "•")
            head = (f"  {_style(glyph, finding.severity)} "
                    f"{_style(finding.rule_id, 'bold')}  {finding.title}")
            out.append(head)
            location = finding.location
            if finding.path:
                location += f"  ({finding.path})"
            out.append(f"      {_style(location, 'dim')}")
            if finding.snippet:
                out.append(f"      {finding.snippet.strip()}")
            out.append(f"      {finding.message}")
            if finding.remediation:
                out.append(_style(f"      ↳ {finding.remediation}", "dim"))
            if show_fix_hint and finding.fix is not None:
                out.append(_style(f"      ✚ fix: {finding.fix.summary}", "ok"))
            out.append("")
        out.append("")

    out.append(_style("── summary " + "─" * 20, "bold"))
    if result.findings:
        out.append("  " + "  ".join(
            _style(f"{name}: {counts.get(name, 0)}", name)
            for name in ("error", "warning", "info")
        ))
        by_cat = result.by_category()
        out.append(_style("  by category: " +
                          ", ".join(f"{k} {v}" for k, v in sorted(by_cat.items())),
                          "dim"))
    else:
        out.append(_style("  ✔ no findings - configuration looks good", "ok"))
    out.append("")
    return "\n".join(out)
