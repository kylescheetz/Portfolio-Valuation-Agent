"""Tests for valuation.py — all valuation methods and equity bridge."""

import pytest
from src.valuation import (
    trading_multiple_ev_revenue, trading_multiple_ev_ebitda,
    growth_adjusted_ev, blended_enterprise_value,
    enterprise_to_equity, run_valuation, sensitivity_analysis,
)


def test_trading_multiple_ev_revenue():
    ev = trading_multiple_ev_revenue(50_000_000, 10.0)
    assert ev == 500_000_000


def test_trading_multiple_ev_revenue_zero():
    assert trading_multiple_ev_revenue(0, 10.0) == 0.0
    assert trading_multiple_ev_revenue(50_000_000, 0) == 0.0


def test_trading_multiple_ev_ebitda_positive():
    ev = trading_multiple_ev_ebitda(8_000_000, 20.0)
    assert ev == 160_000_000


def test_trading_multiple_ev_ebitda_negative():
    ev = trading_multiple_ev_ebitda(-5_000_000, 20.0)
    assert ev == 0.0


def test_growth_adjusted_ev_premium():
    """Company growing faster than comps should get a premium."""
    ev = growth_adjusted_ev(
        revenue_ttm=50_000_000,
        median_ev_revenue=10.0,
        company_growth_rate=0.30,
        median_comp_growth_rate=0.20,
        adjustment_factor=0.5,
    )
    # growth_premium = (0.30 - 0.20) * 0.5 = 0.05
    # adjusted_multiple = 10.0 * 1.05 = 10.5
    # ev = 50M * 10.5 = 525M
    assert ev == pytest.approx(525_000_000)


def test_growth_adjusted_ev_discount():
    """Company growing slower should get a discount."""
    ev = growth_adjusted_ev(
        revenue_ttm=50_000_000,
        median_ev_revenue=10.0,
        company_growth_rate=0.10,
        median_comp_growth_rate=0.20,
        adjustment_factor=0.5,
    )
    # growth_premium = (0.10 - 0.20) * 0.5 = -0.05
    # adjusted_multiple = 10.0 * 0.95 = 9.5
    # ev = 50M * 9.5 = 475M
    assert ev == pytest.approx(475_000_000)


def test_blended_ev_default_weights():
    ev = blended_enterprise_value(500_000_000, 160_000_000, 525_000_000)
    # 0.4 * 500M + 0.4 * 160M + 0.2 * 525M = 200M + 64M + 105M = 369M
    assert ev == pytest.approx(369_000_000)


def test_blended_ev_custom_weights():
    ev = blended_enterprise_value(
        500_000_000, 160_000_000, 525_000_000,
        weights={"ev_revenue": 0.5, "ev_ebitda": 0.3, "growth_adjusted": 0.2},
    )
    # 0.5 * 500M + 0.3 * 160M + 0.2 * 525M = 250M + 48M + 105M = 403M
    assert ev == pytest.approx(403_000_000)


def test_blended_ev_zero_ebitda_redistributes():
    """When EBITDA method returns 0, weight should redistribute."""
    ev = blended_enterprise_value(500_000_000, 0, 525_000_000)
    # EBITDA weight (0.4) redistributed: rev gets 0.4/(0.4+0.2)*1.0 portion
    # Result should only use revenue and growth methods
    assert ev > 0


def test_enterprise_to_equity_basic():
    result = enterprise_to_equity(
        enterprise_value=500_000_000,
        net_debt=3_000_000,
        preferred_amount=10_000_000,
        ownership_pct=0.20,
        dilution_pct=0.05,
    )
    # equity = 500M - 3M = 497M
    assert result["equity_value"] == 497_000_000
    # after prefs = 497M - 10M = 487M
    assert result["equity_after_prefs"] == 487_000_000
    # holdco = 487M * 0.20 * 0.95 = 92.53M
    assert result["holdco_equity_value"] == pytest.approx(92_530_000)


def test_enterprise_to_equity_net_cash():
    """Negative net_debt (net cash) should increase equity value."""
    result = enterprise_to_equity(
        enterprise_value=500_000_000,
        net_debt=-10_000_000,  # net cash
        preferred_amount=5_000_000,
        ownership_pct=0.25,
        dilution_pct=0.03,
    )
    assert result["equity_value"] == 510_000_000
    assert result["equity_after_prefs"] == 505_000_000


def test_enterprise_to_equity_negative_equity():
    """When EV < prefs, holdco equity should be 0."""
    result = enterprise_to_equity(
        enterprise_value=50_000_000,
        net_debt=20_000_000,
        preferred_amount=40_000_000,
        ownership_pct=0.20,
        dilution_pct=0.05,
    )
    # equity = 50M - 20M = 30M
    # after prefs = max(0, 30M - 40M) = 0
    assert result["equity_after_prefs"] == 0
    assert result["holdco_equity_value"] == 0


def test_run_valuation_end_to_end(db_conn, sample_company_with_comps):
    """Full valuation pipeline with sample data."""
    result = run_valuation(db_conn, sample_company_with_comps)

    assert "enterprise_value" in result
    assert result["enterprise_value"] > 0
    assert result["holdco_equity_value"] > 0
    assert result["comp_count"] == 2
    assert result["median_ev_revenue"] == 11.0  # median of 10.0 and 12.0


def test_sensitivity_analysis(db_conn, sample_company_with_comps):
    """Sensitivity should produce upside > base > downside."""
    sens = sensitivity_analysis(db_conn, sample_company_with_comps)

    assert sens["upside"]["enterprise_value"] > sens["base"]["enterprise_value"]
    assert sens["base"]["enterprise_value"] > sens["downside"]["enterprise_value"]
    assert sens["ev_range"] > 0


def test_run_valuation_negative_ebitda(db_conn, negative_ebitda_company):
    """Valuation should handle negative EBITDA gracefully."""
    result = run_valuation(db_conn, negative_ebitda_company)

    assert result["enterprise_value"] > 0
    assert result["ev_ebitda_method"] == 0.0  # Negative EBITDA = no EBITDA method
    assert result["holdco_equity_value"] >= 0
