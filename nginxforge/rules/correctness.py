"""
Correctness rules (``NGX0xx``).

These catch configurations that nginx would reject outright, or that silently
behave differently from what the author intended.
"""

from __future__ import annotations

from typing import Dict, Iterator, List, Set, Tuple

from ..directives import DIRECTIVES, allowed_contexts, arity, suggest
from ..engine import CAT_CORRECTNESS, rule
from ..model import Directive
from .helpers import (
    directive_key,
    effective_contexts,
    location_match,
)

#: Blocks whose children are free-form key/value tables, not directives.
TABLE_CONTEXTS = {"types", "map", "geo", "split_clients"}

#: Directives that are legitimately allowed to repeat inside one block.
REPEATABLE = {
    "add_header", "add_trailer", "allow", "deny", "error_page", "fastcgi_param",
    "include", "index", "listen", "location", "log_format", "more_set_headers",
    "proxy_set_header", "rewrite", "server", "server_name", "set", "upstream",
    "uwsgi_param", "scgi_param", "grpc_set_header", "limit_req", "limit_conn",
    "proxy_cache_valid", "gzip_types", "ssl_protocols", "proxy_hide_header",
    "hide_header", "real_ip_header", "auth_jwt_claim_set",
}

#: Directives whose behaviour inside ``if`` is well known to be surprising.
IF_RISKY = {"add_header", "proxy_pass", "fastcgi_pass", "expires", "limit_rate",
            "alias", "root", "try_files"}


def _in_table(node: Directive) -> bool:
    return any(a.name in TABLE_CONTEXTS for a in node.ancestors())


# ---------------------------------------------------------------------------
# NGX001 - unknown / misspelled directive
# ---------------------------------------------------------------------------

@rule(
    "NGX001",
    "Unknown or misspelled directive",
    severity="info",
    category=CAT_CORRECTNESS,
    remediation=(
        "Check the spelling, or make sure the module providing this directive "
        "is compiled into your nginx build."
    ),
)
def unknown_directive(ctx) -> Iterator[object]:
    R = unknown_directive.__rule__
    for node in ctx.config.walk():
        if _in_table(node):
            continue
        if node.name in DIRECTIVES:
            continue
        guess = suggest(node.name)
        if guess:
            yield ctx.make(
                R,
                f"'{node.name}' is not a known directive - did you mean "
                f"'{guess}'?",
                line=node.line, col=node.col, path=node.path_label(),
                severity="warning",
            )
        else:
            yield ctx.make(
                R,
                f"'{node.name}' is not in the built-in directive table - it "
                "probably comes from a third-party module.",
                line=node.line, col=node.col, path=node.path_label(),
            )


# ---------------------------------------------------------------------------
# NGX002 - directive used in an illegal context
# ---------------------------------------------------------------------------

@rule(
    "NGX002",
    "Directive is not allowed in this context",
    severity="error",
    category=CAT_CORRECTNESS,
    remediation="Move the directive into a block where nginx accepts it.",
)
def invalid_context(ctx) -> Iterator[object]:
    R = invalid_context.__rule__
    for node in ctx.config.walk():
        if _in_table(node) or node.name not in DIRECTIVES:
            continue
        allowed = set(allowed_contexts(node.name))
        if not allowed:
            continue
        if allowed & set(effective_contexts(node)):
            continue
        yield ctx.make(
            R,
            f"'{node.name}' cannot appear inside '{node.context}' - allowed "
            f"contexts: {', '.join(sorted(allowed))}.",
            line=node.line, col=node.col, path=node.path_label(),
            meta={"allowed": sorted(allowed)},
        )


# ---------------------------------------------------------------------------
# NGX003 - wrong number of arguments
# ---------------------------------------------------------------------------

