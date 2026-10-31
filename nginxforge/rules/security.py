"""
Security rules (``NGX1xx``).

Focused on the issues that actually get exploited in the wild: information
disclosure, obsolete TLS, missing hardening headers and unauthenticated
management endpoints.
"""

from __future__ import annotations

import re
from typing import Dict, Iterator, List, Set

from ..engine import CAT_SECURITY, rule
from ..model import FIX_INSERT_AFTER, FIX_REPLACE, Directive, Fix
from .helpers import (
    headers_set_in,
    header_value,
    is_true,
    location_match,
    server_has_tls,
    server_listens,
)

#: Response headers every hardened server should send.
SECURITY_HEADER_TEMPLATES = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "SAMEORIGIN",
    "referrer-policy": "strict-origin-when-cross-origin",
    "permissions-policy": "geolocation=(), microphone=(), camera=()",
}

#: Modern, safe TLS protocol baseline.
SAFE_PROTOCOLS = "TLSv1.2 TLSv1.3"

#: A conservative, widely compatible cipher suite.
SAFE_CIPHERS = "ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305"

_PRIVATE_HOSTS = ("127.0.0.1", "localhost", "::1", "unix:")


def _replace(node: Directive, text: str, summary: str) -> Fix:
    return Fix(mode=FIX_REPLACE, new_line=text, summary=summary)


def _insert_after(node: Directive, text: str, summary: str) -> Fix:
    return Fix(mode=FIX_INSERT_AFTER, new_line=text, summary=summary)


def _is_private_host(host: str) -> bool:
    if host.startswith(_PRIVATE_HOSTS):
        return True
    if re.match(r"^10\.", host) or re.match(r"^192\.168\.", host):
        return True
    match = re.match(r"^172\.(\d+)\.", host)
    if match and 16 <= int(match.group(1)) <= 31:
        return True
    return False


def _inherited_headers(node: Directive) -> Set[str]:
    """Header names visible at ``node`` (its own block plus enclosing ones)."""
    names: Set[str] = set(headers_set_in(node))
    for ancestor in node.ancestors():
        names |= set(headers_set_in(ancestor))
    return names


def _block_has_access_control(block: Directive) -> bool:
    for node in block.walk():
        if node.name in ("allow", "deny", "auth_basic", "auth_request", "auth_jwt"):
            return True
    return False


# ---------------------------------------------------------------------------
# NGX101 - version disclosure
# ---------------------------------------------------------------------------

@rule(
    "NGX101",
    "nginx version is disclosed",
    severity="warning",
    category=CAT_SECURITY,
    remediation="Set 'server_tokens off;' to stop advertising the exact nginx version.",
)
def server_tokens_on(ctx) -> Iterator[object]:
    R = server_tokens_on.__rule__
    for node in ctx.config.find_all("server_tokens"):
        if node.args and is_true(node.args[0]):
            yield ctx.make(
                R,
                "'server_tokens on' leaks the nginx version in responses and "
                "error pages.",
                line=node.line, col=node.col, path=node.path_label(),
                fix=_replace(node, "server_tokens off;",
                             "Disable version disclosure"),
            )
        elif not node.args:
            yield ctx.make(
                R,
                "'server_tokens' without an argument defaults to on.",
                line=node.line, col=node.col, path=node.path_label(),
                fix=_replace(node, "server_tokens off;",
                             "Disable version disclosure"),
            )


# ---------------------------------------------------------------------------
# NGX102 - missing hardening headers
# ---------------------------------------------------------------------------

@rule(
    "NGX102",
    "Missing hardening response headers",
    severity="warning",
    category=CAT_SECURITY,
    remediation="Add X-Content-Type-Options, X-Frame-Options and Referrer-Policy.",
)
def missing_headers(ctx) -> Iterator[object]:
    R = missing_headers.__rule__
    required = [h.lower() for h in ctx.setting("required_headers", [])]
    for server in ctx.config.find_all("server"):
        if server.block is None or server.parent is None:
            continue
        if server.parent.name not in ("http", "mail", "stream"):
            continue
        present = _inherited_headers(server)
        missing = [h for h in required if h not in present]
        if not missing:
            continue
        anchor = server.block[0] if server.block else server
        yield ctx.make(
            R,
            "missing security header(s): " + ", ".join(missing) + ".",
            line=anchor.line, col=anchor.col, path=server.path_label(),
            fix=_insert_after(
                anchor,
                " ".join(
                    f"add_header {_header_name(h)} "
                    f"\"{SECURITY_HEADER_TEMPLATES.get(h, 'off')}\" always;"
                    for h in missing
                ),
                f"Add {len(missing)} hardening header(s)",
            ),
            meta={"missing": missing},
        )


