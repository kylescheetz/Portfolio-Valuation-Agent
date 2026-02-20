"""Valuation History — time series charts, snapshot table, CSV export."""

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
    get_connection, initialize_database, get_all_companies,
    get_valuation_history,
)
from src.config import DB_PATH
from src.portfolio import get_portfolio_time_series
from src.utils import format_large_number
from components.charts import nav_time_series_chart, company_valuation_chart
from components.tables import valuation_snapshot_table

if "db_conn" not in st.session_state:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(DB_PATH)
    initialize_database(conn)
    st.session_state.db_conn = conn

conn = st.session_state.db_conn

st.title("Valuation History")

companies = get_all_companies(conn)

# --- NAV Time Series ---
st.subheader("HoldCo NAV History")
time_series = get_portfolio_time_series(conn, periods=50)
if time_series:
    st.plotly_chart(nav_time_series_chart(time_series), use_container_width=True)
else:
    st.info("No NAV history yet. Run valuations from Portfolio Overview.")

st.divider()

# --- Per-Company History ---
st.subheader("Company Valuation History")

if not companies:
    st.warning("No portfolio companies loaded.")
    st.stop()

company_names = ["All Companies"] + [c["name"] for c in companies]
selected = st.selectbox("Filter by Company", company_names)

if selected == "All Companies":
    # Show all companies' latest snapshots
    for company in companies:
        history = get_valuation_history(conn, company["id"], limit=20)
        if history:
            with st.expander(f"{company['name']} ({len(history)} snapshots)", expanded=False):
                chart_data = list(reversed(history))
                st.plotly_chart(
                    company_valuation_chart(chart_data, company["name"]),
                    use_container_width=True,
                )
                valuation_snapshot_table(history)
else:
    company = next(c for c in companies if c["name"] == selected)
    history = get_valuation_history(conn, company["id"], limit=100)

    if history:
        chart_data = list(reversed(history))
        st.plotly_chart(
            company_valuation_chart(chart_data, company["name"]),
            use_container_width=True,
        )
        valuation_snapshot_table(history)
    else:
        st.info(f"No valuation history for {selected}")

# Export
st.divider()
if st.button("📥 Export Valuation History"):
    from src.data_ingestion import export_valuations_to_csv
    import tempfile, os
    tmp = os.path.join(tempfile.gettempdir(), "valuation_history_export.csv")
    count = export_valuations_to_csv(conn, tmp)
    if count > 0:
        with open(tmp, "r") as f:
            st.download_button("Download CSV", f.read(), "valuation_history.csv", "text/csv")
    else:
        st.info("No valuation data to export")
