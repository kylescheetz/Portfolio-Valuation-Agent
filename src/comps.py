"""Comparable company data: yfinance integration and manual comp management."""

import time
import sqlite3
import statistics
from typing import Dict, List, Optional, Tuple, Any
from datetime import date

import yfinance as yf

from src.config import YFINANCE_SLEEP_SECONDS
from src.database import (
    get_comps_for_company, get_all_companies, get_latest_comp_data,
    insert_comp_data,
)
from src.utils import safe_divide, today_str


def fetch_yfinance_data(ticker: str) -> Optional[Dict[str, Any]]:
    """Pull current financial data for a single ticker from yfinance.

    Returns dict with keys: enterprise_value, revenue, ebitda, market_cap,
    ev_revenue, ev_ebitda, growth_rate. Returns None if unavailable.
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        if not info or info.get("regularMarketPrice") is None:
            return None

        ev = info.get("enterpriseValue") or 0
        revenue = info.get("totalRevenue") or 0
        ebitda = info.get("ebitda") or 0
        market_cap = info.get("marketCap") or 0
        growth_rate = info.get("revenueGrowth") or 0

        ev_revenue = safe_divide(ev, revenue) if revenue > 0 else None
        ev_ebitda = safe_divide(ev, ebitda) if ebitda > 0 else None

        return {
            "enterprise_value": ev,
            "revenue": revenue,
            "ebitda": ebitda,
            "market_cap": market_cap,
            "ev_revenue": ev_revenue,
            "ev_ebitda": ev_ebitda,
            "growth_rate": growth_rate,
        }
    except Exception:
        return None


def refresh_comp_data(conn: sqlite3.Connection, portfolio_company_id: int) -> Tuple[int, List[str]]:
    """Refresh yfinance data for all comps in a company's comp set.

    Returns (success_count, list_of_error_messages).
    """
    comps = get_comps_for_company(conn, portfolio_company_id)
    success_count = 0
    errors: List[str] = []
    date_str = today_str()

    for comp in comps:
        ticker = comp["ticker"]
        data = fetch_yfinance_data(ticker)
        if data is None:
            errors.append(f"{ticker}: failed to fetch data")
            time.sleep(YFINANCE_SLEEP_SECONDS)
            continue

        insert_comp_data(conn, {
            "comp_set_id": comp["id"],
            "ticker": ticker,
            "date_pulled": date_str,
            "enterprise_value": data["enterprise_value"],
            "revenue": data["revenue"],
            "ebitda": data["ebitda"],
            "market_cap": data["market_cap"],
            "ev_revenue": data["ev_revenue"],
            "ev_ebitda": data["ev_ebitda"],
            "growth_rate": data["growth_rate"],
            "source": "yfinance",
        })
        success_count += 1
        time.sleep(YFINANCE_SLEEP_SECONDS)

    return success_count, errors


def refresh_all_comp_data(conn: sqlite3.Connection) -> Dict[int, Tuple[int, List[str]]]:
    """Refresh comp data for ALL portfolio companies."""
    companies = get_all_companies(conn)
    results = {}
    for company in companies:
        results[company["id"]] = refresh_comp_data(conn, company["id"])
    return results


def add_manual_comp_data(conn: sqlite3.Connection, comp_set_id: int, ticker: str,
                         data: Dict[str, float]) -> int:
    """Insert manually entered comp data."""
    return insert_comp_data(conn, {
        "comp_set_id": comp_set_id,
        "ticker": ticker,
        "date_pulled": today_str(),
        "enterprise_value": data.get("enterprise_value"),
        "revenue": data.get("revenue"),
        "ebitda": data.get("ebitda"),
        "market_cap": data.get("market_cap"),
        "ev_revenue": data.get("ev_revenue"),
        "ev_ebitda": data.get("ev_ebitda"),
        "growth_rate": data.get("growth_rate"),
        "source": "manual",
    })


def compute_comp_summary(conn: sqlite3.Connection,
                         portfolio_company_id: int) -> Dict[str, Any]:
    """Compute median, mean, high, low, std for EV/Revenue and EV/EBITDA
    across the latest comp data for a company."""
    comp_rows = get_latest_comp_data(conn, portfolio_company_id)

    ev_revs = [r["ev_revenue"] for r in comp_rows if r["ev_revenue"] is not None and r["ev_revenue"] > 0]
    ev_ebits = [r["ev_ebitda"] for r in comp_rows if r["ev_ebitda"] is not None and r["ev_ebitda"] > 0]
    growth_rates = [r["growth_rate"] for r in comp_rows if r["growth_rate"] is not None]

    result: Dict[str, Any] = {"comp_count": len(comp_rows)}

    if ev_revs:
        result["median_ev_revenue"] = statistics.median(ev_revs)
        result["mean_ev_revenue"] = statistics.mean(ev_revs)
        result["high_ev_revenue"] = max(ev_revs)
        result["low_ev_revenue"] = min(ev_revs)
        result["std_ev_revenue"] = statistics.stdev(ev_revs) if len(ev_revs) > 1 else 0.0
    else:
        result["median_ev_revenue"] = 0.0
        result["mean_ev_revenue"] = 0.0
        result["high_ev_revenue"] = 0.0
        result["low_ev_revenue"] = 0.0
        result["std_ev_revenue"] = 0.0

    if ev_ebits:
        result["median_ev_ebitda"] = statistics.median(ev_ebits)
        result["mean_ev_ebitda"] = statistics.mean(ev_ebits)
        result["high_ev_ebitda"] = max(ev_ebits)
        result["low_ev_ebitda"] = min(ev_ebits)
        result["std_ev_ebitda"] = statistics.stdev(ev_ebits) if len(ev_ebits) > 1 else 0.0
    else:
        result["median_ev_ebitda"] = 0.0
        result["mean_ev_ebitda"] = 0.0
        result["high_ev_ebitda"] = 0.0
        result["low_ev_ebitda"] = 0.0
        result["std_ev_ebitda"] = 0.0

    if growth_rates:
        result["median_growth_rate"] = statistics.median(growth_rates)
    else:
        result["median_growth_rate"] = 0.0

    return result