def _header_name(lower: str) -> str:
    return "-".join(part.capitalize() for part in lower.split("-"))


# ---------------------------------------------------------------------------
# NGX103 - directory listing enabled
# ---------------------------------------------------------------------------

@rule(
    "NGX103",
    "Directory listing is enabled",
    severity="warning",
    category=CAT_SECURITY,
    remediation="Set 'autoindex off;' unless the directory really must be browsable.",
)
def autoindex_on(ctx) -> Iterator[object]:
    R = autoindex_on.__rule__
    for node in ctx.config.find_all("autoindex"):
        if node.args and is_true(node.args[0]):
            yield ctx.make(
                R,
                "'autoindex on' exposes the full directory contents to anyone.",
                line=node.line, col=node.col, path=node.path_label(),
                fix=_replace(node, "autoindex off;", "Disable directory listing"),
            )


# ---------------------------------------------------------------------------
# NGX104 - obsolete TLS protocols
# ---------------------------------------------------------------------------

@rule(
    "NGX104",
    "Obsolete TLS/SSL protocol enabled",
    severity="error",
    category=CAT_SECURITY,
    remediation="Only TLSv1.2 and TLSv1.3 are considered safe today.",
)
def obsolete_tls(ctx) -> Iterator[object]:
    R = obsolete_tls.__rule__
    forbidden = {p.lower() for p in ctx.setting("forbidden_tls", [])}
    for node in ctx.config.find_all("ssl_protocols"):
        bad = [a for a in node.args if a.lower() in forbidden]
        if not bad:
            continue
        yield ctx.make(
            R,
            f"obsolete protocol(s) enabled: {', '.join(bad)}.",
            line=node.line, col=node.col, path=node.path_label(),
            fix=_replace(node, f"ssl_protocols {SAFE_PROTOCOLS};",
                         f"Restrict to {SAFE_PROTOCOLS}"),
            meta={"bad": bad},
        )


# ---------------------------------------------------------------------------
# NGX105 - weak cipher configuration
# ---------------------------------------------------------------------------

@rule(
    "NGX105",
    "Weak SSL cipher configuration",
    severity="error",
    category=CAT_SECURITY,
    remediation="Use an AEAD-only cipher list and explicitly disable NULL/export/MD5 suites.",
)
def weak_ciphers(ctx) -> Iterator[object]:
    R = weak_ciphers.__rule__
    weak = {t.lower() for t in ctx.setting("weak_cipher_tokens", [])}
    for node in ctx.config.find_all("ssl_ciphers"):
        if not node.args:
            continue
        bad: List[str] = []
        for token in node.args[0].split(":"):
            token = token.strip()
            if not token:
                continue
            if token.startswith("!") or token.startswith("-"):
                continue  # explicitly disabled -> fine
            if token.lower() in weak or token.upper() in {"ALL", "COMPLEMENTOFALL"}:
                bad.append(token)
        if bad:
            yield ctx.make(
                R,
                f"weak cipher token(s) present: {', '.join(bad)}.",
                line=node.line, col=node.col, path=node.path_label(),
                fix=_replace(node, f"ssl_ciphers {SAFE_CIPHERS};",
                             "Use a modern AEAD cipher list"),
                meta={"bad": bad},
            )


# ---------------------------------------------------------------------------
# NGX106 - missing HSTS
# ---------------------------------------------------------------------------

