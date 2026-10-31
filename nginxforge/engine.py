"""
The rule engine: registration, discovery, filtering and execution.

Rules are plain functions decorated with :func:`rule`. Keeping them as
functions (instead of classes) makes each audit readable and trivially
unit-testable, while the decorator handles all bookkeeping.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set

from .model import (
    SEVERITIES,
    ConfigFile,
    Finding,
    SEVERITY_RANK,
    sort_findings,
)

#: Signature every rule function must have.
RuleFn = Callable[["AuditContext"], Iterable[Finding]]

#: Categories used for grouping and for ``--select``/``--ignore`` filters.
CAT_CORRECTNESS = "correctness"
CAT_SECURITY = "security"
CAT_PERFORMANCE = "performance"
CAT_STYLE = "style"

CATEGORIES = (CAT_CORRECTNESS, CAT_SECURITY, CAT_PERFORMANCE, CAT_STYLE)


@dataclass
class Rule:
    """Metadata + implementation of a single audit rule."""

    id: str
    title: str
    severity: str
    category: str
    remediation: str
    fn: RuleFn
    enabled: bool = True

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Rule {self.id} {self.severity}/{self.category}>"


#: Global registry, populated by the :func:`rule` decorator at import time.
RULES: List[Rule] = []
_RULES_BY_ID: Dict[str, Rule] = {}


def rule(rule_id: str, title: str, severity: str = "warning",
         category: str = CAT_CORRECTNESS, remediation: str = "") -> Callable[[RuleFn], RuleFn]:
    """Register a rule function in the global registry."""

    def decorator(fn: RuleFn) -> RuleFn:
        if rule_id in _RULES_BY_ID:
            raise ValueError(f"duplicate rule id: {rule_id}")
        if severity not in SEVERITIES:
            raise ValueError(f"invalid severity for {rule_id}: {severity}")
        if category not in CATEGORIES:
            raise ValueError(f"invalid category for {rule_id}: {category}")
        obj = Rule(rule_id, title, severity, category, remediation, fn)
        RULES.append(obj)
        _RULES_BY_ID[rule_id] = obj
        fn.__rule__ = obj  # type: ignore[attr-defined]
        return fn

    return decorator


def get_rule(rule_id: str) -> Optional[Rule]:
    return _RULES_BY_ID.get(rule_id)


# --------------------------------------------------------------------------
# Runtime settings
# --------------------------------------------------------------------------

DEFAULT_SETTINGS: Dict[str, Any] = {
    # performance thresholds
    "max_keepalive_timeout": 75,
    "min_worker_connections": 1024,
    "min_client_max_body_size": "1m",
    # security
    "required_headers": [
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
    ],
    "forbidden_tls": ["SSLv2", "SSLv3", "TLSv1", "TLSv1.1"],
    "weak_cipher_tokens": ["NULL", "aNULL", "eNULL", "MD5", "RC4", "DES",
                           "3DES", "EXPORT", "LOW", "SEED", "IDEA", "PSK"],
    "sensitive_locations": [
        "/status", "/nginx_status", "/admin", "/phpmyadmin",
        "/.git", "/.env", "/server-status", "/metrics",
    ],
}


@dataclass
class AuditOptions:
    """Filters and thresholds applied to a single audit run."""

    select: Set[str] = field(default_factory=set)      # categories or rule ids
    ignore: Set[str] = field(default_factory=set)      # categories or rule ids
    min_severity: str = "info"
    fail_on: str = "error"
    settings: Dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_SETTINGS))
    disabled_rules: Set[str] = field(default_factory=set)

    def load_file(self, path: str) -> None:
        """Merge a JSON settings file into this option set."""
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError(f"{path}: expected a JSON object at the top level")
        for key, value in data.items():
            if key == "settings" and isinstance(value, dict):
                self.settings.update(value)
            elif key in ("select", "ignore", "disabled_rules"):
                getattr(self, key).update(value)
            elif key in ("min_severity", "fail_on"):
                setattr(self, key, value)


@dataclass
class AuditContext:
    """Everything a rule is allowed to look at."""

    config: ConfigFile
    options: AuditOptions

    # -- convenience shortcuts --------------------------------------------

    @property
    def tree(self) -> List[Any]:
        return self.config.tree

    @property
    def path(self) -> Optional[str]:
        return self.config.path

    def setting(self, name: str, default: Any = None) -> Any:
        return self.options.settings.get(name, default)

    def line_of(self, line: int) -> str:
        return self.config.line_text(line)

    def make(self, rule_obj: Rule, message: str, line: int = 0, col: int = 0,
             snippet: str = "", path: str = "", fix: Any = None,
             severity: Optional[str] = None, remediation: Optional[str] = None,
             **meta: Any) -> Finding:
        """Build a finding pre-filled from this context and the rule metadata."""
        return Finding(
            rule_id=rule_obj.id,
            title=rule_obj.title,
            severity=severity or rule_obj.severity,
            category=rule_obj.category,
            message=message,
            file=self.config.path,
            line=line,
            col=col,
            snippet=snippet or self.line_of(line),
            path=path,
            remediation=remediation if remediation is not None else rule_obj.remediation,
            fix=fix,
            meta=meta,
        )


@dataclass
class AuditResult:
    """Aggregated outcome of an audit run."""

    findings: List[Finding]
    syntax_errors: List[Any]
    files: List[str]
    rules_run: List[str]

    def counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {name: 0 for name in SEVERITIES}
        for finding in self.findings:
            out[finding.severity] = out.get(finding.severity, 0) + 1
        return out

    def by_rule(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for finding in self.findings:
            out[finding.rule_id] = out.get(finding.rule_id, 0) + 1
        return out

    def by_category(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for finding in self.findings:
            out[finding.category] = out.get(finding.category, 0) + 1
        return out

    @property
    def ok(self) -> bool:
        return not self.syntax_errors


# --------------------------------------------------------------------------
# Execution
# --------------------------------------------------------------------------

def _rule_selected(obj: Rule, options: AuditOptions) -> bool:
    if obj.id in options.disabled_rules or obj.id in options.ignore:
        return False
    if obj.category in options.ignore:
        return False
    if not obj.enabled:
        return False
    if options.select:
        if obj.id in options.select or obj.category in options.select:
            pass
        else:
            return False
    if SEVERITY_RANK.get(obj.severity, 9) > SEVERITY_RANK.get(options.min_severity, 0):
        return False
    return True


def audit(configs: Sequence[ConfigFile],
          options: Optional[AuditOptions] = None) -> AuditResult:
    """Run every enabled rule against every parsed configuration file."""
    options = options or AuditOptions()
    findings: List[Finding] = []
    syntax_errors: List[Any] = []
    rules_run: List[str] = []
    files: List[str] = []

    for config in configs:
        files.append(config.path or "<stdin>")
        syntax_errors.extend(config.errors)
        ctx = AuditContext(config=config, options=options)
        for obj in RULES:
            if not _rule_selected(obj, options):
                continue
            if obj.id not in rules_run:
                rules_run.append(obj.id)
            try:
                for finding in obj.fn(ctx) or []:
                    if finding.file is None:
                        finding.file = config.path
                    if not finding.snippet and finding.line:
                        finding.snippet = config.line_text(finding.line)
                    findings.append(finding)
            except Exception as exc:  # pragma: no cover - defensive
                # A crashing rule must never take down the whole audit.
                findings.append(Finding(
                    rule_id=obj.id,
                    title=obj.title,
                    severity="info",
                    category=obj.category,
                    message=f"rule raised an unexpected error: {exc!r}",
                    file=config.path,
                ))

    return AuditResult(
        findings=sort_findings(findings),
        syntax_errors=syntax_errors,
        files=files,
        rules_run=rules_run,
    )


def should_fail(result: AuditResult, fail_on: str) -> bool:
    """Decide the process exit code from the configured ``fail_on`` level."""
    threshold = SEVERITY_RANK.get(fail_on)
    if threshold is None:
        return False
    if result.syntax_errors:
        return True
    return any(
        SEVERITY_RANK.get(f.severity, 9) <= threshold for f in result.findings
    )


def load_default_rules() -> None:
    """Import every rule module so the registry is populated."""
    from .rules import correctness, performance, security, style  # noqa: F401


def discover_configs(paths: Sequence[str],
                     patterns: Sequence[str] = (".conf",)) -> List[str]:
    """Expand directories into a sorted list of configuration files."""
    found: List[str] = []
    for path in paths:
        if os.path.isdir(path):
            for root, dirs, filenames in os.walk(path):
                dirs[:] = [d for d in dirs
                           if d not in {".git", "node_modules", "__pycache__"}]
                for name in sorted(filenames):
                    if name.endswith(tuple(patterns)) or name == "nginx.conf":
                        found.append(os.path.join(root, name))
        else:
            found.append(path)
    return sorted(set(found))
