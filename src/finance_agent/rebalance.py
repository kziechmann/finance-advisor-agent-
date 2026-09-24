"""Deterministic allocation-drift and rebalancing-band logic.

This is the only module allowed to compute money math. Every number in a
generated report traces back to a function here — the LLM narrator (added
in a later phase) only ever explains numbers already produced by this
module, never recomputes or overrides them. See docs/spec.md section 9.
"""

from __future__ import annotations

from collections import defaultdict

from finance_agent.models import AssetClassTarget, DriftResult, HoldingRow, RebalanceBandConfig


class RebalanceError(ValueError):
    pass


def aggregate_by_asset_class(holdings: list[HoldingRow]) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for holding in holdings:
        totals[holding.asset_class] += holding.market_value
    return dict(totals)


def validate_targets(targets: list[AssetClassTarget], *, tolerance_pct: float = 0.5) -> None:
    total = sum(t.target_pct for t in targets)
    if abs(total - 100.0) > tolerance_pct:
        raise RebalanceError(
            f"Target allocation sums to {total:.2f}%, expected ~100% "
            f"(tolerance {tolerance_pct}%). Fix config/target_allocation.yaml."
        )


def band_limit_pct(target_pct: float, band: RebalanceBandConfig) -> float:
    """The allowed drift, in percentage points, before this asset class is flagged."""
    if target_pct >= band.relative_threshold_pct:
        return band.absolute_pct
    return target_pct * (band.relative_pct / 100)


def compute_drift(
    holdings: list[HoldingRow],
    targets: list[AssetClassTarget],
    band: RebalanceBandConfig | None = None,
) -> list[DriftResult]:
    band = band or RebalanceBandConfig()
    validate_targets(targets)

    totals = aggregate_by_asset_class(holdings)
    total_value = sum(totals.values())
    if total_value <= 0:
        raise RebalanceError("Total portfolio value is zero or negative; cannot compute allocation.")

    target_map = {t.asset_class: t.target_pct for t in targets}
    all_classes = set(target_map) | set(totals)

    results: list[DriftResult] = []
    for asset_class in sorted(all_classes):
        target_pct = target_map.get(asset_class, 0.0)
        current_value = totals.get(asset_class, 0.0)
        current_pct = current_value / total_value * 100
        diff_pct = current_pct - target_pct
        limit = band_limit_pct(target_pct, band)
        target_value = target_pct / 100 * total_value

        results.append(
            DriftResult(
                asset_class=asset_class,
                target_pct=target_pct,
                current_pct=current_pct,
                current_value=current_value,
                diff_pct=diff_pct,
                band_limit_pct=limit,
                exceeds_band=abs(diff_pct) > limit,
                suggested_trade_amount=target_value - current_value,
            )
        )
    return results
