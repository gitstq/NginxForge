"""
JSON reporter - the machine readable contract of NginxForge.

Stable keys, sorted output and no surprises: this is what CI pipelines and
dashboards should consume.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from ..engine import AuditResult


def render(result: AuditResult, version: str = "1.0.0") -> str:
    payload: Dict[str, Any] = {
        "tool": {
            "name": "nginxforge",
            "version": version,
        },
        "files": result.files,
        "rules_run": sorted(result.rules_run),
        "summary": {
            "total": len(result.findings),
            "by_severity": result.counts(),
            "by_category": result.by_category(),
            "by_rule": dict(sorted(result.by_rule().items())),
            "syntax_errors": len(result.syntax_errors),
        },
        "syntax_errors": [
            {
                "message": err.message,
                "file": err.file,
                "line": err.line,
                "col": err.col,
            }
            for err in result.syntax_errors
        ],
        "findings": [finding.to_dict() for finding in result.findings],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False)


def load(text: str) -> Dict[str, Any]:
    """Parse a report previously produced by :func:`render`."""
    return json.loads(text)


def findings_only(result: AuditResult) -> List[Dict[str, Any]]:
    return [finding.to_dict() for finding in result.findings]