@rule(
    "NGX106",
    "HTTPS server without HSTS",
    severity="warning",
    category=CAT_SECURITY,
    remediation="Send 'Strict-Transport-Security' to pin clients to HTTPS.",
)
def missing_hsts(ctx) -> Iterator[object]:
    R = missing_hsts.__rule__
    for server in ctx.config.find_all("server"):
        if server.block is None or not server_has_tls(server):
            continue
        if "strict-transport-security" in _inherited_headers(server):
            continue
        anchor = server.block[0]
        yield ctx.make(
            R,
            "this TLS-enabled server does not send a Strict-Transport-Security "
            "header.",
            line=anchor.line, col=anchor.col, path=server.path_label(),
            fix=_insert_after(
                anchor,
                "add_header Strict-Transport-Security "
                '"max-age=31536000; includeSubDomains" always;',
                "Enable HSTS (1 year)",
            ),
        )


# ---------------------------------------------------------------------------
# NGX107 - private key stored outside the config directory
# ---------------------------------------------------------------------------

@rule(
    "NGX107",
    "TLS private key path looks unsafe",
    severity="warning",
    category=CAT_SECURITY,
    remediation="Keep private keys in /etc/nginx/ssl (or a secrets mount) with mode 0600.",
)
def unsafe_key_path(ctx) -> Iterator[object]:
    R = unsafe_key_path.__rule__
    for node in ctx.config.find_all("ssl_certificate_key"):
        if not node.args:
            continue
        path = node.args[0]
        if path.startswith(("/etc/nginx", "/etc/ssl", "/run/secrets", "/var/run/secrets")):
            continue
        if path.startswith(("/tmp", "/var/tmp", "/home", ".")) or not path.startswith("/"):
            yield ctx.make(
                R,
                f"private key '{path}' lives outside the hardened certificate "
                "directory.",
                line=node.line, col=node.col, path=node.path_label(),
                meta={"path": path},
            )


# ---------------------------------------------------------------------------
# NGX108 - plain HTTP server without an HTTPS redirect
# ---------------------------------------------------------------------------

@rule(
    "NGX108",
    "Plain HTTP server without an HTTPS redirect",
    severity="info",
    category=CAT_SECURITY,
    remediation="Redirect port 80 to HTTPS with 'return 301 https://$host$request_uri;'.",
)
def no_https_redirect(ctx) -> Iterator[object]:
    R = no_https_redirect.__rule__
    servers = [s for s in ctx.config.find_all("server") if s.block is not None]
    if not any(server_has_tls(s) for s in servers):
        return  # site is HTTP-only by design
    for server in servers:
        if server_has_tls(server):
            continue
        # Look at the whole subtree: the redirect usually lives inside a
        # location block, not directly under the server.
        block_text = " ".join(
            child.source_line() for child in server.walk()
        ).lower()
        if "https://" in block_text or "301" in block_text or "302" in block_text:
            continue
        yield ctx.make(
            R,
            "another server block in this file serves HTTPS, but this HTTP "
            "server does not redirect to it.",
            line=server.line, col=server.col, path=server.path_label(),
            fix=_insert_after(
                server.block[0] if server.block else server,
                "return 301 https://$host$request_uri;",
                "Redirect all traffic to HTTPS",
            ),
        )


# ---------------------------------------------------------------------------
# NGX109 - proxy_pass without an explicit Host header
# ---------------------------------------------------------------------------

@rule(
    "NGX109",
    "proxy_pass without an explicit Host header",
    severity="info",
    category=CAT_SECURITY,
    remediation="Set 'proxy_set_header Host $host;' (or the upstream hostname) explicitly.",
)
def missing_host_header(ctx) -> Iterator[object]:
    R = missing_host_header.__rule__
    for loc in ctx.config.walk():
        if loc.block is None:
            continue
        if not any(c.name == "proxy_pass" for c in loc.block):
            continue
        has_host = any(
            c.name == "proxy_set_header" and c.args and c.args[0].lower() == "host"
            for c in loc.block
        )
        if has_host:
            continue
        inherited = any(
            c.name == "proxy_set_header" and c.args and c.args[0].lower() == "host"
            for a in loc.ancestors() for c in (a.children("proxy_set_header"))
        )
        if inherited:
            continue
        proxy = next(c for c in loc.block if c.name == "proxy_pass")
        yield ctx.make(
            R,
            "proxy_pass without an explicit Host header forwards "
            "'proxy_pass' derived host values, which breaks virtual hosting "
            "and enables cache poisoning.",
            line=proxy.line, col=proxy.col, path=loc.path_label(),
            fix=_insert_after(proxy, "proxy_set_header Host $host;",
                              "Forward the original Host header"),
        )


