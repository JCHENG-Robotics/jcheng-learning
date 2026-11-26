"""Render a quality report as Markdown (the JSON report is canonical)."""

from __future__ import annotations

from typing import Any


def render_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    dataset = report.get("dataset", {})
    lines = [
        "# Dataset quality report",
        "",
        f"- Dataset: `{dataset.get('id')}`",
        f"- Source class: `{dataset.get('source_class')}`",
        f"- Profile: `{dataset.get('profile_id')}`",
        f"- Root SHA-256: `{dataset.get('root_sha256')}`",
        f"- Result: **{summary.get('result')}**",
        f"- Usable for training: `{summary.get('usable_for_training')}`",
        "",
        "## Summary",
        "",
        "| Errors | Warnings | Skipped | Inconclusive | Checks |",
        "|---:|---:|---:|---:|---:|",
        f"| {summary.get('errors', 0)} | {summary.get('warnings', 0)} | "
        f"{summary.get('skipped', 0)} | {summary.get('inconclusive', 0)} | "
        f"{summary.get('checks', 0)} |",
        "",
        "## Checks",
        "",
        "| ID | Severity | Status | Message |",
        "|---|---|---|---|",
    ]
    for check in report.get("checks", []):
        message = str(check.get("message", "")).replace("|", "\\|")
        lines.append(
            f"| {check.get('id')} | {check.get('severity')} | "
            f"{check.get('status')} | {message} |"
        )
    lines += [
        "",
        "## Features",
        "",
    ]
    for name, stats in report.get("features", {}).items():
        if not isinstance(stats, dict) or "count" not in stats:
            continue
        lines.append(
            f"- `{name}`: count={stats.get('count')} min={stats.get('min')} "
            f"max={stats.get('max')} mean={stats.get('mean')} std={stats.get('std')}"
        )
    limitations = report.get("limitations", [])
    if limitations:
        lines += ["", "## Limitations", ""]
        lines.extend(f"- {item}" for item in limitations)
    return "\n".join(lines) + "\n"
