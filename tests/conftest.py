"""Shared pytest fixtures for the EV MTM Engine test suite."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import sqlite3
from src.database import initialize_database, insert_company, insert_comp, insert_comp_data


@pytest.fixture
def db_conn():
    """Provide a fresh in-memory SQLite database for each test."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    initialize_database(conn)
    yield conn
    conn.close()


@pytest.fixture
def sample_company(db_conn):
    """Insert and return a single sample portfolio company."""
    company_id = insert_company(db_conn, {
        "name": "TestCo",
        "sector": "SaaS",
        "subsector": "Analytics",
        "revenue_ttm": 50_000_000,
        "revenue_run_rate": 55_000_000,
        "ebitda": 8_000_000,
        "gross_margin": 0.68,
        "growth_rate": 0.25,
        "net_debt": 3_000_000,
        "ownership_pct": 0.20,
        "preferred_amount": 10_000_000,
        "dilution_pct": 0.05,
    })
    return company_id


@pytest.fixture
def sample_company_with_comps(db_conn, sample_company):
    """Insert a company with comp set and comp data pre-loaded."""
    comp1_id = insert_comp(db_conn, sample_company, "FAKE1", "FakeComp One", "manual")
    comp2_id = insert_comp(db_conn, sample_company, "FAKE2", "FakeComp Two", "manual")

    for comp_id, ticker, ev_rev, ev_ebitda, growth in [
        (comp1_id, "FAKE1", 12.0, 25.0, 0.20),
        (comp2_id, "FAKE2", 10.0, 20.0, 0.18),
    ]:
        insert_comp_data(db_conn, {
            "comp_set_id": comp_id,
            "ticker": ticker,
            "date_pulled": "2025-01-15",
            "enterprise_value": 5_000_000_000,
            "revenue": 400_000_000,
            "ebitda": 200_000_000,
            "market_cap": 4_500_000_000,
            "ev_revenue": ev_rev,
            "ev_ebitda": ev_ebitda,
            "growth_rate": growth,
            "source": "manual",
        })

    return sample_company


@pytest.fixture
def negative_ebitda_company(db_conn):
    """Insert a company with negative EBITDA."""
    company_id = insert_company(db_conn, {
        "name": "PreProfitCo",
        "sector": "SaaS",
        "revenue_ttm": 30_000_000,
        "revenue_run_rate": 35_000_000,
        "ebitda": -5_000_000,
        "gross_margin": 0.72,
        "growth_rate": 0.40,
        "net_debt": -8_000_000,
        "ownership_pct": 0.30,
        "preferred_amount": 5_000_000,
        "dilution_pct": 0.05,
    })

    comp_id = insert_comp(db_conn, company_id, "COMP1", "Comp One", "manual")
    insert_comp_data(db_conn, {
        "comp_set_id": comp_id,
        "ticker": "COMP1",
        "date_pulled": "2025-01-15",
        "enterprise_value": 3_000_000_000,
        "revenue": 200_000_000,
        "ebitda": 50_000_000,
        "market_cap": 2_800_000_000,
        "ev_revenue": 15.0,
        "ev_ebitda": 60.0,
        "growth_rate": 0.30,
        "source": "manual",
    })

    return company_id


@pytest.fixture
def sample_portfolio(db_conn):
    """Insert multiple companies with comps for portfolio-level tests."""
    companies = []

    for name, revenue, ebitda, net_debt, ownership, prefs, dilution in [
        ("AlphaCo", 40_000_000, 6_000_000, 2_000_000, 0.25, 8_000_000, 0.04),
        ("BetaCo", 80_000_000, 15_000_000, 5_000_000, 0.18, 12_000_000, 0.03),
        ("GammaCo", 60_000_000, -3_000_000, -4_000_000, 0.22, 10_000_000, 0.05),
    ]:
        cid = insert_company(db_conn, {
            "name": name, "sector": "SaaS", "revenue_ttm": revenue,
            "revenue_run_rate": revenue * 1.1, "ebitda": ebitda,
            "gross_margin": 0.65, "growth_rate": 0.20,
            "net_debt": net_debt, "ownership_pct": ownership,
            "preferred_amount": prefs, "dilution_pct": dilution,
        })

        comp_id = insert_comp(db_conn, cid, f"CMP{cid}", f"Comp{cid}", "manual")
        insert_comp_data(db_conn, {
            "comp_set_id": comp_id, "ticker": f"CMP{cid}",
            "date_pulled": "2025-01-15",
            "enterprise_value": 2_000_000_000, "revenue": 300_000_000,
            "ebitda": 100_000_000, "market_cap": 1_800_000_000,
            "ev_revenue": 10.0, "ev_ebitda": 20.0, "growth_rate": 0.18,
            "source": "manual",
        })
        companies.append(cid)

    return companies
