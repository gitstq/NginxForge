"""
Metadata about real nginx directives.

The table below is intentionally *descriptive*, not exhaustive: it covers the
directives that actually show up in production configurations. It powers two
audits:

* ``NGX001`` - unknown / misspelled directive name
* ``NGX002`` - directive used in a context where nginx would reject it

Arity is expressed as ``(min, max)``; ``None`` for ``max`` means "unbounded".
"""

from __future__ import annotations

from typing import Dict, Optional, Set, Tuple

# --------------------------------------------------------------------------
# Context vocabulary
# --------------------------------------------------------------------------

MAIN = "main"
EVENTS = "events"
HTTP = "http"
SERVER = "server"
LOCATION = "location"
IF = "if"
UPSTREAM = "upstream"
STREAM = "stream"
MAIL = "mail"
MAP = "map"
GEO = "geo"
TYPES = "types"
LIMIT_EXCEPT = "limit_except"

#: Directive names that open a block (and therefore define a context).
BLOCK_DIRECTIVES: Set[str] = {
    "events", "http", "server", "location", "upstream", "if", "stream",
    "mail", "map", "geo", "types", "limit_except", "split_clients",
    "perl_modules", "thread_pool", "resolver",
}

#: Contexts in which ``if`` may legally appear.
IF_PARENTS = (SERVER, LOCATION)

#: ``(min_args, max_args_or_None)``
Arity = Tuple[int, Optional[int]]

