"""
Output reporters.

Each reporter turns an :class:`~nginxforge.engine.AuditResult` into a string.
The registry maps the CLI's ``--format`` value to the rendering function.
"""

from __future__ import annotations

from typing import Callable, Dict

from ..engine import AuditResult
from . import html as htmlfmt
from . import jsonfmt, markdown, sarif, text

__all__ = ["htmlfmt", "jsonfmt", "markdown", "sarif", "text", "REGISTRY", "render"]

#: Supported ``--format`` values.
REGISTRY: Dict[str, Callable[..., str]] = {
    "text": text.render,
    "json": jsonfmt.render,
    "sarif": sarif.render,
    "markdown": markdown.render,
    "md": markdown.render,
    "html": htmlfmt.render,
}

#: Formats that should never be coloured / interactive.
MACHINE_FORMATS = frozenset({"json", "sarif"})


def render(fmt: str, result: AuditResult, version: str = "1.0.0", **kwargs) -> str:
    """Render ``result`` using the reporter registered under ``fmt``."""
    try:
        fn = REGISTRY[fmt]
    except KeyError:
        raise KeyError(
            f"unknown format '{fmt}' - available: {', '.join(sorted(REGISTRY))}"
        ) from None
    return fn(result, version, **kwargs)


def formats() -> list:
    return sorted(set(REGISTRY))
