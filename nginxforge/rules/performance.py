"""
Performance rules (``NGX2xx``).

These are advisory: they flag configurations that work, but leave throughput or
latency on the table.
"""

from __future__ import annotations

from typing import Iterator, Set

from ..engine import CAT_PERFORMANCE, rule
from ..model import FIX_INSERT_AFTER, FIX_REPLACE, Fix
from .helpers import (
    is_false,
    location_match,
    parse_time,
    server_has_tls,
)

#: MIME families that benefit most from compression.
COMMON_COMPRESSIBLE = (
    "text/plain", "text/css", "application/javascript", "application/json",
    "application/xml", "image/svg+xml",
)


def _replace(node, text: str, summary: str) -> Fix:
    return Fix(mode=FIX_REPLACE, new_line=text, summary=summary)


def _insert_after(node, text: str, summary: str) -> Fix:
    return Fix(mode=FIX_INSERT_AFTER, new_line=text, summary=summary)


# ---------------------------------------------------------------------------
# NGX201 - compression disabled
# ---------------------------------------------------------------------------

@rule(
    "NGX201",
    "Response compression is disabled",
    severity="info",
    category=CAT_PERFORMANCE,
    remediation="Enable 'gzip on;' (and brotli/zstd if your build supports them).",
)
def compression_disabled(ctx) -> Iterator[object]:
    R = compression_disabled.__rule__
    http = ctx.config.find_first("http")
    if http is None:
        return
    if ctx.config.find_first("gzip") is not None:
        return
    if ctx.config.find_first("brotli") is not None:
        return
    if ctx.config.find_first("zstd") is not None:
        return
    yield ctx.make(
        R,
        "no compression module is enabled - text responses are sent "
        "uncompressed.",
        line=http.line, col=http.col, path=http.path_label(),
        fix=_insert_after(
            http.block[0] if http.block else http,
            "gzip on;\ngzip_types text/plain text/css application/json "
            "application/javascript text/xml application/xml image/svg+xml;",
            "Enable gzip for text responses",
        ),
    )


# ---------------------------------------------------------------------------
# NGX202 - sendfile disabled
# ---------------------------------------------------------------------------

@rule(
    "NGX202",
    "sendfile is disabled",
    severity="info",
    category=CAT_PERFORMANCE,
    remediation="Enable 'sendfile on;' for zero-copy static file delivery.",
)
def sendfile_disabled(ctx) -> Iterator[object]:
    R = sendfile_disabled.__rule__
    for node in ctx.config.find_all("sendfile"):
        if node.args and is_false(node.args[0]):
            yield ctx.make(
                R,
                "'sendfile off' forces nginx to copy file data through user "
                "space.",
                line=node.line, col=node.col, path=node.path_label(),
                fix=_replace(node, "sendfile on;", "Enable sendfile"),
            )


# ---------------------------------------------------------------------------
# NGX203 - TCP socket flags
# ---------------------------------------------------------------------------

@rule(
    "NGX203",
    "TCP socket flags not tuned",
    severity="info",
    category=CAT_PERFORMANCE,
    remediation="Enable 'tcp_nopush on;' and 'tcp_nodelay on;' for keep-alive connections.",
)
def tcp_flags(ctx) -> Iterator[object]:
    R = tcp_flags.__rule__
    for name in ("tcp_nopush", "tcp_nodelay"):
        nodes = list(ctx.config.find_all(name))
        if not nodes:
            http = ctx.config.find_first("http")
            if http is None:
                continue
            yield ctx.make(
                R,
                f"'{name}' is never configured - defaults leave throughput on "
                "the table for keep-alive traffic.",
                line=http.line, col=http.col, path=http.path_label(),
                fix=_insert_after(http.block[0] if http.block else http,
                                  f"{name} on;", f"Enable {name}"),
            )
            continue
        for node in nodes:
            if node.args and is_false(node.args[0]):
                yield ctx.make(
                    R,
                    f"'{name} off' reduces throughput for keep-alive traffic.",
                    line=node.line, col=node.col, path=node.path_label(),
                    fix=_replace(node, f"{name} on;", f"Enable {name}"),
                )


