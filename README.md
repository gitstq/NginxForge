<div align="center">

# 🔥 NginxForge

**零依赖 · 离线优先 · 纯 Python 的 nginx 配置解析器 / 审计器 / 修复器 / 生成器**

[简体中文](README.md) · [繁體中文](README.zh-TW.md) · [English](README.en.md)

![Python](https://img.shields.io/badge/python-3.8%2B-blue?logo=python&logoColor=white)
![Dependencies](https://img.shields.io/badge/runtime%20dependencies-0-brightgreen)
![Rules](https://img.shields.io/badge/rules-54-orange)
![Tests](https://img.shields.io/badge/tests-125%20passing-success)
![Offline](https://img.shields.io/badge/needs-nginx%20binary%3F%20NO-important)
![License](https://img.shields.io/badge/license-MIT-green)

</div>

---

## 📑 目录

| 章节 | 内容 |
| --- | --- |
| [🎉 项目介绍](#-项目介绍) | NginxForge 是什么、解决什么问题、和同类工具的差异 |
| [✨ 核心特性](#-核心特性) | 解析 / 审计 / 语义 diff / 自动修复 / 生成 / 多格式报告 |
| [🚀 快速开始](#-快速开始) | 30 秒装上并跑通第一条命令 |
| [📖 详细使用指南](#-详细使用指南) | 7 个子命令、配置项、退出码、Python API |
| [💡 设计思路与迭代规划](#-设计思路与迭代规划) | 架构分层、关键取舍、版本路线图 |
| [📦 打包与部署指南](#-打包与部署指南) | 构建分发、Docker、CI 集成、pre-commit |
| [🤝 贡献指南](#-贡献指南) | 开发环境、新增规则 / 模板、提交规范 |
| [📄 开源协议](#-开源协议) | MIT 全文与署名说明 |

---

## 🎉 项目介绍

nginx 的配置文件是一门"看起来像 JSON 的表亲，实际上到处是坑"的小语言：没有真正的布尔类型、`add_header` 会被子块静默覆盖、`if` 在 `location` 里有著名的非直觉行为、`root` 与 `alias` 混用会 404、`ssl_protocols` 少写一个版本就让整站降级。这些问题有共同的三个特点：

1. **只有上线才暴露** —— `nginx -t` 只检查语法，不检查语义；
2. **难以 review** —— 两份配置"看起来不一样"和"真的不一样"是两回事；
3. **修复成本高** —— 每次都要翻文档确认 `keepalive_timeout` 该填多少。

**NginxForge** 就是为此而生的离线工具箱。它用纯 Python 手写了一整套 nginx 配置语言的**词法分析器 → 递归下降解析器 → AST**，在这棵 AST 上跑 **54 条可配置规则**，输出可读报告，并且能给出**逐行、可回滚的自动修复补丁**。

### 它刻意不做的事

| 不做 | 原因 |
| --- | --- |
| ❌ 调用 `nginx -t` / `nginx -T` | 目标环境往往没有 nginx 二进制（CI 容器、本地笔记本、离线内网） |
| ❌ 引入任何第三方运行时依赖 | 装一个 linter 连带装半个生态是运维噩梦；`pip install` 之后只有一个纯 Python 包 |
| ❌ 联网请求 | 配置里可能含内网域名与密钥路径，任何外发流量都是不可接受的 |
| ❌ 一键"优化到底" | 真正的修复必须可解释；`--safe` 模式只改写已有行，绝不增删 |

### 和同类方案的差异

| 能力 | `nginx -t` | 通用 YAML/TOML linter | 在线配置检查站 | **NginxForge** |
| --- | :-: | :-: | :-: | :-: |
| 语法检查 | ✅ | ❌ | ✅ | ✅ |
| 语义 / 最佳实践规则 | ❌ | ❌ | 部分 | **54 条** |
| 离线运行 | ✅ | ✅ | ❌ | **✅** |
| 需要 nginx 二进制 | ✅ | ❌ | ❌ | **❌** |
| 自动修复 | ❌ | ❌ | ❌ | **✅** |
| 语义级 diff（忽略顺序/缩进） | ❌ | ❌ | ❌ | **✅** |
| 从模板生成合规配置 | ❌ | ❌ | 部分 | **✅ 8 套** |
| SARIF / Code Scanning | ❌ | 部分 | ❌ | **✅** |

---

## ✨ 核心特性

### 🔍 完整的 nginx 配置语言前端

- **手写 Lexer**：正确处理 `#` 注释、单/双引号字符串、反斜杠转义、跨行字符串、`$variable` 与正则中的 `{`/`}`。
- **递归下降 Parser**：产出带父子关系的 `Directive` 树，每个节点都记住自己的**文件、行号、列号与上下文路径**（`http > server > location /api/ > proxy_pass`）。
- **容错设计**：遇到语法错误**不中止**，把它记成一条 `NGX004` 问题后同步恢复继续解析 —— 一份有 3 处错误的配置，你一次就能看到全部 3 处。
- **280 条指令元数据表**：每条指令记录"允许出现在哪些上下文"与"参数个数区间"，拼错 `sever_name` 会被告知"你是不是想写 `server_name`"。

### 🛡️ 54 条规则，四类分域

| 编号段 | 类别 | 数量 | 举例 |
| --- | --- | --- | --- |
| `NGX0xx` | **correctness** 正确性 | 15 | 未知指令 / 上下文非法 / 参数个数不符 / `try_files` 无兜底 / `root`+`alias` 冲突 / `proxy_pass` 斜杠语义不一致 / 重复的 `server` |
| `NGX1xx` | **security** 安全 | 20 | 泄露版本号 / 缺失安全响应头 / 开启目录列表 / 过期 TLS 协议 / 弱加密套件 / 缺 HSTS / 私钥路径可疑 / 明文跳到远端上游 / WebDAV 可写 / 宽松 CORS |
| `NGX2xx` | **performance** 性能 | 14 | 未开压缩 / `sendfile` 关闭 / `worker_processes` 非 `auto` / 静态资源无缓存头 / HTTPS 未开 HTTP/2 / `upstream` 无 `keepalive` |
| `NGX3xx` | **style** 风格 | 5 | 混用 Tab 与空格 / 行尾空白 / 超长行 / 硬编码非常规路径 / 指令名非 snake_case |

每条规则都带 **severity**（`error` / `warning` / `info`）、**可点击的定位**、**原因解释**和**修复建议**。

### 🔀 语义级 Diff —— 而不是文本 Diff

两份配置只换了 `location` 的顺序、或者把 4 空格缩进改成了 Tab，文本 diff 会刷出上百行噪音，语义 diff 会告诉你：

```console
$ nginxforge diff old.conf new.conf
# old.conf -> new.conf
# configurations are semantically identical
```

实现方式是把两侧配置**规范化**（按上下文路径排序、剥离缩进与换行差异），再按"身份签名"配对比较。顺序变化、缩进变化 = 无差异；指令参数变化 = 精确指出哪一条变了。

### 🩹 可解释、可回滚的自动修复

```console
$ nginxforge fix nginx.conf --safe          # 干跑，只打印 unified diff
$ nginxforge fix nginx.conf --safe --apply  # 落盘
```

- 修复是**行级补丁**（`replace` / `delete` / `insert_before` / `insert_after`），从下往上应用，自动复用目标行的缩进。
- `--safe` 只保留 `replace` 模式，**永不新增或删除行** —— 适合放进 CI 或交给你不信任的代码库。
- 同一行只会被一条规则改写，避免补丁互踩。

### 🏭 生成器：从零拿到一份"审计满分"的配置

```console
$ nginxforge gen --template reverse-proxy --domain example.com --upstream 10.0.0.5:8080 --audit
nginxforge: generated configuration passes all rules ✔
```

8 套模板 —— `reverse-proxy` / `static` / `spa` / `websocket` / `api-gateway` / `load-balancer` / `cache` / `tls`。**每一套的输出都被单元测试强制要求"审计零告警"**，不是样板片段，是可以直接进生产的基线。

### 📊 五种报告格式，覆盖人机两侧

| 格式 | 用途 |
| --- | --- |
| `text` | 终端彩色输出，带 `↳` 原因与 `✚` 修复提示 |
| `json` | 稳定的机器契约，供脚本消费 |
| `sarif` | SARIF 2.1.0，直接上传 GitHub Code Scanning |
| `markdown` | 贴到 PR 评论里的表格 |
| `html` | **单文件、CSS/JS 全内联**的深色报告，离线双击即开，自带筛选 |

### 🧩 零依赖 · 离线 · 类型标注

- 运行时依赖 **0 个**，纯标准库。
- Python **3.8+**（含 3.12），自带 `py.typed`，`mypy` 可直接检查调用方。
- 既能当 CLI 用，也能当库用（`from nginxforge import parse`）。

---

## 🚀 快速开始

### 安装

```bash
# 方式一：从源码安装（推荐，拿到 nginxforge 命令）
git clone https://github.com/gitstq/NginxForge.git
cd NginxForge
pip install -e .

# 方式二：完全不安装，直接跑（最轻）
python -m nginxforge --help

# 方式三：用户级安装
pip install --user .
```

> **环境要求**：Python 3.8 及以上，**无需** nginx 二进制，**无需**联网，**无需**任何第三方包。

### 三条命令跑通

```bash
# 1. 审一份现有配置
nginxforge audit /etc/nginx/nginx.conf

# 2. 看看能自动修什么（默认干跑，不落盘）
nginxforge fix /etc/nginx/nginx.conf --safe

# 3. 生成一份审计零告警的新配置
nginxforge gen --template reverse-proxy --domain example.com --upstream 127.0.0.1:8080 -o nginx.conf
```

### 真实输出示例

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

## 📖 详细使用指南

### 1️⃣ `audit` —— 审计

```bash
# 审单个文件 / 整个目录（目录会被递归扫描 .conf）
nginxforge audit nginx.conf
nginxforge audit /etc/nginx

# 只看安全类，且遇到 warning 就失败（CI 用法）
nginxforge audit ./conf.d --select security --fail-on warning

# 输出 SARIF 给 GitHub Code Scanning
nginxforge audit ./conf.d --format sarif --output nginxforge.sarif

# 输出单文件 HTML 报告
nginxforge audit ./conf.d --format html --output report.html

# 只打印一行摘要
nginxforge audit ./conf.d --summary
```

常用参数：

| 参数 | 说明 |
| --- | --- |
| `-f, --format` | `text`（默认）/ `json` / `sarif` / `markdown` / `html` |
| `-o, --output` | 写文件，省略则写 stdout |
| `--select` | 只跑指定规则或类别，可重复：`--select NGX104 --select security` |
| `--ignore` | 跳过指定规则或类别 |
| `--min-severity` | 过滤掉低于该级别的发现 |
| `--fail-on` | 命中该级别就 `exit 1`；`never` 表示永不失败 |
| `--config` | JSON 设置文件（见下文"可调设置"） |
| `--set` | 临时覆盖一项设置：`--set max_keepalive_timeout=60` |
| `--no-color` | 关闭 ANSI 颜色（非 TTY 时自动关闭） |

**可调设置**（`--config` 里写 JSON，或用 `--set` 单点覆盖）：

| 键 | 默认值 | 含义 |
| --- | --- | --- |
| `max_keepalive_timeout` | `75` | 超过该秒数提示 NGX204 |
| `min_worker_connections` | `1024` | 低于该值提示 NGX206 |
| `min_client_max_body_size` | `"1m"` | 请求体上限低于该值提示 NGX112 |
| `required_headers` | `X-Content-Type-Options` / `X-Frame-Options` / `Referrer-Policy` | NGX102 要求的安全响应头 |
| `forbidden_tls` | `SSLv2 SSLv3 TLSv1 TLSv1.1` | NGX104 判定的过期协议 |
| `weak_cipher_tokens` | `NULL aNULL eNULL MD5 RC4 DES 3DES EXPORT LOW SEED IDEA PSK` | NGX105 判定的弱套件关键字 |
| `sensitive_locations` | `/status /admin /.git /.env /metrics …` | NGX110 判定的敏感路径 |

```json
{
  "max_keepalive_timeout": 60,
  "required_headers": ["X-Content-Type-Options", "X-Frame-Options", "Referrer-Policy", "Content-Security-Policy"],
  "sensitive_locations": ["/status", "/admin", "/internal"]
}
```

### 2️⃣ `fix` —— 自动修复

```bash
nginxforge fix nginx.conf                 # 干跑：打印将要发生的改动
nginxforge fix nginx.conf --apply         # 真落盘
nginxforge fix nginx.conf --safe --apply  # 只改写已有行，不增删
nginxforge fix nginx.conf --rule NGX101 --rule NGX103 --apply
nginxforge fix /etc/nginx --safe --apply  # 整个目录
```

| 参数 | 说明 |
| --- | --- |
| `--apply` | 写回磁盘；**默认永远是干跑** |
| `--safe` | 仅 `replace` 模式，绝不新增/删除行 |
| `--rule` | 只应用指定规则 id 的修复 |
| `--select` / `--ignore` / `--min-severity` / `--fail-on` / `--config` / `--set` | 同 `audit` |

> 💡 建议顺序：先 `--safe --apply` 处理低风险改写，人工 review 后再放开到完整模式。
> 修复器保证"同一行只被改一次"，但**请务必把配置纳入版本控制**再执行 `--apply`。

### 3️⃣ `diff` —— 语义对比

```bash
nginxforge diff old.conf new.conf
nginxforge diff old.conf new.conf --unified    # 额外打印规范化后的文本 diff
nginxforge diff old.conf new.conf --format json
```

输出形如：

```console
# old.conf -> new.conf
# 0 added, 0 removed, 1 changed
```

**身份签名**的构成：上下文路径 + 指令名 + 参数列表。因此：

| 变化类型 | 语义 diff 结果 |
| --- | --- |
| 兄弟块顺序调换 | 无差异 |
| 4 空格 → Tab 缩进 | 无差异 |
| 空行 / 注释变化 | 无差异 |
| 指令参数变化 | 记为 `changed` |
| 新增 / 删除指令 | 记为 `added` / `removed` |

### 4️⃣ `gen` —— 生成配置

```bash
nginxforge gen --list                     # 列出 8 套模板

nginxforge gen --template reverse-proxy \
    --domain example.com --upstream 10.0.0.5:8080 \
    --name app_backend --audit --out nginx.conf

nginxforge gen -t static --domain cdn.example.com --root /var/www/cdn --out static.conf
nginxforge gen -t spa    --domain app.example.com  --root /var/www/app --out spa.conf
nginxforge gen -t tls    --domain api.example.com  --upstream 10.0.0.9:3000 --tls on
nginxforge gen -t cache  --domain www.example.com  --upstream 10.0.0.5:8080 --set rate=50r/s
```

| 模板 | 说明 | 主要参数 |
| --- | --- | --- |
| `reverse-proxy` | TLS 终结 + 单后端反代 | `domain` `upstream` |
| `static` | 静态站点，带缓存与压缩 | `domain` `root` |
| `spa` | History 路由 SPA，资源 immutable 缓存 | `domain` `root` |
| `websocket` | Upgrade 感知代理，长读超时 | `domain` `upstream` |
| `api-gateway` | 限流 JSON 网关，带健康检查 | `domain` `upstream` |
| `load-balancer` | `least_conn` 三节点 + 被动健康检查 | `domain` `upstream` |
| `cache` | 激进微缓存 + stale-while-revalidate | `domain` `upstream` |
| `tls` | 纯 TLS 终结转发 | `domain` `upstream` |

通用参数：`--domain` `--upstream` `--root` `--port` `--name`（upstream 组名） `--tls {on,off}` `--set k=v` `-o/--out` `--audit`。

### 5️⃣ `fmt` —— 格式化

```bash
nginxforge fmt nginx.conf                     # 打印重排后的结果
nginxforge fmt nginx.conf --in-place          # 就地重写
nginxforge fmt ./conf.d --indent "  " --check # CI 校验，未格式化则 exit 1
```

### 6️⃣ `parse` —— 查看语法树

```bash
nginxforge parse nginx.conf            # 缩进树 + 上下文路径 + 行号
nginxforge parse nginx.conf -f json    # JSON
```

### 7️⃣ `rules` —— 规则目录

```bash
nginxforge rules                # 54 条规则的表格
nginxforge rules NGX104         # 单条规则的详解
nginxforge rules --format json
```

### 🔢 退出码

| 码 | 含义 |
| --- | --- |
| `0` | 无发现，或未达到 `--fail-on` 阈值 |
| `1` | 发现达到 `--fail-on` 阈值（默认 `error`）；或 `fmt --check` 未通过 |
| `2` | 用法错误（参数缺失、路径不存在、模板/规则名未知） |

### 🐍 Python API

```python
from nginxforge import parse, parse_file
from nginxforge.engine import audit, load_default_rules, AuditOptions
from nginxforge.reporters import render
from nginxforge.generator import generate
from nginxforge.semdiff import compare

load_default_rules()                      # 注册全部内置规则（库使用时需显式调用）

# --- 解析 -------------------------------------------------------------
cfg = parse_file("nginx.conf")
print(cfg.ok)                             # 是否有语法错误
print(cfg.errors)                         # -> [ConfigError(...)]
for node in cfg.find_all("server"):
    print(node.context_path())            # http > server
    print(node.path_label())              # http > server > listen 443 ssl

# --- 审计 -------------------------------------------------------------
result = audit([cfg], AuditOptions(min_severity="warning"))
result.counts()                           # {'error': 2, 'warning': 9, 'info': 0}
result.syntax_errors                      # 语法错误（result.ok 即 not syntax_errors）
for f in result.findings:
    print(f.rule_id, f.location, f.message, f.fix)

print(render("sarif", result, "1.0.0"))   # 任意报告格式

# --- 语义 diff --------------------------------------------------------
d = compare(parse_file("old.conf"), parse_file("new.conf"))
d.identical, d.change_count, d.summary()

# --- 生成 -------------------------------------------------------------
text = generate("reverse-proxy", domain="example.com", upstream="127.0.0.1:8080")
```

---

## 💡 设计思路与迭代规划

### 🏛️ 架构分层

```
                 ┌──────────────────────────────────────────┐
   nginx.conf ─▶ │ lexer.py        词法：注释/引号/转义/跨行  │
                 └───────────────┬──────────────────────────┘
                                 ▼ Token 流
                 ┌──────────────────────────────────────────┐
                 │ parser.py      递归下降 → Directive AST   │
                 │ directives.py  280 条指令上下文/元数元数据 │
                 └───────────────┬──────────────────────────┘
                                 ▼ AST
    ┌────────────┬───────────────┼────────────────┬──────────────┐
    ▼            ▼               ▼                ▼              ▼
 engine.py   generator.py   semdiff.py      fixer.py      reporters/
 规则引擎     模板生成       语义规范化      行级补丁       text/json/
 │                                                        sarif/md/html
 └─ rules/{correctness,security,performance,style}.py
                                 ▼
                             cli.py
```

### 🎯 五个关键设计取舍

**1. 容错优先于严格。** 一份有问题的配置，用户最需要的是"全部问题清单"，而不是"第一处错误在哪"。解析器遇到 `server_tokens off { ... }`（漏分号后被 `{` 吞掉）这类错误时，会记录 `NGX004` 并同步到下一个安全恢复点继续解析。为此专门加了 `_cannot_take_a_block()` 启发式来给出**人话**提示，而不是一句 "unexpected token"。

**2. 规则用装饰器注册，而不是硬编码列表。**

```python
@rule("NGX101", "nginx version is disclosed",
      severity="warning", category="security",
      remediation="Set 'server_tokens off;' …")
def server_tokens_on(ctx: AuditContext) -> Iterator[Finding]: ...
```

新增规则 = 新增一个函数，自动进入注册表、自动出现在 `rules` 命令、自动获得 SARIF 元数据。装饰器在注册时就校验 severity / category 合法性，写错立刻失败。

**3. 规则彼此隔离。** 引擎逐条规则执行并捕获异常：某条规则在一个畸形节点上崩了，只会降级为一条内部警告，其余 53 条照常工作。

**4. 修复必须是"行级 + 模式化"。** 不做 AST 重写，因为 AST 重写会丢失注释与空行，而 nginx 运维对注释的依赖很强。每个 `Fix` 携带 `mode`（`replace`/`delete`/`insert_before`/`insert_after`）与一行新文本，应用时**从下往上**执行以避免行号漂移，并复用目标行原有缩进。`--safe` 是给不信任场景准备的护栏。

**5. 生成器的硬约束是"自己审自己"。** 单元测试会遍历全部 8 套模板，要求 `audit()` 返回 **0 findings**。这条不变量让"生成"从"给你一段样板"变成"给你一条基线"——过去几次迭代中，正是这条测试抓出了 `add_header` 缩进错位、`upstream` 块被塞进 `server`、WS 场景下 `proxy_buffering off` 误报等问题。

### 🗺️ 迭代规划

| 版本 | 主题 | 计划内容 |
| --- | --- | --- |
| **v1.0.x** | 稳定化 | ✅ 54 规则 / 8 模板 / 5 报告 / 语义 diff / 安全修复 |
| **v1.1** | 规则可配置化 | 每条规则的启用开关与阈值全部外置；支持 `.nginxforge.toml` 项目级配置；`--baseline` 基线快照（只报新增问题） |
| **v1.2** | 生态扩展 | 支持 OpenResty / APISIX / NGINX Unit 扩展指令；`stream` / `mail` 块规则补全；`include` 跨文件语义解析 |
| **v1.3** | 协作能力 | `nginxforge explain <rule>` 交互式讲解；VS Code / JetBrains 插件的 LSP 原型；注释保留式 `fmt` |
| **v2.0** | 平台化 | 规则市场（第三方规则包）；多配置仓库的批量仪表盘；与 Kubernetes Ingress / IngressRoute 的双向映射 |

**欢迎投票** —— 上述路线不是承诺，提 issue 说明你的场景会直接影响优先级。

---

## 📦 打包与部署指南

### 本地构建

```bash
pip install -r requirements-dev.txt       # build / twine / coverage

python -m build                           # 产出 dist/*.whl 与 dist/*.tar.gz
python -m twine check dist/*

pip install dist/nginxforge-1.0.0-py3-none-any.whl
```

`scripts/build.sh` 封装了清理 → 构建 → 校验 → 冒烟测试的全过程。

### 免安装分发（单文件 zipapp）

适合离线内网：整个工具可以被打成一个可直接 `python` 执行的文件。

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

### CI 集成

**GitHub Actions（含 Code Scanning）**

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
      - run: pip install ./nginxforge   # 或 pip install nginxforge
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

### 发布到 PyPI

```bash
# 1. 更新 pyproject.toml 里的 version 与 nginxforge/__init__.py 的 __version__
# 2. 构建并校验
./scripts/build.sh
# 3. 上传到 PyPI
python -m twine upload dist/*
```

`scripts/release.sh` 会把"打 tag → 构建 → 上传 → 生成变更摘要"串成一条命令。

### ⚠️ 部署注意事项

- 工具**只读**配置文件，`fix --apply` 是唯一的写操作，且默认关闭。
- HTML 报告为单文件自包含（CSS/JS 内联），可离线分发；但请注意报告中会包含**文件路径与配置片段**，对外分享前请确认不含敏感信息。
- 建议把 `nginxforge audit --fail-on warning` 作为发布流水线的卡点，把 `--fail-on error` 作为本地 pre-commit 卡点。

---

## 🤝 贡献指南

### 开发环境

```bash
git clone https://github.com/gitstq/NginxForge.git
cd NginxForge
pip install -r requirements-dev.txt

python -m unittest discover -s tests -p "test_*.py"   # 125 个测试
python -m unittest discover -s tests -p "test_*.py" -v
coverage run -m unittest discover -s tests && coverage report
```

**不需要**任何虚拟环境技巧、不需要 nginx、不需要联网。

### 新增一条规则

在 `nginxforge/rules/` 下选一个分域文件，写一个生成器函数：

```python
from ..engine import rule, AuditContext
from ..model import Finding

@rule(
    "NGX121",                       # 唯一 id，遵循 NGX<类别><序号>
    "Something risky is enabled",   # 一句话标题
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

然后：

1. 在 `tests/fixtures/` 补一份能触发它的配置；
2. 在 `tests/test_rules.py` 里断言它被触发；
3. 确认**现有 8 套模板仍然审计零告警**（`test_generator.py` 会替你把关）。

> 规则函数必须是**生成器**（`yield ctx.make(...)`）或返回可迭代对象；引擎会捕获异常，但请自行保证幂等与无副作用。

### 新增一套模板

在 `nginxforge/generator.py` 里加一个被 `@template(...)` 装饰的函数，复用 `_wrap_http()` / `_http_server_open()` / `_https_server_open()` / `_proxy_headers()` 等共享构件。**硬性要求**：`nginxforge gen -t <你的模板> --audit` 必须输出零告警。

### 提交规范（Angular）

```
feat(rules): 新增 NGX121 检测危险的 risky_directive
fix(parser): 修复跨行引号字符串被截断的问题
docs(readme): 补充 SARIF 集成示例
refactor(engine): 将规则执行改为异常隔离
test(generator): 为 cache 模板补充回归用例
chore(ci): 添加 SARIF 上传步骤
perf(semdiff): 规范化阶段改用签名缓存
```

允许的 type：`feat` / `fix` / `docs` / `refactor` / `perf` / `test` / `build` / `ci` / `chore` / `revert`。

### PR 清单

- [ ] `python -m unittest discover -s tests -p "test_*.py"` 全绿
- [ ] 新增规则 / 模板配有对应测试
- [ ] 未引入任何第三方运行时依赖
- [ ] 提交信息符合 Angular 规范
- [ ] 如影响 CLI，同步更新 README 的**三个语言版本**

### 报告问题

提 issue 时请附上：

1. 能复现的**最小配置片段**（记得脱敏）；
2. `nginxforge --version` 与 Python 版本；
3. 实际输出 vs 期望输出。

---

## 📄 开源协议

本项目采用 **MIT License** 开源，完整条文见 [LICENSE](LICENSE)。

```
MIT License

Copyright (c) 2026 琦琦

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

**署名与免责**

- `nginx` 是 NGINX, Inc. 的商标；本项目与其**无任何隶属、赞助或背书关系**，所有指令语义均来自公开的 nginx 官方文档。
- 工具给出的建议是"最佳实践基线"，**不构成安全合规承诺**；生产环境变更前请结合自身架构评估并先做灰度。

---

<div align="center">

如果 NginxForge 帮你拦下了一次线上事故，欢迎 ⭐ 一下这个仓库 —— 这是它继续迭代的唯一燃料。

[简体中文](README.md) · [繁體中文](README.zh-TW.md) · [English](README.en.md)

</div>