#: name -> (allowed contexts, arity)
DIRECTIVES: Dict[str, Tuple[Tuple[str, ...], Arity]] = {
    # -- core -------------------------------------------------------------
    "user": ((MAIN,), (1, 2)),
    "worker_processes": ((MAIN,), (1, 1)),
    "worker_rlimit_nofile": ((MAIN,), (1, 1)),
    "worker_priority": ((MAIN,), (1, 1)),
    "worker_cpu_affinity": ((MAIN,), (1, None)),
    "daemon": ((MAIN,), (1, 1)),
    "master_process": ((MAIN,), (1, 1)),
    "error_log": ((MAIN, HTTP, MAIL, STREAM, SERVER, LOCATION), (1, 2)),
    "pid": ((MAIN,), (1, 1)),
    "env": ((MAIN,), (1, None)),
    "load_module": ((MAIN,), (1, 1)),
    "lock_file": ((MAIN,), (1, 1)),
    "pcre_jit": ((MAIN,), (1, 1)),
    "ssl_engine": ((MAIN,), (1, 1)),
    "timer_resolution": ((MAIN,), (1, 1)),
    "working_directory": ((MAIN,), (1, 1)),
    "thread_pool": ((MAIN, HTTP,), (1, None)),
    "debug_points": ((MAIN,), (1, 1)),

    # -- events -----------------------------------------------------------
    "worker_connections": ((EVENTS,), (1, 1)),
    "use": ((EVENTS,), (1, 1)),
    "multi_accept": ((EVENTS,), (1, 1)),
    "accept_mutex": ((EVENTS,), (1, 1)),
    "accept_mutex_delay": ((EVENTS,), (1, 1)),
    "debug_connection": ((EVENTS,), (1, None)),

    # -- http core --------------------------------------------------------
    "location": ((SERVER, LOCATION,), (1, None)),
    "listen": ((SERVER,), (1, None)),
    "server_name": ((SERVER,), (1, None)),
    "server_name_in_redirect": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "root": ((HTTP, SERVER, LOCATION, IF), (1, 1)),
    "alias": ((LOCATION,), (1, 1)),
    "index": ((HTTP, SERVER, LOCATION,), (1, None)),
    "error_page": ((HTTP, SERVER, LOCATION, IF), (2, None)),
    "try_files": ((SERVER, LOCATION,), (2, None)),
    "types": ((HTTP, SERVER, LOCATION,), (0, None)),
    "default_type": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "charset": ((HTTP, SERVER, LOCATION, IF), (1, 1)),
    "charset_types": ((HTTP, SERVER, LOCATION,), (1, None)),
    "client_max_body_size": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "client_body_buffer_size": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "client_body_timeout": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "client_header_timeout": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "client_header_buffer_size": ((HTTP, SERVER,), (1, 1)),
    "large_client_header_buffers": ((HTTP, SERVER,), (2, 2)),
    "send_timeout": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "sendfile": ((HTTP, SERVER, LOCATION, IF), (1, 1)),
    "sendfile_max_chunk": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "tcp_nopush": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "tcp_nodelay": ((HTTP, SERVER, LOCATION, STREAM), (1, 1)),
    "keepalive_timeout": ((HTTP, SERVER, LOCATION, UPSTREAM), (1, 2)),
    "keepalive_requests": ((HTTP, SERVER, LOCATION, UPSTREAM), (1, 1)),
    "keepalive_disable": ((HTTP, SERVER, LOCATION,), (1, 2)),
    "lingering_close": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "lingering_time": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "lingering_timeout": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "reset_timedout_connection": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "absolute_redirect": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "port_in_redirect": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "server_tokens": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "msie_padding": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "msie_refresh": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "log_not_found": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "log_subrequest": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "recursive_error_pages": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "if_modified_since": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "open_file_cache": ((HTTP, SERVER, LOCATION,), (1, 2)),
    "open_file_cache_valid": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "open_file_cache_min_uses": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "open_file_cache_errors": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "disable_symlinks": ((HTTP, SERVER, LOCATION,), (1, 2)),
    "subrequest_output_buffer_size": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "aio": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "aio_write": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "directio": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "directio_alignment": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "read_ahead": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "internal": ((LOCATION,), (0, 0)),
    "satisfy": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "resolver": ((HTTP, SERVER, LOCATION, UPSTREAM,), (1, None)),
    "resolver_timeout": ((HTTP, SERVER, LOCATION,), (1, 1)),

    # -- logging ----------------------------------------------------------
    "access_log": ((HTTP, SERVER, LOCATION, IF, LIMIT_EXCEPT, STREAM), (1, None)),
    "log_format": ((HTTP,), (2, None)),
    "open_log_file_cache": ((HTTP, SERVER, LOCATION,), (1, None)),

    # -- gzip -------------------------------------------------------------
    "gzip": ((HTTP, SERVER, LOCATION, IF), (1, 1)),
    "gzip_buffers": ((HTTP, SERVER, LOCATION,), (2, 2)),
    "gzip_comp_level": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "gzip_disable": ((HTTP, SERVER, LOCATION,), (1, None)),
    "gzip_http_version": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "gzip_min_length": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "gzip_proxied": ((HTTP, SERVER, LOCATION,), (1, None)),
    "gzip_types": ((HTTP, SERVER, LOCATION,), (1, None)),
    "gzip_vary": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "gunzip": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "brotli": ((HTTP, SERVER, LOCATION, IF), (1, 1)),
    "brotli_comp_level": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "brotli_types": ((HTTP, SERVER, LOCATION,), (1, None)),
    "zstd": ((HTTP, SERVER, LOCATION, IF), (1, 1)),
    "zstd_comp_level": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "zstd_types": ((HTTP, SERVER, LOCATION,), (1, None)),

    # -- proxy ------------------------------------------------------------
    "proxy_pass": ((LOCATION, IF, LIMIT_EXCEPT,), (1, 1)),
    "proxy_redirect": ((HTTP, SERVER, LOCATION, IF), (1, 2)),
    "proxy_set_header": ((HTTP, SERVER, LOCATION, IF), (2, 2)),
    "proxy_hide_header": ((HTTP, SERVER, LOCATION,), (1, None)),
    "proxy_pass_header": ((HTTP, SERVER, LOCATION,), (1, None)),
    "proxy_set_body": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "proxy_method": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "proxy_http_version": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "proxy_buffering": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "proxy_buffers": ((HTTP, SERVER, LOCATION,), (2, 2)),
    "proxy_buffer_size": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "proxy_busy_buffers_size": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "proxy_max_temp_file_size": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "proxy_temp_file_write_size": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "proxy_connect_timeout": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "proxy_send_timeout": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "proxy_read_timeout": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "proxy_next_upstream": ((HTTP, SERVER, LOCATION,), (1, None)),
    "proxy_next_upstream_tries": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "proxy_next_upstream_timeout": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "proxy_intercept_errors": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "proxy_ignore_headers": ((HTTP, SERVER, LOCATION,), (1, None)),
    "proxy_cache": ((HTTP, SERVER, LOCATION,), (1, None)),
    "proxy_cache_path": ((HTTP,), (1, None)),
    "proxy_cache_key": ((HTTP, SERVER, LOCATION,), (1, None)),
    "proxy_cache_valid": ((HTTP, SERVER, LOCATION,), (1, None)),
    "proxy_cache_methods": ((HTTP, SERVER, LOCATION,), (1, None)),
    "proxy_cache_min_uses": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "proxy_cache_bypass": ((HTTP, SERVER, LOCATION,), (1, None)),
    "proxy_no_cache": ((HTTP, SERVER, LOCATION,), (1, None)),
    "proxy_cache_use_stale": ((HTTP, SERVER, LOCATION,), (1, None)),
    "proxy_cache_background_update": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "proxy_cache_lock": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "proxy_cache_lock_timeout": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "proxy_cache_revalidate": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "proxy_ssl_server_name": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "proxy_ssl_protocols": ((HTTP, SERVER, LOCATION,), (1, None)),
    "proxy_ssl_verify": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "proxy_ssl_trusted_certificate": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "proxy_ssl_certificate": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "proxy_ssl_certificate_key": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "proxy_request_buffering": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "proxy_socket_keepalive": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "proxy_force_ranges": ((HTTP, SERVER, LOCATION,), (1, 1)),

    # -- upstream / load balancing ----------------------------------------
    "upstream": ((HTTP, STREAM), (1, 1)),
    "server": ((HTTP, MAIL, STREAM, UPSTREAM), (0, None)),
    "zone": ((UPSTREAM,), (1, 2)),
    "least_conn": ((UPSTREAM,), (0, 0)),
    "ip_hash": ((UPSTREAM,), (0, 0)),
    "hash": ((UPSTREAM,), (1, None)),
    "random": ((UPSTREAM,), (0, None)),
    "keepalive": ((UPSTREAM,), (1, 1)),
    "least_time": ((UPSTREAM,), (1, None)),
    "queue": ((UPSTREAM,), (1, 2)),
    "sticky": ((UPSTREAM,), (1, None)),
    "ntlm": ((UPSTREAM,), (0, 0)),

    # -- fastcgi / uwsgi / scgi -------------------------------------------
    "fastcgi_pass": ((LOCATION, IF), (1, 1)),
    "fastcgi_index": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "fastcgi_param": ((HTTP, SERVER, LOCATION,), (2, 3)),
    "fastcgi_split_path_info": ((LOCATION,), (1, 1)),
    "fastcgi_buffers": ((HTTP, SERVER, LOCATION,), (2, 2)),
    "fastcgi_buffer_size": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "fastcgi_read_timeout": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "fastcgi_connect_timeout": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "fastcgi_send_timeout": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "fastcgi_keep_conn": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "fastcgi_intercept_errors": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "fastcgi_cache": ((HTTP, SERVER, LOCATION,), (1, None)),
    "fastcgi_cache_path": ((HTTP,), (1, None)),
    "fastcgi_cache_key": ((HTTP, SERVER, LOCATION,), (1, None)),
    "fastcgi_cache_valid": ((HTTP, SERVER, LOCATION,), (1, None)),
    "fastcgi_hide_header": ((HTTP, SERVER, LOCATION,), (1, None)),
    "fastcgi_pass_header": ((HTTP, SERVER, LOCATION,), (1, None)),
    "uwsgi_pass": ((LOCATION, IF), (1, 1)),
    "uwsgi_param": ((HTTP, SERVER, LOCATION,), (2, 3)),
    "uwsgi_read_timeout": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "scgi_pass": ((LOCATION, IF), (1, 1)),
    "scgi_param": ((HTTP, SERVER, LOCATION,), (2, 3)),
    "grpc_pass": ((LOCATION, IF), (1, 1)),
    "grpc_set_header": ((HTTP, SERVER, LOCATION,), (2, 2)),
    "grpc_read_timeout": ((HTTP, SERVER, LOCATION,), (1, 1)),

    # -- ssl / tls --------------------------------------------------------
    "ssl_certificate": ((HTTP, SERVER, STREAM), (1, 1)),
    "ssl_certificate_key": ((HTTP, SERVER, STREAM), (1, 1)),
    "ssl_protocols": ((HTTP, SERVER, STREAM), (1, None)),
    "ssl_ciphers": ((HTTP, SERVER, STREAM), (1, 1)),
    "ssl_prefer_server_ciphers": ((HTTP, SERVER, STREAM), (1, 1)),
    "ssl_session_cache": ((HTTP, SERVER, STREAM), (1, 2)),
    "ssl_session_timeout": ((HTTP, SERVER, STREAM), (1, 1)),
    "ssl_session_tickets": ((HTTP, SERVER, STREAM), (1, 1)),
    "ssl_session_ticket_key": ((HTTP, SERVER, STREAM), (1, 1)),
    "ssl_dhparam": ((HTTP, SERVER, STREAM), (1, 1)),
    "ssl_ecdh_curve": ((HTTP, SERVER, STREAM), (1, 1)),
    "ssl_stapling": ((HTTP, SERVER,), (1, 1)),
    "ssl_stapling_verify": ((HTTP, SERVER,), (1, 1)),
    "ssl_trusted_certificate": ((HTTP, SERVER, STREAM), (1, 1)),
    "ssl_verify_client": ((HTTP, SERVER, STREAM), (1, 1)),
    "ssl_verify_depth": ((HTTP, SERVER, STREAM), (1, 1)),
    "ssl_client_certificate": ((HTTP, SERVER, STREAM), (1, 1)),
    "ssl_crl": ((HTTP, SERVER, STREAM), (1, 1)),
    "ssl_buffer_size": ((HTTP, SERVER,), (1, 1)),
    "ssl_early_data": ((HTTP, SERVER,), (1, 1)),
    "ssl_conf_command": ((HTTP, SERVER,), (2, None)),
    "ssl_reject_handshake": ((HTTP, SERVER,), (1, 1)),
    "ssl_preread": ((STREAM, SERVER), (1, 1)),

    # -- security headers / add_header ------------------------------------
    "add_header": ((HTTP, SERVER, LOCATION, IF), (2, 3)),
    "add_trailer": ((HTTP, SERVER, LOCATION, IF), (2, 3)),
    "more_set_headers": ((HTTP, SERVER, LOCATION, IF), (2, None)),

    # -- access control ---------------------------------------------------
    "allow": ((HTTP, SERVER, LOCATION, LIMIT_EXCEPT), (1, None)),
    "deny": ((HTTP, SERVER, LOCATION, LIMIT_EXCEPT), (1, None)),
    "auth_basic": ((HTTP, SERVER, LOCATION, LIMIT_EXCEPT), (1, 1)),
    "auth_basic_user_file": ((HTTP, SERVER, LOCATION, LIMIT_EXCEPT), (1, 1)),
    "auth_request": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "auth_request_set": ((HTTP, SERVER, LOCATION,), (2, 2)),
    "auth_jwt": ((HTTP, SERVER, LOCATION, LIMIT_EXCEPT), (1, None)),

    # -- request limiting -------------------------------------------------
    "limit_req": ((HTTP, SERVER, LOCATION,), (1, None)),
    "limit_req_zone": ((HTTP,), (1, None)),
    "limit_req_status": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "limit_req_log_level": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "limit_conn": ((HTTP, SERVER, LOCATION,), (1, 2)),
    "limit_conn_zone": ((HTTP,), (1, 2)),
    "limit_conn_status": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "limit_conn_log_level": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "limit_rate": ((HTTP, SERVER, LOCATION, IF), (1, 1)),
    "limit_rate_after": ((HTTP, SERVER, LOCATION, IF), (1, 1)),

    # -- rewrite ----------------------------------------------------------
    "rewrite": ((SERVER, LOCATION, IF), (2, 3)),
    "return": ((SERVER, LOCATION, IF), (1, 2)),
    "break": ((SERVER, LOCATION, IF), (0, 0)),
    "last": ((SERVER, LOCATION, IF), (0, 0)),
    "redirect": ((SERVER, LOCATION, IF), (0, 0)),
    "permanent": ((SERVER, LOCATION, IF), (0, 0)),
    "set": ((SERVER, LOCATION, IF), (2, 2)),
    "uninitialized_variable_warn": ((HTTP, SERVER, LOCATION, IF), (1, 1)),
    "if": ((SERVER, LOCATION,), (1, None)),

    # -- static / autoindex ------------------------------------------------
    "autoindex": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "autoindex_exact_size": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "autoindex_format": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "autoindex_localtime": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "expires": ((HTTP, SERVER, LOCATION, IF), (1, None)),
    "etag": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "add_before_body": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "add_after_body": ((HTTP, SERVER, LOCATION,), (1, 1)),

    # -- real ip -----------------------------------------------------------
    "real_ip_header": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "real_ip_recursive": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "set_real_ip_from": ((HTTP, SERVER, LOCATION,), (1, 1)),

    # -- stub_status / misc modules ---------------------------------------
    "stub_status": ((SERVER, LOCATION,), (0, 1)),
    "status": ((SERVER, LOCATION,), (0, None)),
    "dav_methods": ((HTTP, SERVER, LOCATION,), (1, None)),
    "dav_access": ((HTTP, SERVER, LOCATION,), (1, 3)),
    "create_full_put_path": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "empty_gif": ((LOCATION,), (0, 0)),
    "secure_link": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "secure_link_md5": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "secure_link_secret": ((HTTP, SERVER, LOCATION,), (1, 1)),
    "sub_filter": ((HTTP, SERVER, LOCATION,), (2, 2)),
    "sub_filter_types": ((HTTP, SERVER, LOCATION,), (1, None)),
    "sub_filter_once": ((HTTP, SERVER, LOCATION,), (1, 1)),

    # -- map / geo / split clients ----------------------------------------
    "map": ((HTTP, STREAM), (2, 2)),
    "map_hash_bucket_size": ((HTTP, STREAM), (1, 1)),
    "map_hash_max_size": ((HTTP, STREAM), (1, 1)),
    "geo": ((HTTP, STREAM), (1, 2)),
    "geoip_country": ((HTTP,), (1, 1)),
    "geoip_city": ((HTTP,), (1, 1)),
    "split_clients": ((HTTP, STREAM), (2, 2)),
    "default": ((MAP, GEO), (1, 1)),
    "include": ((MAIN, EVENTS, HTTP, SERVER, LOCATION, STREAM, MAIL, MAP, GEO, TYPES), (1, 1)),

    # -- stream ------------------------------------------------------------
    "stream": ((MAIN,), (0, None)),
    "preread_buffer_size": ((STREAM, SERVER), (1, 1)),
    "proxy_protocol": ((STREAM, SERVER), (1, 1)),

    # -- mail --------------------------------------------------------------
    "mail": ((MAIN,), (0, None)),
    "auth_http": ((MAIL, SERVER), (1, 1)),
    "auth_http_header": ((MAIL, SERVER), (2, 2)),
    "imap_auth": ((MAIL, SERVER), (1, None)),
    "pop3_auth": ((MAIL, SERVER), (1, None)),
    "smtp_auth": ((MAIL, SERVER), (1, None)),
    "protocol": ((MAIL, SERVER), (1, 1)),
    "smtp_greeting_delay": ((MAIL, SERVER), (1, 1)),
    "xclient": ((MAIL, SERVER), (1, 1)),
    "starttls": ((MAIL, SERVER), (1, 1)),
    "max_errors": ((MAIL, SERVER), (1, 1)),
    "timeout": ((MAIL, SERVER), (1, 1)),

    # -- events/http duplication fixes ------------------------------------
    "events": ((MAIN,), (0, None)),
    "http": ((MAIN,), (0, None)),
}

