"""
Single-file HTML reporter.

No external assets: the stylesheet and the (tiny) filter script are inlined so
the report can be emailed, archived or uploaded as a CI artifact and still look
right offline.
"""

from __future__ import annotations

import html
from typing import Dict, List

from ..engine import AuditResult
from ..model import Finding

_CSS = """
:root{
  --bg:#0f1115; --card:#171a21; --line:#262b36; --fg:#e6e9ef;
  --muted:#98a2b3; --err:#f0555f; --warn:#f0b429; --info:#4aa8ff; --ok:#3ecf8e;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
  font:14px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,"PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:1100px;margin:0 auto;padding:32px 20px 64px}
h1{font-size:24px;margin:0 0 4px}
.sub{color:var(--muted);margin:0 0 24px}
.cards{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px}
.card{flex:1 1 140px;background:var(--card);border:1px solid var(--line);
  border-radius:12px;padding:14px 16px}
.card .n{font-size:26px;font-weight:700}
.card .l{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.06em}
.err{color:var(--err)} .warn{color:var(--warn)} .info{color:var(--info)} .ok{color:var(--ok)}
.bar{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 18px}
button{background:var(--card);color:var(--fg);border:1px solid var(--line);
  border-radius:8px;padding:6px 12px;cursor:pointer;font-size:13px}
button:hover{border-color:#3b4252}
table{width:100%;border-collapse:collapse;background:var(--card);
  border:1px solid var(--line);border-radius:12px;overflow:hidden;margin-bottom:22px}
th,td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}
th{background:#1b1f27;font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
tr:last-child td{border-bottom:none}
code{background:#0b0d12;border:1px solid var(--line);border-radius:5px;padding:1px 5px;font-size:12px}
.sev{font-weight:700;white-space:nowrap}
.file{color:var(--muted);font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}
.path{color:var(--muted);font-size:12px}
.rem{color:var(--muted);font-size:12px}
h2{font-size:16px;margin:26px 0 10px}
footer{color:var(--muted);font-size:12px;margin-top:32px}
.empty{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px;text-align:center}
"""

_JS = """
function filter(sev){
  document.querySelectorAll('tr[data-sev]').forEach(function(tr){
    tr.style.display = (sev === 'all' || tr.dataset.sev === sev) ? '' : 'none';
  });
  document.querySelectorAll('.bar button').forEach(function(b){
    b.style.borderColor = (b.dataset.sev === sev) ? '#4aa8ff' : '';
  });
}
"""


def _esc(text: str) -> str:
    return html.escape(text or "")


def render(result: AuditResult, version: str = "1.0.0") -> str:
    counts = result.counts()
    by_cat = result.by_category()

    total = len(result.findings)
    cards = "".join(
        f'<div class="card"><div class="n {cls}">{value}</div>'
        f'<div class="l">{label}</div></div>'
        for cls, value, label in (
            ("err", counts.get("error", 0), "errors"),
            ("warn", counts.get("warning", 0), "warnings"),
            ("info", counts.get("info", 0), "info"),
            ("ok", total, "total"),
        )
    )

    grouped: Dict[str, List[Finding]] = {}
    for finding in result.findings:
        grouped.setdefault(finding.file or "config", []).append(finding)

    sections: List[str] = []
    for file_name in sorted(grouped):
        rows: List[str] = []
        for finding in grouped[file_name]:
            fix = (f'<span class="ok">✚ {_esc(finding.fix.summary)}</span>'
                   if finding.fix else '<span class="path">—</span>')
            rows.append(
                f'<tr data-sev="{finding.severity}">'
                f'<td class="sev {finding.severity[:4]}">{finding.severity}</td>'
                f'<td><code>{_esc(finding.rule_id)}</code></td>'
                f'<td><span class="file">{_esc(file_name)}:{finding.line}</span>'
                f'<div class="path">{_esc(finding.path)}</div></td>'
                f'<td>{_esc(finding.title)}'
                f'<div class="rem">{_esc(finding.message)}</div>'
                f'<div class="rem">↳ {_esc(finding.remediation)}</div></td>'
                f'<td>{fix}</td>'
                f"</tr>"
            )
        sections.append(
            f"<h2>📄 {_esc(file_name)}</h2>"
            '<table><thead><tr><th>Severity</th><th>Rule</th>'
            "<th>Location</th><th>Details</th><th>Auto fix</th></tr></thead>"
            f'<tbody>{"".join(rows)}</tbody></table>'
        )

    if not sections:
        sections.append(
            '<div class="empty">✅ No findings — the configuration passed every '
            "enabled rule.</div>"
        )

    cat_line = ", ".join(f"{k}: {v}" for k, v in sorted(by_cat.items())) or "none"
    syntax = ""
    if result.syntax_errors:
        items = "".join(f"<li>{_esc(str(e))}</li>"
                        for e in result.syntax_errors)
        syntax = (f"<h2>🚧 Syntax errors</h2><ul>{items}</ul>")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NginxForge audit report</title>
<style>{_CSS}</style>
</head>
<body>
<div class="wrap">
  <h1>🛡️ NginxForge audit report</h1>
  <p class="sub">nginxforge v{_esc(version)} · {len(result.files)} file(s) · \
{len(result.rules_run)} rule(s) · categories: {_esc(cat_line)}</p>
  <div class="cards">{cards}</div>
  <div class="bar">
    <button data-sev="all" onclick="filter('all')">All</button>
    <button data-sev="error" onclick="filter('error')">Errors</button>
    <button data-sev="warning" onclick="filter('warning')">Warnings</button>
    <button data-sev="info" onclick="filter('info')">Info</button>
  </div>
  {"".join(sections)}
  {syntax}
  <footer>Generated by NginxForge — zero-dependency, offline-first nginx \
configuration toolkit.</footer>
</div>
<script>{_JS}</script>
</body>
</html>
"""