# ---------------------------------------------------------------------------
# NGX204 - keepalive timeout too long
# ---------------------------------------------------------------------------

@rule(
    "NGX204",
    "keepalive_timeout is unusually long",
    severity="info",
    category=CAT_PERFORMANCE,
    remediation="Keep idle keep-alive connections under ~75s to avoid exhausting worker slots.",
)
def long_keepalive(ctx) -> Iterator[object]:
    R = long_keepalive.__rule__
    limit = float(ctx.setting("max_keepalive_timeout", 75))
    for node in ctx.config.find_all("keepalive_timeout"):
        if not node.args:
            continue
        seconds = parse_time(node.args[0])
        if seconds is None or seconds <= limit:
            continue
        yield ctx.make(
            R,
            f"keepalive_timeout of {node.args[0]} exceeds {int(limit)}s - idle "
            "connections will hold worker slots.",
            line=node.line, col=node.col, path=node.path_label(),
            fix=_replace(node, "keepalive_timeout 65;",
                         "Lower keepalive timeout to 65s"),
            meta={"seconds": seconds, "limit": limit},
        )


# ---------------------------------------------------------------------------
# NGX205 - worker_processes not set to auto
# ---------------------------------------------------------------------------

@rule(
    "NGX205",
    "worker_processes is not 'auto'",
    severity="info",
    category=CAT_PERFORMANCE,
    remediation="Use 'worker_processes auto;' so nginx matches the CPU count.",
)
def worker_processes_fixed(ctx) -> Iterator[object]:
    R = worker_processes_fixed.__rule__
    for node in ctx.config.find_all("worker_processes"):
        if node.args and node.args[0].lower() == "auto":
            continue
        yield ctx.make(
            R,
            "worker_processes is pinned to a fixed value instead of 'auto'.",
            line=node.line, col=node.col, path=node.path_label(),
            fix=_replace(node, "worker_processes auto;",
                         "Scale workers to the CPU count"),
        )


# ---------------------------------------------------------------------------
# NGX206 - worker_connections too low
# ---------------------------------------------------------------------------

@rule(
    "NGX206",
    "worker_connections is very low",
    severity="info",
    category=CAT_PERFORMANCE,
    remediation="Raise 'worker_connections' (1024 is the bare minimum, 4096+ for busy hosts).",
)
def low_worker_connections(ctx) -> Iterator[object]:
    R = low_worker_connections.__rule__
    floor = int(ctx.setting("min_worker_connections", 1024))
    for node in ctx.config.find_all("worker_connections"):
        if not node.args or not node.args[0].isdigit():
            continue
        value = int(node.args[0])
        if value >= floor:
            continue
        yield ctx.make(
            R,
            f"worker_connections={value} is below {floor} - the host will "
            "refuse connections under load.",
            line=node.line, col=node.col, path=node.path_label(),
            fix=_replace(node,
                         f"worker_connections {max(floor * 4, 4096)};",
                         "Raise the per-worker connection limit"),
            meta={"value": value},
        )


# ---------------------------------------------------------------------------
# NGX207 - static assets without cache headers
# ---------------------------------------------------------------------------

@rule(
    "NGX207",
    "Static assets without cache headers",
    severity="info",
    category=CAT_PERFORMANCE,
    remediation="Add 'expires' or 'Cache-Control' for immutable asset locations.",
)
def static_without_cache(ctx) -> Iterator[object]:
    R = static_without_cache.__rule__
    for loc in ctx.config.find_all("location"):
        kind, pattern = location_match(loc)
        if kind not in ("prefix", "~", "~*"):
            continue
        low = pattern.lower()
        if not low.endswith((".css", ".js", ".png", ".jpg", ".jpeg", ".gif",
                             ".svg", ".woff", ".woff2", ".ico", ".webp")):
            if not (kind in ("~", "~*") and "assets" in low):
                continue
        if loc.block is None:
            continue
        names = {c.name for c in loc.block}
        if {"expires", "add_header"} & names:
            continue
        yield ctx.make(
            R,
            f"location '{pattern}' serves static assets without any caching "
            "header.",
            line=loc.line, col=loc.col, path=loc.path_label(),
            fix=_insert_after(
                loc.block[0],
                'expires 30d;\nadd_header Cache-Control "public, immutable" always;',
                "Add long-lived cache headers",
            ),
        )


