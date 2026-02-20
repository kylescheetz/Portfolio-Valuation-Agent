"""Comps Manager — add/remove comps, refresh from yfinance, view multiples."""

import sys
from pathlib import Path
_project_root = str(Path(__file__).parent.parent.parent)
_app_root = str(Path(__file__).parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
if _app_root not in sys.path:
    sys.path.insert(0, _app_root)

import streamlit as st
from src.database import (
    get_db, get_all_companies,
    get_comps_for_company, get_latest_comp_data, insert_comp, delete_comp,
)
from src.comps import refresh_comp_data, compute_comp_summary, add_manual_comp_data
from src.utils import format_multiple
from components.tables import comp_data_table
from components.charts import comp_multiples_bar_chart

conn = get_db()

st.title("Comps Manager")

companies = get_all_companies(conn)
if not companies:
    st.warning("No portfolio companies loaded. Import data in Settings.")
    st.stop()

company_names = {c["name"]: c for c in companies}
selected_name = st.selectbox("Select Company", list(company_names.keys()))
company = company_names[selected_name]
company_id = company["id"]

# --- Current Comp Set ---
st.subheader("Current Comp Set")

comps = get_comps_for_company(conn, company_id)
comp_data = get_latest_comp_data(conn, company_id)
comp_summary = compute_comp_summary(conn, company_id)

# Refresh button
col1, col2 = st.columns([0.3, 0.7])
with col1:
    if st.button("🔄 Refresh from yfinance", type="primary"):
        with st.spinner("Pulling live data..."):
            success, errors = refresh_comp_data(conn, company_id)
        st.success(f"Refreshed {success} comps")
        if errors:
            for err in errors:
                st.warning(err)
        st.rerun()

# Show comp data
comp_data_table(comp_data)

# Summary stats
if comp_summary["comp_count"] > 0:
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Median EV/Revenue", format_multiple(comp_summary["median_ev_revenue"]))
    with col2:
        st.metric("Median EV/EBITDA", format_multiple(comp_summary["median_ev_ebitda"]))
    with col3:
        st.metric("Comp Count", comp_summary["comp_count"])
    with col4:
        st.metric("Median Growth", f"{comp_summary['median_growth_rate']*100:.1f}%"
                  if comp_summary["median_growth_rate"] else "N/A")

# Multiples chart
if comp_data:
    st.plotly_chart(comp_multiples_bar_chart(comp_data, comp_summary), use_container_width=True)

st.divider()

# --- Remove Comps ---
st.subheader("Manage Comps")
if comps:
    for comp in comps:
        col1, col2, col3 = st.columns([0.4, 0.3, 0.3])
        with col1:
            st.text(f"{comp['ticker']} — {comp['company_name']}")
        with col2:
            st.caption(f"Source: {comp['source']}")
        with col3:
            if st.button("Remove", key=f"remove_{comp['id']}"):
                delete_comp(conn, comp["id"])
                st.success(f"Removed {comp['ticker']}")
                st.rerun()

st.divider()

# --- Add Comp ---
st.subheader("Add Comp")
tab1, tab2 = st.tabs(["Add by Ticker", "Manual Entry"])

with tab1:
    with st.form("add_ticker_form"):
        col1, col2 = st.columns(2)
        with col1:
            new_ticker = st.text_input("Ticker Symbol (e.g., AAPL)")
        with col2:
            new_name = st.text_input("Company Name (e.g., Apple Inc)")

        if st.form_submit_button("Add Comp"):
            if new_ticker and new_name:
                try:
                    insert_comp(conn, company_id, new_ticker.upper(), new_name)
                    st.success(f"Added {new_ticker.upper()}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.warning("Please fill in both fields")

with tab2:
    with st.form("manual_comp_form"):
        st.caption("Enter comp data manually (for private comps or overrides)")
        col1, col2 = st.columns(2)
        with col1:
            m_ticker = st.text_input("Ticker / ID")
            m_name = st.text_input("Company Name")
            m_ev = st.number_input("Enterprise Value", value=0.0, format="%.0f")
        with col2:
            m_revenue = st.number_input("Revenue", value=0.0, format="%.0f")
            m_ebitda = st.number_input("EBITDA", value=0.0, format="%.0f")
            m_growth = st.number_input("Growth Rate", value=0.0, format="%.2f")

        if st.form_submit_button("Add Manual Comp"):
            if m_ticker and m_name:
                try:
                    # Insert comp set entry if not exists
                    existing = get_comps_for_company(conn, company_id)
                    existing_tickers = {c["ticker"] for c in existing}
                    if m_ticker.upper() not in existing_tickers:
                        comp_id = insert_comp(conn, company_id, m_ticker.upper(), m_name, "manual")
                    else:
                        comp_id = next(c["id"] for c in existing if c["ticker"] == m_ticker.upper())

                    ev_rev = m_ev / m_revenue if m_revenue > 0 else None
                    ev_ebit = m_ev / m_ebitda if m_ebitda > 0 else None

                    add_manual_comp_data(conn, comp_id, m_ticker.upper(), {
                        "enterprise_value": m_ev,
                        "revenue": m_revenue,
                        "ebitda": m_ebitda,
                        "market_cap": 0,
                        "ev_revenue": ev_rev,
                        "ev_ebitda": ev_ebit,
                        "growth_rate": m_growth,
                    })
                    st.success(f"Added manual data for {m_ticker.upper()}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.warning("Please fill in ticker and company name")