@rule(
    "NGX003",
    "Wrong number of directive arguments",
    severity="error",
    category=CAT_CORRECTNESS,
    remediation="Compare with the official directive signature.",
)
def arity_mismatch(ctx) -> Iterator[object]:
    R = arity_mismatch.__rule__
    for node in ctx.config.walk():
        if _in_table(node):
            continue
        spec = arity(node.name)
        if spec is None:
            continue
        low, high = spec
        count = len(node.args)
        if count < low or (high is not None and count > high):
            expected = f"at least {low}" if high is None else (
                f"exactly {low}" if low == high else f"{low}..{high}"
            )
            yield ctx.make(
                R,
                f"'{node.name}' received {count} argument(s) but expects "
                f"{expected}.",
                line=node.line, col=node.col, path=node.path_label(),
                meta={"got": count, "min": low, "max": high},
            )


# ---------------------------------------------------------------------------
# NGX004 - syntax errors reported by the parser
# ---------------------------------------------------------------------------

@rule(
    "NGX004",
    "Configuration syntax error",
    severity="error",
    category=CAT_CORRECTNESS,
    remediation="Fix the reported syntax problem; nginx would refuse to start.",
)
def syntax_error(ctx) -> Iterator[object]:
    R = syntax_error.__rule__
    for err in ctx.config.errors:
        yield ctx.make(
            R,
            str(err.message),
            line=err.line or 0, col=err.col or 0,
        )


# ---------------------------------------------------------------------------
# NGX005 - try_files without a safe fallback
# ---------------------------------------------------------------------------

@rule(
    "NGX005",
    "try_files has no safe fallback",
    severity="warning",
    category=CAT_CORRECTNESS,
    remediation=(
        "End try_files with an explicit fallback such as '=404', a named "
        "location, or an existing file - otherwise nginx may loop or return 500."
    ),
)
def try_files_fallback(ctx) -> Iterator[object]:
    R = try_files_fallback.__rule__
    for node in ctx.config.find_all("try_files"):
        if len(node.args) < 2:
            yield ctx.make(
                R,
                "try_files needs at least one candidate plus a fallback "
                "(e.g. 'try_files $uri $uri/ =404;').",
                line=node.line, col=node.col, path=node.path_label(),
            )
            continue
        last = node.args[-1]
        if not (last.startswith("=") or last.startswith("@") or last.startswith("/")):
            yield ctx.make(
                R,
                f"the last try_files argument '{last}' is neither an error "
                "code (=404), a named location (@name) nor an absolute URI.",
                line=node.line, col=node.col, path=node.path_label(),
            )


# ---------------------------------------------------------------------------
# NGX006 - root and alias used together
# ---------------------------------------------------------------------------

@rule(
    "NGX006",
    "root and alias declared in the same location",
    severity="warning",
    category=CAT_CORRECTNESS,
    remediation="Pick one of 'root' or 'alias'; mixing them makes the resolved path hard to predict.",
)
def root_alias_conflict(ctx) -> Iterator[object]:
    R = root_alias_conflict.__rule__
    for node in ctx.config.find_all("location"):
        if node.block is None:
            continue
        has_root = node.find_first("root") is not None
        has_alias = node.find_first("alias") is not None
        if has_root and has_alias:
            alias = node.find_first("alias")
            yield ctx.make(
                R,
                "this location declares both 'root' and 'alias'.",
                line=alias.line, col=alias.col, path=node.path_label(),
            )


# ---------------------------------------------------------------------------
# NGX007 - proxy_pass / location prefix slash mismatch
# ---------------------------------------------------------------------------

@rule(
    "NGX007",
    "proxy_pass URI replacement mismatch",
    severity="warning",
    category=CAT_CORRECTNESS,
    remediation=(
        "Either give both the location prefix and proxy_pass a trailing slash, "
        "or neither - otherwise the request path is rewritten unexpectedly."
    ),
)
def proxy_pass_slash(ctx) -> Iterator[object]:
    R = proxy_pass_slash.__rule__
    for loc in ctx.config.find_all("location"):
        kind, pattern = location_match(loc)
        if kind != "prefix" or not pattern.endswith("/"):
            continue
        for proxy in loc.find_all("proxy_pass"):
            if not proxy.args:
                continue
            target = proxy.args[0]
            if "://" not in target:
                continue
            path_part = target.split("://", 1)[1]
            if "/" not in path_part:
                # no URI part -> nginx forwards the original request URI
                continue
            uri = path_part[path_part.index("/"):]
            if uri and not uri.endswith("/") and not uri.endswith("$1"):
                yield ctx.make(
                    R,
                    f"location '{pattern}' ends with '/' but proxy_pass URI "
                    f"'{uri}' does not - the matched prefix is not stripped "
                    "the way you probably expect.",
                    line=proxy.line, col=proxy.col, path=loc.path_label(),
                )


