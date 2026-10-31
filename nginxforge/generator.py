"""
Best-practice configuration generator.

Every template is written so that the generated file passes ``nginxforge audit``
with **zero findings** - the test suite enforces this. That is the real value of
the generator: you get a starting point that is already hardened, instead of a
snippet you have to audit yourself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

# --------------------------------------------------------------------------
# Defaults
# --------------------------------------------------------------------------

DEFAULTS: Dict[str, str] = {
    "domain": "example.com",
    "upstream": "127.0.0.1:8080",
    "name": "backend",
    "root": "/var/www/html",
    "port": "8080",
    "tls": "on",
    "acme": "on",
}

#: Every header a hardened server should emit (kept at server level on purpose:
#: nginx drops inherited add_header as soon as a child block declares one).
SECURITY_HEADERS = [
    'add_header X-Content-Type-Options "nosniff" always;',
    'add_header X-Frame-Options "SAMEORIGIN" always;',
    'add_header Referrer-Policy "strict-origin-when-cross-origin" always;',
    'add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;',
]

HSTS_HEADER = (
    'add_header Strict-Transport-Security '
    '"max-age=31536000; includeSubDomains" always;'
)


@dataclass
class Template:
    """A named, parameterised configuration blueprint."""

    name: str
    title: str
    description: str
    params: Dict[str, str] = field(default_factory=dict)
    build: Optional[Callable[[Dict[str, str]], str]] = None


TEMPLATES: Dict[str, Template] = {}


def template(name: str, title: str, description: str,
             params: Optional[Dict[str, str]] = None) -> Callable:
    """Decorator registering a template builder."""

    def decorator(fn: Callable[[Dict[str, str]], str]) -> Callable:
        TEMPLATES[name] = Template(
            name=name, title=title, description=description,
            params=params or {}, build=fn,
        )
        fn.__template__ = TEMPLATES[name]  # type: ignore[attr-defined]
        return fn

    return decorator


def list_templates() -> List[Template]:
    """Templates in registration order."""
    return list(TEMPLATES.values())


def get_template(name: str) -> Optional[Template]:
    return TEMPLATES.get(name)


def generate(template: str, **overrides: str) -> str:
    """Render ``template`` with the given parameters.

    ``template`` is the blueprint name (see :func:`list_templates`); every
    keyword argument is forwarded to the builder, so template specific keys
    such as ``domain``, ``upstream``, ``root`` or ``name`` all work here.
    """
    tpl = get_template(template)
    if tpl is None or tpl.build is None:
        raise KeyError(f"unknown template: {template}")
    params = dict(DEFAULTS)
    params.update({k: str(v) for k, v in overrides.items() if v is not None})
    return tpl.build(params)


# --------------------------------------------------------------------------
# Shared building blocks
# --------------------------------------------------------------------------

def _on(value: str) -> bool:
    return str(value).strip().lower() in ("on", "true", "yes", "1")


def _indent(lines: List[str], spaces: int) -> List[str]:
    """Re-indent ``lines`` to an absolute column, keeping blanks blank."""
    pad = " " * spaces
    return [pad + line if line.strip() else line for line in lines]


#: Children of a ``server {}`` block live at column 8 (http > server).
SERVER_INDENT = 8


def _main_block(params: Dict[str, str]) -> List[str]:
    return [
        "user  nginx;",
        "worker_processes  auto;",
        "",
        "error_log  /var/log/nginx/error.log warn;",
        "pid        /var/run/nginx.pid;",
        "",
        "events {",
        "    worker_connections  4096;",
        "    multi_accept        on;",
        "}",
        "",
    ]


def _http_preamble() -> List[str]:
    return [
        "    include       /etc/nginx/mime.types;",
        "    default_type  application/octet-stream;",
        "",
        "    log_format  main  '$remote_addr - $remote_user [$time_local] "
        '"$request" \'',
        "                      '$status $body_bytes_sent \"$http_referer\" '",
        '                      \'"$http_user_agent" "$http_x_forwarded_for"\';',
        "    access_log  /var/log/nginx/access.log  main;",
        "",
        "    server_tokens      off;",
        "    sendfile           on;",
        "    tcp_nopush         on;",
        "    tcp_nodelay        on;",
        "    keepalive_timeout  65;",
        "    client_max_body_size  10m;",
        "",
        "    gzip               on;",
        "    gzip_comp_level    5;",
        "    gzip_min_length    1024;",
        "    gzip_proxied       any;",
        "    gzip_vary          on;",
        "    gzip_types         text/plain text/css application/json "
        "application/javascript application/xml image/svg+xml;",
        "",
        "    open_file_cache          max=10000 inactive=60s;",
        "    open_file_cache_valid    60s;",
        "    open_file_cache_min_uses 2;",
        "    open_file_cache_errors   on;",
        "",
        "    limit_req_zone  $binary_remote_addr zone=req_limit:10m rate=10r/s;",
        "    limit_conn_zone $binary_remote_addr zone=conn_limit:10m;",
        "",
        "    proxy_cache_path  /var/cache/nginx/proxy levels=1:2 "
        "keys_zone=proxy_zone:10m max_size=1g inactive=60m use_temp_path=off;",
        "",
    ]


def _tls_lines(params: Dict[str, str]) -> List[str]:
    domain = params["domain"]
    return _indent([
        f"ssl_certificate      /etc/nginx/ssl/{domain}/fullchain.pem;",
        f"ssl_certificate_key  /etc/nginx/ssl/{domain}/privkey.pem;",
        "ssl_protocols              TLSv1.2 TLSv1.3;",
        "ssl_prefer_server_ciphers  on;",
        "ssl_session_cache          shared:SSL:10m;",
        "ssl_session_timeout        1d;",
        "ssl_session_tickets        off;",
    ], SERVER_INDENT)


def _acme_location() -> List[str]:
    return _indent([
        "",
        "location ^~ /.well-known/acme-challenge/ {",
        "    root /var/www/acme;",
        "    default_type \"text/plain\";",
        "}",
    ], SERVER_INDENT)


def _wrap_http(body: List[str]) -> str:
    lines = _main_block({})
    lines.append("http {")
    lines.extend(_http_preamble())
    lines.extend(body)
    lines.append("}")
    return "\n".join(lines) + "\n"


def _redirect_server(params: Dict[str, str]) -> List[str]:
    domain = params["domain"]
    lines = [
        "    server {",
        "        listen      80 default_server;",
        "        listen      [::]:80 default_server;",
        f"        server_name {domain};",
        "",
    ]
    lines.extend(_indent(SECURITY_HEADERS, SERVER_INDENT))
    if _on(params["acme"]):
        lines.extend(_acme_location())
    lines.extend([
        "",
        "        location / {",
        "            return 301 https://$host$request_uri;",
        "        }",
        "    }",
        "",
    ])
    return lines


def _http_server_open(params: Dict[str, str]) -> List[str]:
    domain = params["domain"]
    lines = [
        "    server {",
        "        listen      80;",
        f"        server_name {domain};",
        "",
    ]
    lines.extend(_indent(SECURITY_HEADERS, SERVER_INDENT))
    return lines


def _https_server_open(params: Dict[str, str]) -> List[str]:
    domain = params["domain"]
    lines = [
        "    server {",
        "        listen      443 ssl http2;",
        "        listen      [::]:443 ssl http2;",
        f"        server_name {domain};",
        "",
    ]
    lines.extend(_tls_lines(params))
    lines.append("")
    lines.extend(_indent(SECURITY_HEADERS + [HSTS_HEADER], SERVER_INDENT))
    return lines


def _proxy_headers() -> List[str]:
    return [
        "        proxy_http_version  1.1;",
        "        proxy_set_header    Host              $host;",
        "        proxy_set_header    X-Real-IP         $remote_addr;",
        "        proxy_set_header    X-Forwarded-For   $proxy_add_x_forwarded_for;",
        "        proxy_set_header    X-Forwarded-Proto $scheme;",
        "        proxy_connect_timeout 5s;",
        "        proxy_send_timeout    30s;",
        "        proxy_read_timeout    60s;",
    ]


# --------------------------------------------------------------------------
# Templates
# --------------------------------------------------------------------------

@template(
    "reverse-proxy",
    "Reverse proxy",
    "TLS terminating reverse proxy in front of a single HTTP backend.",
    {"domain": "public hostname", "upstream": "backend host:port"},
)
def _tpl_reverse_proxy(params: Dict[str, str]) -> str:
    body: List[str] = [
        f"    upstream {params['name']} {{",
        f"        server {params['upstream']} max_fails=3 fail_timeout=10s;",
        "        keepalive 32;",
        "    }",
        "",
    ]
    if _on(params["tls"]):
        body.extend(_redirect_server(params))
        body.extend(_https_server_open(params))
    else:
        body.extend(_http_server_open(params))
    body.extend([
        "",
        "        location / {",
        f"            proxy_pass http://{params['name']};",
    ])
    body.extend("    " + line for line in _proxy_headers())
    body.extend([
        "            proxy_cache           proxy_zone;",
        "            proxy_cache_valid     200 302 10m;",
        "            proxy_cache_use_stale error timeout updating;",
        "            limit_req            zone=req_limit burst=20 nodelay;",
        "        }",
        "    }",
    ])
    return _wrap_http(body)


@template(
    "static",
    "Static site",
    "Static file server with caching, compression and hardened headers.",
    {"domain": "public hostname", "root": "document root"},
)
def _tpl_static(params: Dict[str, str]) -> str:
    body: List[str] = []
    if _on(params["tls"]):
        body.extend(_redirect_server(params))
        open_lines = _https_server_open(params)
    else:
        open_lines = _http_server_open(params)
    body.extend(open_lines)
    body.extend([
        "",
        f"        root {params['root']};",
        "        index index.html index.htm;",
        "",
        "        location / {",
        "            try_files $uri $uri/ =404;",
        "        }",
        "",
        "        location ~* \\.(?:css|js|woff2?|png|jpe?g|gif|svg|ico|webp)$ {",
        "            expires 30d;",
        "            try_files $uri =404;",
        "        }",
        "    }",
    ])
    return _wrap_http(body)


@template(
    "spa",
    "Single page application",
    "History-routing SPA with immutable asset caching and an index fallback.",
    {"domain": "public hostname", "root": "build output directory"},
)
def _tpl_spa(params: Dict[str, str]) -> str:
    body: List[str] = []
    open_lines = (_https_server_open(params) if _on(params["tls"])
                  else _http_server_open(params))
    if _on(params["tls"]):
        body.extend(_redirect_server(params))
    body.extend(open_lines)
    body.extend([
        "",
        f"        root {params['root']};",
        "        index index.html;",
        "",
        "        location / {",
        "            try_files $uri $uri/ /index.html;",
        "        }",
        "",
        "        location /assets/ {",
        "            expires 1y;",
        "            try_files $uri =404;",
        "        }",
        "    }",
    ])
    return _wrap_http(body)


@template(
    "websocket",
    "WebSocket proxy",
    "Upgrade-aware proxy with long read timeouts for persistent connections.",
    {"domain": "public hostname", "upstream": "backend host:port"},
)
def _tpl_websocket(params: Dict[str, str]) -> str:
    body: List[str] = [
        f"    upstream {params['name']}_ws {{",
        f"        server {params['upstream']} max_fails=3 fail_timeout=10s;",
        "        keepalive 32;",
        "    }",
        "",
    ]
    if _on(params["tls"]):
        body.extend(_redirect_server(params))
        body.extend(_https_server_open(params))
    else:
        body.extend(_http_server_open(params))
    body.extend([
        "",
        "        location /ws/ {",
        f"            proxy_pass http://{params['name']}_ws;",
        "            proxy_http_version  1.1;",
        '            proxy_set_header    Upgrade    $http_upgrade;',
        '            proxy_set_header    Connection "upgrade";',
        "            proxy_set_header    Host       $host;",
        "            proxy_set_header    X-Real-IP  $remote_addr;",
        "            proxy_set_header    X-Forwarded-For $proxy_add_x_forwarded_for;",
        "            proxy_set_header    X-Forwarded-Proto $scheme;",
        "            proxy_read_timeout  3600s;",
        "            proxy_send_timeout  3600s;",
        "            proxy_buffering     off;",
        "        }",
        "    }",
    ])
    return _wrap_http(body)


@template(
    "api-gateway",
    "API gateway",
    "Rate limited JSON API gateway with health checks and cache bypass.",
    {"domain": "public hostname", "upstream": "backend host:port"},
)
def _tpl_api_gateway(params: Dict[str, str]) -> str:
    body: List[str] = [
        f"    upstream {params['name']} {{",
        f"        server {params['upstream']} max_fails=3 fail_timeout=10s;",
        "        keepalive 64;",
        "    }",
        "",
    ]
    if _on(params["tls"]):
        body.extend(_redirect_server(params))
        body.extend(_https_server_open(params))
    else:
        body.extend(_http_server_open(params))
    body.extend([
        "",
        "        location = /healthz {",
        "            access_log off;",
        "            return 200 \"ok\\n\";",
        "        }",
        "",
        "        location /api/ {",
        f"            proxy_pass http://{params['name']};",
    ])
    body.extend("    " + line for line in _proxy_headers())
    body.extend([
        "            proxy_cache           proxy_zone;",
        "            proxy_cache_valid     200 1m;",
        "            proxy_cache_methods   GET HEAD;",
        "            limit_req            zone=req_limit burst=40 nodelay;",
        "            limit_conn           conn_limit 20;",
        "        }",
        "    }",
    ])
    return _wrap_http(body)


@template(
    "load-balancer",
    "Load balancer",
    "Least-connection balancing across three peers with passive health checks.",
    {"domain": "public hostname", "upstream": "peer1 host:port (others derived)"},
)
def _tpl_load_balancer(params: Dict[str, str]) -> str:
    host, _, port = params["upstream"].rpartition(":")
    port = port or "80"
    peers = [f"{host}:{port}"]
    # Derive two extra peers by incrementing the port; callers normally pass
    # explicit peers through --set, this keeps the template self-contained.
    if port.isdigit():
        peers.append(f"{host}:{int(port) + 1}")
        peers.append(f"{host}:{int(port) + 2}")

    body: List[str] = [
        f"    upstream {params['name']} {{",
        "        least_conn;",
    ]
    for peer in peers:
        body.append(f"        server {peer} max_fails=3 fail_timeout=10s;")
    body.extend([
        "        keepalive 64;",
        "    }",
        "",
    ])
    if _on(params["tls"]):
        body.extend(_redirect_server(params))
        body.extend(_https_server_open(params))
    else:
        body.extend(_http_server_open(params))
    body.extend([
        "",
        "        location / {",
        f"            proxy_pass http://{params['name']};",
    ])
    body.extend("    " + line for line in _proxy_headers())
    body.extend([
        "            proxy_next_upstream     error timeout http_502 http_503;",
        "            proxy_next_upstream_tries 3;",
        "            limit_req               zone=req_limit burst=50 nodelay;",
        "        }",
        "    }",
    ])
    return _wrap_http(body)


@template(
    "cache",
    "Caching accelerator",
    "Aggressive micro-caching layer with stale-while-revalidate behaviour.",
    {"domain": "public hostname", "upstream": "backend host:port"},
)
def _tpl_cache(params: Dict[str, str]) -> str:
    body: List[str] = [
        f"    upstream {params['name']} {{",
        f"        server {params['upstream']} max_fails=3 fail_timeout=10s;",
        "        keepalive 32;",
        "    }",
        "",
    ]
    if _on(params["tls"]):
        body.extend(_redirect_server(params))
        body.extend(_https_server_open(params))
    else:
        body.extend(_http_server_open(params))
    body.extend([
        "        add_header X-Cache-Status $upstream_cache_status;",
        "",
        "        location / {",
        f"            proxy_pass http://{params['name']};",
    ])
    body.extend("    " + line for line in _proxy_headers())
    body.extend([
        "            proxy_cache              proxy_zone;",
        "            proxy_cache_key          $scheme$host$request_uri;",
        "            proxy_cache_valid        200 302 5s;",
        "            proxy_cache_valid        404 1m;",
        "            proxy_cache_use_stale    error timeout updating http_500 "
        "http_502 http_503 http_504;",
        "            proxy_cache_background_update on;",
        "            proxy_cache_lock         on;",
        "            limit_req                zone=req_limit burst=30 nodelay;",
        "        }",
        "    }",
    ])
    return _wrap_http(body)


@template(
    "tls",
    "TLS termination only",
    "Minimal HTTPS endpoint that forwards everything to a backend.",
    {"domain": "public hostname", "upstream": "backend host:port"},
)
def _tpl_tls(params: Dict[str, str]) -> str:
    body: List[str] = []
    body.extend(_redirect_server(params))
    body.extend(_https_server_open(params))
    body.extend([
        "",
        "        location / {",
        f"            proxy_pass http://{params['upstream']};",
    ])
    body.extend("    " + line for line in _proxy_headers())
    body.extend([
        "            limit_req zone=req_limit burst=20 nodelay;",
        "        }",
        "    }",
    ])
    return _wrap_http(body)
