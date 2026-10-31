# 📝 Changelog

本文件记录每个版本的显著变更，格式遵循 [Keep a Changelog](https://keepachangelog.com/)，版本号遵循 [Semantic Versioning](https://semver.org/)。

All notable changes are documented here. Versioning follows [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-10-31

### ✨ Added - 新增

**解析层 / Parsing**
- 手写 nginx 配置词法分析器：注释、单双引号字符串、反斜杠转义、跨行字符串。
- 递归下降解析器，产出带父子关系与上下文路径的 `Directive` AST。
- 容错解析：语法错误记录为 `NGX004` 后同步恢复，不清空后续结果。
- 280 条指令元数据（允许上下文 + 参数个数区间），含 Levenshtein 拼写建议。

**规则引擎 / Rules (54)**
- `NGX001`–`NGX015` correctness：未知指令、上下文非法、参数个数、语法错误、`try_files` 兜底、`root`/`alias` 冲突、`proxy_pass` 斜杠语义、缺失 `server_name`、重复 `server`、`upstream` 端口、`if` 内高风险指令、重复指令、缺失核心块、`rewrite` 标志、`add_header` 覆盖。
- `NGX101`–`NGX120` security：版本泄露、安全响应头、目录列表、过期 TLS、弱套件、HSTS、私钥路径、HTTPS 跳转、`Host` 头、敏感端点、CORS、请求体上限、限流、WebDAV、废弃 XSS 头、session tickets、默认协议、明文上游、`default_server`、套件优先级。
- `NGX201`–`NGX214` performance：压缩、`sendfile`、TCP 参数、`keepalive_timeout`、`worker_processes`、`worker_connections`、静态缓存、HTTP/2、`proxy_buffering`、`open_file_cache`、`gzip_types`、`upstream keepalive`、`proxy_cache`、TLS 会话缓存。
- `NGX301`–`NGX305` style：缩进混用、行尾空白、超长行、硬编码路径、命名风格。
- 规则以 `@rule(...)` 装饰器注册，注册时校验 severity/category；执行时逐条异常隔离。

**其他能力 / Other**
- 语义 diff（`diff`）：规范化后按身份签名配对，忽略顺序与缩进差异。
- 自动修复（`fix`）：`replace`/`delete`/`insert_before`/`insert_after` 四种行级模式，默认干跑，`--safe` 只允许改写。
- 配置生成（`gen`）：8 套模板，每一套都被测试强制要求审计零告警。
- 五种报告格式：text / json / SARIF 2.1.0 / markdown / 自包含 HTML。
- 完整 CLI：`audit` `fix` `diff` `gen` `fmt` `parse` `rules`，语义化退出码 0/1/2。
- Python API 与 `py.typed` 类型标注；运行时零第三方依赖，支持 Python 3.8–3.12。
- 125 个单元测试，覆盖 lexer / parser / rules / fixer / generator / semdiff / reporters / cli。
- 三语文档（简体中文 / 繁體中文 / English）、MIT 协议、CI 工作流与构建发布脚本。

### 🐛 Fixed - 修复

- 生成模板中 `add_header` 与 `ssl_*` 在 `server` 层级缩进错位。
- `upstream` 块被误放进 `server` 内部（应位于 `http`）。
- `NGX108` 对「跳转写在 `location` 内」的误报。
- `NGX118` 把 upstream 组名当成远端主机而误报明文链路。
- `NGX209` 在 WebSocket / SSE 场景下对 `proxy_buffering off` 的误报。
- `path_label()` 未包含节点自身，导致上下文路径缺少末级指令。
- `render()` 递归缩进失效。

[1.0.0]: https://github.com/gitstq/NginxForge/releases/tag/v1.0.0