# ---------------------------------------------------------------------------
# NGX008 - server block without server_name
# ---------------------------------------------------------------------------

@rule(
    "NGX008",
    "server block has no server_name",
    severity="info",
    category=CAT_CORRECTNESS,
    remediation="Declare 'server_name' explicitly so the block cannot silently capture unrelated hostnames.",
)
def missing_server_name(ctx) -> Iterator[object]:
    R = missing_server_name.__rule__
    for server in ctx.config.find_all("server"):
        if server.parent is None:
            continue
        if server.parent.name not in ("http", "mail", "stream"):
            continue
        if server.find_first("server_name") is None:
            yield ctx.make(
                R,
                "this server block has no 'server_name' directive.",
                line=server.line, col=server.col, path=server.path_label(),
            )


# ---------------------------------------------------------------------------
# NGX009 - duplicate server definition
# ---------------------------------------------------------------------------

@rule(
    "NGX009",
    "Duplicate server block",
    severity="warning",
    category=CAT_CORRECTNESS,
    remediation="Remove the duplicate or give it a distinct server_name / listen pair.",
)
def duplicate_server(ctx) -> Iterator[object]:
    R = duplicate_server.__rule__
    seen: Dict[Tuple[str, ...], Directive] = {}
    for server in ctx.config.find_all("server"):
        if server.block is None:
            continue
        names = tuple(sorted(
            a for a in (server.find_first("server_name").args
                        if server.find_first("server_name") else [])
        ))
        listens = tuple(sorted(
            a[0] + (" ssl" if "ssl" in a[1].lower().split() else "")
            for a in (
                (lst.args[0] if lst.args else "*:80",
                 " ".join(lst.args[1:])) for lst in server.children("listen")
            )
        ))
        key = (server.context, names, listens)
        if key in seen:
            first = seen[key]
            yield ctx.make(
                R,
                f"this server block duplicates the one defined at line "
                f"{first.line} (same context, server_name and listen set).",
                line=server.line, col=server.col, path=server.path_label(),
                meta={"first_line": first.line},
            )
        else:
            seen[key] = server


# ---------------------------------------------------------------------------
# NGX010 - upstream server without an explicit port
# ---------------------------------------------------------------------------

@rule(
    "NGX010",
    "upstream server without an explicit port",
    severity="info",
    category=CAT_CORRECTNESS,
    remediation="Specify the port explicitly (e.g. 'server 10.0.0.1:8080;') to avoid silently defaulting to 80.",
)
def upstream_server_port(ctx) -> Iterator[object]:
    R = upstream_server_port.__rule__
    for upstream in ctx.config.find_all("upstream"):
        if upstream.block is None:
            continue
        for peer in upstream.children("server"):
            if not peer.args:
                continue
            host = peer.args[0]
            if host.startswith("unix:"):
                continue
            if ":" not in host:
                yield ctx.make(
                    R,
                    f"upstream peer '{host}' has no port and will default to 80.",
                    line=peer.line, col=peer.col, path=upstream.path_label(),
                )


# ---------------------------------------------------------------------------
# NGX011 - risky directive inside an if block
# ---------------------------------------------------------------------------

@rule(
    "NGX011",
    "Risky directive inside an 'if' block",
    severity="warning",
    category=CAT_CORRECTNESS,
    remediation="'if is evil' - move the logic to a dedicated location/map block instead.",
)
def if_is_evil(ctx) -> Iterator[object]:
    R = if_is_evil.__rule__
    for node in ctx.config.find_all("if"):
        if node.block is None:
            continue
        for child in node.block:
            if child.name in IF_RISKY:
                yield ctx.make(
                    R,
                    f"'{child.name}' inside an 'if' block has surprising "
                    "semantics in nginx and is a frequent source of bugs.",
                    line=child.line, col=child.col, path=child.path_label(),
                )


