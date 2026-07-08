#!/usr/bin/env python3
"""Backtest report writer — renders the summary from ``backtest_aggregator``
into a JSON payload and a human-readable Markdown report.
"""

from __future__ import annotations

import json
import os


def _fmt(value, suffix: str = "") -> str:
    return f"{value}{suffix}" if value is not None else "—"


def _stats_row(label: str, stats: dict) -> str:
    counts = stats["counts"]
    return (
        f"| {label} | {stats['total_detections']} | {counts['breakout']} | "
        f"{counts['stop_hit']} | {counts['timeout']} | "
        f"{_fmt(stats['breakout_rate_pct'], '%')} | "
        f"{_fmt(stats['avg_days_to_breakout'])} | "
        f"{_fmt(stats['avg_max_gain_pct'], '%')} | "
        f"{_fmt(stats['avg_max_loss_pct'], '%')} |"
    )


_TABLE_HEADER = (
    "| Bucket | Detections | Breakouts | Stops | Timeouts | Breakout rate | "
    "Avg days to breakout | Avg max gain | Avg max loss |\n"
    "|---|---|---|---|---|---|---|---|---|"
)


def _section(title: str, rows_by_label: dict[str, dict]) -> list[str]:
    lines = [f"## {title}", "", _TABLE_HEADER]
    lines.extend(_stats_row(label, stats) for label, stats in rows_by_label.items())
    lines.append("")
    return lines


def generate_backtest_markdown(summary: dict, metadata: dict) -> str:
    """Render the full backtest summary as a Markdown document."""
    overall = summary["overall"]
    lines = [
        "# VCP Historical Backtest Report",
        "",
        f"Generated: {metadata.get('generated_at', '?')}",
        "",
        f"- **Universe:** {metadata.get('universe_description', '?')} "
        f"({summary['tickers_scanned']} tickers scanned, "
        f"{summary['tickers_with_detections']} with detections)",
        f"- **Scan window:** {metadata.get('scan_days', '?')} trading days "
        f"(~{metadata.get('years', '?')} years)",
        f"- **Stride:** {metadata.get('stride_days', '?')} trading days | "
        f"**Outcome window:** {metadata.get('outcome_days', '?')} trading days",
        "",
        "## Overall",
        "",
        _TABLE_HEADER,
        _stats_row("All detections", overall),
        "",
        f"- Avg max gain on breakout: "
        f"{_fmt(overall['avg_max_gain_on_breakout_pct'], '%')} | "
        f"avg max loss on stop: {_fmt(overall['avg_max_loss_on_stop_pct'], '%')}",
        f"- Unresolved (insufficient forward data): "
        f"{overall['counts']['insufficient_data']}",
        "",
    ]
    lines.extend(_section("By Year", summary["by_year"]))
    lines.extend(_section("By Rating Band", summary["by_rating_band"]))

    with_detections = {
        sym: stats
        for sym, stats in summary["by_ticker"].items()
        if stats["total_detections"] > 0
    }
    lines.extend(_section("By Ticker", with_detections))

    lines.extend(
        [
            "## Notes",
            "",
            "- Outcomes are pattern-level labels (pivot cross / stop hit / timeout),",
            "  not a portfolio simulation: no position sizing, slippage, or overlap",
            "  handling is applied.",
            "- `max_gain` / `max_loss` are measured from the detection-day close over",
            "  the full outcome window, regardless of outcome type.",
            "- Universe membership is today's snapshot applied backwards, so results",
            "  carry survivorship bias — winners that stayed in the index are",
            "  overrepresented. Treat rates as optimistic upper bounds.",
            "",
        ]
    )
    return "\n".join(lines)


def write_backtest_reports(
    summary: dict,
    metadata: dict,
    output_dir: str,
    timestamp: str,
    detections_by_ticker: dict[str, list[dict]] | None = None,
) -> tuple[str, str]:
    """Write JSON and Markdown reports; returns (json_path, md_path).

    The JSON payload always contains metadata + summary; full per-detection
    timelines are included when ``detections_by_ticker`` is provided.
    """
    os.makedirs(output_dir, exist_ok=True)
    json_path = os.path.join(output_dir, f"vcp_backtest_{timestamp}.json")
    md_path = os.path.join(output_dir, f"vcp_backtest_{timestamp}.md")

    payload = {"metadata": metadata, "summary": summary}
    if detections_by_ticker is not None:
        payload = {**payload, "detections_by_ticker": detections_by_ticker}

    with open(json_path, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    with open(md_path, "w") as f:
        f.write(generate_backtest_markdown(summary, metadata))

    return json_path, md_path
