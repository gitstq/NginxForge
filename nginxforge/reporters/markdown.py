"""
Markdown reporter - designed to be pasted into a pull request comment.
"""

from __future__ import annotations

from typing import Dict, List

from ..engine import AuditResult
from ..model import Finding

_SEV_BADGE = {
    "error": "🔴 error",
    "warning": "🟡 warning",
    "info": "🔵 info",
}


def render(result: AuditResult, version: str = "1.0.0") -> str:
    out: List[str] = []
    counts = result.counts()
    out.append(f"## 🛡️ NginxForge audit (`v{version}`)")
    out.append("")
    out.append(
        f"Scanned **{len(result.files)}** file(s) with "
        f"**{len(result.rules_run)}** rule(s) → "
        f"**{len(result.findings)}** finding(s) "
        f"(🔴 {counts.get('error', 0)} / "
        f"🟡 {counts.get('warning', 0)} / "
        f"🔵 {counts.get('info', 0)})."
    )
    out.append("")

    if not result.findings:
        out.append("✅ No findings. The configuration looks good.")
        out.append("")
        return "\n".join(out)

    grouped: Dict[str, List[Finding]] = {}
    for finding in result.findings:
        grouped.setdefault(finding.file or "config", []).append(finding)

    out.append("| Severity | Rule | Location | Message | Fix |")
    out.append("| --- | --- | --- | --- | --- |")
    for finding in result.findings:
        fix = f"`{finding.fix.summary}`" if finding.fix else "—"
        message = finding.message.replace("|", "\\|").replace("\n", " ")
        out.append(
            f"| {_SEV_BADGE.get(finding.severity, finding.severity)} "
            f"| `{finding.rule_id}` "
            f"| {finding.file or '-'}:{finding.line} "
            f"| {message} "
            f"| {fix} |"
        )
    out.append("")

    by_rule = result.by_rule()
    out.append("### 📊 Findings by rule")
    out.append("")
    for rule_id, count in sorted(by_rule.items(), key=lambda kv: (-kv[1], kv[0])):
        out.append(f"- `{rule_id}` — {count}")
    out.append("")
    return "\n".join(out)
