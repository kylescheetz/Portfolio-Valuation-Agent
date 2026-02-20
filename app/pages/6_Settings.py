"""Settings — methodology weights, HoldCo params, CSV upload, data management."""

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
    get_connection, initialize_database, set_config, get_config_float, get_config,
)
from src.config import DB_PATH, DEFAULT_WEIGHTS, GROWTH_ADJUSTMENT_FACTOR
from src.data_ingestion import import_companies_from_csv, import_comps_from_csv
from src.utils import format_large_number
import tempfile
import os

if "db_conn" not in st.session_state:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(DB_PATH)
    initialize_database(conn)
    st.session_state.db_conn = conn

conn = st.session_state.db_conn

st.title("Settings")

# --- Methodology Weights ---
st.subheader("Valuation Methodology Weights")
with st.form("weights_form"):
    w_rev = st.slider(
        "EV/Revenue Weight",
        0.0, 1.0,
        value=get_config_float(conn, "weight_ev_revenue", DEFAULT_WEIGHTS["ev_revenue"]),
        step=0.05,
    )
    w_ebit = st.slider(
        "EV/EBITDA Weight",
        0.0, 1.0,
        value=get_config_float(conn, "weight_ev_ebitda", DEFAULT_WEIGHTS["ev_ebitda"]),
        step=0.05,
    )
    w_growth = st.slider(
        "Growth-Adjusted Weight",
        0.0, 1.0,
        value=get_config_float(conn, "weight_growth_adjusted", DEFAULT_WEIGHTS["growth_adjusted"]),
        step=0.05,
    )

    total = w_rev + w_ebit + w_growth
    if abs(total - 1.0) > 0.01:
        st.warning(f"Weights sum to {total:.2f} — should be 1.0")
    else:
        st.success(f"Weights sum to {total:.2f}")

    adj_factor = st.number_input(
        "Growth Adjustment Factor",
        value=get_config_float(conn, "growth_adjustment_factor", GROWTH_ADJUSTMENT_FACTOR),
        min_value=0.0, max_value=2.0, step=0.1,
    )

    if st.form_submit_button("Save Weights"):
        set_config(conn, "weight_ev_revenue", str(w_rev))
        set_config(conn, "weight_ev_ebitda", str(w_ebit))
        set_config(conn, "weight_growth_adjusted", str(w_growth))
        set_config(conn, "growth_adjustment_factor", str(adj_factor))
        st.success("Weights saved!")

st.divider()

# --- HoldCo Parameters ---
st.subheader("HoldCo Parameters")
with st.form("holdco_form"):
    holdco_cash = st.number_input(
        "HoldCo Cash",
        value=get_config_float(conn, "holdco_cash", 0.0),
        format="%.0f",
    )
    holdco_debt = st.number_input(
        "HoldCo Debt",
        value=get_config_float(conn, "holdco_debt", 0.0),
        format="%.0f",
    )
    shares_outstanding = st.number_input(
        "Shares Outstanding",
        value=get_config_float(conn, "shares_outstanding", 1.0),
        format="%.0f", min_value=1.0,
    )

    if st.form_submit_button("Save HoldCo Parameters"):
        set_config(conn, "holdco_cash", str(holdco_cash))
        set_config(conn, "holdco_debt", str(holdco_debt))
        set_config(conn, "shares_outstanding", str(shares_outstanding))
        st.success("HoldCo parameters saved!")

st.divider()

# --- Data Import ---
st.subheader("Data Import")

tab1, tab2 = st.tabs(["Upload Companies CSV", "Upload Comps CSV"])

with tab1:
    uploaded_companies = st.file_uploader("Upload Companies CSV", type=["csv"], key="companies_csv")
    update_existing = st.checkbox("Update existing companies (match by name)")

    if uploaded_companies is not None:
        if st.button("Import Companies"):
            tmp = os.path.join(tempfile.gettempdir(), "upload_companies.csv")
            with open(tmp, "wb") as f:
                f.write(uploaded_companies.getvalue())
            result = import_companies_from_csv(conn, tmp, update_existing=update_existing)
            st.success(
                f"Imported: {result['imported_count']}, "
                f"Updated: {result['updated_count']}, "
                f"Skipped: {result['skipped_count']}"
            )
            if result["errors"]:
                for err in result["errors"]:
                    st.warning(err)

with tab2:
    uploaded_comps = st.file_uploader("Upload Comps CSV", type=["csv"], key="comps_csv")
    st.caption("CSV must have columns: portfolio_company_name, ticker, company_name")

    if uploaded_comps is not None:
        if st.button("Import Comps"):
            tmp = os.path.join(tempfile.gettempdir(), "upload_comps.csv")
            with open(tmp, "wb") as f:
                f.write(uploaded_comps.getvalue())
            result = import_comps_from_csv(conn, tmp)
            st.success(f"Imported: {result['imported_count']} comp entries")
            if result["errors"]:
                for err in result["errors"]:
                    st.warning(err)

st.divider()

# --- Data Export ---
st.subheader("Data Export")
col1, col2 = st.columns(2)
with col1:
    if st.button("📥 Export Companies CSV"):
        from src.data_ingestion import export_companies_to_csv
        tmp = os.path.join(tempfile.gettempdir(), "companies_export.csv")
        count = export_companies_to_csv(conn, tmp)
        if count > 0:
            with open(tmp, "r") as f:
                st.download_button("Download", f.read(), "companies_export.csv", "text/csv")
        else:
            st.info("No companies to export")

with col2:
    if st.button("📥 Export Valuations CSV"):
        from src.data_ingestion import export_valuations_to_csv
        tmp = os.path.join(tempfile.gettempdir(), "valuations_export.csv")
        count = export_valuations_to_csv(conn, tmp)
        if count > 0:
            with open(tmp, "r") as f:
                st.download_button("Download", f.read(), "valuations_export.csv", "text/csv")
        else:
            st.info("No valuations to export")

st.divider()

# --- Database Info ---
st.subheader("Database Info")
st.caption(f"Database path: `{DB_PATH}`")
from src.database import get_all_companies
companies = get_all_companies(conn)
st.caption(f"Portfolio companies: {len(companies)}")
