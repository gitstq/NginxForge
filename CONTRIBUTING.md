# 🤝 贡献指南 / Contributing to NginxForge

感谢你愿意花时间改进 NginxForge。这份文档说明如何搭环境、如何加规则与模板，以及提交规范。

Thanks for taking the time to improve NginxForge. This document covers the dev
setup, how to add rules and templates, and the commit convention.

---

## 🧑‍💻 开发环境 / Dev setup

```bash
git clone https://github.com/gitstq/NginxForge.git
cd NginxForge
pip install -r requirements-dev.txt        # build / twine / coverage

python -m unittest discover -s tests -p "test_*.py"          # 125 tests
coverage run -m unittest discover -s tests && coverage report
```

环境变量要求：**只需要 Python 3.8+**。不需要 nginx、不需要联网、不需要虚拟环境。

Requirements: **Python 3.8+** only. No nginx binary, no network, no virtualenv needed.

---

## 🧱 代码结构 / Layout

| 路径 | 职责 |
| --- | --- |
| `nginxforge/lexer.py` | 词法分析：注释、引号、转义、跨行字符串 |
| `nginxforge/parser.py` | 递归下降解析 → `Directive` AST，以及 `render()` |
| `nginxforge/model.py` | `Token` / `Directive` / `ConfigFile` / `Finding` / `Fix` |
| `nginxforge/directives.py` | 280 条指令的上下文与参数个数元数据 |
| `nginxforge/engine.py` | 规则注册表、审计编排、`AuditOptions` |
| `nginxforge/rules/*.py` | 四个分域的规则实现 |
| `nginxforge/semdiff.py` | 语义规范化与对比 |
| `nginxforge/fixer.py` | 行级补丁的规划与应用 |
| `nginxforge/generator.py` | 8 套配置模板 |
| `nginxforge/reporters/` | text / json / sarif / markdown / html |
| `nginxforge/cli.py` | argparse CLI |

---

## ➕ 新增一条规则 / Adding a rule

1. 在 `nginxforge/rules/` 选一个分域文件（`correctness` / `security` / `performance` / `style`）。
2. 用 `@rule(...)` 装饰器写一个**生成器**函数。
3. 编号遵循 `NGX<类别号><序号>`：正确性 `0xx`、安全 `1xx`、性能 `2xx`、风格 `3xx`。

```python
from ..engine import rule, AuditContext
from ..model import Finding

@rule(
    "NGX121",
    "Something risky is enabled",
    severity="warning",               # error | warning | info
    category="security",              # correctness | security | performance | style
    remediation="Do X instead of Y",
)
def my_rule(ctx: AuditContext):
    for node in ctx.walk():
        if node.name == "risky_directive" and node.args == ["on"]:
            yield ctx.make(
                node,
                "risky_directive on is dangerous because ...",
                fix="risky_directive off;",   # optional
            )
```

4. 在 `tests/fixtures/` 加一份能触发它的配置，在 `tests/test_rules.py` 断言它会命中。
5. 跑 `python scripts/gen_rules_doc.py` 重新生成 `docs/RULES.md`。
6. 确认 8 套模板**依然审计零告警**（`tests/test_generator.py` 会替你把关）。

约定 / conventions：

- 规则必须**幂等且无副作用**；引擎会捕获异常，但别依赖这一点。
- 消息写"为什么危险"，不要只写"这样不好"。
- 能自动修的就给 `fix=`；不能安全自动修的就只给 `remediation=`。

---

## ➕ 新增一套模板 / Adding a template

在 `nginxforge/generator.py` 加一个 `@template(...)` 函数，尽量复用共享构件
`_wrap_http()` / `_http_server_open()` / `_https_server_open()` / `_proxy_headers()` / `_tls_lines()`。

**硬性要求**：`nginxforge gen -t <name> --audit` 必须输出零告警。

---

## ✅ 提交规范 / Commit convention (Angular)

```
<type>(<scope>): <subject>
```

允许的 `type`：`feat` / `fix` / `docs` / `refactor` / `perf` / `test` / `build` / `ci` / `chore` / `revert`

```
feat(rules): 新增 NGX121 检测危险的 risky_directive
fix(parser): 修复跨行引号字符串被截断的问题
docs(readme): 补充 SARIF 集成示例
refactor(engine): 将规则执行改为异常隔离
test(generator): 为 cache 模板补充回归用例
chore(ci): 添加 SARIF 上传步骤
```

- subject 用祈使句、结尾不加句号；
- 一次提交只做一件事；
- 破坏性变更在正文里以 `BREAKING CHANGE:` 开头说明。

---

## 📋 PR 清单 / PR checklist

- [ ] `python -m unittest discover -s tests -p "test_*.py"` 全绿
- [ ] 新增规则 / 模板都配有测试
- [ ] **未引入任何第三方运行时依赖**（CI 会静态检查 import）
- [ ] 提交信息符合 Angular 规范
- [ ] 若影响 CLI 或规则集，同步更新 `README.md` / `README.zh-TW.md` / `README.en.md` 与 `docs/RULES.md`

---

## 🐛 报告问题 / Reporting bugs

请附带：

1. 能复现的**最小配置片段**（记得脱敏）；
2. `nginxforge --version` 与 Python 版本；
3. 实际输出 vs 期望输出。

---

## 📄 协议 / License

贡献即表示你同意代码以本项目采用的 **MIT License** 发布。
By contributing you agree that your code is released under the project's **MIT License**.
