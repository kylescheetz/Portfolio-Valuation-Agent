"""Settings — methodology weights, HoldCo params, CSV upload, data management."""

import sys
from pathlib import Path
_project_root = str(Path(__file__).parent.parent.parent)
_src_dir = str(Path(__file__).parent.parent.parent / "src")
_app_root = str(Path(__file__).parent.parent)
for _p in [_project_root, _src_dir, _app_root]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import streamlit as st
from database import (
    get_db, set_config, get_config_float, get_config,
)
from config import DEFAULT_WEIGHTS, GROWTH_ADJUSTMENT_FACTOR
from data_ingestion import import_companies_from_csv, import_comps_from_csv
from utils import format_large_number
import tempfile
import os

conn = get_db()

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
        from data_ingestion import export_companies_to_csv
        tmp = os.path.join(tempfile.gettempdir(), "companies_export.csv")
        count = export_companies_to_csv(conn, tmp)
        if count > 0:
            with open(tmp, "r") as f:
                st.download_button("Download", f.read(), "companies_export.csv", "text/csv")
        else:
            st.info("No companies to export")

with col2:
    if st.button("📥 Export Valuations CSV"):
        from data_ingestion import export_valuations_to_csv
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
from config import DB_PATH as _db_path
st.caption(f"Database path: `{_db_path}`")
from database import get_all_companies
conn2 = get_db()
companies = get_all_companies(conn2)
conn2.close()
st.caption(f"Portfolio companies: {len(companies)}")
