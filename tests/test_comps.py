"""Tests for comps.py — comp summary computation and manual data entry."""

from src.comps import compute_comp_summary, add_manual_comp_data
from src.database import insert_comp, insert_comp_data, get_latest_comp_data


def test_compute_comp_summary(db_conn, sample_company_with_comps):
    """Should compute correct median/mean for known data."""
    summary = compute_comp_summary(db_conn, sample_company_with_comps)

    assert summary["comp_count"] == 2
    assert summary["median_ev_revenue"] == 11.0  # median of 10.0 and 12.0
    assert summary["median_ev_ebitda"] == 22.5  # median of 20.0 and 25.0
    assert summary["mean_ev_revenue"] == 11.0
    assert summary["high_ev_revenue"] == 12.0
    assert summary["low_ev_revenue"] == 10.0


def test_compute_comp_summary_empty(db_conn, sample_company):
    """No comp data should return zeros."""
    summary = compute_comp_summary(db_conn, sample_company)
    assert summary["comp_count"] == 0
    assert summary["median_ev_revenue"] == 0.0


def test_add_manual_comp_data(db_conn, sample_company):
    """Manual comp data should be insertable and retrievable."""
    comp_id = insert_comp(db_conn, sample_company, "PRIV1", "Private Co", "manual")

    add_manual_comp_data(db_conn, comp_id, "PRIV1", {
        "enterprise_value": 1_000_000_000,
        "revenue": 100_000_000,
        "ebitda": 20_000_000,
        "ev_revenue": 10.0,
        "ev_ebitda": 50.0,
        "growth_rate": 0.15,
    })

    data = get_latest_comp_data(db_conn, sample_company)
    assert len(data) == 1
    assert data[0]["ticker"] == "PRIV1"
    assert data[0]["source"] == "manual"
    assert data[0]["ev_revenue"] == 10.0
