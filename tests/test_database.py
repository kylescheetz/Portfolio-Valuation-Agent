"""Tests for database.py — schema creation, CRUD operations."""

from src.database import (
    initialize_database, insert_company, get_company, get_all_companies,
    update_company, delete_company, insert_comp, get_comps_for_company,
    delete_comp, insert_comp_data, get_latest_comp_data,
    insert_valuation_snapshot, get_valuation_history, get_latest_valuation,
    insert_holdco_snapshot, get_holdco_history, get_latest_holdco_snapshot,
    insert_alert, get_active_alerts, acknowledge_alert, get_alerts_for_company,
    set_config, get_config, get_config_float,
)


def test_schema_creation_is_idempotent(db_conn):
    """Calling initialize_database twice should not error."""
    initialize_database(db_conn)
    initialize_database(db_conn)


def test_insert_and_get_company(db_conn):
    cid = insert_company(db_conn, {"name": "TestCo", "sector": "SaaS", "revenue_ttm": 100})
    company = get_company(db_conn, cid)
    assert company is not None
    assert company["name"] == "TestCo"
    assert company["revenue_ttm"] == 100


def test_get_all_companies(db_conn):
    insert_company(db_conn, {"name": "Alpha"})
    insert_company(db_conn, {"name": "Beta"})
    companies = get_all_companies(db_conn)
    assert len(companies) == 2
    assert companies[0]["name"] == "Alpha"  # ordered by name


def test_update_company(db_conn):
    cid = insert_company(db_conn, {"name": "TestCo", "revenue_ttm": 100})
    update_company(db_conn, cid, {"revenue_ttm": 200, "ebitda": 50})
    company = get_company(db_conn, cid)
    assert company["revenue_ttm"] == 200
    assert company["ebitda"] == 50


def test_delete_company_cascades(db_conn):
    cid = insert_company(db_conn, {"name": "TestCo"})
    comp_id = insert_comp(db_conn, cid, "AAPL", "Apple")
    insert_comp_data(db_conn, {
        "comp_set_id": comp_id, "ticker": "AAPL", "date_pulled": "2025-01-01",
        "ev_revenue": 10.0,
    })
    delete_company(db_conn, cid)
    assert get_company(db_conn, cid) is None
    assert get_comps_for_company(db_conn, cid) == []


def test_comp_set_crud(db_conn, sample_company):
    comp_id = insert_comp(db_conn, sample_company, "MSFT", "Microsoft")
    comps = get_comps_for_company(db_conn, sample_company)
    assert len(comps) == 1
    assert comps[0]["ticker"] == "MSFT"

    delete_comp(db_conn, comp_id)
    assert get_comps_for_company(db_conn, sample_company) == []


def test_comp_data_latest(db_conn, sample_company):
    comp_id = insert_comp(db_conn, sample_company, "AAPL", "Apple")

    # Insert old data
    insert_comp_data(db_conn, {
        "comp_set_id": comp_id, "ticker": "AAPL", "date_pulled": "2025-01-01",
        "ev_revenue": 8.0, "ev_ebitda": 18.0,
    })
    # Insert newer data
    insert_comp_data(db_conn, {
        "comp_set_id": comp_id, "ticker": "AAPL", "date_pulled": "2025-02-01",
        "ev_revenue": 10.0, "ev_ebitda": 22.0,
    })

    latest = get_latest_comp_data(db_conn, sample_company)
    assert len(latest) == 1
    assert latest[0]["ev_revenue"] == 10.0


def test_valuation_snapshot_crud(db_conn, sample_company):
    insert_valuation_snapshot(db_conn, {
        "portfolio_company_id": sample_company,
        "snapshot_date": "2025-01-15",
        "method": "blended",
        "enterprise_value": 500_000_000,
        "equity_value": 400_000_000,
        "holdco_equity_value": 80_000_000,
        "median_ev_revenue": 10.0,
        "median_ev_ebitda": 20.0,
        "weights_json": {"ev_revenue": 0.4, "ev_ebitda": 0.4, "growth_adjusted": 0.2},
    })

    history = get_valuation_history(db_conn, sample_company)
    assert len(history) == 1
    assert history[0]["enterprise_value"] == 500_000_000

    latest = get_latest_valuation(db_conn, sample_company)
    assert latest is not None
    assert latest["method"] == "blended"


def test_holdco_snapshot_crud(db_conn):
    insert_holdco_snapshot(db_conn, {
        "snapshot_date": "2025-01-15",
        "total_equity_value": 200_000_000,
        "holdco_cash": 50_000_000,
        "holdco_debt": 30_000_000,
        "nav": 220_000_000,
        "nav_per_share": 22.0,
        "shares_outstanding": 10_000_000,
        "change_vs_prior_pct": None,
    })

    latest = get_latest_holdco_snapshot(db_conn)
    assert latest is not None
    assert latest["nav"] == 220_000_000

    history = get_holdco_history(db_conn)
    assert len(history) == 1


def test_alert_crud(db_conn, sample_company):
    aid = insert_alert(db_conn, {
        "alert_type": "comp_multiple_change",
        "portfolio_company_id": sample_company,
        "message": "EV/Revenue changed 20%",
        "severity": "high",
    })

    active = get_active_alerts(db_conn)
    assert len(active) == 1

    acknowledge_alert(db_conn, aid)
    active = get_active_alerts(db_conn)
    assert len(active) == 0

    company_alerts = get_alerts_for_company(db_conn, sample_company)
    assert len(company_alerts) == 1
    assert company_alerts[0]["acknowledged"] == 1


def test_config_crud(db_conn):
    set_config(db_conn, "test_key", "42")
    assert get_config(db_conn, "test_key") == "42"
    assert get_config_float(db_conn, "test_key") == 42.0

    # Update
    set_config(db_conn, "test_key", "99")
    assert get_config(db_conn, "test_key") == "99"

    # Default
    assert get_config(db_conn, "missing", "default") == "default"
    assert get_config_float(db_conn, "missing", 1.5) == 1.5
