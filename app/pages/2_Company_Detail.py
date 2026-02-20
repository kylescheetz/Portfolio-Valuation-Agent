"""Company Detail — deep dive on one company: financials, comps, valuation, sensitivity."""

import sys
from pathlib import Path
_project_root = str(Path(__file__).parent.parent.parent)
_app_root = str(Path(__file__).parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
if _app_root not in sys.path:
    sys.path.insert(0, _app_root)

import streamlit as st
from src.database import get_connection, initialize_database, get_all_companies, update_company, get_latest_comp_data
from src.config import DB_PATH, DEFAULT_WEIGHTS
from src.valuation import run_valuation, sensitivity_analysis
from src.comps import compute_comp_summary
from src.database import get_valuation_history
from src.utils import format_large_number, format_multiple, format_percentage
from components.charts import (
    company_valuation_chart, sensitivity_tornado_chart,
    equity_bridge_waterfall, comp_multiples_bar_chart,
)
from components.tables import comp_data_table, valuation_snapshot_table

if "db_conn" not in st.session_state:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(DB_PATH)
    initialize_database(conn)
    st.session_state.db_conn = conn

conn = st.session_state.db_conn

st.title("Company Detail")

companies = get_all_companies(conn)
if not companies:
    st.warning("No portfolio companies loaded. Import data in Settings.")
    st.stop()

company_names = {c["name"]: c for c in companies}
selected_name = st.selectbox("Select Company", list(company_names.keys()))
company = company_names[selected_name]
company_id = company["id"]

# --- Financials Section ---
st.subheader("Financials")
with st.form("financials_form"):
    col1, col2, col3 = st.columns(3)
    with col1:
        revenue_ttm = st.number_input("Revenue (TTM)", value=float(company["revenue_ttm"]), format="%.0f")
        revenue_rr = st.number_input("Revenue (Run-Rate)", value=float(company["revenue_run_rate"]), format="%.0f")
        ebitda = st.number_input("EBITDA", value=float(company["ebitda"]), format="%.0f")
    with col2:
        gross_margin = st.number_input("Gross Margin", value=float(company["gross_margin"]), format="%.2f", min_value=0.0, max_value=1.0)
        growth_rate = st.number_input("Growth Rate", value=float(company["growth_rate"]), format="%.2f")
        net_debt = st.number_input("Net Debt", value=float(company["net_debt"]), format="%.0f")
    with col3:
        ownership_pct = st.number_input("Ownership %", value=float(company["ownership_pct"]), format="%.2f", min_value=0.0, max_value=1.0)
        preferred_amount = st.number_input("Preferred Amount", value=float(company["preferred_amount"]), format="%.0f")
        dilution_pct = st.number_input("Dilution %", value=float(company["dilution_pct"]), format="%.2f", min_value=0.0, max_value=1.0)

    if st.form_submit_button("Save Financials"):
        update_company(conn, company_id, {
            "revenue_ttm": revenue_ttm, "revenue_run_rate": revenue_rr,
            "ebitda": ebitda, "gross_margin": gross_margin,
            "growth_rate": growth_rate, "net_debt": net_debt,
            "ownership_pct": ownership_pct, "preferred_amount": preferred_amount,
            "dilution_pct": dilution_pct,
        })
        st.success("Financials updated!")
        st.rerun()

st.divider()

# --- Comp Summary ---
st.subheader("Comparable Companies")
comp_data = get_latest_comp_data(conn, company_id)
comp_summary = compute_comp_summary(conn, company_id)

col_l, col_r = st.columns([0.6, 0.4])
with col_l:
    comp_data_table(comp_data)
with col_r:
    if comp_data:
        st.metric("Median EV/Revenue", format_multiple(comp_summary["median_ev_revenue"]))
        st.metric("Median EV/EBITDA", format_multiple(comp_summary["median_ev_ebitda"]))
        st.metric("Comp Count", comp_summary["comp_count"])

if comp_data:
    st.plotly_chart(comp_multiples_bar_chart(comp_data, comp_summary), use_container_width=True)

st.divider()

# --- Valuation Breakdown ---
st.subheader("Valuation Breakdown")

if st.button("🔄 Run Valuation", type="primary"):
    with st.spinner("Calculating..."):
        result = run_valuation(conn, company_id)
    st.success("Valuation complete!")
    st.rerun()

# Show latest valuation
from src.database import get_latest_valuation
latest = get_latest_valuation(conn, company_id)

if latest:
    # Method comparison
    try:
        # Re-compute for display (without saving)
        result = run_valuation(conn, company_id, save_snapshot=False)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("EV/Revenue Method", format_large_number(result["ev_revenue_method"]))
        with col2:
            st.metric("EV/EBITDA Method", format_large_number(result["ev_ebitda_method"]))
        with col3:
            st.metric("Growth-Adjusted", format_large_number(result["ev_growth_adjusted_method"]))

        st.divider()

        # Blended result
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Blended EV", format_large_number(result["enterprise_value"]))
        with col2:
            st.metric("Equity Value", format_large_number(result["equity_value"]))
        with col3:
            st.metric("HoldCo Equity", format_large_number(result["holdco_equity_value"]))

        # Equity bridge waterfall
        equity_after_debt = result["enterprise_value"] - company["net_debt"]
        equity_after_prefs = result.get("equity_after_prefs", 0)
        ownership_reduction = equity_after_prefs - (equity_after_prefs * company["ownership_pct"])
        dilution_reduction = (equity_after_prefs * company["ownership_pct"]) - result["holdco_equity_value"]

        st.plotly_chart(
            equity_bridge_waterfall(
                company["name"],
                ev=result["enterprise_value"],
                net_debt=company["net_debt"],
                prefs=company["preferred_amount"],
                ownership_adj=-ownership_reduction,
                dilution_adj=-dilution_reduction,
                holdco_equity=result["holdco_equity_value"],
            ),
            use_container_width=True,
        )
    except Exception as e:
        st.error(f"Valuation error: {e}")

    st.divider()

    # --- Sensitivity Analysis ---
    st.subheader("Sensitivity Analysis")
    try:
        sens = sensitivity_analysis(conn, company_id)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Downside EV", format_large_number(sens["downside"]["enterprise_value"]))
        with col2:
            st.metric("Base EV", format_large_number(sens["base"]["enterprise_value"]))
        with col3:
            st.metric("Upside EV", format_large_number(sens["upside"]["enterprise_value"]))

        st.plotly_chart(
            sensitivity_tornado_chart(
                company["name"],
                sens["base"]["enterprise_value"],
                sens["upside"]["enterprise_value"],
                sens["downside"]["enterprise_value"],
            ),
            use_container_width=True,
        )
    except Exception as e:
        st.error(f"Sensitivity error: {e}")

    st.divider()

    # --- Valuation History ---
    st.subheader("Valuation History")
    history = get_valuation_history(conn, company_id)
    if history:
        # Reverse for charting (oldest first)
        chart_data = list(reversed(history))
        st.plotly_chart(company_valuation_chart(chart_data, company["name"]), use_container_width=True)
        valuation_snapshot_table(history)
else:
    st.info("No valuations yet. Click 'Run Valuation' to start.")
