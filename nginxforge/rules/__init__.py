"""
Rule package.

Importing this package registers every built-in rule in
:data:`nginxforge.engine.RULES`. The modules are imported in a fixed order so
that rule ids stay grouped by category.

============================  ================================================
Range                         Meaning
============================  ================================================
``NGX0xx``                    correctness - nginx would reject it, or the
                              behaviour differs from what the author meant
``NGX1xx``                    security hardening
``NGX2xx``                    performance / throughput
``NGX3xx``                    style and maintainability
============================  ================================================
"""

from __future__ import annotations

from . import correctness, helpers, performance, security, style  # noqa: F401

__all__ = ["correctness", "performance", "security", "style", "helpers"]
