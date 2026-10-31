"""
Style / maintainability rules (``NGX3xx``).

Low severity by design: these keep a configuration readable and diff-friendly,
which matters a lot once more than one person edits the file.
"""

from __future__ import annotations

import re
from typing import Iterator

from ..engine import CAT_STYLE, rule
from ..model import Directive

#: Absolute paths that are conventional in nginx deployments.
TRUSTED_PREFIXES = (
    "/etc/nginx", "/var/www", "/usr/share/nginx", "/var/cache/nginx",
    "/var/log/nginx", "/run", "/usr/local/nginx", "/var/run",
)

_MAX_LINE_LENGTH = 200


def _prefix_of(text: str) -> str:
    return text[: len(text) - len(text.lstrip())]


# ---------------------------------------------------------------------------
# NGX301 - mixed indentation
# ---------------------------------------------------------------------------

@rule(
    "NGX301",
    "Mixed tabs and spaces for indentation",
    severity="info",
    category=CAT_STYLE,
    remediation="Pick one indentation style (4 spaces is the nginx convention) and convert the file.",
)
def mixed_indentation(ctx) -> Iterator[object]:
    R = mixed_indentation.__rule__
    tab_lines: list[int] = []
    space_lines: list[int] = []
    for number, text in enumerate(ctx.config.text.splitlines(), start=1):
        if not text.strip():
            continue
        prefix = _prefix_of(text)
        if "\t" in prefix:
            tab_lines.append(number)
        elif prefix:
            space_lines.append(number)
    if tab_lines and space_lines:
        yield ctx.make(
            R,
            f"the file mixes tabs ({len(tab_lines)} lines) and spaces "
            f"({len(space_lines)} lines) for indentation.",
            line=tab_lines[0],
            snippet=ctx.config.line_text(tab_lines[0]),
            meta={"tab_lines": len(tab_lines), "space_lines": len(space_lines)},
        )


# ---------------------------------------------------------------------------
# NGX302 - trailing whitespace
# ---------------------------------------------------------------------------

@rule(
    "NGX302",
    "Trailing whitespace",
    severity="info",
    category=CAT_STYLE,
    remediation="Strip trailing whitespace; it produces noisy diffs.",
)
def trailing_whitespace(ctx) -> Iterator[object]:
    R = trailing_whitespace.__rule__
    for number, text in enumerate(ctx.config.text.splitlines(), start=1):
        if text != text.rstrip():
            yield ctx.make(
                R,
                "line ends with trailing whitespace.",
                line=number,
                snippet=text,
            )


# ---------------------------------------------------------------------------
# NGX303 - very long line
# ---------------------------------------------------------------------------

@rule(
    "NGX303",
    "Very long configuration line",
    severity="info",
    category=CAT_STYLE,
    remediation="Wrap long argument lists over multiple lines (nginx allows newlines inside a directive).",
)
def long_line(ctx) -> Iterator[object]:
    R = long_line.__rule__
    limit = int(ctx.setting("max_line_length", _MAX_LINE_LENGTH))
    for number, text in enumerate(ctx.config.text.splitlines(), start=1):
        if len(text) > limit:
            yield ctx.make(
                R,
                f"line is {len(text)} characters long (limit {limit}).",
                line=number,
                snippet=text[: limit + 40],
                meta={"length": len(text)},
            )


# ---------------------------------------------------------------------------
# NGX304 - suspicious absolute path
# ---------------------------------------------------------------------------

@rule(
    "NGX304",
    "Hard-coded path outside the conventional directories",
    severity="info",
    category=CAT_STYLE,
    remediation="Prefer paths under /etc/nginx, /var/www or /usr/share/nginx so the config stays portable.",
)
def hardcoded_path(ctx) -> Iterator[object]:
    R = hardcoded_path.__rule__
    checked = {"root", "alias", "access_log", "error_log", "ssl_certificate",
               "ssl_certificate_key", "ssl_trusted_certificate",
               "ssl_client_certificate", "auth_basic_user_file", "include",
               "fastcgi_param", "proxy_cache_path", "client_body_temp_path",
               "proxy_temp_path"}
    for node in ctx.config.walk():
        if node.name not in checked:
            continue
        for arg in node.args:
            if not arg.startswith("/"):
                continue
            if arg.startswith(TRUSTED_PREFIXES):
                continue
            if arg in ("/dev/null",):
                continue
            yield ctx.make(
                R,
                f"'{node.name}' points at '{arg}', which lives outside the "
                "conventional nginx directories.",
                line=node.line, col=node.col, path=node.path_label(),
                meta={"path": arg},
            )
            break


# ---------------------------------------------------------------------------
# NGX305 - non snake_case directive name
# ---------------------------------------------------------------------------

@rule(
    "NGX305",
    "Directive name is not lower snake_case",
    severity="info",
    category=CAT_STYLE,
    remediation="nginx directive names are always lowercase with underscores.",
)
def directive_casing(ctx) -> Iterator[object]:
    R = directive_casing.__rule__
    for node in ctx.config.walk():
        if not node.name:
            continue
        if re.fullmatch(r"[a-z0-9_]+", node.name):
            continue
        yield ctx.make(
            R,
            f"'{node.name}' contains characters that nginx directives never use "
            "- check for a typo.",
            line=node.line, col=node.col, path=node.path_label(),
            severity="warning" if node.name.lower() != node.name else "info",
        )
