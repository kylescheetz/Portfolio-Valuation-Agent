"""SQLite database management: schema creation, connection handling, CRUD operations."""

import sqlite3
import json
import threading
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager

from src.config import DB_PATH

# Thread-local storage for connections
_local = threading.local()


def get_connection(db_path: str = None) -> sqlite3.Connection:
    """Return a SQLite connection with row_factory set to sqlite3.Row."""
    path = db_path or DB_PATH
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


_initialized_paths: set = set()


def get_db(db_path: str = None) -> sqlite3.Connection:
    """Return a fresh, thread-safe SQLite connection.

    This is the preferred way to get a DB connection in Streamlit pages.
    Creates a new connection each call to avoid cross-thread and stale
    connection issues on Streamlit Cloud.
    Auto-initializes the schema on first use per path.
    """
    path = db_path or DB_PATH
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    # Auto-initialize schema once per path per process
    if path not in _initialized_paths:
        initialize_database(conn)
        _initialized_paths.add(path)

    return conn


def initialize_database(conn: sqlite3.Connection) -> None:
    """Create all tables if they do not exist. Idempotent."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS portfolio_companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            sector TEXT,
            subsector TEXT,
            revenue_ttm REAL DEFAULT 0,
            revenue_run_rate REAL DEFAULT 0,
            ebitda REAL DEFAULT 0,
            gross_margin REAL DEFAULT 0,
            growth_rate REAL DEFAULT 0,
            net_debt REAL DEFAULT 0,
            ownership_pct REAL DEFAULT 0,
            preferred_amount REAL DEFAULT 0,
            dilution_pct REAL DEFAULT 0,
            last_mark_date TEXT,
            last_mark_ev REAL,
            last_mark_equity REAL,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS comp_sets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portfolio_company_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            company_name TEXT,
            source TEXT DEFAULT 'manual',
            FOREIGN KEY (portfolio_company_id) REFERENCES portfolio_companies(id) ON DELETE CASCADE,
            UNIQUE(portfolio_company_id, ticker)
        );

        CREATE TABLE IF NOT EXISTS comp_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comp_set_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            date_pulled TEXT NOT NULL,
            enterprise_value REAL,
            revenue REAL,
            ebitda REAL,
            market_cap REAL,
            ev_revenue REAL,
            ev_ebitda REAL,
            growth_rate REAL,
            source TEXT DEFAULT 'yfinance',
            FOREIGN KEY (comp_set_id) REFERENCES comp_sets(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS valuation_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portfolio_company_id INTEGER NOT NULL,
            snapshot_date TEXT NOT NULL,
            method TEXT NOT NULL,
            enterprise_value REAL,
            equity_value REAL,
            holdco_equity_value REAL,
            median_ev_revenue REAL,
            median_ev_ebitda REAL,
            weights_json TEXT,
            notes TEXT,
            FOREIGN KEY (portfolio_company_id) REFERENCES portfolio_companies(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS holdco_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date TEXT NOT NULL,
            total_equity_value REAL,
            holdco_cash REAL,
            holdco_debt REAL,
            nav REAL,
            nav_per_share REAL,
            shares_outstanding REAL,
            change_vs_prior_pct REAL
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_type TEXT NOT NULL,
            portfolio_company_id INTEGER,
            message TEXT NOT NULL,
            severity TEXT DEFAULT 'medium',
            triggered_at TEXT DEFAULT (datetime('now')),
            acknowledged INTEGER DEFAULT 0,
            FOREIGN KEY (portfolio_company_id) REFERENCES portfolio_companies(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS app_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_comp_data_comp_set ON comp_data(comp_set_id, date_pulled);
        CREATE INDEX IF NOT EXISTS idx_valuation_snapshots_company ON valuation_snapshots(portfolio_company_id, snapshot_date);
        CREATE INDEX IF NOT EXISTS idx_holdco_snapshots_date ON holdco_snapshots(snapshot_date);
        CREATE INDEX IF NOT EXISTS idx_alerts_active ON alerts(acknowledged, triggered_at);
    """)
    conn.commit()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert a sqlite3.Row to a plain dict."""
    return dict(row)


# ---------------------------------------------------------------------------
# portfolio_companies CRUD
# ---------------------------------------------------------------------------

def insert_company(conn: sqlite3.Connection, data: Dict[str, Any]) -> int:
    """Insert a new portfolio company. Returns the new row id."""
    cur = conn.execute(
        """INSERT INTO portfolio_companies
           (name, sector, subsector, revenue_ttm, revenue_run_rate, ebitda,
            gross_margin, growth_rate, net_debt, ownership_pct,
            preferred_amount, dilution_pct, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data["name"], data.get("sector"), data.get("subsector"),
            data.get("revenue_ttm", 0), data.get("revenue_run_rate", 0),
            data.get("ebitda", 0), data.get("gross_margin", 0),
            data.get("growth_rate", 0), data.get("net_debt", 0),
            data.get("ownership_pct", 0), data.get("preferred_amount", 0),
            data.get("dilution_pct", 0), data.get("notes"),
        ),
    )
    conn.commit()
    return cur.lastrowid