# ---------------------------------------------------------------------------
# NGX012 - exact duplicate directive inside one block
# ---------------------------------------------------------------------------

@rule(
    "NGX012",
    "Exact duplicate directive",
    severity="info",
    category=CAT_CORRECTNESS,
    remediation="Remove the redundant line; the second occurrence has no effect.",
)
def duplicate_directive(ctx) -> Iterator[object]:
    R = duplicate_directive.__rule__
    for node in ctx.config.walk():
        if node.block is None or _in_table(node):
            continue
        seen: Set[Tuple[str, ...]] = set()
        for child in node.block:
            if child.name in REPEATABLE:
                continue
            key = directive_key(child)
            if key in seen:
                yield ctx.make(
                    R,
                    f"'{child.name}' is declared twice with identical "
                    "arguments in the same block.",
                    line=child.line, col=child.col, path=child.path_label(),
                )
            seen.add(key)


# ---------------------------------------------------------------------------
# NGX013 - main context is missing http/events
# ---------------------------------------------------------------------------

@rule(
    "NGX013",
    "Main configuration is missing core blocks",
    severity="info",
    category=CAT_CORRECTNESS,
    remediation="A complete nginx.conf normally contains 'events { }' and (for web traffic) 'http { }'.",
)
def missing_core_blocks(ctx) -> Iterator[object]:
    R = missing_core_blocks.__rule__
    root_names = {node.name for node in ctx.config.tree}
    markers = {"worker_processes", "user", "pid", "events"}
    if not (markers & root_names):
        return  # this is probably an include fragment, not a main file
    if "events" not in root_names:
        yield ctx.make(
            R,
            "no 'events { }' block at the top level - nginx requires one.",
            line=1,
        )
    if "http" not in root_names and "stream" not in root_names:
        yield ctx.make(
            R,
            "no 'http { }' or 'stream { }' block at the top level - this file "
            "looks like an incomplete main configuration.",
            line=1,
        )


# ---------------------------------------------------------------------------
# NGX014 - rewrite without a terminating flag
# ---------------------------------------------------------------------------

@rule(
    "NGX014",
    "rewrite without a terminating flag",
    severity="info",
    category=CAT_CORRECTNESS,
    remediation="Add 'last', 'break', 'redirect' or 'permanent' to make the intent explicit.",
)
def rewrite_without_flag(ctx) -> Iterator[object]:
    R = rewrite_without_flag.__rule__
    for node in ctx.config.find_all("rewrite"):
        if len(node.args) >= 3:
            continue
        yield ctx.make(
            R,
            "'rewrite' without a flag keeps processing the rewritten URI "
            "inside the current location, which is rarely intended.",
            line=node.line, col=node.col, path=node.path_label(),
        )


# ---------------------------------------------------------------------------
# NGX015 - add_header in a child block drops inherited headers
# ---------------------------------------------------------------------------

@rule(
    "NGX015",
    "add_header overrides inherited headers",
    severity="warning",
    category=CAT_CORRECTNESS,
    remediation=(
        "add_header in a nested block replaces every inherited add_header. "
        "Repeat the security headers, or add the 'always' parameter."
    ),
)
def add_header_override(ctx) -> Iterator[object]:
    R = add_header_override.__rule__
    for block in ctx.config.walk():
        if block.block is None:
            continue
        own = [c for c in block.block if c.name == "add_header"]
        if not own:
            continue
        inherited = [a for a in block.ancestors() if a.name in ("server", "http", "location")]
        for ancestor in inherited:
            parent_headers = ancestor.children("add_header")
            if parent_headers:
                yield ctx.make(
                    R,
                    f"the {len(own)} add_header directive(s) here discard the "
                    f"{len(parent_headers)} add_header directive(s) inherited "
                    f"from the enclosing {ancestor.name} block.",
                    line=own[0].line, col=own[0].col, path=block.path_label(),
                    meta={"inherited": len(parent_headers)},
                )
                break
