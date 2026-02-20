"""Valuation engine: trading multiples, growth-adjusted, blended EV, equity conversion."""

import sqlite3
from typing import Dict, Any, List, Optional

from src.config import DEFAULT_WEIGHTS, GROWTH_ADJUSTMENT_FACTOR, SENSITIVITY_STD_DEVS
from src.database import (
    get_company, get_all_companies, insert_valuation_snapshot, update_company,
)
from src.comps import compute_comp_summary
from src.utils import today_str, pct_change


def trading_multiple_ev_revenue(revenue_ttm: float, median_ev_revenue: float) -> float:
    """EV via revenue trading multiple."""
    if median_ev_revenue <= 0 or revenue_ttm <= 0:
        return 0.0
    return revenue_ttm * median_ev_revenue


def trading_multiple_ev_ebitda(ebitda: float, median_ev_ebitda: float) -> float:
    """EV via EBITDA trading multiple. Returns 0.0 if ebitda <= 0."""
    if ebitda <= 0 or median_ev_ebitda <= 0:
        return 0.0
    return ebitda * median_ev_ebitda


def growth_adjusted_ev(revenue_ttm: float, median_ev_revenue: float,
                       company_growth_rate: float, median_comp_growth_rate: float,
                       adjustment_factor: float = None) -> float:
    """Growth-adjusted EV: applies growth premium/discount to revenue multiple."""
    if adjustment_factor is None:
        adjustment_factor = GROWTH_ADJUSTMENT_FACTOR
    if median_ev_revenue <= 0 or revenue_ttm <= 0:
        return 0.0
    growth_premium = (company_growth_rate - median_comp_growth_rate) * adjustment_factor
    adjusted_multiple = median_ev_revenue * (1 + growth_premium)
    return revenue_ttm * max(adjusted_multiple, 0)


def blended_enterprise_value(ev_revenue: float, ev_ebitda: float,
                             ev_growth_adjusted: float,
                             weights: Dict[str, float] = None) -> float:
    """Weighted blend of three EV methods.

    If ev_ebitda is 0 (negative EBITDA), redistributes its weight proportionally.
    """
    w = weights or DEFAULT_WEIGHTS.copy()
    w_rev = w.get("ev_revenue", 0.4)
    w_ebit = w.get("ev_ebitda", 0.4)
    w_growth = w.get("growth_adjusted", 0.2)

    # Redistribute EBITDA weight if unavailable
    if ev_ebitda <= 0 and w_ebit > 0:
        remaining = w_rev + w_growth
        if remaining > 0:
            w_rev = w_rev / remaining * (w_rev + w_ebit + w_growth)
            w_growth = w_growth / remaining * (w_rev + w_ebit + w_growth)
        else:
            w_rev = 1.0
            w_growth = 0.0
        w_ebit = 0.0
        ev_ebitda = 0.0

    return w_rev * ev_revenue + w_ebit * ev_ebitda + w_growth * ev_growth_adjusted


def enterprise_to_equity(enterprise_value: float, net_debt: float,
                         preferred_amount: float, ownership_pct: float,
                         dilution_pct: float) -> Dict[str, float]:
    """Convert EV to HoldCo equity value through the full bridge."""
    equity_value = enterprise_value - net_debt
    equity_after_prefs = max(0, equity_value - preferred_amount)
    holdco_equity = equity_after_prefs * ownership_pct * (1 - dilution_pct)
    return {
        "equity_value": equity_value,
        "equity_after_prefs": equity_after_prefs,
        "holdco_equity_value": holdco_equity,
    }


