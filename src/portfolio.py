"""Portfolio aggregation: HoldCo NAV calculation and portfolio-level analytics."""

import sqlite3
from typing import Dict, Any, List, Optional

from src.database import (
    get_all_companies, get_latest_valuation, get_latest_holdco_snapshot,
    insert_holdco_snapshot, get_holdco_history, get_config_float,
)
from src.utils import today_str, pct_change, safe_divide


def calculate_holdco_nav(conn: sqlite3.Connection,
                         holdco_cash: float = None,
                         holdco_debt: float = None,
                         shares_outstanding: float = None,
                         save_snapshot: bool = True) -> Dict[str, Any]:
    """Aggregate all portfolio company holdco equity values into NAV."""
    # Use provided values or fall back to config
    if holdco_cash is None:
        holdco_cash = get_config_float(conn, "holdco_cash", 0.0)
    if holdco_debt is None:
        holdco_debt = get_config_float(conn, "holdco_debt", 0.0)
    if shares_outstanding is None:
        shares_outstanding = get_config_float(conn, "shares_outstanding", 1.0)

    companies = get_all_companies(conn)
    company_contributions = []
    total_equity = 0.0

    for company in companies:
        latest = get_latest_valuation(conn, company["id"])
        holdco_equity = latest["holdco_equity_value"] if latest else 0.0
        total_equity += holdco_equity
        company_contributions.append({
            "company_id": company["id"],
            "company_name": company["name"],
            "holdco_equity_value": holdco_equity,
            "enterprise_value": latest["enterprise_value"] if latest else 0.0,
        })

    nav = total_equity + holdco_cash - holdco_debt
    nav_per_share = safe_divide(nav, shares_outstanding)

    # Change vs prior
    prior = get_latest_holdco_snapshot(conn)
    change_vs_prior = pct_change(prior["nav"], nav) if prior else None

    result = {
        "total_equity_value": total_equity,
        "holdco_cash": holdco_cash,
        "holdco_debt": holdco_debt,
        "nav": nav,
        "nav_per_share": nav_per_share,
        "shares_outstanding": shares_outstanding,
        "change_vs_prior_pct": change_vs_prior,
        "company_contributions": company_contributions,
    }

    if save_snapshot:
        insert_holdco_snapshot(conn, {
            "snapshot_date": today_str(),
            "total_equity_value": total_equity,
            "holdco_cash": holdco_cash,
            "holdco_debt": holdco_debt,
            "nav": nav,
            "nav_per_share": nav_per_share,
            "shares_outstanding": shares_outstanding,
            "change_vs_prior_pct": change_vs_prior,
        })

    return result


def get_portfolio_summary(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Build a summary view of the entire portfolio."""
    companies = get_all_companies(conn)
    company_summaries = []
    total_equity = 0.0
    sector_breakdown: Dict[str, float] = {}

    for company in companies:
        latest = get_latest_valuation(conn, company["id"])
        holdco_equity = latest["holdco_equity_value"] if latest else 0.0
        total_equity += holdco_equity

        sector = company.get("sector") or "Other"
        sector_breakdown[sector] = sector_breakdown.get(sector, 0) + holdco_equity

        company_summaries.append({
            "id": company["id"],
            "name": company["name"],
            "sector": sector,
            "revenue_ttm": company["revenue_ttm"],
            "ebitda": company["ebitda"],
            "growth_rate": company["growth_rate"],
            "enterprise_value": latest["enterprise_value"] if latest else None,
            "holdco_equity_value": holdco_equity,
            "last_mark_date": company.get("last_mark_date"),
            "last_mark_ev": company.get("last_mark_ev"),
            "weight_pct": 0.0,  # filled below
        })

    # Calculate weights
    for cs in company_summaries:
        cs["weight_pct"] = safe_divide(cs["holdco_equity_value"], total_equity) if total_equity > 0 else 0.0

    latest_holdco = get_latest_holdco_snapshot(conn)

    return {
        "companies": company_summaries,
        "total_equity": total_equity,
        "nav": latest_holdco["nav"] if latest_holdco else None,
        "nav_per_share": latest_holdco["nav_per_share"] if latest_holdco else None,
        "change_vs_prior_pct": latest_holdco["change_vs_prior_pct"] if latest_holdco else None,
        "company_count": len(companies),
        "sector_breakdown": sector_breakdown,
    }


def get_portfolio_time_series(conn: sqlite3.Connection,
                              periods: int = 12) -> List[Dict[str, Any]]:
    """Return historical NAV snapshots for charting."""
    snapshots = get_holdco_history(conn, limit=periods)
    snapshots.reverse()  # oldest first for charting
    return snapshots


def get_concentration_analysis(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Return each company's percentage of total portfolio equity value."""
    companies = get_all_companies(conn)
    entries = []
    total = 0.0

    for company in companies:
        latest = get_latest_valuation(conn, company["id"])
        equity = latest["holdco_equity_value"] if latest else 0.0
        total += equity
        entries.append({
            "company_id": company["id"],
            "company_name": company["name"],
            "holdco_equity_value": equity,
        })

    for entry in entries:
        entry["weight_pct"] = safe_divide(entry["holdco_equity_value"], total) if total > 0 else 0.0

    entries.sort(key=lambda x: x["weight_pct"], reverse=True)
    return entries
