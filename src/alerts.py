"""Alert detection: threshold checks, alert generation, and management."""

import sqlite3
from typing import Dict, Any, List, Optional

from .config import (
    ALERT_COMP_MULTIPLE_CHANGE_PCT,
    ALERT_PORTFOLIO_VALUE_DELTA_PCT,
    ALERT_UNDERPERFORMANCE_PCT,
)
from .database import (
    get_all_companies, get_company, get_latest_valuation,
    get_latest_comp_data, get_active_alerts, insert_alert, get_config_float,
)
from .comps import compute_comp_summary
from .utils import pct_change


def check_comp_multiple_change(conn: sqlite3.Connection,
                               portfolio_company_id: int,
                               threshold_pct: float = None) -> List[Dict[str, Any]]:
    """Compare current comp medians vs last valuation snapshot medians.

    If median EV/Revenue or EV/EBITDA moved > threshold_pct, generate alert.
    """
    if threshold_pct is None:
        threshold_pct = get_config_float(
            conn, "alert_comp_change_pct", ALERT_COMP_MULTIPLE_CHANGE_PCT
        )

    alerts = []
    company = get_company(conn, portfolio_company_id)
    if not company:
        return alerts

    latest_val = get_latest_valuation(conn, portfolio_company_id)
    if not latest_val:
        return alerts

    comp_summary = compute_comp_summary(conn, portfolio_company_id)

    # Check EV/Revenue change
    old_ev_rev = latest_val.get("median_ev_revenue") or 0
    new_ev_rev = comp_summary.get("median_ev_revenue") or 0
    if old_ev_rev > 0:
        change = pct_change(old_ev_rev, new_ev_rev)
        if change is not None and abs(change) > threshold_pct:
            direction = "increased" if change > 0 else "decreased"
            alerts.append({
                "alert_type": "comp_multiple_change",
                "portfolio_company_id": portfolio_company_id,
                "message": (
                    f"{company['name']}: Median EV/Revenue {direction} "
                    f"{abs(change)*100:.1f}% (from {old_ev_rev:.1f}x to {new_ev_rev:.1f}x)"
                ),
                "severity": "high" if abs(change) > threshold_pct * 2 else "medium",
            })

    # Check EV/EBITDA change
    old_ev_ebit = latest_val.get("median_ev_ebitda") or 0
    new_ev_ebit = comp_summary.get("median_ev_ebitda") or 0
    if old_ev_ebit > 0:
        change = pct_change(old_ev_ebit, new_ev_ebit)
        if change is not None and abs(change) > threshold_pct:
            direction = "increased" if change > 0 else "decreased"
            alerts.append({
                "alert_type": "comp_multiple_change",
                "portfolio_company_id": portfolio_company_id,
                "message": (
                    f"{company['name']}: Median EV/EBITDA {direction} "
                    f"{abs(change)*100:.1f}% (from {old_ev_ebit:.1f}x to {new_ev_ebit:.1f}x)"
                ),
                "severity": "high" if abs(change) > threshold_pct * 2 else "medium",
            })

    return alerts


def check_valuation_delta(conn: sqlite3.Connection,
                          portfolio_company_id: int,
                          threshold_pct: float = None) -> Optional[Dict[str, Any]]:
    """Compare latest valuation EV to company's last_mark_ev."""
    if threshold_pct is None:
        threshold_pct = get_config_float(
            conn, "alert_value_delta_pct", ALERT_PORTFOLIO_VALUE_DELTA_PCT
        )

    company = get_company(conn, portfolio_company_id)
    if not company or not company.get("last_mark_ev"):
        return None

    latest = get_latest_valuation(conn, portfolio_company_id)
    if not latest:
        return None

    change = pct_change(company["last_mark_ev"], latest["enterprise_value"])
    if change is not None and abs(change) > threshold_pct:
        direction = "increased" if change > 0 else "decreased"
        return {
            "alert_type": "valuation_delta",
            "portfolio_company_id": portfolio_company_id,
            "message": (
                f"{company['name']}: EV {direction} {abs(change)*100:.1f}% "
                f"vs last mark"
            ),
            "severity": "high" if abs(change) > threshold_pct * 2 else "medium",
        }

    return None


def check_underperformance(conn: sqlite3.Connection,
                           portfolio_company_id: int,
                           threshold_pct: float = None) -> Optional[Dict[str, Any]]:
    """Check if company financials are underperforming vs growth_rate expectations."""
    if threshold_pct is None:
        threshold_pct = get_config_float(
            conn, "alert_underperformance_pct", ALERT_UNDERPERFORMANCE_PCT
        )

    company = get_company(conn, portfolio_company_id)
    if not company:
        return None

    # Compare run-rate vs TTM growth expectations
    expected_revenue = company["revenue_ttm"] * (1 + company["growth_rate"])
    if expected_revenue > 0 and company["revenue_run_rate"] > 0:
        miss = pct_change(expected_revenue, company["revenue_run_rate"])
        if miss is not None and miss < -threshold_pct:
            return {
                "alert_type": "underperformance",
                "portfolio_company_id": portfolio_company_id,
                "message": (
                    f"{company['name']}: Revenue run-rate "
                    f"({company['revenue_run_rate']/1e6:.1f}M) is "
                    f"{abs(miss)*100:.1f}% below expected "
                    f"({expected_revenue/1e6:.1f}M)"
                ),
                "severity": "high" if abs(miss) > threshold_pct * 2 else "medium",
            }

    return None


def run_all_checks(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Run all alert checks across all portfolio companies.

    Inserts any new alerts into the alerts table.
    """
    companies = get_all_companies(conn)
    new_alerts = []

    for company in companies:
        cid = company["id"]

        # Comp multiple changes
        comp_alerts = check_comp_multiple_change(conn, cid)
        new_alerts.extend(comp_alerts)

        # Valuation delta
        val_alert = check_valuation_delta(conn, cid)
        if val_alert:
            new_alerts.append(val_alert)

        # Underperformance
        perf_alert = check_underperformance(conn, cid)
        if perf_alert:
            new_alerts.append(perf_alert)

    # Insert all new alerts
    for alert in new_alerts:
        insert_alert(conn, alert)

    return new_alerts


def get_alert_summary(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Return summary: total_active, by_severity counts, by_type counts."""
    active = get_active_alerts(conn)
    by_severity: Dict[str, int] = {}
    by_type: Dict[str, int] = {}

    for alert in active:
        sev = alert.get("severity", "medium")
        by_severity[sev] = by_severity.get(sev, 0) + 1
        atype = alert.get("alert_type", "unknown")
        by_type[atype] = by_type.get(atype, 0) + 1

    return {
        "total_active": len(active),
        "by_severity": by_severity,
        "by_type": by_type,
    }