# ---------------------------------------------------------------------------
# NGX110 - sensitive endpoint without access control
# ---------------------------------------------------------------------------

@rule(
    "NGX110",
    "Sensitive endpoint is publicly reachable",
    severity="warning",
    category=CAT_SECURITY,
    remediation="Restrict it with 'allow'/'deny' or HTTP basic authentication.",
)
def exposed_sensitive_location(ctx) -> Iterator[object]:
    R = exposed_sensitive_location.__rule__
    sensitive = {p.lower() for p in ctx.setting("sensitive_locations", [])}
    for loc in ctx.config.find_all("location"):
        kind, pattern = location_match(loc)
        if kind not in ("prefix", "=", "^~"):
            continue
        normalized = pattern.rstrip("/").lower()
        if normalized not in sensitive and not any(
            normalized.startswith(s) for s in sensitive if s.endswith("*")
        ):
            continue
        if _block_has_access_control(loc):
            continue
        if any(_block_has_access_control(a) for a in loc.ancestors()):
            continue
        yield ctx.make(
            R,
            f"location '{pattern}' exposes a sensitive path without any "
            "access control.",
            line=loc.line, col=loc.col, path=loc.path_label(),
            meta={"pattern": pattern},
        )


# ---------------------------------------------------------------------------
# NGX111 - permissive CORS
# ---------------------------------------------------------------------------

@rule(
    "NGX111",
    "Permissive CORS configuration",
    severity="warning",
    category=CAT_SECURITY,
    remediation="Never combine 'Access-Control-Allow-Origin: *' with credentials - echo the origin instead.",
)
def permissive_cors(ctx) -> Iterator[object]:
    R = permissive_cors.__rule__
    for node in ctx.config.find_all("add_header"):
        if not node.args or node.args[0].lower() != "access-control-allow-origin":
            continue
        value = header_value(node)
        if value.strip() != "*":
            continue
        creds = any(
            n.name == "add_header" and n.args
            and n.args[0].lower() == "access-control-allow-credentials"
            and header_value(n).strip().lower() == "true"
            for n in ctx.config.find_all("add_header")
        )
        yield ctx.make(
            R,
            "'Access-Control-Allow-Origin: *' allows any site to read the "
            "response" + (" and credentials are also allowed." if creds else "."),
            line=node.line, col=node.col, path=node.path_label(),
            severity="error" if creds else "warning",
        )


# ---------------------------------------------------------------------------
# NGX112 - request body size is unbounded
# ---------------------------------------------------------------------------

@rule(
    "NGX112",
    "Request body size is unbounded",
    severity="info",
    category=CAT_SECURITY,
    remediation="Set a sane 'client_max_body_size' (e.g. 10m) to limit upload abuse.",
)
def unbounded_body(ctx) -> Iterator[object]:
    R = unbounded_body.__rule__
    if ctx.config.find_first("client_max_body_size") is not None:
        return
    http = ctx.config.find_first("http")
    if http is None or http.block is None:
        return
    if not any(s.name == "server" for s in http.block):
        return  # fragment file, nothing to protect yet
    yield ctx.make(
        R,
        "no 'client_max_body_size' anywhere - nginx defaults to 1m, but the "
        "limit should be explicit and reviewed.",
        line=http.line, col=http.col, path=http.path_label(),
        fix=_insert_after(http.block[0] if http.block else http,
                          "client_max_body_size 10m;",
                          "Cap request bodies at 10m"),
    )


# ---------------------------------------------------------------------------
# NGX113 - no rate limiting configured
# ---------------------------------------------------------------------------

