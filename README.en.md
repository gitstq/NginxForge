<div align="center">

# 🔥 NginxForge

**Zero-dependency · offline-first · pure-Python nginx config parser, auditor, fixer and generator**

[简体中文](README.md) · [繁體中文](README.zh-TW.md) · [English](README.en.md)

![Python](https://img.shields.io/badge/python-3.8%2B-blue?logo=python&logoColor=white)
![Dependencies](https://img.shields.io/badge/runtime%20dependencies-0-brightgreen)
![Rules](https://img.shields.io/badge/rules-54-orange)
![Tests](https://img.shields.io/badge/tests-125%20passing-success)
![Offline](https://img.shields.io/badge/needs-nginx%20binary%3F%20NO-important)
![License](https://img.shields.io/badge/license-MIT-green)

</div>

---

## 📑 Table of contents

| Section | What's inside |
| --- | --- |
| [🎉 Introduction](#-introduction) | What NginxForge is, the problem it solves, how it differs |
| [✨ Key features](#-key-features) | Parse / audit / semantic diff / autofix / generate / multi-format reports |
| [🚀 Quick start](#-quick-start) | Install and get a first result in 30 seconds |
| [📖 Usage guide](#-usage-guide) | 7 subcommands, settings, exit codes, Python API |
| [💡 Design & roadmap](#-design--roadmap) | Architecture, key trade-offs, release roadmap |
| [📦 Packaging & deployment](#-packaging--deployment) | Build, Docker, CI integration, pre-commit |
| [🤝 Contributing](#-contributing) | Dev setup, adding rules / templates, commit convention |
| [📄 License](#-license) | Full MIT text and disclaimers |

---

## 🎉 Introduction

An nginx config file is a small language that "looks like a cousin of JSON and is full of traps": there is no real boolean type, `add_header` is silently dropped as soon as a child block declares its own, `if` inside `location` has famously non-intuitive behaviour, mixing `root` and `alias` produces 404s, and omitting one protocol version in `ssl_protocols` downgrades your whole site. These problems share three traits:

1. **They only surface in production** — `nginx -t` checks syntax, not semantics;
2. **They are hard to review** — "looks different" and "is different" are two different things;
3. **They are expensive to fix** — you end up re-reading the docs to confirm what `keepalive_timeout` should be.

**NginxForge** is the offline toolbox built for exactly that. It implements a hand-written **lexer → recursive-descent parser → AST** for the nginx config language in pure Python, runs **54 configurable rules** over that AST, emits a human-readable report, and can produce **line-level, reversible autofix patches**.

### What it deliberately does *not* do

| Not doing | Why |
| --- | --- |
| ❌ Shell out to `nginx -t` / `nginx -T` | Target environments frequently have no nginx binary at all (CI containers, laptops, air-gapped networks) |
| ❌ Pull in third-party runtime dependencies | Installing a linter shouldn't drag in half an ecosystem; after `pip install` you get one pure-Python package |
| ❌ Make network calls | Configs contain internal hostnames and key paths; any outbound traffic is unacceptable |
| ❌ One-click "optimise everything" | Real fixes must be explainable; `--safe` only rewrites existing lines and never adds or removes any |

### How it compares

| Capability | `nginx -t` | Generic YAML/TOML linter | Online config checker | **NginxForge** |
| --- | :-: | :-: | :-: | :-: |
| Syntax check | ✅ | ❌ | ✅ | ✅ |
| Semantic / best-practice rules | ❌ | ❌ | partial | **54** |
| Runs offline | ✅ | ✅ | ❌ | **✅** |
| Needs an nginx binary | ✅ | ❌ | ❌ | **❌** |
| Automatic fixes | ❌ | ❌ | ❌ | **✅** |
| Semantic diff (order/indent agnostic) | ❌ | ❌ | ❌ | **✅** |
| Generate a compliant config | ❌ | ❌ | partial | **✅ 8 templates** |
| SARIF / code scanning | ❌ | partial | ❌ | **✅** |

---

## ✨ Key features

### 🔍 A complete front end for the nginx config language

- **Hand-written lexer** — handles `#` comments, single/double-quoted strings, backslash escapes, multi-line strings, and the `{` / `}` inside `$variables` and regexes.
- **Recursive-descent parser** — produces a `Directive` tree with parent links; every node remembers its **file, line, column and context path** (`http > server > location /api/ > proxy_pass`).
- **Fault tolerant** — a syntax error **does not abort** parsing: it is recorded as an `NGX004` finding and the parser resynchronises. A config with three mistakes shows you all three at once.
- **280-entry directive metadata table** — each entry stores "which contexts is this allowed in" and "how many arguments". Typing `sever_name` gets you "did you mean `server_name`?".

### 🛡️ 54 rules across four domains

| Range | Category | Count | Examples |
| --- | --- | --- | --- |
| `NGX0xx` | **correctness** | 15 | unknown directive / illegal context / wrong arity / `try_files` without a fallback / `root` + `alias` conflict / `proxy_pass` slash mismatch / duplicate `server` |
| `NGX1xx` | **security** | 20 | version disclosure / missing hardening headers / directory listing on / obsolete TLS / weak ciphers / missing HSTS / suspicious key path / cleartext hop to a remote upstream / writable WebDAV / permissive CORS |
| `NGX2xx` | **performance** | 14 | compression off / `sendfile` off / `worker_processes` not `auto` / static assets without cache headers / HTTPS without HTTP/2 / `upstream` without `keepalive` |
| `NGX3xx` | **style** | 5 | mixed tabs and spaces / trailing whitespace / very long lines / hard-coded unconventional paths / non-snake_case directive names |

Every rule carries a **severity** (`error` / `warning` / `info`), a **clickable location**, a **plain-language reason**, and a **remediation**.

### 🔀 Semantic diff — not text diff

Swap the order of two `location` blocks, or re-indent from 4 spaces to tabs, and a text diff floods you with hundreds of noisy lines. A semantic diff says:

```console
$ nginxforge diff old.conf new.conf
# old.conf -> new.conf
# configurations are semantically identical
```

Both sides are **canonicalised** (sorted by context path, stripped of indentation and whitespace differences) and then paired by **identity signature**. Reordering and re-indenting = no difference. Changed arguments = one precise `changed` entry.

### 🩹 Explainable, reversible autofixes

```console
$ nginxforge fix nginx.conf --safe          # dry run, prints a unified diff
$ nginxforge fix nginx.conf --safe --apply  # write it
```

- Fixes are **line-level patches** (`replace` / `delete` / `insert_before` / `insert_after`), applied bottom-up so line numbers don't drift, reusing the target line's original indentation.
- `--safe` keeps only `replace` mode and **never adds or removes a line** — ideal for CI or a repo you don't fully trust.
- A single line is only ever rewritten by one rule, so patches never collide.

### 🏭 Generator: start from a config that already audits clean

```console
$ nginxforge gen --template reverse-proxy --domain example.com --upstream 10.0.0.5:8080 --audit
nginxforge: generated configuration passes all rules ✔
```

Eight templates — `reverse-proxy` / `static` / `spa` / `websocket` / `api-gateway` / `load-balancer` / `cache` / `tls`. **Every template's output is required by the test suite to produce zero audit findings.** That's not boilerplate; it's a baseline you can ship.

### 📊 Five report formats, for humans and machines

| Format | Use it for |
| --- | --- |
| `text` | Coloured terminal output with `↳` reasons and `✚` fix hints |
| `json` | A stable machine contract for scripts |
| `sarif` | SARIF 2.1.0 uploaded straight to GitHub code scanning |
| `markdown` | A table to paste into a PR comment |
| `html` | A **single self-contained file** with inlined CSS/JS — dark theme, offline, filterable |

### 🧩 Zero dependencies · offline · typed

- **Zero** runtime dependencies, standard library only.
- Python **3.8+** (through 3.12), ships `py.typed` so `mypy` can check your call sites.
- Works as a CLI *and* as a library (`from nginxforge import parse`).

---

## 🚀 Quick start

### Install

```bash
# Option 1: install from source (recommended, gives you the `nginxforge` command)
git clone https://github.com/gitstq/NginxForge.git
cd NginxForge
pip install -e .

# Option 2: no install at all (lightest)
python -m nginxforge --help

# Option 3: user-level install
pip install --user .
```

> **Requirements**: Python 3.8 or newer. **No** nginx binary, **no** network access, **no** third-party packages.

### Three commands to get going

```bash
# 1. Audit an existing config
nginxforge audit /etc/nginx/nginx.conf

# 2. See what can be fixed automatically (dry run by default)
nginxforge fix /etc/nginx/nginx.conf --safe

# 3. Generate a config that audits clean
nginxforge gen --template reverse-proxy --domain example.com --upstream 127.0.0.1:8080 -o nginx.conf
```

### Real output

```console
$ nginxforge audit tests/fixtures/bad.conf
nginxforge 1.0.0 - nginx configuration audit
scanned 1 file(s) · 54 rule(s) · 25 finding(s)

── tests/fixtures/bad.conf ────────
  ✖ NGX104  Obsolete TLS/SSL protocol enabled
      tests/fixtures/bad.conf:25  (http > server > ssl_protocols SSLv3 TLSv1 TLSv1.1 TLSv1.2)
      ssl_protocols  SSLv3 TLSv1 TLSv1.1 TLSv1.2;
      obsolete protocol(s) enabled: SSLv3, TLSv1, TLSv1.1.
      ↳ Only TLSv1.2 and TLSv1.3 are considered safe today.
      ✚ fix: Restrict to TLSv1.2 TLSv1.3

  ⚠ NGX101  nginx version is disclosed
      tests/fixtures/bad.conf:13  (http > server_tokens on)
      server_tokens on;
      'server_tokens on' leaks the nginx version in responses and error pages.
      ↳ Set 'server_tokens off;' to stop advertising the exact nginx version.
      ✚ fix: Disable version disclosure
```

---

## 📖 Usage guide

### 1️⃣ `audit`

```bash
# A single file, or a directory (recursively scans *.conf)
nginxforge audit nginx.conf
nginxforge audit /etc/nginx

# Security rules only, fail the build on any warning (CI usage)
nginxforge audit ./conf.d --select security --fail-on warning

# SARIF for GitHub code scanning
nginxforge audit ./conf.d --format sarif --output nginxforge.sarif

# Self-contained HTML report
nginxforge audit ./conf.d --format html --output report.html

# One-line summary
nginxforge audit ./conf.d --summary
```

| Flag | Meaning |
| --- | --- |
| `-f, --format` | `text` (default) / `json` / `sarif` / `markdown` / `html` |
| `-o, --output` | Write to a file; stdout when omitted |
| `--select` | Run only these rules or categories, repeatable: `--select NGX104 --select security` |
| `--ignore` | Skip these rules or categories |
| `--min-severity` | Drop findings below this level |
| `--fail-on` | `exit 1` at this level; `never` disables failing |
| `--config` | JSON settings file (see *Tunable settings*) |
| `--set` | Override one setting: `--set max_keepalive_timeout=60` |
| `--no-color` | Disable ANSI colour (auto-disabled when not a TTY) |

**Tunable settings** (JSON via `--config`, or one-off via `--set`):

| Key | Default | Meaning |
| --- | --- | --- |
| `max_keepalive_timeout` | `75` | Above this many seconds, report NGX204 |
| `min_worker_connections` | `1024` | Below this, report NGX206 |
| `min_client_max_body_size` | `"1m"` | Below this, report NGX112 |
| `required_headers` | `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` | Headers NGX102 demands |
| `forbidden_tls` | `SSLv2 SSLv3 TLSv1 TLSv1.1` | Protocols NGX104 treats as obsolete |
| `weak_cipher_tokens` | `NULL aNULL eNULL MD5 RC4 DES 3DES EXPORT LOW SEED IDEA PSK` | Tokens NGX105 treats as weak |
| `sensitive_locations` | `/status /admin /.git /.env /metrics …` | Paths NGX110 treats as sensitive |

```json
{
  "max_keepalive_timeout": 60,
  "required_headers": ["X-Content-Type-Options", "X-Frame-Options", "Referrer-Policy", "Content-Security-Policy"],
  "sensitive_locations": ["/status", "/admin", "/internal"]
}
```

### 2️⃣ `fix`

```bash
nginxforge fix nginx.conf                 # dry run: print what would change
nginxforge fix nginx.conf --apply         # write it
nginxforge fix nginx.conf --safe --apply  # rewrite existing lines only, no add/remove
nginxforge fix nginx.conf --rule NGX101 --rule NGX103 --apply
nginxforge fix /etc/nginx --safe --apply  # whole directory
```

| Flag | Meaning |
| --- | --- |
| `--apply` | Write back to disk; **the default is always a dry run** |
| `--safe` | `replace` mode only — never add or delete a line |
| `--rule` | Apply only fixes from these rule ids |
| `--select` / `--ignore` / `--min-severity` / `--fail-on` / `--config` / `--set` | Same as `audit` |

> 💡 Recommended order: run `--safe --apply` for the low-risk rewrites, review the diff, then relax to the full mode.
> The fixer guarantees one edit per line, but **keep your config under version control before running `--apply`**.

### 3️⃣ `diff`

```bash
nginxforge diff old.conf new.conf
nginxforge diff old.conf new.conf --unified    # also print a unified diff of the canonical form
nginxforge diff old.conf new.conf --format json
```

```console
# old.conf -> new.conf
# 0 added, 0 removed, 1 changed
```

The **identity signature** is context path + directive name + argument list, so:

| Kind of change | Semantic diff result |
| --- | --- |
| Sibling blocks reordered | no difference |
| 4 spaces → tabs | no difference |
| Blank lines / comments changed | no difference |
| Directive arguments changed | `changed` |
| Directive added / removed | `added` / `removed` |

### 4️⃣ `gen`

```bash
nginxforge gen --list                     # list the 8 templates

nginxforge gen --template reverse-proxy \
    --domain example.com --upstream 10.0.0.5:8080 \
    --name app_backend --audit --out nginx.conf

nginxforge gen -t static --domain cdn.example.com --root /var/www/cdn --out static.conf
nginxforge gen -t spa    --domain app.example.com  --root /var/www/app --out spa.conf
nginxforge gen -t tls    --domain api.example.com  --upstream 10.0.0.9:3000 --tls on
nginxforge gen -t cache  --domain www.example.com  --upstream 10.0.0.5:8080 --set rate=50r/s
```

| Template | What it builds | Main params |
| --- | --- | --- |
| `reverse-proxy` | TLS-terminating proxy in front of one backend | `domain` `upstream` |
| `static` | Static site with caching and compression | `domain` `root` |
| `spa` | History-routing SPA, immutable asset caching | `domain` `root` |
| `websocket` | Upgrade-aware proxy with long read timeouts | `domain` `upstream` |
| `api-gateway` | Rate-limited JSON gateway with a health check | `domain` `upstream` |
| `load-balancer` | `least_conn` across three peers, passive health checks | `domain` `upstream` |
| `cache` | Aggressive micro-caching with stale-while-revalidate | `domain` `upstream` |
| `tls` | Minimal TLS termination that forwards everything | `domain` `upstream` |

Common flags: `--domain` `--upstream` `--root` `--port` `--name` (upstream group) `--tls {on,off}` `--set k=v` `-o/--out` `--audit`.

### 5️⃣ `fmt`

```bash
nginxforge fmt nginx.conf                     # print the reformatted result
nginxforge fmt nginx.conf --in-place          # rewrite in place
nginxforge fmt ./conf.d --indent "  " --check # CI mode: exit 1 if unformatted
```

### 6️⃣ `parse`

```bash
nginxforge parse nginx.conf            # indented tree with context paths and line numbers
nginxforge parse nginx.conf -f json    # JSON
```

### 7️⃣ `rules`

```bash
nginxforge rules                # table of all 54 rules
nginxforge rules NGX104         # explain a single rule
nginxforge rules --format json
```

### 🔢 Exit codes

| Code | Meaning |
| --- | --- |
| `0` | No findings, or the `--fail-on` threshold was not reached |
| `1` | Findings reached `--fail-on` (default `error`); or `fmt --check` failed |
| `2` | Usage error (missing argument, bad path, unknown template/rule) |

### 🐍 Python API

```python
from nginxforge import parse, parse_file
from nginxforge.engine import audit, load_default_rules, AuditOptions
from nginxforge.reporters import render
from nginxforge.generator import generate
from nginxforge.semdiff import compare

load_default_rules()                      # register the built-in rules (required when used as a library)

# --- parse --------------------------------------------------------------
cfg = parse_file("nginx.conf")
print(cfg.ok)                             # any syntax errors?
print(cfg.errors)                         # -> [ConfigError(...)]
for node in cfg.find_all("server"):
    print(node.context_path())            # http > server
    print(node.path_label())              # http > server > listen 443 ssl

# --- audit --------------------------------------------------------------
result = audit([cfg], AuditOptions(min_severity="warning"))
result.counts()                           # {'error': 2, 'warning': 9, 'info': 0}
result.syntax_errors                      # syntax errors (result.ok == not syntax_errors)
for f in result.findings:
    print(f.rule_id, f.location, f.message, f.fix)

print(render("sarif", result, "1.0.0"))   # any report format

# --- semantic diff ------------------------------------------------------
d = compare(parse_file("old.conf"), parse_file("new.conf"))
d.identical, d.change_count, d.summary()

# --- generate -----------------------------------------------------------
text = generate("reverse-proxy", domain="example.com", upstream="127.0.0.1:8080")
```

---

## 💡 Design & roadmap

### 🏛️ Architecture

```
                 ┌──────────────────────────────────────────┐
   nginx.conf ─▶ │ lexer.py        comments/quotes/escapes   │
                 └───────────────┬──────────────────────────┘
                                 ▼ token stream
                 ┌──────────────────────────────────────────┐
                 │ parser.py      recursive descent → AST    │
                 │ directives.py  280-entry context/arity DB │
                 └───────────────┬──────────────────────────┘
                                 ▼ AST
    ┌────────────┬───────────────┼────────────────┬──────────────┐
    ▼            ▼               ▼                ▼              ▼
 engine.py   generator.py   semdiff.py      fixer.py      reporters/
 rule engine   templates      canonicalise    line patches   text/json/
 │                                                          sarif/md/html
 └─ rules/{correctness,security,performance,style}.py
                                 ▼
                             cli.py
```

### 🎯 Five decisions that shaped it

**1. Fault tolerance beats strictness.** For a broken config, what you need is *the whole list of problems*, not the first one. When the parser hits something like `server_tokens off { ... }` (a missing `;` swallowed by `{`), it records `NGX004` and resynchronises at the next safe point. A dedicated `_cannot_take_a_block()` heuristic turns that into a human sentence rather than "unexpected token".

**2. Rules register themselves via a decorator, not a hardcoded list.**

```python
@rule("NGX101", "nginx version is disclosed",
      severity="warning", category="security",
      remediation="Set 'server_tokens off;' …")
def server_tokens_on(ctx: AuditContext): ...
```

Adding a rule is adding a function: it joins the registry, shows up in `rules`, and gets SARIF metadata automatically. The decorator validates `severity` / `category` at registration time, so a typo fails fast.

**3. Rules are isolated from each other.** The engine runs each rule inside its own exception boundary. If one rule crashes on a malformed node it degrades to an internal warning and the other 53 still run.

**4. Fixes must be line-level and mode-based.** No AST rewriting, because that loses comments and blank lines — and nginx operators rely heavily on comments. Each `Fix` carries a `mode` (`replace`/`delete`/`insert_before`/`insert_after`) plus one line of text; patches are applied bottom-up to avoid line drift and reuse the target line's indentation. `--safe` is the guardrail for untrusted contexts.

**5. The generator's hard constraint is that it audits itself.** The test suite walks all eight templates and asserts **zero findings**. That invariant is what turns "generate" from "here's a snippet" into "here's a baseline" — in earlier iterations it caught mis-indented `add_header` lines, an `upstream` block nested inside `server`, and a false `proxy_buffering off` warning in the WebSocket template.

### 🗺️ Roadmap

| Version | Theme | Planned |
| --- | --- | --- |
| **v1.0.x** | Stabilisation | ✅ 54 rules / 8 templates / 5 reports / semantic diff / safe fixes |
| **v1.1** | Configurable rules | Per-rule enable flags and thresholds; project-level `.nginxforge.toml`; `--baseline` snapshots that only report new findings |
| **v1.2** | Ecosystem | OpenResty / APISIX / NGINX Unit extension directives; full `stream` / `mail` block rules; cross-file `include` resolution |
| **v1.3** | Collaboration | `nginxforge explain <rule>`; an LSP prototype for VS Code / JetBrains; comment-preserving `fmt` |
| **v2.0** | Platform | Third-party rule packs; a batch dashboard across many config repos; bidirectional mapping with Kubernetes Ingress / IngressRoute |

**Vote with an issue** — this roadmap is not a promise; describing your scenario moves it up the list.

---

## 📦 Packaging & deployment

### Build locally

```bash
pip install -r requirements-dev.txt       # build / twine / coverage

python -m build                           # produces dist/*.whl and dist/*.tar.gz
python -m twine check dist/*

pip install dist/nginxforge-1.0.0-py3-none-any.whl
```

`scripts/build.sh` wraps clean → build → check → smoke test.

### Install-free distribution (single-file zipapp)

Handy for air-gapped networks: the whole tool collapses into one file you can run with `python`.

```bash
python -m zipapp nginxforge -m "nginxforge.__main__:main" -o nginxforge.pyz -p "/usr/bin/env python3"
python nginxforge.pyz audit /etc/nginx/nginx.conf
```

### Docker

```dockerfile
FROM python:3.12-alpine
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir .
ENTRYPOINT ["nginxforge"]
CMD ["--help"]
```

```bash
docker build -t nginxforge:1.0.0 .
docker run --rm -v "$PWD/conf.d:/conf" nginxforge:1.0.0 audit /conf --format sarif
```

### CI integration

**GitHub Actions (with code scanning)**

```yaml
name: nginx-config-audit
on: [push, pull_request]
jobs:
  nginxforge:
    runs-on: ubuntu-latest
    permissions:
      security-events: write
      contents: read
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install ./nginxforge   # or: pip install nginxforge
      - name: Audit nginx configuration
        run: nginxforge audit ./conf.d --format sarif --output nginxforge.sarif --fail-on never
      - name: Upload to code scanning
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: nginxforge.sarif
```

**GitLab CI**

```yaml
nginxforge:
  image: python:3.12-slim
  script:
    - pip install ./nginxforge
    - nginxforge audit ./conf.d --fail-on warning --format markdown --output report.md
  artifacts:
    when: always
    paths: [report.md]
```

**pre-commit**

```yaml
repos:
  - repo: local
    hooks:
      - id: nginxforge-audit
        name: nginxforge audit
        entry: nginxforge audit --fail-on error
        language: system
        files: \.conf$
      - id: nginxforge-fmt
        name: nginxforge fmt
        entry: nginxforge fmt --check
        language: system
        files: \.conf$
```

### Publishing to PyPI

```bash
# 1. Bump `version` in pyproject.toml and `__version__` in nginxforge/__init__.py
# 2. Build and check
./scripts/build.sh
# 3. Upload
python -m twine upload dist/*
```

`scripts/release.sh` chains tag → build → upload → changelog into one command.

### ⚠️ Deployment notes

- The tool is **read-only** against your configs; `fix --apply` is the only write, and it is off by default.
- The HTML report is a single self-contained file (inlined CSS/JS) suitable for offline distribution — but it embeds **file paths and config excerpts**, so check for sensitive content before sharing it.
- A good split: `nginxforge audit --fail-on warning` as a release-pipeline gate, `--fail-on error` as a local pre-commit gate.

---

## 🤝 Contributing

### Development setup

```bash
git clone https://github.com/gitstq/NginxForge.git
cd NginxForge
pip install -r requirements-dev.txt

python -m unittest discover -s tests -p "test_*.py"   # 125 tests
python -m unittest discover -s tests -p "test_*.py" -v
coverage run -m unittest discover -s tests && coverage report
```

No virtualenv tricks, no nginx, no network access required.

### Add a rule

Pick a domain file under `nginxforge/rules/` and write a generator function:

```python
from ..engine import rule, AuditContext
from ..model import Finding

@rule(
    "NGX121",                       # unique id, NGX<category><number>
    "Something risky is enabled",   # one-line title
    severity="warning",             # error / warning / info
    category="security",            # correctness / security / performance / style
    remediation="Do X instead of Y",
)
def my_rule(ctx: AuditContext):
    for node in ctx.walk():
        if node.name == "risky_directive" and node.args == ["on"]:
            yield ctx.make(
                node,
                "risky_directive on is dangerous because …",
                fix="risky_directive off;",
            )
```

Then:

1. Add a fixture under `tests/fixtures/` that triggers it;
2. Assert it fires in `tests/test_rules.py`;
3. Confirm the **existing eight templates still audit clean** (`test_generator.py` enforces this for you).

> Rule functions must be **generators** (`yield ctx.make(...)`) or return an iterable. The engine traps exceptions, but please keep rules idempotent and side-effect free.

### Add a template

Add a `@template(...)`-decorated function in `nginxforge/generator.py`, reusing the shared builders `_wrap_http()` / `_http_server_open()` / `_https_server_open()` / `_proxy_headers()`. **Hard requirement**: `nginxforge gen -t <your-template> --audit` must report zero findings.

### Commit convention (Angular)

```
feat(rules): add NGX121 for the risky_directive footgun
fix(parser): stop truncating multi-line quoted strings
docs(readme): add a SARIF integration example
refactor(engine): isolate rule execution behind an exception boundary
test(generator): add regression coverage for the cache template
chore(ci): add the SARIF upload step
perf(semdiff): cache signatures during canonicalisation
```

Allowed types: `feat` / `fix` / `docs` / `refactor` / `perf` / `test` / `build` / `ci` / `chore` / `revert`.

### PR checklist

- [ ] `python -m unittest discover -s tests -p "test_*.py"` is green
- [ ] New rules / templates come with tests
- [ ] No third-party runtime dependency was added
- [ ] Commit messages follow the Angular convention
- [ ] If the CLI changed, all **three** README translations were updated

### Reporting bugs

Please include:

1. A **minimal config snippet** that reproduces it (redacted as needed);
2. `nginxforge --version` and your Python version;
3. Actual output vs expected output.

---

## 📄 License

Released under the **MIT License**; see [LICENSE](LICENSE) for the full text.

```
MIT License

Copyright (c) 2026 NginxForge contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

**Attribution & disclaimer**

- `nginx` is a trademark of NGINX, Inc. This project has **no affiliation, sponsorship or endorsement** from them; all directive semantics come from the public nginx documentation.
- The advice this tool gives is a *best-practice baseline*, **not a security compliance guarantee**. Evaluate changes against your own architecture and roll them out gradually.

---

<div align="center">

If NginxForge saved you from a production incident, ⭐ the repo — that's the only fuel keeping it moving.

[简体中文](README.md) · [繁體中文](README.zh-TW.md) · [English](README.en.md)

</div>
