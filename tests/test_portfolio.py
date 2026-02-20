"""Tests for portfolio.py — HoldCo NAV aggregation and analytics."""

from src.portfolio import calculate_holdco_nav, get_portfolio_summary, get_concentration_analysis
from src.valuation import run_all_valuations


def test_calculate_holdco_nav(db_conn, sample_portfolio):
    """NAV should aggregate correctly."""
    run_all_valuations(db_conn)

    result = calculate_holdco_nav(
        db_conn,
        holdco_cash=50_000_000,
        holdco_debt=30_000_000,
        shares_outstanding=10_000_000,
    )

    assert result["total_equity_value"] > 0
    assert result["nav"] == result["total_equity_value"] + 50_000_000 - 30_000_000
    assert result["nav_per_share"] == result["nav"] / 10_000_000
    assert len(result["company_contributions"]) == 3


def test_nav_change_vs_prior(db_conn, sample_portfolio):
    """Second NAV snapshot should have change_vs_prior."""
    run_all_valuations(db_conn)

    # First snapshot
    r1 = calculate_holdco_nav(db_conn, 50e6, 30e6, 10e6)
    assert r1["change_vs_prior_pct"] is None  # No prior

    # Second snapshot
    r2 = calculate_holdco_nav(db_conn, 50e6, 30e6, 10e6)
    assert r2["change_vs_prior_pct"] is not None


def test_portfolio_summary(db_conn, sample_portfolio):
    """Summary should include all companies."""
    run_all_valuations(db_conn)
    calculate_holdco_nav(db_conn, 50e6, 30e6, 10e6)

    summary = get_portfolio_summary(db_conn)
    assert summary["company_count"] == 3
    assert len(summary["companies"]) == 3
    assert summary["total_equity"] > 0
    assert summary["nav"] is not None


def test_concentration_analysis(db_conn, sample_portfolio):
    """Concentration weights should sum to ~1.0."""
    run_all_valuations(db_conn)

    concentration = get_concentration_analysis(db_conn)
    assert len(concentration) == 3

    total_weight = sum(c["weight_pct"] for c in concentration)
    assert abs(total_weight - 1.0) < 0.01

    # Should be sorted descending by weight
    assert concentration[0]["weight_pct"] >= concentration[1]["weight_pct"]