def run_valuation(conn: sqlite3.Connection, company_id: int,
                  weights: Dict[str, float] = None,
                  save_snapshot: bool = True,
                  notes: str = "") -> Dict[str, Any]:
    """Full valuation pipeline for a single company."""
    company = get_company(conn, company_id)
    if not company:
        raise ValueError(f"Company {company_id} not found")

    comp_summary = compute_comp_summary(conn, company_id)

    # Calculate each method
    ev_rev = trading_multiple_ev_revenue(
        company["revenue_ttm"], comp_summary["median_ev_revenue"]
    )
    ev_ebit = trading_multiple_ev_ebitda(
        company["ebitda"], comp_summary["median_ev_ebitda"]
    )
    ev_growth = growth_adjusted_ev(
        company["revenue_ttm"],
        comp_summary["median_ev_revenue"],
        company["growth_rate"],
        comp_summary["median_growth_rate"],
    )

    # Blend
    blended_ev = blended_enterprise_value(ev_rev, ev_ebit, ev_growth, weights)

    # Equity conversion
    equity_result = enterprise_to_equity(
        blended_ev,
        company["net_debt"],
        company["preferred_amount"],
        company["ownership_pct"],
        company["dilution_pct"],
    )

    # Change vs last mark
    change_ev_pct = pct_change(company["last_mark_ev"] or 0, blended_ev)
    change_equity_pct = pct_change(
        company["last_mark_equity"] or 0, equity_result["holdco_equity_value"]
    )

    result = {
        "company_id": company_id,
        "company_name": company["name"],
        "ev_revenue_method": ev_rev,
        "ev_ebitda_method": ev_ebit,
        "ev_growth_adjusted_method": ev_growth,
        "enterprise_value": blended_ev,
        "equity_value": equity_result["equity_value"],
        "equity_after_prefs": equity_result["equity_after_prefs"],
        "holdco_equity_value": equity_result["holdco_equity_value"],
        "median_ev_revenue": comp_summary["median_ev_revenue"],
        "median_ev_ebitda": comp_summary["median_ev_ebitda"],
        "comp_count": comp_summary["comp_count"],
        "weights": weights or DEFAULT_WEIGHTS,
        "change_ev_pct": change_ev_pct,
        "change_equity_pct": change_equity_pct,
    }

    if save_snapshot:
        snapshot_date = today_str()
        insert_valuation_snapshot(conn, {
            "portfolio_company_id": company_id,
            "snapshot_date": snapshot_date,
            "method": "blended",
            "enterprise_value": blended_ev,
            "equity_value": equity_result["equity_value"],
            "holdco_equity_value": equity_result["holdco_equity_value"],
            "median_ev_revenue": comp_summary["median_ev_revenue"],
            "median_ev_ebitda": comp_summary["median_ev_ebitda"],
            "weights_json": weights or DEFAULT_WEIGHTS,
            "notes": notes,
        })
        update_company(conn, company_id, {
            "last_mark_date": snapshot_date,
            "last_mark_ev": blended_ev,
            "last_mark_equity": equity_result["holdco_equity_value"],
        })

    return result


def sensitivity_analysis(conn: sqlite3.Connection, company_id: int,
                         std_devs: float = None,
                         weights: Dict[str, float] = None) -> Dict[str, Any]:
    """Run valuation at base, +/- std dev on comp multiples."""
    if std_devs is None:
        std_devs = SENSITIVITY_STD_DEVS

    company = get_company(conn, company_id)
    if not company:
        raise ValueError(f"Company {company_id} not found")

    comp_summary = compute_comp_summary(conn, company_id)

    scenarios = {}
    for scenario, multiplier in [("base", 0), ("upside", std_devs), ("downside", -std_devs)]:
        adj_ev_rev = comp_summary["median_ev_revenue"] + multiplier * comp_summary["std_ev_revenue"]
        adj_ev_ebit = comp_summary["median_ev_ebitda"] + multiplier * comp_summary["std_ev_ebitda"]
        adj_ev_rev = max(adj_ev_rev, 0)
        adj_ev_ebit = max(adj_ev_ebit, 0)

        ev_rev = trading_multiple_ev_revenue(company["revenue_ttm"], adj_ev_rev)
        ev_ebit = trading_multiple_ev_ebitda(company["ebitda"], adj_ev_ebit)
        ev_growth = growth_adjusted_ev(
            company["revenue_ttm"], adj_ev_rev,
            company["growth_rate"], comp_summary["median_growth_rate"],
        )
        blended_ev = blended_enterprise_value(ev_rev, ev_ebit, ev_growth, weights)
        equity_result = enterprise_to_equity(
            blended_ev, company["net_debt"], company["preferred_amount"],
            company["ownership_pct"], company["dilution_pct"],
        )

        scenarios[scenario] = {
            "enterprise_value": blended_ev,
            "equity_value": equity_result["equity_value"],
            "holdco_equity_value": equity_result["holdco_equity_value"],
            "adj_ev_revenue_multiple": adj_ev_rev,
            "adj_ev_ebitda_multiple": adj_ev_ebit,
        }

    ev_range = scenarios["upside"]["enterprise_value"] - scenarios["downside"]["enterprise_value"]
    base_ev = scenarios["base"]["enterprise_value"]
    pct_range = (ev_range / base_ev) if base_ev > 0 else 0

    return {
        "company_id": company_id,
        "company_name": company["name"],
        **scenarios,
        "ev_range": ev_range,
        "pct_range": pct_range,
    }


def run_all_valuations(conn: sqlite3.Connection,
                       weights: Dict[str, float] = None,
                       save_snapshots: bool = True) -> List[Dict[str, Any]]:
    """Run valuations for all portfolio companies."""
    companies = get_all_companies(conn)
    results = []
    for company in companies:
        try:
            result = run_valuation(conn, company["id"], weights, save_snapshots)
            results.append(result)
        except Exception as e:
            results.append({
                "company_id": company["id"],
                "company_name": company["name"],
                "error": str(e),
            })
    return results