def update_company(conn: sqlite3.Connection, company_id: int, data: Dict[str, Any]) -> None:
    """Update fields on an existing portfolio company."""
    allowed = {
        "name", "sector", "subsector", "revenue_ttm", "revenue_run_rate",
        "ebitda", "gross_margin", "growth_rate", "net_debt", "ownership_pct",
        "preferred_amount", "dilution_pct", "last_mark_date", "last_mark_ev",
        "last_mark_equity", "notes",
    }
    fields = {k: v for k, v in data.items() if k in allowed}
    if not fields:
        return
    fields["updated_at"] = datetime.now().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [company_id]
    conn.execute(f"UPDATE portfolio_companies SET {set_clause} WHERE id = ?", values)
    conn.commit()


def get_company(conn: sqlite3.Connection, company_id: int) -> Optional[Dict[str, Any]]:
    """Return a single company record as a dict, or None."""
    row = conn.execute("SELECT * FROM portfolio_companies WHERE id = ?", (company_id,)).fetchone()
    return _row_to_dict(row) if row else None


def get_all_companies(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Return all portfolio companies ordered by name."""
    rows = conn.execute("SELECT * FROM portfolio_companies ORDER BY name").fetchall()
    return [_row_to_dict(r) for r in rows]


def delete_company(conn: sqlite3.Connection, company_id: int) -> None:
    """Delete a company and cascade to related comp_sets, snapshots, alerts."""
    conn.execute("DELETE FROM portfolio_companies WHERE id = ?", (company_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# comp_sets CRUD
# ---------------------------------------------------------------------------

def insert_comp(conn: sqlite3.Connection, portfolio_company_id: int,
                ticker: str, company_name: str, source: str = "manual") -> int:
    """Add a comp ticker to a portfolio company's comp set."""
    cur = conn.execute(
        """INSERT INTO comp_sets (portfolio_company_id, ticker, company_name, source)
           VALUES (?, ?, ?, ?)""",
        (portfolio_company_id, ticker.upper(), company_name, source),
    )
    conn.commit()
    return cur.lastrowid


def get_comps_for_company(conn: sqlite3.Connection, portfolio_company_id: int) -> List[Dict[str, Any]]:
    """Return all comp set entries for a given portfolio company."""
    rows = conn.execute(
        "SELECT * FROM comp_sets WHERE portfolio_company_id = ? ORDER BY ticker",
        (portfolio_company_id,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def delete_comp(conn: sqlite3.Connection, comp_set_id: int) -> None:
    """Remove a comp from a company's comp set."""
    conn.execute("DELETE FROM comp_sets WHERE id = ?", (comp_set_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# comp_data CRUD
# ---------------------------------------------------------------------------

def insert_comp_data(conn: sqlite3.Connection, data: Dict[str, Any]) -> int:
    """Insert a row of comp financial data."""
    cur = conn.execute(
        """INSERT INTO comp_data
           (comp_set_id, ticker, date_pulled, enterprise_value, revenue,
            ebitda, market_cap, ev_revenue, ev_ebitda, growth_rate, source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data["comp_set_id"], data["ticker"], data["date_pulled"],
            data.get("enterprise_value"), data.get("revenue"),
            data.get("ebitda"), data.get("market_cap"),
            data.get("ev_revenue"), data.get("ev_ebitda"),
            data.get("growth_rate"), data.get("source", "yfinance"),
        ),
    )
    conn.commit()
    return cur.lastrowid


def get_latest_comp_data(conn: sqlite3.Connection, portfolio_company_id: int) -> List[Dict[str, Any]]:
    """Return the most recent comp_data row for each ticker in a company's comp set."""
    rows = conn.execute(
        """SELECT cd.* FROM comp_data cd
           INNER JOIN comp_sets cs ON cd.comp_set_id = cs.id
           WHERE cs.portfolio_company_id = ?
           AND cd.id = (
               SELECT cd2.id FROM comp_data cd2
               WHERE cd2.comp_set_id = cd.comp_set_id
               ORDER BY cd2.date_pulled DESC, cd2.id DESC
               LIMIT 1
           )
           ORDER BY cd.ticker""",
        (portfolio_company_id,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_comp_data_history(conn: sqlite3.Connection, comp_set_id: int,
                          start_date: str = None, end_date: str = None) -> List[Dict[str, Any]]:
    """Return historical comp data for a single comp, optionally filtered by date range."""
    query = "SELECT * FROM comp_data WHERE comp_set_id = ?"
    params: list = [comp_set_id]
    if start_date:
        query += " AND date_pulled >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date_pulled <= ?"
        params.append(end_date)
    query += " ORDER BY date_pulled DESC"
    rows = conn.execute(query, params).fetchall()
    return [_row_to_dict(r) for r in rows]


# ---------------------------------------------------------------------------
# valuation_snapshots CRUD
# ---------------------------------------------------------------------------

def insert_valuation_snapshot(conn: sqlite3.Connection, data: Dict[str, Any]) -> int:
    """Record a valuation snapshot."""
    weights_json = data.get("weights_json")
    if isinstance(weights_json, dict):
        weights_json = json.dumps(weights_json)
    cur = conn.execute(
        """INSERT INTO valuation_snapshots
           (portfolio_company_id, snapshot_date, method, enterprise_value,
            equity_value, holdco_equity_value, median_ev_revenue,
            median_ev_ebitda, weights_json, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data["portfolio_company_id"], data["snapshot_date"],
            data.get("method", "blended"), data.get("enterprise_value"),
            data.get("equity_value"), data.get("holdco_equity_value"),
            data.get("median_ev_revenue"), data.get("median_ev_ebitda"),
            weights_json, data.get("notes"),
        ),
    )
    conn.commit()
    return cur.lastrowid


def get_valuation_history(conn: sqlite3.Connection, portfolio_company_id: int,
                          limit: int = 50) -> List[Dict[str, Any]]:
    """Return valuation snapshots for a company, newest first."""
    rows = conn.execute(
        """SELECT * FROM valuation_snapshots
           WHERE portfolio_company_id = ?
           ORDER BY snapshot_date DESC, id DESC
           LIMIT ?""",
        (portfolio_company_id, limit),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_latest_valuation(conn: sqlite3.Connection, portfolio_company_id: int) -> Optional[Dict[str, Any]]:
    """Return the single most recent blended valuation snapshot for a company."""
    row = conn.execute(
        """SELECT * FROM valuation_snapshots
           WHERE portfolio_company_id = ? AND method = 'blended'
           ORDER BY snapshot_date DESC, id DESC
           LIMIT 1""",
        (portfolio_company_id,),
    ).fetchone()
    return _row_to_dict(row) if row else None


# ---------------------------------------------------------------------------
# holdco_snapshots CRUD
# ---------------------------------------------------------------------------

def insert_holdco_snapshot(conn: sqlite3.Connection, data: Dict[str, Any]) -> int:
    """Record a HoldCo NAV snapshot."""
    cur = conn.execute(
        """INSERT INTO holdco_snapshots
           (snapshot_date, total_equity_value, holdco_cash, holdco_debt,
            nav, nav_per_share, shares_outstanding, change_vs_prior_pct)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data["snapshot_date"], data.get("total_equity_value"),
            data.get("holdco_cash"), data.get("holdco_debt"),
            data.get("nav"), data.get("nav_per_share"),
            data.get("shares_outstanding"), data.get("change_vs_prior_pct"),
        ),
    )
    conn.commit()
    return cur.lastrowid


def get_holdco_history(conn: sqlite3.Connection, limit: int = 50) -> List[Dict[str, Any]]:
    """Return HoldCo NAV snapshots, newest first."""
    rows = conn.execute(
        "SELECT * FROM holdco_snapshots ORDER BY snapshot_date DESC, id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_latest_holdco_snapshot(conn: sqlite3.Connection) -> Optional[Dict[str, Any]]:
    """Return the most recent HoldCo NAV snapshot."""
    row = conn.execute(
        "SELECT * FROM holdco_snapshots ORDER BY snapshot_date DESC, id DESC LIMIT 1"
    ).fetchone()
    return _row_to_dict(row) if row else None


# ---------------------------------------------------------------------------
# alerts CRUD
# ---------------------------------------------------------------------------

def insert_alert(conn: sqlite3.Connection, data: Dict[str, Any]) -> int:
    """Create an alert record."""
    cur = conn.execute(
        """INSERT INTO alerts (alert_type, portfolio_company_id, message, severity)
           VALUES (?, ?, ?, ?)""",
        (
            data["alert_type"], data.get("portfolio_company_id"),
            data["message"], data.get("severity", "medium"),
        ),
    )
    conn.commit()
    return cur.lastrowid


def get_active_alerts(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Return all unacknowledged alerts, newest first."""
    rows = conn.execute(
        "SELECT * FROM alerts WHERE acknowledged = 0 ORDER BY triggered_at DESC"
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def acknowledge_alert(conn: sqlite3.Connection, alert_id: int) -> None:
    """Mark an alert as acknowledged."""
    conn.execute("UPDATE alerts SET acknowledged = 1 WHERE id = ?", (alert_id,))
    conn.commit()


def get_alerts_for_company(conn: sqlite3.Connection, portfolio_company_id: int) -> List[Dict[str, Any]]:
    """Return all alerts for a specific company."""
    rows = conn.execute(
        "SELECT * FROM alerts WHERE portfolio_company_id = ? ORDER BY triggered_at DESC",
        (portfolio_company_id,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


# ---------------------------------------------------------------------------
# app_config CRUD
# ---------------------------------------------------------------------------

def get_config(conn: sqlite3.Connection, key: str, default: str = None) -> Optional[str]:
    """Get a config value by key."""
    row = conn.execute("SELECT value FROM app_config WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_config(conn: sqlite3.Connection, key: str, value: str) -> None:
    """Set a config value (upsert)."""
    conn.execute(
        """INSERT INTO app_config (key, value, updated_at)
           VALUES (?, ?, datetime('now'))
           ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at""",
        (key, value),
    )
    conn.commit()


def get_config_float(conn: sqlite3.Connection, key: str, default: float = 0.0) -> float:
    """Get a config value as float."""
    val = get_config(conn, key)
    if val is None:
        return default
    try:
        return float(val)
    except ValueError:
        return default
