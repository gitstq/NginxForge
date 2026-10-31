<div align="center">

# 🔥 NginxForge

**零依賴 · 離線優先 · 純 Python 的 nginx 組態解析器 / 稽核器 / 修復器 / 產生器**

[简体中文](README.md) · [繁體中文](README.zh-TW.md) · [English](README.en.md)

![Python](https://img.shields.io/badge/python-3.8%2B-blue?logo=python&logoColor=white)
![Dependencies](https://img.shields.io/badge/runtime%20dependencies-0-brightgreen)
![Rules](https://img.shields.io/badge/rules-54-orange)
![Tests](https://img.shields.io/badge/tests-125%20passing-success)
![Offline](https://img.shields.io/badge/needs-nginx%20binary%3F%20NO-important)
![License](https://img.shields.io/badge/license-MIT-green)

</div>

---

## 📑 目錄

| 章節 | 內容 |
| --- | --- |
| [🎉 專案介紹](#-專案介紹) | NginxForge 是什麼、解決什麼痛點、與同類工具的差異 |
| [✨ 核心特性](#-核心特性) | 解析 / 稽核 / 語義 diff / 自動修復 / 產生 / 多格式報表 |
| [🚀 快速開始](#-快速開始) | 30 秒裝好並跑出第一個結果 |
| [📖 詳細使用指南](#-詳細使用指南) | 7 個子命令、設定項、結束碼、Python API |
| [💡 設計思路與迭代規劃](#-設計思路與迭代規劃) | 架構分層、關鍵取捨、版本路線圖 |
| [📦 打包與部署指南](#-打包與部署指南) | 建置散佈、Docker、CI 整合、pre-commit |
| [🤝 貢獻指南](#-貢獻指南) | 開發環境、新增規則 / 範本、提交規範 |
| [📄 開源協議](#-開源協議) | MIT 全文與免責聲明 |

---

## 🎉 專案介紹

nginx 的組態檔是一門「看起來像 JSON 的遠房親戚，實際上滿地是坑」的小型語言：沒有真正的布林型別、`add_header` 會被子區塊靜默覆蓋、`if` 在 `location` 裡有惡名昭彰的非直覺行為、`root` 與 `alias` 混用會噴 404、`ssl_protocols` 少寫一個版本就讓整站降級。這些問題有三個共同特徵：

1. **只有上線才會暴露** —— `nginx -t` 只檢查語法，不檢查語義；
2. **難以 review** —— 兩份組態「看起來不一樣」與「真的不一樣」是兩回事；
3. **修復成本高** —— 每次都得翻文件確認 `keepalive_timeout` 到底該填多少。

**NginxForge** 就是為此而生的離線工具箱。它用純 Python 手刻了一整套 nginx 組態語言的**詞法分析器 → 遞迴下降剖析器 → AST**，在這棵 AST 上跑 **54 條可調校規則**，輸出人類可讀的報表，並能產生**逐行、可回復的自動修補**。

### 它刻意不做的事

| 不做 | 理由 |
| --- | --- |
| ❌ 呼叫 `nginx -t` / `nginx -T` | 目標環境常常根本沒有 nginx 執行檔（CI 容器、筆電、離線內網） |
| ❌ 引入任何第三方執行期依賴 | 裝一個 linter 卻拖進半個生態系是維運噩夢；`pip install` 之後只會多一個純 Python 套件 |
| ❌ 發出任何網路請求 | 組態裡可能含內網網域與憑證路徑，任何外送流量都不可接受 |
| ❌ 一鍵「最佳化到底」 | 真正的修補必須可解釋；`--safe` 模式只改寫既有行，絕不增刪 |

### 與同類方案的差異

| 能力 | `nginx -t` | 通用 YAML/TOML linter | 線上組態檢查站 | **NginxForge** |
| --- | :-: | :-: | :-: | :-: |
| 語法檢查 | ✅ | ❌ | ✅ | ✅ |
| 語義 / 最佳實踐規則 | ❌ | ❌ | 部分 | **54 條** |
| 離線執行 | ✅ | ✅ | ❌ | **✅** |
| 需要 nginx 執行檔 | ✅ | ❌ | ❌ | **❌** |
| 自動修復 | ❌ | ❌ | ❌ | **✅** |
| 語義級 diff（忽略順序/縮排） | ❌ | ❌ | ❌ | **✅** |
| 從範本產生合規組態 | ❌ | ❌ | 部分 | **✅ 8 套** |
| SARIF / Code Scanning | ❌ | 部分 | ❌ | **✅** |

---

## ✨ 核心特性

### 🔍 完整的 nginx 組態語言前端

- **手刻 Lexer**：正確處理 `#` 註解、單/雙引號字串、反斜線跳脫、跨行字串，以及 `$variable` 與正則裡的 `{` / `}`。
- **遞迴下降 Parser**：產出帶父子關係的 `Directive` 樹，每個節點都記住自己的**檔案、行號、欄位與上下文路徑**（`http > server > location /api/ > proxy_pass`）。
- **容錯設計**：遇到語法錯誤**不中斷**，登記成一條 `NGX004` 之後同步恢復繼續剖析 —— 一份有 3 處錯誤的組態，你一次就看到全部 3 處。
- **280 條指令後設資料表**：每條指令記錄「允許出現在哪些上下文」與「參數個數區間」，把 `sever_name` 打錯會被告知「你是不是想寫 `server_name`」。

### 🛡️ 54 條規則，四大分域

| 編號段 | 類別 | 數量 | 舉例 |
| --- | --- | --- | --- |
| `NGX0xx` | **correctness** 正確性 | 15 | 未知指令 / 上下文非法 / 參數個數不符 / `try_files` 無收尾 / `root`+`alias` 衝突 / `proxy_pass` 斜線語義不一致 / 重複的 `server` |
| `NGX1xx` | **security** 安全性 | 20 | 洩漏版本號 / 缺少強化回應標頭 / 開啟目錄列表 / 過期 TLS 協定 / 弱加密套件 / 缺 HSTS / 私鑰路徑可疑 / 明文跳到遠端上游 / WebDAV 可寫 / 寬鬆 CORS |
| `NGX2xx` | **performance** 效能 | 14 | 未開壓縮 / `sendfile` 關閉 / `worker_processes` 非 `auto` / 靜態資源無快取標頭 / HTTPS 未開 HTTP/2 / `upstream` 無 `keepalive` |
| `NGX3xx` | **style** 風格 | 5 | 混用 Tab 與空白 / 行尾空白 / 過長的單行 / 硬編碼非常規路徑 / 指令名非 snake_case |

每條規則都帶 **severity**（`error` / `warning` / `info`）、**可定位的座標**、**原因說明**與**修復建議**。

### 🔀 語義級 Diff —— 而不是文字 Diff

兩份組態只換了 `location` 的順序，或把 4 空白縮排改成 Tab，文字 diff 會噴出上百行噪音，語義 diff 則直接告訴你：

```console
$ nginxforge diff old.conf new.conf
# old.conf -> new.conf
# configurations are semantically identical
```

作法是將兩側組態**正規化**（按上下文路徑排序、剝離縮排與換行差異），再依「身分簽章」配對比較。順序變動、縮排變動＝無差異；指令參數變動＝精確指出哪一條變了。

### 🩹 可解釋、可回復的自動修復

```console
$ nginxforge fix nginx.conf --safe          # 乾跑，只印出 unified diff
$ nginxforge fix nginx.conf --safe --apply  # 真的寫入
```

- 修補是**行級 patch**（`replace` / `delete` / `insert_before` / `insert_after`），由下往上套用，並自動沿用目標行的縮排。
- `--safe` 只保留 `replace` 模式，**永不新增或刪除行** —— 適合放進 CI，或套在你不完全信任的儲存庫。
- 同一行只會被一條規則改寫，避免修補互相踩踏。

### 🏭 產生器：從零拿到一份「稽核滿分」的組態

```console
$ nginxforge gen --template reverse-proxy --domain example.com --upstream 10.0.0.5:8080 --audit
nginxforge: generated configuration passes all rules ✔
```

8 套範本 —— `reverse-proxy` / `static` / `spa` / `websocket` / `api-gateway` / `load-balancer` / `cache` / `tls`。**每一套的輸出都被單元測試強制要求「稽核零告警」**，不是樣板片段，而是可以直接進生產的基準線。

### 📊 五種報表格式，兼顧人與機器

| 格式 | 用途 |
| --- | --- |
| `text` | 終端機彩色輸出，附 `↳` 原因與 `✚` 修復提示 |
| `json` | 穩定的機器合約，供腳本消費 |
| `sarif` | SARIF 2.1.0，可直接上傳 GitHub Code Scanning |
| `markdown` | 貼進 PR 留言的表格 |
| `html` | **單檔、CSS/JS 全內嵌**的深色報表，離線點兩下就開，內建篩選 |

### 🧩 零依賴 · 離線 · 型別標註

- 執行期依賴 **0 個**，純標準函式庫。
- 支援 Python **3.8+**（含 3.12），內附 `py.typed`，`mypy` 可直接檢查呼叫端。
- 既能當 CLI 用，也能當函式庫用（`from nginxforge import parse`）。

---

## 🚀 快速開始

### 安裝

```bash
# 方式一：從原始碼安裝（建議，可取得 nginxforge 指令）
git clone https://github.com/gitstq/NginxForge.git
cd NginxForge
pip install -e .

# 方式二：完全不安裝，直接跑（最輕量）
python -m nginxforge --help

# 方式三：使用者層級安裝
pip install --user .
```

> **環境需求**：Python 3.8 以上，**不需要** nginx 執行檔，**不需要**連網，**不需要**任何第三方套件。

### 三行指令跑起來

```bash
# 1. 稽核既有組態
nginxforge audit /etc/nginx/nginx.conf

# 2. 看看能自動修什麼（預設乾跑，不寫入）
nginxforge fix /etc/nginx/nginx.conf --safe

# 3. 產生一份稽核零告警的新組態
nginxforge gen --template reverse-proxy --domain example.com --upstream 127.0.0.1:8080 -o nginx.conf
```

### 真實輸出範例

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

## 📖 詳細使用指南

### 1️⃣ `audit` —— 稽核

```bash
# 稽核單一檔案 / 整個目錄（目錄會被遞迴搜尋 .conf）
nginxforge audit nginx.conf
nginxforge audit /etc/nginx

# 只看安全性類別，且遇到 warning 就失敗（CI 用法）
nginxforge audit ./conf.d --select security --fail-on warning

# 輸出 SARIF 給 GitHub Code Scanning
nginxforge audit ./conf.d --format sarif --output nginxforge.sarif

# 輸出單檔 HTML 報表
nginxforge audit ./conf.d --format html --output report.html

# 只印一行摘要
nginxforge audit ./conf.d --summary
```

常用參數：

| 參數 | 說明 |
| --- | --- |
| `-f, --format` | `text`（預設）/ `json` / `sarif` / `markdown` / `html` |
| `-o, --output` | 寫入檔案，省略則輸出到 stdout |
| `--select` | 只跑指定規則或類別，可重複：`--select NGX104 --select security` |
| `--ignore` | 跳過指定規則或類別 |
| `--min-severity` | 過濾低於此等級的發現 |
| `--fail-on` | 命中此等級就 `exit 1`；`never` 表示永不失敗 |
| `--config` | JSON 設定檔（見下方「可調設定」） |
| `--set` | 單點覆寫設定：`--set max_keepalive_timeout=60` |
| `--no-color` | 關閉 ANSI 顏色（非 TTY 時自動關閉） |

**可調設定**（寫在 `--config` 的 JSON 裡，或用 `--set` 單點覆寫）：

| 鍵 | 預設值 | 意義 |
| --- | --- | --- |
| `max_keepalive_timeout` | `75` | 超過此秒數提醒 NGX204 |
| `min_worker_connections` | `1024` | 低於此值提醒 NGX206 |
| `min_client_max_body_size` | `"1m"` | 請求體上限低於此值提醒 NGX112 |
| `required_headers` | `X-Content-Type-Options` / `X-Frame-Options` / `Referrer-Policy` | NGX102 要求的強化標頭 |
| `forbidden_tls` | `SSLv2 SSLv3 TLSv1 TLSv1.1` | NGX104 判定的過期協定 |
| `weak_cipher_tokens` | `NULL aNULL eNULL MD5 RC4 DES 3DES EXPORT LOW SEED IDEA PSK` | NGX105 判定的弱套件關鍵字 |
| `sensitive_locations` | `/status /admin /.git /.env /metrics …` | NGX110 判定的敏感路徑 |

```json
{
  "max_keepalive_timeout": 60,
  "required_headers": ["X-Content-Type-Options", "X-Frame-Options", "Referrer-Policy", "Content-Security-Policy"],
  "sensitive_locations": ["/status", "/admin", "/internal"]
}
```

### 2️⃣ `fix` —— 自動修復

```bash
nginxforge fix nginx.conf                 # 乾跑：印出即將發生的變更
nginxforge fix nginx.conf --apply         # 真的寫入
nginxforge fix nginx.conf --safe --apply  # 只改寫既有行，不增刪
nginxforge fix nginx.conf --rule NGX101 --rule NGX103 --apply
nginxforge fix /etc/nginx --safe --apply  # 整個目錄
```

| 參數 | 說明 |
| --- | --- |
| `--apply` | 寫回磁碟；**預設永遠是乾跑** |
| `--safe` | 僅 `replace` 模式，絕不新增/刪除行 |
| `--rule` | 只套用指定規則 id 的修補 |
| `--select` / `--ignore` / `--min-severity` / `--fail-on` / `--config` / `--set` | 同 `audit` |

> 💡 建議順序：先 `--safe --apply` 處理低風險改寫，人工 review 之後再放寬到完整模式。
> 修復器保證「同一行只改一次」，但**執行 `--apply` 前請務必讓組態受版本控制保護**。

### 3️⃣ `diff` —— 語義比對

```bash
nginxforge diff old.conf new.conf
nginxforge diff old.conf new.conf --unified    # 額外印出正規化後的文字 diff
nginxforge diff old.conf new.conf --format json
```

輸出形如：

```console
# old.conf -> new.conf
# 0 added, 0 removed, 1 changed
```

**身分簽章**由「上下文路徑 + 指令名 + 參數列」構成，因此：

| 變動類型 | 語義 diff 結果 |
| --- | --- |
| 兄弟區塊順序調換 | 無差異 |
| 4 空白 → Tab 縮排 | 無差異 |
| 空行 / 註解變動 | 無差異 |
| 指令參數變動 | 記為 `changed` |
| 新增 / 刪除指令 | 記為 `added` / `removed` |

### 4️⃣ `gen` —— 產生組態

```bash
nginxforge gen --list                     # 列出 8 套範本

nginxforge gen --template reverse-proxy \
    --domain example.com --upstream 10.0.0.5:8080 \
    --name app_backend --audit --out nginx.conf

nginxforge gen -t static --domain cdn.example.com --root /var/www/cdn --out static.conf
nginxforge gen -t spa    --domain app.example.com  --root /var/www/app --out spa.conf
nginxforge gen -t tls    --domain api.example.com  --upstream 10.0.0.9:3000 --tls on
nginxforge gen -t cache  --domain www.example.com  --upstream 10.0.0.5:8080 --set rate=50r/s
```

| 範本 | 說明 | 主要參數 |
| --- | --- | --- |
| `reverse-proxy` | TLS 終結 + 單一後端反向代理 | `domain` `upstream` |
| `static` | 靜態站台，含快取與壓縮 | `domain` `root` |
| `spa` | History 路由 SPA，資源 immutable 快取 | `domain` `root` |
| `websocket` | 感知 Upgrade 的代理，長讀取逾時 | `domain` `upstream` |
| `api-gateway` | 限流 JSON 閘道，含健康檢查 | `domain` `upstream` |
| `load-balancer` | `least_conn` 三節點 + 被動健康檢查 | `domain` `upstream` |
| `cache` | 激進微快取 + stale-while-revalidate | `domain` `upstream` |
| `tls` | 純 TLS 終結轉發 | `domain` `upstream` |

通用參數：`--domain` `--upstream` `--root` `--port` `--name`（upstream 群組名） `--tls {on,off}` `--set k=v` `-o/--out` `--audit`。

### 5️⃣ `fmt` —— 格式化

```bash
nginxforge fmt nginx.conf                     # 印出重排結果
nginxforge fmt nginx.conf --in-place          # 就地改寫
nginxforge fmt ./conf.d --indent "  " --check # CI 校驗，未格式化則 exit 1
```

### 6️⃣ `parse` —— 檢視語法樹

```bash
nginxforge parse nginx.conf            # 縮排樹 + 上下文路徑 + 行號
nginxforge parse nginx.conf -f json    # JSON
```

### 7️⃣ `rules` —— 規則總表

```bash
nginxforge rules                # 54 條規則的表格
nginxforge rules NGX104         # 單條規則詳解
nginxforge rules --format json
```

### 🔢 結束碼

| 碼 | 意義 |
| --- | --- |
| `0` | 無發現，或未達 `--fail-on` 門檻 |
| `1` | 發現已達 `--fail-on` 門檻（預設 `error`）；或 `fmt --check` 未通過 |
| `2` | 用法錯誤（缺少參數、路徑不存在、範本/規則名稱未知） |

### 🐍 Python API

```python
from nginxforge import parse, parse_file
from nginxforge.engine import audit, load_default_rules, AuditOptions
from nginxforge.reporters import render
from nginxforge.generator import generate
from nginxforge.semdiff import compare

load_default_rules()                      # 註冊所有內建規則（作為函式庫使用時需顯式呼叫）

# --- 解析 -------------------------------------------------------------
cfg = parse_file("nginx.conf")
print(cfg.ok)                             # 是否有語法錯誤
print(cfg.errors)                         # -> [ConfigError(...)]
for node in cfg.find_all("server"):
    print(node.context_path())            # http > server
    print(node.path_label())              # http > server > listen 443 ssl

# --- 稽核 -------------------------------------------------------------
result = audit([cfg], AuditOptions(min_severity="warning"))
result.counts()                           # {'error': 2, 'warning': 9, 'info': 0}
result.syntax_errors                      # 語法錯誤（result.ok 即 not syntax_errors）
for f in result.findings:
    print(f.rule_id, f.location, f.message, f.fix)

print(render("sarif", result, "1.0.0"))   # 任一種報表格式

# --- 語義 diff --------------------------------------------------------
d = compare(parse_file("old.conf"), parse_file("new.conf"))
d.identical, d.change_count, d.summary()

# --- 產生 -------------------------------------------------------------
text = generate("reverse-proxy", domain="example.com", upstream="127.0.0.1:8080")
```

---

## 💡 設計思路與迭代規劃

### 🏛️ 架構分層

```
                 ┌──────────────────────────────────────────┐
   nginx.conf ─▶ │ lexer.py        詞法：註解/引號/跳脫/跨行  │
                 └───────────────┬──────────────────────────┘
                                 ▼ Token 流
                 ┌──────────────────────────────────────────┐
                 │ parser.py      遞迴下降 → Directive AST   │
                 │ directives.py  280 條指令上下文/元數後設資料│
                 └───────────────┬──────────────────────────┘
                                 ▼ AST
    ┌────────────┬───────────────┼────────────────┬──────────────┐
    ▼            ▼               ▼                ▼              ▼
 engine.py   generator.py   semdiff.py      fixer.py      reporters/
 規則引擎     範本產生       語義正規化      行級修補       text/json/
 │                                                        sarif/md/html
 └─ rules/{correctness,security,performance,style}.py
                                 ▼
                             cli.py
```

### 🎯 五個關鍵取捨

**1. 容錯優先於嚴格。** 一份有問題的組態，使用者最需要的是「完整問題清單」，而不是「第一個錯在哪」。剖析器遇到 `server_tokens off { ... }`（漏了分號卻被 `{` 吃掉）這類錯誤時，會登記一條 `NGX004` 並同步到下一個安全恢復點繼續剖析。為此還特別加了 `_cannot_take_a_block()` 啟發式，好給出**人話**提示，而不是一句 "unexpected token"。

**2. 規則以裝飾器註冊，而非硬編碼清單。**

```python
@rule("NGX101", "nginx version is disclosed",
      severity="warning", category="security",
      remediation="Set 'server_tokens off;' …")
def server_tokens_on(ctx: AuditContext): ...
```

新增規則 = 新增一個函式，自動進入註冊表、自動出現在 `rules` 指令、自動取得 SARIF 後設資料。裝飾器在註冊當下就校驗 severity / category 合法性，寫錯立刻失敗。

**3. 規則彼此隔離。** 引擎逐條執行並攔截例外：某條規則在畸形節點上炸了，只會降級成一條內部警告，其餘 53 條照常工作。

**4. 修補必須「行級 + 模式化」。** 不做 AST 重寫，因為那會丟掉註解與空行，而 nginx 維運對註解的依賴很深。每個 `Fix` 攜帶 `mode`（`replace`/`delete`/`insert_before`/`insert_after`）與一行新文字，套用時**由下而上**以避免行號漂移，並沿用目標行原本的縮排。`--safe` 則是為不完全信任的場景準備的護欄。

**5. 產生器的硬性約束是「自己稽核自己」。** 單元測試會遍歷全部 8 套範本，要求 `audit()` 回傳 **0 findings**。這條不變式讓「產生」從「給你一段樣板」升級成「給你一條基準線」——前幾次迭代正是靠這條測試抓出 `add_header` 縮排錯位、`upstream` 區塊被塞進 `server`、WS 情境下 `proxy_buffering off` 誤報等問題。

### 🗺️ 迭代規劃

| 版本 | 主題 | 規劃內容 |
| --- | --- | --- |
| **v1.0.x** | 穩定化 | ✅ 54 規則 / 8 範本 / 5 報表 / 語義 diff / 安全修補 |
| **v1.1** | 規則可配置化 | 每條規則的開關與閾值全部外置；支援 `.nginxforge.toml` 專案層級設定；`--baseline` 基準快照（只報新增問題） |
| **v1.2** | 生態擴充 | 支援 OpenResty / APISIX / NGINX Unit 擴充指令；補齊 `stream` / `mail` 區塊規則；`include` 跨檔案語義解析 |
| **v1.3** | 協作能力 | `nginxforge explain <rule>` 互動式講解；VS Code / JetBrains 外掛的 LSP 原型；保留註解的 `fmt` |
| **v2.0** | 平台化 | 規則市集（第三方規則包）；多組態儲存庫的批次儀表板；與 Kubernetes Ingress / IngressRoute 的雙向對應 |

**歡迎投票** —— 上述路線不是承諾，開一張 issue 說明你的情境會直接影響優先順序。

---

## 📦 打包與部署指南

### 本地建置

```bash
pip install -r requirements-dev.txt       # build / twine / coverage

python -m build                           # 產出 dist/*.whl 與 dist/*.tar.gz
python -m twine check dist/*

pip install dist/nginxforge-1.0.0-py3-none-any.whl
```

`scripts/build.sh` 把「清理 → 建置 → 校驗 → 冒煙測試」整串包起來。

### 免安裝散佈（單檔 zipapp）

適合離線內網：整組工具可以被壓成一個能直接用 `python` 執行的檔案。

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

### CI 整合

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

### 發佈到 PyPI

```bash
# 1. 更新 pyproject.toml 的 version 與 nginxforge/__init__.py 的 __version__
# 2. 建置並校驗
./scripts/build.sh
# 3. 上傳到 PyPI
python -m twine upload dist/*
```

`scripts/release.sh` 會把「打 tag → 建置 → 上傳 → 產生變更摘要」串成一條指令。

### ⚠️ 部署注意事項

- 工具對組態檔**唯讀**，`fix --apply` 是唯一的寫入操作，且預設關閉。
- HTML 報表為單檔自包含（CSS/JS 內嵌），可離線散佈；但請留意報表中含有**檔案路徑與組態片段**，對外分享前請確認不含敏感資訊。
- 建議把 `nginxforge audit --fail-on warning` 作為發佈流程的卡點，把 `--fail-on error` 作為本機 pre-commit 卡點。

---

## 🤝 貢獻指南

### 開發環境

```bash
git clone https://github.com/gitstq/NginxForge.git
cd NginxForge
pip install -r requirements-dev.txt

python -m unittest discover -s tests -p "test_*.py"   # 125 個測試
python -m unittest discover -s tests -p "test_*.py" -v
coverage run -m unittest discover -s tests && coverage report
```

**不需要**任何虛擬環境技巧、不需要 nginx、不需要連網。

### 新增一條規則

在 `nginxforge/rules/` 下挑一個分域檔案，寫一個產生器函式：

```python
from ..engine import rule, AuditContext
from ..model import Finding

@rule(
    "NGX121",                       # 唯一 id，遵循 NGX<類別><序號>
    "Something risky is enabled",   # 一句話標題
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

然後：

1. 在 `tests/fixtures/` 補一份能觸發它的組態；
2. 在 `tests/test_rules.py` 裡斷言它會被觸發；
3. 確認**既有 8 套範本仍維持稽核零告警**（`test_generator.py` 會替你把關）。

> 規則函式必須是**產生器**（`yield ctx.make(...)`）或回傳可迭代物件；引擎會攔截例外，但仍請自行確保冪等與無副作用。

### 新增一套範本

在 `nginxforge/generator.py` 裡加一個被 `@template(...)` 裝飾的函式，並複用 `_wrap_http()` / `_http_server_open()` / `_https_server_open()` / `_proxy_headers()` 等共用構件。**硬性要求**：`nginxforge gen -t <你的範本> --audit` 必須輸出零告警。

### 提交規範（Angular）

```
feat(rules): 新增 NGX121 檢測危險的 risky_directive
fix(parser): 修正跨行引號字串被截斷的問題
docs(readme): 補充 SARIF 整合範例
refactor(engine): 將規則執行改為例外隔離
test(generator): 為 cache 範本補上回歸案例
chore(ci): 新增 SARIF 上傳步驟
perf(semdiff): 正規化階段改用簽章快取
```

允許的 type：`feat` / `fix` / `docs` / `refactor` / `perf` / `test` / `build` / `ci` / `chore` / `revert`。

### PR 清單

- [ ] `python -m unittest discover -s tests -p "test_*.py"` 全綠
- [ ] 新增規則 / 範本皆附對應測試
- [ ] 未引入任何第三方執行期依賴
- [ ] 提交訊息符合 Angular 規範
- [ ] 若影響 CLI，同步更新 README 的**三個語言版本**

### 回報問題

開 issue 時請附上：

1. 能重現的**最小組態片段**（記得去敏感資訊）；
2. `nginxforge --version` 與 Python 版本；
3. 實際輸出 vs 期望輸出。

---

## 📄 開源協議

本專案採用 **MIT License** 開源，完整條文見 [LICENSE](LICENSE)。

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

**署名與免責**

- `nginx` 為 NGINX, Inc. 之商標；本專案與該公司**無任何隸屬、贊助或背書關係**，所有指令語義皆取自公開的 nginx 官方文件。
- 工具給出的建議是「最佳實踐基準」，**不構成安全合規承諾**；生產環境變更前請依自身架構評估並先行灰度。

---

<div align="center">

如果 NginxForge 幫你攔下了一次線上事故，歡迎 ⭐ 一下這個儲存庫 —— 那是它繼續迭代的唯一燃料。

[简体中文](README.md) · [繁體中文](README.zh-TW.md) · [English](README.en.md)

</div>