# ---------------------------------------------------------------------------
# NGX208 - HTTPS without HTTP/2
# ---------------------------------------------------------------------------

@rule(
    "NGX208",
    "HTTPS listener without HTTP/2",
    severity="info",
    category=CAT_PERFORMANCE,
    remediation="Add the 'http2' parameter to the TLS listen directive.",
)
def no_http2(ctx) -> Iterator[object]:
    R = no_http2.__rule__
    for listen in ctx.config.find_all("listen"):
        if not listen.args:
            continue
        flags = " ".join(listen.args[1:]).lower()
        if "ssl" not in flags.split():
            continue
        if "http2" in flags.split() or "http3" in flags.split() or "quic" in flags.split():
            continue
        yield ctx.make(
            R,
            "TLS listener without 'http2' - multiplexing and header "
            "compression stay disabled.",
            line=listen.line, col=listen.col, path=listen.path_label(),
            fix=_replace(listen, f"listen {listen.args[0]} ssl http2;",
                         "Enable HTTP/2 on this listener"),
        )


# ---------------------------------------------------------------------------
# NGX209 - proxy_buffering disabled
# ---------------------------------------------------------------------------

@rule(
    "NGX209",
    "proxy_buffering disabled",
    severity="info",
    category=CAT_PERFORMANCE,
    remediation="Keep 'proxy_buffering on' unless you truly need streaming responses.",
)
def proxy_buffering_off(ctx) -> Iterator[object]:
    R = proxy_buffering_off.__rule__
    for node in ctx.config.find_all("proxy_buffering"):
        if not (node.args and is_false(node.args[0])):
            continue
        # WebSocket / SSE streaming requires buffering to be off.
        siblings = list(node.parent.children("proxy_set_header")) if node.parent else []
        if any(s.args and s.args[0].lower() in ("upgrade", "connection")
               for s in siblings):
            continue
        yield ctx.make(
                R,
                "'proxy_buffering off' ties up an upstream connection for the "
                "whole response and disables proxy caching.",
                line=node.line, col=node.col, path=node.path_label(),
                fix=_replace(node, "proxy_buffering on;", "Enable proxy buffering"),
            )


# ---------------------------------------------------------------------------
# NGX210 - no open_file_cache for static content
# ---------------------------------------------------------------------------

@rule(
    "NGX210",
    "Static file serving without open_file_cache",
    severity="info",
    category=CAT_PERFORMANCE,
    remediation="Add 'open_file_cache' to avoid repeated stat() calls on hot files.",
)
def no_open_file_cache(ctx) -> Iterator[object]:
    R = no_open_file_cache.__rule__
    if ctx.config.find_first("open_file_cache") is not None:
        return
    http = ctx.config.find_first("http")
    if http is None or http.block is None:
        return
    serves_static = ctx.config.find_first("root") is not None or \
        ctx.config.find_first("alias") is not None or \
        ctx.config.find_first("try_files") is not None
    if not serves_static:
        return
    yield ctx.make(
        R,
        "static files are served but no 'open_file_cache' is configured.",
        line=http.line, col=http.col, path=http.path_label(),
        fix=_insert_after(
            http.block[0] if http.block else http,
            "open_file_cache max=10000 inactive=60s;\nopen_file_cache_valid 60s;\n"
            "open_file_cache_min_uses 2;\nopen_file_cache_errors on;",
            "Enable the open file cache",
        ),
    )


# ---------------------------------------------------------------------------
# NGX211 - gzip_types missing common types
# ---------------------------------------------------------------------------

