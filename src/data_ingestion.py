"""CSV upload handling: parsing, validation, and bulk import of portfolio data."""

import sqlite3
from typing import Dict, Any, List, Tuple
from pathlib import Path

import pandas as pd

from src.database import (
    insert_company, update_company, get_all_companies,
    insert_comp, get_comps_for_company,
)


REQUIRED_COMPANY_COLUMNS = {"name"}
OPTIONAL_COMPANY_COLUMNS = {
    "sector", "subsector", "revenue_ttm", "revenue_run_rate", "ebitda",
    "gross_margin", "growth_rate", "net_debt", "ownership_pct",
    "preferred_amount", "dilution_pct", "notes",
}
NUMERIC_COMPANY_COLUMNS = {
    "revenue_ttm", "revenue_run_rate", "ebitda", "gross_margin",
    "growth_rate", "net_debt", "ownership_pct", "preferred_amount", "dilution_pct",
}


def validate_company_csv(file_path: str) -> Tuple[bool, List[str], pd.DataFrame]:
    """Validate a CSV file for company import."""
    errors: List[str] = []
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        return False, [f"Failed to read CSV: {e}"], pd.DataFrame()

    # Check required columns
    missing = REQUIRED_COMPANY_COLUMNS - set(df.columns)
    if missing:
        errors.append(f"Missing required columns: {missing}")
        return False, errors, df

    # Check for empty names
    if df["name"].isna().any() or (df["name"].astype(str).str.strip() == "").any():
        errors.append("Some rows have empty 'name' values")

    # Check duplicates
    dupes = df["name"].duplicated()
    if dupes.any():
        errors.append(f"Duplicate company names: {df.loc[dupes, 'name'].tolist()}")

    # Coerce numeric columns
    for col in NUMERIC_COMPANY_COLUMNS & set(df.columns):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Validate ranges
    if "ownership_pct" in df.columns:
        invalid = df[(df["ownership_pct"] < 0) | (df["ownership_pct"] > 1)]
        if len(invalid) > 0:
            errors.append("ownership_pct must be between 0 and 1")

    if "dilution_pct" in df.columns:
        invalid = df[(df["dilution_pct"] < 0) | (df["dilution_pct"] > 1)]
        if len(invalid) > 0:
            errors.append("dilution_pct must be between 0 and 1")

    return len(errors) == 0, errors, df


def import_companies_from_csv(conn: sqlite3.Connection, file_path: str,
                              update_existing: bool = False) -> Dict[str, Any]:
    """Import portfolio companies from a CSV file."""
    is_valid, errors, df = validate_company_csv(file_path)
    if not is_valid:
        return {"imported_count": 0, "updated_count": 0, "skipped_count": 0, "errors": errors}

    existing = {c["name"]: c["id"] for c in get_all_companies(conn)}
    imported = 0
    updated = 0
    skipped = 0

    for _, row in df.iterrows():
        data = {k: (row[k] if k in row.index and pd.notna(row[k]) else None)
                for k in REQUIRED_COMPANY_COLUMNS | OPTIONAL_COMPANY_COLUMNS}
        data["name"] = str(data["name"]).strip()

        if data["name"] in existing:
            if update_existing:
                update_company(conn, existing[data["name"]], data)
                updated += 1
            else:
                skipped += 1
        else:
            try:
                insert_company(conn, data)
                imported += 1
            except Exception as e:
                errors.append(f"Failed to insert {data['name']}: {e}")

    return {
        "imported_count": imported,
        "updated_count": updated,
        "skipped_count": skipped,
        "errors": errors,
    }


def validate_comps_csv(file_path: str) -> Tuple[bool, List[str], pd.DataFrame]:
    """Validate a CSV file for comp set import."""
    errors: List[str] = []
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        return False, [f"Failed to read CSV: {e}"], pd.DataFrame()

    required = {"portfolio_company_name", "ticker", "company_name"}
    missing = required - set(df.columns)
    if missing:
        errors.append(f"Missing required columns: {missing}")
        return False, errors, df

    if df["ticker"].isna().any():
        errors.append("Some rows have empty ticker values")

    return len(errors) == 0, errors, df


def import_comps_from_csv(conn: sqlite3.Connection, file_path: str) -> Dict[str, Any]:
    """Import comp sets from a CSV file."""
    is_valid, errors, df = validate_comps_csv(file_path)
    if not is_valid:
        return {"imported_count": 0, "errors": errors}

    companies = {c["name"]: c["id"] for c in get_all_companies(conn)}
    imported = 0

    for _, row in df.iterrows():
        company_name = str(row["portfolio_company_name"]).strip()
        if company_name not in companies:
            errors.append(f"Company not found: {company_name}")
            continue

        company_id = companies[company_name]
        ticker = str(row["ticker"]).strip().upper()
        comp_name = str(row["company_name"]).strip()

        # Check if already exists
        existing = get_comps_for_company(conn, company_id)
        existing_tickers = {c["ticker"] for c in existing}
        if ticker in existing_tickers:
            continue

        try:
            insert_comp(conn, company_id, ticker, comp_name, "manual")
            imported += 1
        except Exception as e:
            errors.append(f"Failed to insert comp {ticker}: {e}")

    return {"imported_count": imported, "errors": errors}


def export_companies_to_csv(conn: sqlite3.Connection, file_path: str) -> int:
    """Export all portfolio companies to CSV."""
    companies = get_all_companies(conn)
    if not companies:
        return 0
    df = pd.DataFrame(companies)
    export_cols = ["name", "sector", "subsector"] + list(NUMERIC_COMPANY_COLUMNS) + ["notes"]
    export_cols = [c for c in export_cols if c in df.columns]
    df[export_cols].to_csv(file_path, index=False)
    return len(df)


def export_valuations_to_csv(conn: sqlite3.Connection, file_path: str,
                             company_id: int = None) -> int:
    """Export valuation history to CSV."""
    from src.database import get_valuation_history
    if company_id:
        snapshots = get_valuation_history(conn, company_id, limit=1000)
    else:
        # Get all companies' history
        snapshots = []
        for company in get_all_companies(conn):
            hist = get_valuation_history(conn, company["id"], limit=1000)
            for h in hist:
                h["company_name"] = company["name"]
            snapshots.extend(hist)

    if not snapshots:
        return 0

    df = pd.DataFrame(snapshots)
    df.to_csv(file_path, index=False)
    return len(df)
