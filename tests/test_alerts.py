"""Tests for alerts.py — threshold checks and alert generation."""

from src.alerts import (
    check_comp_multiple_change, check_valuation_delta,
    check_underperformance, run_all_checks, get_alert_summary,
)
from src.database import (
    insert_valuation_snapshot, update_company, insert_alert,
    get_active_alerts, acknowledge_alert,
)
from src.valuation import run_valuation


def test_check_comp_multiple_change_triggers(db_conn, sample_company_with_comps):
    """Should trigger alert when comp multiples diverge from last snapshot."""
    # Create a valuation snapshot with different medians
    insert_valuation_snapshot(db_conn, {
        "portfolio_company_id": sample_company_with_comps,
        "snapshot_date": "2025-01-01",
        "method": "blended",
        "enterprise_value": 500_000_000,
        "equity_value": 400_000_000,
        "holdco_equity_value": 80_000_000,
        "median_ev_revenue": 8.0,  # Current is 11.0 — 37.5% change
        "median_ev_ebitda": 18.0,  # Current is 22.5 — 25% change
    })

    alerts = check_comp_multiple_change(db_conn, sample_company_with_comps, threshold_pct=0.15)
    assert len(alerts) >= 1


def test_check_comp_multiple_change_no_trigger(db_conn, sample_company_with_comps):
    """Should not trigger when change is within threshold."""
    insert_valuation_snapshot(db_conn, {
        "portfolio_company_id": sample_company_with_comps,
        "snapshot_date": "2025-01-01",
        "method": "blended",
        "median_ev_revenue": 10.5,  # Close to current 11.0 — ~5% change
        "median_ev_ebitda": 22.0,  # Close to current 22.5 — ~2% change
    })

    alerts = check_comp_multiple_change(db_conn, sample_company_with_comps, threshold_pct=0.15)
    assert len(alerts) == 0


def test_check_valuation_delta(db_conn, sample_company_with_comps):
    """Should trigger when current EV differs from last mark."""
    # Set last mark
    update_company(db_conn, sample_company_with_comps, {"last_mark_ev": 300_000_000})

    # Run valuation (will produce EV based on comps)
    result = run_valuation(db_conn, sample_company_with_comps, save_snapshot=True)

    # Now the last_mark_ev is updated to new value, so re-set a different one
    update_company(db_conn, sample_company_with_comps, {"last_mark_ev": 300_000_000})

    alert = check_valuation_delta(db_conn, sample_company_with_comps, threshold_pct=0.10)
    # EV should be around 500M+, which is >10% from 300M
    assert alert is not None


def test_check_underperformance(db_conn):
    """Should trigger when run-rate misses growth expectations."""
    from src.database import insert_company
    cid = insert_company(db_conn, {
        "name": "SlowCo",
        "revenue_ttm": 100_000_000,
        "revenue_run_rate": 95_000_000,  # Below expected 120M (20% growth)
        "growth_rate": 0.20,
    })

    alert = check_underperformance(db_conn, cid, threshold_pct=0.10)
    assert alert is not None
    assert "below expected" in alert["message"]


def test_alert_summary(db_conn, sample_company_with_comps):
    """Summary should count correctly."""
    insert_alert(db_conn, {
        "alert_type": "comp_multiple_change",
        "portfolio_company_id": sample_company_with_comps,
        "message": "Test alert 1",
        "severity": "high",
    })
    insert_alert(db_conn, {
        "alert_type": "valuation_delta",
        "portfolio_company_id": sample_company_with_comps,
        "message": "Test alert 2",
        "severity": "medium",
    })

    summary = get_alert_summary(db_conn)
    assert summary["total_active"] == 2
    assert summary["by_severity"]["high"] == 1
    assert summary["by_severity"]["medium"] == 1
