"""
SARIF 2.1.0 reporter.

Uploading this to GitHub code scanning (or any SARIF viewer) renders the audit
inline on pull requests.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from ..engine import AuditResult, RULES, get_rule

_SCHEMA = ("https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/"
           "Schemata/sarif-schema-2.1.0.json")

_SEVERITY_TO_LEVEL = {
    "error": "error",
    "warning": "warning",
    "info": "note",
}

_SEVERITY_TO_RANK = {
    "error": 9.0,
    "warning": 5.0,
    "info": 1.0,
}


def _driver(version: str, rule_ids: List[str]) -> Dict[str, Any]:
    rules: List[Dict[str, Any]] = []
    for rule_id in sorted(set(rule_ids)):
        obj = get_rule(rule_id)
        if obj is None:
            continue
        rules.append({
            "id": obj.id,
            "name": obj.id,
            "shortDescription": {"text": obj.title},
            "fullDescription": {"text": obj.remediation or obj.title},
            "defaultConfiguration": {"level": _SEVERITY_TO_LEVEL.get(obj.severity, "note")},
            "properties": {
                "category": obj.category,
                "severity": obj.severity,
                "security-severity": _SEVERITY_TO_RANK.get(obj.severity, 1.0),
                "tags": ["nginx", "configuration", obj.category],
            },
            "helpUri": f"https://nginx.org/en/docs/",
        })
    return {
        "name": "nginxforge",
        "semanticVersion": version,
        "informationUri": "https://github.com/gitstq/NginxForge",
        "rules": rules,
    }


def render(result: AuditResult, version: str = "1.0.0") -> str:
    results: List[Dict[str, Any]] = []
    seen_rules = list(result.rules_run)

    for finding in result.findings:
        uri = finding.file or "nginx.conf"
        results.append({
            "ruleId": finding.rule_id,
            "level": _SEVERITY_TO_LEVEL.get(finding.severity, "note"),
            "message": {"text": finding.message},
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": {"uri": uri},
                    "region": {
                        "startLine": max(finding.line, 1),
                        "startColumn": max(finding.col, 1),
                        "snippet": {"text": finding.snippet.strip()},
                    },
                },
                "logicalLocations": ([{"fullyQualifiedName": finding.path}]
                                     if finding.path else []),
            }],
            "fixes": ([{
                "description": {"text": finding.fix.summary},
            }] if finding.fix else []),
            "properties": {
                "category": finding.category,
                "remediation": finding.remediation,
            },
        })

    payload = {
        "$schema": _SCHEMA,
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": _driver(version, seen_rules)},
            "results": results,
        }],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)
