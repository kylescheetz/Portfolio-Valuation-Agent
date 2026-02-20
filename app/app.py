"""EV Mark-to-Market Engine — Streamlit entrypoint."""

import sys
from pathlib import Path

# Add project root and src/ to path for Streamlit Cloud compatibility
project_root = Path(__file__).parent.parent
src_dir = project_root / "src"
for p in [str(project_root), str(src_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import streamlit as st
from database import get_db
from portfolio import get_portfolio_summary
from utils import format_large_number, format_percentage

st.set_page_config(
    page_title="EV Mark-to-Market Engine",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for EV branding
st.markdown("""
<style>
    /* Sidebar branding */
    [data-testid="stSidebar"] {
        background-color: #26352F;
    }
    [data-testid="stSidebar"] * {
        color: #F2F1ED !important;
    }
    [data-testid="stSidebar"] [data-testid="stMetricValue"] {
        color: #B06D27 !important;
    }
    [data-testid="stSidebar"] [data-testid="stMetricDelta"] {
        color: #A2C699 !important;
    }
    /* Headers */
    h1, h2, h3 {
        color: #26352F !important;
    }
    /* Primary buttons */
    .stButton > button[kind="primary"] {
        background-color: #B06D27;
        border-color: #B06D27;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: #9A5E20;
        border-color: #9A5E20;
    }
    /* Metric styling */
    [data-testid="stMetricValue"] {
        color: #26352F;
    }
    /* Dividers */
    hr {
        border-color: #E6E3D4;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar
st.sidebar.markdown("### ENDURING VENTURES")
st.sidebar.caption("Mark-to-Market Engine")
st.sidebar.divider()

# Show NAV headline in sidebar
try:
    conn = get_db()
    summary = get_portfolio_summary(conn)
    conn.close()
    if summary["nav"] is not None:
        st.sidebar.metric("HoldCo NAV", format_large_number(summary["nav"]),
                          delta=format_percentage(summary["change_vs_prior_pct"])
                          if summary["change_vs_prior_pct"] is not None else None)
        st.sidebar.metric("NAV / Share", f"${summary['nav_per_share']:.2f}"
                          if summary["nav_per_share"] else "N/A")
    st.sidebar.caption(f"{summary['company_count']} portfolio companies")
except Exception:
    st.sidebar.caption("No data loaded yet")

st.sidebar.divider()
st.sidebar.caption("Built to Endure")

# Main page content
st.title("EV Mark-to-Market Engine")
st.markdown("Continuously monitor portfolio company valuations, "
            "track public comps, and aggregate to HoldCo NAV.")

st.info("Use the sidebar to navigate: Portfolio Overview, Company Detail, "
        "Comps Manager, Valuation History, Alerts, and Settings.")

# Quick stats
try:
    conn = get_db()
    summary = get_portfolio_summary(conn)
    conn.close()
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
except Exception:
    st.warning("No portfolio data loaded. Go to **Settings** to import data, "
               "or run `python -m scripts.seed_database` to seed sample data.")