@rule(
    "NGX211",
    "gzip_types is missing common text types",
    severity="info",
    category=CAT_PERFORMANCE,
    remediation="Add JSON, XML and SVG to gzip_types - they compress extremely well.",
)
def gzip_types_incomplete(ctx) -> Iterator[object]:
    R = gzip_types_incomplete.__rule__
    for node in ctx.config.find_all("gzip_types"):
        present: Set[str] = {a.lower() for a in node.args}
        if "*" in present:
            continue
        missing = [t for t in COMMON_COMPRESSIBLE if t not in present]
        if len(missing) < 2:
            continue
        yield ctx.make(
            R,
            "gzip_types does not include " + ", ".join(missing) + ".",
            line=node.line, col=node.col, path=node.path_label(),
            fix=_replace(node,
                         "gzip_types " + " ".join(sorted(present | set(missing)))
                         + ";",
                         "Extend gzip_types"),
            meta={"missing": missing},
        )


# ---------------------------------------------------------------------------
# NGX212 - upstream without keepalive
# ---------------------------------------------------------------------------

@rule(
    "NGX212",
    "upstream group without keepalive",
    severity="info",
    category=CAT_PERFORMANCE,
    remediation="Add 'keepalive 32;' to the upstream block to reuse backend connections.",
)
def upstream_without_keepalive(ctx) -> Iterator[object]:
    R = upstream_without_keepalive.__rule__
    for upstream in ctx.config.find_all("upstream"):
        if upstream.block is None:
            continue
        if upstream.find_first("keepalive") is not None:
            continue
        peer = upstream.find_first("server")
        anchor = peer or (upstream.block[0] if upstream.block else upstream)
        yield ctx.make(
            R,
            f"upstream '{' '.join(upstream.args)}' opens a fresh connection "
            "per request.",
            line=anchor.line, col=anchor.col, path=upstream.path_label(),
            fix=_insert_after(anchor, "keepalive 32;",
                              "Reuse 32 backend connections"),
        )


# ---------------------------------------------------------------------------
# NGX213 - proxied traffic is never cached
# ---------------------------------------------------------------------------

@rule(
    "NGX213",
    "Proxied responses are never cached",
    severity="info",
    category=CAT_PERFORMANCE,
    remediation="Declare a proxy_cache_path and enable proxy_cache for cacheable endpoints.",
)
def no_proxy_cache(ctx) -> Iterator[object]:
    R = no_proxy_cache.__rule__
    http = ctx.config.find_first("http")
    if http is None or http.block is None:
        return
    if http.find_first("proxy_cache_path") is not None or \
            http.find_first("proxy_cache") is not None:
        return
    if ctx.config.find_first("proxy_cache") is not None:
        return
    servers = [s for s in http.children("server") if s.block]
    if not servers:
        return
    proxies = [p for p in ctx.config.find_all("proxy_pass")]
    if len(proxies) < 2:
        return
    yield ctx.make(
        R,
        f"{len(proxies)} proxy_pass endpoints share no cache - every request "
        "hits the backend.",
        line=http.line, col=http.col, path=http.path_label(),
        fix=_insert_after(
            http.block[0] if http.block else http,
            "proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=main:10m "
            "max_size=1g inactive=60m use_temp_path=off;",
            "Declare a proxy cache zone",
        ),
        meta={"proxies": len(proxies)},
    )


# ---------------------------------------------------------------------------
# NGX214 - TLS session cache missing
# ---------------------------------------------------------------------------

@rule(
    "NGX214",
    "TLS session cache is not configured",
    severity="info",
    category=CAT_PERFORMANCE,
    remediation="Add 'ssl_session_cache shared:SSL:10m;' to avoid a full handshake per connection.",
)
def no_session_cache(ctx) -> Iterator[object]:
    R = no_session_cache.__rule__
    if ctx.config.find_first("ssl_session_cache") is not None:
        return
    for server in ctx.config.find_all("server"):
        if server.block is None or not server_has_tls(server):
            continue
        anchor = server.block[0]
        yield ctx.make(
            R,
            "TLS handshakes are never reused - every connection pays the full "
            "handshake cost.",
            line=anchor.line, col=anchor.col, path=server.path_label(),
            fix=_insert_after(
                anchor,
                "ssl_session_cache shared:SSL:10m;\nssl_session_timeout 1d;",
                "Enable the shared TLS session cache",
            ),
        )
