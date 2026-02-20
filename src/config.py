"""Centralized configuration constants for the EV MTM Engine."""

import os
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = os.environ.get("EVP_DB_PATH", str(PROJECT_ROOT / "data" / "ev_mtm.db"))

# Default valuation weights (must sum to 1.0)
DEFAULT_WEIGHTS = {
    "ev_revenue": 0.40,
    "ev_ebitda": 0.40,
    "growth_adjusted": 0.20,
}

# Alert thresholds
ALERT_COMP_MULTIPLE_CHANGE_PCT = 0.15  # 15% move in comp multiples
ALERT_PORTFOLIO_VALUE_DELTA_PCT = 0.10  # 10% delta vs last mark
ALERT_UNDERPERFORMANCE_PCT = 0.10  # 10% miss vs model

# Growth-adjusted valuation
GROWTH_ADJUSTMENT_FACTOR = 0.5  # how much to scale the growth premium

# Sensitivity
SENSITIVITY_STD_DEVS = 1.0  # +/- 1 std dev for sensitivity analysis

# yfinance rate limiting
YFINANCE_SLEEP_SECONDS = 0.5