#: Aliases that nginx accepts but that are frequently typos of the real name.
COMMON_TYPOS: Dict[str, str] = {
    "server_names_hash_bucket_size_missing": "",
}


def is_known(name: str) -> bool:
    return name in DIRECTIVES


def allowed_contexts(name: str) -> Tuple[str, ...]:
    entry = DIRECTIVES.get(name)
    return entry[0] if entry else ()


def arity(name: str) -> Optional[Arity]:
    entry = DIRECTIVES.get(name)
    return entry[1] if entry else None


def normalize_context(node_name: str, parent_name: Optional[str]) -> str:
    """Resolve the effective context name for a directive node."""
    if parent_name is None:
        return MAIN
    return parent_name


def suggest(name: str) -> Optional[str]:
    """Return the closest known directive name for a probable typo."""
    if not name:
        return None
    if name in DIRECTIVES:
        return None
    best: Optional[str] = None
    best_score = 0.0
    for candidate in DIRECTIVES:
        score = _similarity(name, candidate)
        if score > best_score:
            best_score = score
            best = candidate
    return best if best_score >= 0.82 else None


def _similarity(a: str, b: str) -> float:
    """Cheap normalised Levenshtein ratio (no external dependencies)."""
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(
                previous[j] + 1,
                current[j - 1] + 1,
                previous[j - 1] + (ca != cb),
            ))
        previous = current
    distance = previous[-1]
    return 1.0 - distance / max(len(a), len(b))
