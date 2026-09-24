"""Markdown report rendering.

The report shows the computed drift table as the source of truth. A later
phase adds an LLM-written narrative section beneath it — that section must
never restate numbers itself, only reference this table. See docs/spec.md
section 10 on the disclaimer/liability posture this enforces.
"""

from __future__ import annotations

from datetime import date, datetime

from finance_agent.models import DriftResult

DISCLAIMER = (
    "> **Informational only.** This report is generated for personal use "
    "and is not financial, tax, or legal advice. This system is not a "
    "registered investment adviser and no trades are ever placed "
    "automatically. You are the sole decision-maker — verify all figures "
    "independently before acting."
)


def _fmt_money(amount: float) -> str:
    sign = "-" if amount < 0 else ""
    return f"{sign}${abs(amount):,.2f}"


def render_markdown_report(
    drift_results: list[DriftResult],
    *,
    as_of_date: date,
    generated_at: datetime | None = None,
) -> str:
    generated_at = generated_at or datetime.now()
    total_value = sum(r.current_value for r in drift_results)
    flagged = [r for r in drift_results if r.exceeds_band]

    lines: list[str] = []
    lines.append(f"# Portfolio Report — {as_of_date.isoformat()}")
    lines.append("")
    lines.append(DISCLAIMER)
    lines.append("")
    lines.append(f"Generated: {generated_at.isoformat(timespec='seconds')}")
    lines.append(f"Total portfolio value: {_fmt_money(total_value)}")
    lines.append("")

    lines.append("## Allocation vs. target")
    lines.append("")
    lines.append("| Asset class | Target | Current | Value | Drift | Band limit | Flagged |")
    lines.append("|---|---:|---:|---:|---:|---:|:---:|")
    for r in drift_results:
        flag = "⚠️" if r.exceeds_band else ""
        lines.append(
            f"| {r.asset_class} | {r.target_pct:.1f}% | {r.current_pct:.1f}% | "
            f"{_fmt_money(r.current_value)} | {r.diff_pct:+.1f}pp | "
            f"±{r.band_limit_pct:.1f}pp | {flag} |"
        )
    lines.append("")

    lines.append("## Rebalancing signals")
    lines.append("")
    if not flagged:
        lines.append("No asset class has crossed its rebalancing band. No action suggested.")
    else:
        for r in flagged:
            is_buy = r.suggested_trade_amount > 0
            direction = "buy more of" if is_buy else "trim"
            hint = (
                " In a taxable account, prefer directing new contributions "
                "here over selling an overweight class elsewhere, to avoid "
                "an unnecessary taxable event."
                if is_buy
                else " Selling in a taxable account may realize a gain or "
                "loss — check the tax-awareness notes (once implemented) "
                "before acting."
            )
            lines.append(
                f"- **{r.asset_class}** is {abs(r.diff_pct):.1f}pp "
                f"{'above' if r.diff_pct > 0 else 'below'} target "
                f"(band limit ±{r.band_limit_pct:.1f}pp). To restore target: "
                f"{direction} **{r.asset_class}** by roughly "
                f"{_fmt_money(abs(r.suggested_trade_amount))}.{hint}"
            )
    lines.append("")

    return "\n".join(lines)
