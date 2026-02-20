"""Portfolio Overview — NAV summary, all companies, charts."""

import sys
from pathlib import Path
_project_root = str(Path(__file__).parent.parent.parent)
_src_dir = str(Path(__file__).parent.parent.parent / "src")
_app_root = str(Path(__file__).parent.parent)
for _p in [_project_root, _src_dir, _app_root]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import streamlit as st
from database import get_db
from portfolio import get_portfolio_summary, get_portfolio_time_series, get_concentration_analysis
from valuation import run_all_valuations
from portfolio import calculate_holdco_nav
from utils import format_large_number, format_percentage
from components.charts import nav_time_series_chart, concentration_pie_chart, sector_bar_chart
from components.tables import portfolio_summary_table

conn = get_db()

st.title("Portfolio Overview")

# Action buttons
col_a, col_b, _ = st.columns([0.2, 0.2, 0.6])
with col_a:
    if st.button("🔄 Run All Valuations", type="primary"):
        with st.spinner("Running valuations..."):
            results = run_all_valuations(conn)
            calculate_holdco_nav(conn)
        st.success(f"Valued {len(results)} companies")
        st.rerun()
with col_b:
    if st.button("📥 Export CSV"):
        from data_ingestion import export_companies_to_csv
        import tempfile, os
        tmp = os.path.join(tempfile.gettempdir(), "ev_portfolio_export.csv")
        export_companies_to_csv(conn, tmp)
        with open(tmp, "r") as f:
            st.download_button("Download", f.read(), "portfolio_export.csv", "text/csv")

# Summary metrics
summary = get_portfolio_summary(conn)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Portfolio Companies", summary["company_count"])
with col2:
    st.metric("Total Portfolio Equity", format_large_number(summary["total_equity"]))
with col3:
    nav_display = format_large_number(summary["nav"]) if summary["nav"] else "N/A"
    st.metric("HoldCo NAV", nav_display,
              delta=format_percentage(summary["change_vs_prior_pct"])
              if summary["change_vs_prior_pct"] is not None else None)
with col4:
    nav_ps = f"${summary['nav_per_share']:.2f}" if summary["nav_per_share"] else "N/A"
    st.metric("NAV / Share", nav_ps)

st.divider()

# Portfolio table
st.subheader("Portfolio Companies")
portfolio_summary_table(summary["companies"])

# Charts row
col_left, col_right = st.columns(2)

with col_left:
    concentration = get_concentration_analysis(conn)
    if concentration and any(c["holdco_equity_value"] > 0 for c in concentration):
        st.plotly_chart(concentration_pie_chart(concentration), use_container_width=True)
    else:
        st.info("No valuation data for concentration chart")

with col_right:
    if summary["sector_breakdown"]:
        st.plotly_chart(sector_bar_chart(summary["sector_breakdown"]), use_container_width=True)
    else:
        st.info("No sector data available")

# NAV time series
time_series = get_portfolio_time_series(conn)
if time_series:
    st.plotly_chart(nav_time_series_chart(time_series), use_container_width=True)
else:
    st.info("No historical NAV data yet. Run valuations to start tracking.")