@rule(
    "NGX113",
    "No request rate limiting",
    severity="info",
    category=CAT_SECURITY,
    remediation="Define a 'limit_req_zone' and apply 'limit_req' to public endpoints.",
)
def no_rate_limit(ctx) -> Iterator[object]:
    R = no_rate_limit.__rule__
    http = ctx.config.find_first("http")
    if http is None:
        return
    has_zone = http.find_first("limit_req_zone") is not None
    has_req = ctx.config.find_first("limit_req") is not None
    has_conn = ctx.config.find_first("limit_conn") is not None
    if has_zone or has_req or has_conn:
        return
    servers = [s for s in http.children("server") if s.block]
    if not servers:
        return
    yield ctx.make(
        R,
        "no rate limiting (limit_req / limit_conn) is configured - the server "
        "is exposed to trivial DoS amplification.",
        line=http.line, col=http.col, path=http.path_label(),
        fix=_insert_after(
            http.block[0] if http.block else http,
            "limit_req_zone $binary_remote_addr zone=req_limit:10m rate=10r/s;",
            "Declare a 10r/s per-IP request zone",
        ),
    )


# ---------------------------------------------------------------------------
# NGX114 - WebDAV write methods enabled
# ---------------------------------------------------------------------------

@rule(
    "NGX114",
    "WebDAV write methods enabled",
    severity="warning",
    category=CAT_SECURITY,
    remediation="Disable dav_methods unless the location is a protected, authenticated share.",
)
def webdav_enabled(ctx) -> Iterator[object]:
    R = webdav_enabled.__rule__
    for node in ctx.config.find_all("dav_methods"):
        write_methods = {"PUT", "DELETE", "MKCOL", "COPY", "MOVE"}
        if write_methods & {a.upper() for a in node.args}:
            yield ctx.make(
                R,
                "dav_methods allows write operations - anyone who can reach "
                "this location may upload or delete files.",
                line=node.line, col=node.col, path=node.path_label(),
                fix=_replace(node, "dav_methods off;", "Disable WebDAV writes"),
            )


# ---------------------------------------------------------------------------
# NGX115 - deprecated X-XSS-Protection header
# ---------------------------------------------------------------------------

@rule(
    "NGX115",
    "Deprecated X-XSS-Protection header",
    severity="info",
    category=CAT_SECURITY,
    remediation="Remove it and rely on a Content-Security-Policy instead.",
)
def legacy_xss_header(ctx) -> Iterator[object]:
    R = legacy_xss_header.__rule__
    for node in ctx.config.find_all("add_header"):
        if node.args and node.args[0].lower() == "x-xss-protection":
            yield ctx.make(
                R,
                "X-XSS-Protection is deprecated and can introduce "
                "vulnerabilities in older browsers.",
                line=node.line, col=node.col, path=node.path_label(),
                fix=Fix(mode=FIX_INSERT_AFTER,
                        new_line='add_header Content-Security-Policy '
                                 '"default-src \'self\'" always;',
                        summary="Replace with a CSP header"),
            )


# ---------------------------------------------------------------------------
# NGX116 - session tickets without rotation
# ---------------------------------------------------------------------------

@rule(
    "NGX116",
    "TLS session tickets enabled",
    severity="info",
    category=CAT_SECURITY,
    remediation="Disable session tickets or rotate the ticket key regularly to keep forward secrecy.",
)
def session_tickets(ctx) -> Iterator[object]:
    R = session_tickets.__rule__
    for node in ctx.config.find_all("ssl_session_tickets"):
        if node.args and is_true(node.args[0]):
            if ctx.config.find_first("ssl_session_ticket_key") is not None:
                continue
            yield ctx.make(
                R,
                "session tickets are on without a rotated ticket key, which "
                "weakens forward secrecy.",
                line=node.line, col=node.col, path=node.path_label(),
                fix=_replace(node, "ssl_session_tickets off;",
                             "Disable session tickets"),
            )


# ---------------------------------------------------------------------------
# NGX117 - TLS server without an explicit protocol baseline
# ---------------------------------------------------------------------------

@rule(
    "NGX117",
    "TLS server relies on default protocols",
    severity="info",
    category=CAT_SECURITY,
    remediation="Declare 'ssl_protocols TLSv1.2 TLSv1.3;' explicitly instead of relying on build defaults.",
)
def tls_default_protocols(ctx) -> Iterator[object]:
    R = tls_default_protocols.__rule__
    if ctx.config.find_first("ssl_protocols") is not None:
        return
    for server in ctx.config.find_all("server"):
        if server.block is None or not server_has_tls(server):
            continue
        cert = server.find_first("ssl_certificate")
        anchor = cert or server.block[0]
        yield ctx.make(
            R,
            "TLS is enabled but 'ssl_protocols' is never set, so the supported "
            "versions depend on the OpenSSL build.",
            line=anchor.line, col=anchor.col, path=server.path_label(),
            fix=_insert_after(anchor, f"ssl_protocols {SAFE_PROTOCOLS};",
                              f"Pin to {SAFE_PROTOCOLS}"),
        )


