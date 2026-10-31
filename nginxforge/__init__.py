"""
NginxForge - zero-dependency, offline-first nginx configuration toolkit.

NginxForge parses nginx configuration files into an AST, audits them against a
growing set of correctness / security / performance / style rules, produces
reviewable automatic fixes, diffs configurations *semantically* and generates
best-practice configuration templates.

Quick start (library)::

    from nginxforge import parse_file, audit, AuditOptions
    from nginxforge.engine import load_default_rules
    from nginxforge.reporters import render

    load_default_rules()
    result = audit([parse_file("nginx.conf")], AuditOptions())
    print(render("text", result))

Quick start (CLI)::

    nginxforge audit /etc/nginx/nginx.conf
    nginxforge gen --template reverse-proxy --domain example.com --out nginx.conf

The package has **no third-party dependencies** and never performs network
calls: it is safe to run inside air-gapped environments and CI runners.
"""

from __future__ import annotations

from .model import (
    SEVERITIES,
    ConfigError,
    ConfigFile,
    Directive,
    Finding,
)
from .parser import parse, parse_file
from .semdiff import compare

__version__ = "1.0.0"

__all__ = [
    "__version__",
    "parse",
    "parse_file",
    "compare",
    "ConfigFile",
    "ConfigError",
    "Directive",
    "Finding",
    "SEVERITIES",
]


def load_rules() -> None:
    """Register every built-in rule (imported lazily to keep startup fast)."""
    from .engine import load_default_rules
    load_default_rules()
