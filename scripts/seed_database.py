"""Seed the database with sample data and pull live comp data from yfinance."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import DB_PATH
from src.database import get_connection, initialize_database, set_config
from src.data_ingestion import import_companies_from_csv, import_comps_from_csv
from src.comps import refresh_all_comp_data
from src.valuation import run_all_valuations
from src.portfolio import calculate_holdco_nav
from src.alerts import run_all_checks
from src.utils import format_large_number

import pandas as pd


def main():
    samples_dir = project_root / "data" / "samples"

    # Ensure data directory exists
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

    print(f"Initializing database at {DB_PATH}...")
    conn = get_connection(DB_PATH)
    initialize_database(conn)

    # Import companies
    print("\nImporting portfolio companies...")
    result = import_companies_from_csv(conn, str(samples_dir / "sample_companies.csv"))
    print(f"  Imported: {result['imported_count']}, Skipped: {result['skipped_count']}")
    if result["errors"]:
        print(f"  Errors: {result['errors']}")

    # Import comps
    print("\nImporting comp sets...")
    result = import_comps_from_csv(conn, str(samples_dir / "sample_comps.csv"))
    print(f"  Imported: {result['imported_count']} comp entries")
    if result["errors"]:
        print(f"  Errors: {result['errors']}")

    # Set HoldCo config
    print("\nSetting HoldCo parameters...")
    holdco_df = pd.read_csv(str(samples_dir / "sample_holdco.csv"))
    holdco_cash = float(holdco_df.iloc[0]["holdco_cash"])
    holdco_debt = float(holdco_df.iloc[0]["holdco_debt"])
    shares = float(holdco_df.iloc[0]["shares_outstanding"])
    set_config(conn, "holdco_cash", str(holdco_cash))
    set_config(conn, "holdco_debt", str(holdco_debt))
    set_config(conn, "shares_outstanding", str(shares))
    print(f"  Cash: {format_large_number(holdco_cash)}, "
          f"Debt: {format_large_number(holdco_debt)}, "
          f"Shares: {shares/1e6:.0f}M")

    # Refresh comp data from yfinance
    print("\nRefreshing comp data from yfinance (this may take a minute)...")
    from src.database import get_all_companies
    companies = get_all_companies(conn)
    results = refresh_all_comp_data(conn)
    for company in companies:
        cid = company["id"]
        if cid in results:
            success, errs = results[cid]
            status = f"{success} comps refreshed"
            if errs:
                status += f", {len(errs)} errors"
            print(f"  {company['name']}: {status}")

    # Run initial valuations
    print("\nRunning initial valuations...")
    val_results = run_all_valuations(conn)
    for v in val_results:
        if "error" in v:
            print(f"  {v['company_name']}: ERROR - {v['error']}")
        else:
            print(f"  {v['company_name']}: EV={format_large_number(v['enterprise_value'])}, "
                  f"HoldCo Equity={format_large_number(v['holdco_equity_value'])}")

    # Calculate HoldCo NAV
    print("\nCalculating HoldCo NAV...")
    nav_result = calculate_holdco_nav(conn, holdco_cash, holdco_debt, shares)
    print(f"  Total Portfolio Equity: {format_large_number(nav_result['total_equity_value'])}")
    print(f"  HoldCo NAV: {format_large_number(nav_result['nav'])}")
    print(f"  NAV/Share: ${nav_result['nav_per_share']:.2f}")

    # Run alert checks
    print("\nRunning alert checks...")
    alerts = run_all_checks(conn)
    print(f"  {len(alerts)} alert(s) generated")

    conn.close()
    print("\nSeeding complete!")


if __name__ == "__main__":
    main()
