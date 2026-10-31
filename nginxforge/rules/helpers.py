"""
Shared helpers used by the rule modules.

Everything here is pure-Python and side-effect free so the rules stay easy to
reason about (and to unit test).
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from ..model import Directive

_SIZE_RE = re.compile(r"^(\d+)\s*([kKmMgG]?)(?:b|B)?$")
_TIME_RE = re.compile(r"^(\d+)\s*(ms|s|m|h|d|w|M|y)?$")

_TIME_UNITS = {
    "": 1,
    "ms": 0.001,
    "s": 1,
    "m": 60,
    "h": 3600,
    "d": 86400,
    "w": 604800,
    "M": 2592000,
    "y": 31536000,
}

_SIZE_UNITS = {"": 1, "k": 1024, "K": 1024, "m": 1024 ** 2, "M": 1024 ** 2,
               "g": 1024 ** 3, "G": 1024 ** 3}


def parse_size(text: str) -> Optional[int]:
    """``"8k"`` -> ``8192``. Returns ``None`` when not parseable."""
    match = _SIZE_RE.match(text.strip())
    if not match:
        return None
    return int(match.group(1)) * _SIZE_UNITS.get(match.group(2), 1)


def parse_time(text: str) -> Optional[float]:
    """``"75s"`` -> ``75.0``. Returns ``None`` when not parseable."""
    match = _TIME_RE.match(text.strip())
    if not match:
        return None
    return int(match.group(1)) * _TIME_UNITS.get(match.group(2) or "", 1)


def is_true(text: str) -> bool:
    return text.strip().lower() in ("on", "true", "yes", "1")


def is_false(text: str) -> bool:
    return text.strip().lower() in ("off", "false", "no", "0")


# --------------------------------------------------------------------------
# Location introspection
# --------------------------------------------------------------------------

def location_match(node: Directive) -> Tuple[str, str]:
    """Return ``(kind, pattern)`` for a ``location`` directive.

    ``kind`` is one of ``=`` (exact), ``^~`` (prefix, no regex), ``~``
    (case sensitive regex), ``~*`` (case insensitive regex), ``@`` (named) or
    ``prefix`` (plain prefix match).
    """
    if not node.args:
        return "prefix", ""
    head = node.args[0]
    if head == "=":
        return "=", " ".join(node.args[1:])
    if head == "^~":
        return "^~", " ".join(node.args[1:])
    if head in ("~", "~*"):
        return head, " ".join(node.args[1:])
    if head.startswith("@"):
        return "@", head
    return "prefix", head


def is_named_location(node: Directive) -> bool:
    return location_match(node)[0] == "@"


# --------------------------------------------------------------------------
# server introspection
# --------------------------------------------------------------------------

def server_listens(server: Directive) -> List[Tuple[str, str]]:
    """Return ``[(address, flags...)]`` pairs for every ``listen`` directive."""
    out: List[Tuple[str, str]] = []
    for listen in server.children("listen"):
        addr = listen.args[0] if listen.args else "*:80"
        out.append((addr, " ".join(listen.args[1:])))
    return out


def listen_is_https(flags: str) -> bool:
    low = flags.lower()
    return "ssl" in low.split() or "https" in low


def listen_port(address: str, flags: str) -> str:
    """Best effort port extraction from a ``listen`` directive."""
    if listen_is_https(flags) and ":" not in address:
        return "443"
    if ":" in address:
        return address.rsplit(":", 1)[1]
    if address.isdigit():
        return address
    return "443" if listen_is_https(flags) else "80"


def server_has_tls(server: Directive) -> bool:
    """True when the server block actually terminates TLS."""
    if server.find_first("ssl_certificate") is not None:
        return True
    for _addr, flags in server_listens(server):
        if listen_is_https(flags):
            return True
    return False


def server_is_default(server: Directive) -> bool:
    for _addr, flags in server_listens(server):
        if "default_server" in flags.lower().split():
            return True
    return False


# --------------------------------------------------------------------------
# header helpers
# --------------------------------------------------------------------------

def headers_set_in(block: Directive) -> Dict[str, Directive]:
    """Map lower-cased header name -> the directive that sets it."""
    out: Dict[str, Directive] = {}
    for node in block.children("add_header"):
        if node.args:
            out[node.args[0].lower()] = node
    for node in block.children("more_set_headers"):
        if node.args:
            out[node.args[0].lower()] = node
    return out


def header_value(node: Directive) -> str:
    return node.args[1] if len(node.args) > 1 else ""


def header_condition(node: Directive) -> str:
    """The ``always``/conditional third argument of ``add_header``."""
    return node.args[2].lower() if len(node.args) > 2 else ""


# --------------------------------------------------------------------------
# misc
# --------------------------------------------------------------------------

def effective_contexts(node: Directive) -> List[str]:
    """Contexts nginx would consider when validating ``node``.

    ``if`` blocks inherit their parent's context, so both names are returned.
    """
    if node.parent is None:
        return ["main"]
    out = [node.parent.name]
    if node.parent.name == "if" and node.parent.parent is not None:
        out.append(node.parent.parent.name)
    return out


def indent_of(line_text: str) -> str:
    return line_text[: len(line_text) - len(line_text.lstrip())]


def directive_key(node: Directive) -> Tuple[str, ...]:
    """Stable identity of a directive, used for duplicate detection."""
    return (node.name, tuple(node.args))


def find_upstream_for(proxy_pass: str) -> Optional[str]:
    """Extract the upstream group name from a ``proxy_pass`` target."""
    value = proxy_pass.strip()
    if value.startswith("http://"):
        value = value[len("http://"):]
    elif value.startswith("https://"):
        value = value[len("https://"):]
    if "://" in value:
        return None
    value = value.split("/")[0]
    if ":" in value:
        value = value.split(":", 1)[0]
    if re.fullmatch(r"[A-Za-z0-9_.\-]+", value):
        return value
    return None


def looks_like_variable(text: str) -> bool:
    return text.startswith("$")
