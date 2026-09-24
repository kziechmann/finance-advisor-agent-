from datetime import date

import pytest

from finance_agent.models import AssetClassTarget, HoldingRow, RebalanceBandConfig
from finance_agent.rebalance import RebalanceError, band_limit_pct, compute_drift, validate_targets


def _holding(asset_class: str, market_value: float) -> HoldingRow:
    return HoldingRow(
        account_name="Test",
        account_type="taxable",
        ticker="TEST",
        asset_class=asset_class,
        shares=1.0,
        price=market_value,
        market_value=market_value,
        cost_basis=market_value,
        as_of_date=date(2026, 6, 30),
        source_file="test.csv",
    )


def test_band_limit_uses_absolute_band_above_threshold():
    band = RebalanceBandConfig(absolute_pct=5, relative_pct=25, relative_threshold_pct=20)
    assert band_limit_pct(50, band) == 5


def test_band_limit_uses_relative_band_below_threshold():
    band = RebalanceBandConfig(absolute_pct=5, relative_pct=25, relative_threshold_pct=20)
    # 5% target * 25% relative band = 1.25 percentage points
    assert band_limit_pct(5, band) == pytest.approx(1.25)


def test_validate_targets_rejects_allocation_not_summing_to_100():
    targets = [AssetClassTarget("us_equity", 60), AssetClassTarget("bonds", 30)]
    with pytest.raises(RebalanceError):
        validate_targets(targets)


def test_compute_drift_flags_asset_class_beyond_absolute_band():
    holdings = [_holding("us_equity", 6000), _holding("bonds", 4000)]
    targets = [AssetClassTarget("us_equity", 50), AssetClassTarget("bonds", 50)]

    results = {r.asset_class: r for r in compute_drift(holdings, targets)}

    assert results["us_equity"].current_pct == pytest.approx(60.0)
    assert results["us_equity"].diff_pct == pytest.approx(10.0)
    assert results["us_equity"].exceeds_band is True
    assert results["us_equity"].suggested_trade_amount == pytest.approx(-1000.0)  # trim by $1000


def test_compute_drift_within_band_is_not_flagged():
    holdings = [_holding("us_equity", 5200), _holding("bonds", 4800)]
    targets = [AssetClassTarget("us_equity", 50), AssetClassTarget("bonds", 50)]

    results = {r.asset_class: r for r in compute_drift(holdings, targets)}

    assert results["us_equity"].exceeds_band is False
    assert results["bonds"].exceeds_band is False


def test_compute_drift_flags_small_target_via_relative_band():
    # cash target 5%, actual drifts to 6.5% -> diff 1.5pp, relative band limit
    # for a 5% target is 5 * 0.25 = 1.25pp, so this should be flagged.
    holdings = [_holding("us_equity", 9350), _holding("cash", 650)]
    targets = [AssetClassTarget("us_equity", 95), AssetClassTarget("cash", 5)]

    results = {r.asset_class: r for r in compute_drift(holdings, targets)}

    assert results["cash"].current_pct == pytest.approx(6.5)
    assert results["cash"].band_limit_pct == pytest.approx(1.25)
    assert results["cash"].exceeds_band is True


def test_compute_drift_handles_asset_class_with_no_target():
    # A holding in a class you haven't configured a target for still shows
    # up in the report rather than silently vanishing.
    holdings = [_holding("us_equity", 9000), _holding("crypto", 1000)]
    targets = [AssetClassTarget("us_equity", 100)]

    results = {r.asset_class: r for r in compute_drift(holdings, targets)}

    assert results["crypto"].target_pct == 0
    assert results["crypto"].current_pct == pytest.approx(10.0)
    assert results["crypto"].exceeds_band is True


def test_compute_drift_rejects_zero_value_portfolio():
    holdings = [_holding("us_equity", 0)]
    targets = [AssetClassTarget("us_equity", 100)]
    with pytest.raises(RebalanceError):
        compute_drift(holdings, targets)
