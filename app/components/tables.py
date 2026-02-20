"""Styled dataframe renderers for consistent table display."""

import streamlit as st
import pandas as pd
from typing import List, Dict, Any

from src.utils import format_large_number, format_multiple, format_percentage


def portfolio_summary_table(companies: List[Dict[str, Any]]) -> None:
    """Render the portfolio overview table."""
    if not companies:
        st.info("No portfolio companies yet. Import data in Settings.")
        return

    rows = []
    for c in companies:
        rows.append({
            "Company": c["name"],
            "Sector": c.get("sector", ""),
            "Revenue (TTM)": format_large_number(c.get("revenue_ttm") or 0),
            "EBITDA": format_large_number(c.get("ebitda") or 0),
            "Enterprise Value": format_large_number(c.get("enterprise_value") or 0),
            "HoldCo Equity": format_large_number(c.get("holdco_equity_value") or 0),
            "Weight": format_percentage(c.get("weight_pct") or 0),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


def comp_data_table(comps: List[Dict[str, Any]]) -> None:
    """Render comp set table with formatted multiples."""
    if not comps:
        st.info("No comps data available. Add comps and refresh from yfinance.")
        return

    rows = []
    for c in comps:
        rows.append({
            "Ticker": c.get("ticker", ""),
            "EV/Revenue": format_multiple(c["ev_revenue"]) if c.get("ev_revenue") else "N/A",
            "EV/EBITDA": format_multiple(c["ev_ebitda"]) if c.get("ev_ebitda") else "N/A",
            "Growth Rate": format_percentage(c["growth_rate"]) if c.get("growth_rate") is not None else "N/A",
            "Enterprise Value": format_large_number(c.get("enterprise_value") or 0),
            "Source": c.get("source", ""),
            "Date": c.get("date_pulled", ""),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


def valuation_snapshot_table(snapshots: List[Dict[str, Any]]) -> None:
    """Render valuation history table."""
    if not snapshots:
        st.info("No valuation history available.")
        return

    rows = []
    for s in snapshots:
        rows.append({
            "Date": s["snapshot_date"],
            "Method": s.get("method", ""),
            "Enterprise Value": format_large_number(s.get("enterprise_value") or 0),
            "Equity Value": format_large_number(s.get("equity_value") or 0),
            "HoldCo Equity": format_large_number(s.get("holdco_equity_value") or 0),
            "Med EV/Rev": format_multiple(s["median_ev_revenue"]) if s.get("median_ev_revenue") else "N/A",
            "Med EV/EBITDA": format_multiple(s["median_ev_ebitda"]) if s.get("median_ev_ebitda") else "N/A",
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


def alerts_table(alerts: List[Dict[str, Any]]) -> List[int]:
    """Render alerts table. Returns list of alert_ids user clicked to acknowledge."""
    if not alerts:
        st.info("No active alerts.")
        return []

    acknowledged_ids = []
    for alert in alerts:
        severity = alert.get("severity", "medium")
        icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(severity, "⚪")
        col1, col2, col3 = st.columns([0.7, 0.15, 0.15])
        with col1:
            st.markdown(f"{icon} **{alert['alert_type']}** — {alert['message']}")
            st.caption(f"Triggered: {alert['triggered_at']}")
        with col2:
            st.text(severity.upper())
        with col3:
            if st.button("Ack", key=f"ack_{alert['id']}"):
                acknowledged_ids.append(alert["id"])

    return acknowledged_ids