# ---------------------------------------------------------------------------
# NGX118 - cleartext upstream for a TLS-enabled server
# ---------------------------------------------------------------------------

@rule(
    "NGX118",
    "Cleartext hop to a remote upstream",
    severity="info",
    category=CAT_SECURITY,
    remediation="Terminate TLS end-to-end, or keep the cleartext hop inside a trusted network.",
)
def cleartext_upstream(ctx) -> Iterator[object]:
    R = cleartext_upstream.__rule__
    # Resolve upstream group names to their peers first.
    groups: Dict[str, List[str]] = {}
    for upstream in ctx.config.find_all("upstream"):
        if not upstream.args:
            continue
        peers = [p.args[0].split(":")[0] for p in upstream.children("server")
                 if p.args]
        groups[upstream.args[0]] = peers

    for proxy in ctx.config.find_all("proxy_pass"):
        if not proxy.args:
            continue
        target = proxy.args[0]
        if not target.lower().startswith("http://"):
            continue
        rest = target[len("http://"):]
        host = rest.split("/")[0].split(":")[0]
        if not host:
            continue
        hosts = groups.get(host, [host])
        remote = [h for h in hosts if not _is_private_host(h)]
        if not remote:
            continue
        yield ctx.make(
            R,
            f"traffic to upstream '{host}' crosses the network in cleartext.",
            line=proxy.line, col=proxy.col, path=proxy.path_label(),
            meta={"host": host, "peers": remote},
        )


# ---------------------------------------------------------------------------
# NGX119 - no default_server defined
# ---------------------------------------------------------------------------

@rule(
    "NGX119",
    "No default server for unmatched Host headers",
    severity="info",
    category=CAT_SECURITY,
    remediation="Add a catch-all 'listen 80 default_server;' block that returns 444.",
)
def no_default_server(ctx) -> Iterator[object]:
    R = no_default_server.__rule__
    http = ctx.config.find_first("http")
    if http is None or http.block is None:
        return
    servers = [s for s in http.children("server") if s.block]
    if len(servers) < 2:
        return
    if any("default_server" in flags for _a, flags in
           (pair for s in servers for pair in server_listens(s))):
        return
    yield ctx.make(
        R,
        "with multiple server blocks but no 'default_server', unmatched Host "
        "headers silently fall through to the first block.",
        line=servers[0].line, col=servers[0].col, path=servers[0].path_label(),
    )


# ---------------------------------------------------------------------------
# NGX120 - obsolete TLS cipher ordering
# ---------------------------------------------------------------------------

@rule(
    "NGX120",
    "Server cipher preference disabled",
    severity="info",
    category=CAT_SECURITY,
    remediation="Enable 'ssl_prefer_server_ciphers on;' so the server - not the client - picks the suite.",
)
def no_server_cipher_pref(ctx) -> Iterator[object]:
    R = no_server_cipher_pref.__rule__
    for server in ctx.config.find_all("server"):
        if server.block is None or not server_has_tls(server):
            continue
        node = server.find_first("ssl_prefer_server_ciphers")
        if node is None:
            anchor = server.block[0]
            yield ctx.make(
                R,
                "TLS is enabled but the client picks the cipher suite.",
                line=anchor.line, col=anchor.col, path=server.path_label(),
                fix=_insert_after(anchor, "ssl_prefer_server_ciphers on;",
                                  "Prefer server ciphers"),
            )
        elif node.args and not is_true(node.args[0]):
            yield ctx.make(
                R,
                "'ssl_prefer_server_ciphers' is off - the client chooses the "
                "cipher suite.",
                line=node.line, col=node.col, path=node.path_label(),
                fix=_replace(node, "ssl_prefer_server_ciphers on;",
                             "Prefer server ciphers"),
            )
