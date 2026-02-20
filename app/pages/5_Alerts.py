"""Alerts — active alerts, acknowledge, threshold config."""

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
    get_connection, initialize_database, get_active_alerts,
    acknowledge_alert, set_config, get_config_float,
)
from src.config import (
    DB_PATH, ALERT_COMP_MULTIPLE_CHANGE_PCT,
    ALERT_PORTFOLIO_VALUE_DELTA_PCT, ALERT_UNDERPERFORMANCE_PCT,
)
from src.alerts import run_all_checks, get_alert_summary
from components.tables import alerts_table

if "db_conn" not in st.session_state:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(DB_PATH)
    initialize_database(conn)
    st.session_state.db_conn = conn

conn = st.session_state.db_conn

st.title("Alerts")

# Summary cards
summary = get_alert_summary(conn)

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Active Alerts", summary["total_active"])
with col2:
    st.metric("High Severity", summary["by_severity"].get("high", 0))
with col3:
    st.metric("Medium Severity", summary["by_severity"].get("medium", 0))

# Run checks button
if st.button("🔍 Run Alert Checks Now", type="primary"):
    with st.spinner("Checking..."):
        new_alerts = run_all_checks(conn)
    st.success(f"{len(new_alerts)} new alert(s) generated")
    st.rerun()

st.divider()

# Active alerts
st.subheader("Active Alerts")
active = get_active_alerts(conn)
acked_ids = alerts_table(active)
for aid in acked_ids:
    acknowledge_alert(conn, aid)
    st.rerun()

st.divider()

# Threshold configuration
st.subheader("Alert Thresholds")
with st.form("thresholds_form"):
    comp_thresh = st.number_input(
        "Comp Multiple Change Threshold (%)",
        value=get_config_float(conn, "alert_comp_change_pct", ALERT_COMP_MULTIPLE_CHANGE_PCT) * 100,
        min_value=1.0, max_value=100.0, step=1.0,
    )
    val_thresh = st.number_input(
        "Valuation Delta Threshold (%)",
        value=get_config_float(conn, "alert_value_delta_pct", ALERT_PORTFOLIO_VALUE_DELTA_PCT) * 100,
        min_value=1.0, max_value=100.0, step=1.0,
    )
    perf_thresh = st.number_input(
        "Underperformance Threshold (%)",
        value=get_config_float(conn, "alert_underperformance_pct", ALERT_UNDERPERFORMANCE_PCT) * 100,
        min_value=1.0, max_value=100.0, step=1.0,
    )

    if st.form_submit_button("Save Thresholds"):
        set_config(conn, "alert_comp_change_pct", str(comp_thresh / 100))
        set_config(conn, "alert_value_delta_pct", str(val_thresh / 100))
        set_config(conn, "alert_underperformance_pct", str(perf_thresh / 100))
        st.success("Thresholds saved!")
