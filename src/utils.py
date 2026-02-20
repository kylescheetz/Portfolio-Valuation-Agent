"""Utility functions: formatting, date helpers, common transformations."""

from datetime import datetime, date
from typing import Any, Optional


def format_currency(value: float, decimals: int = 0) -> str:
    """Format a number as currency: $1,234,567."""
    if value < 0:
        return f"-${abs(value):,.{decimals}f}"
    return f"${value:,.{decimals}f}"


def format_multiple(value: float) -> str:
    """Format a valuation multiple: 12.3x."""
    return f"{value:.1f}x"


def format_percentage(value: float, decimals: int = 1) -> str:
    """Format as percentage: 15.3%. Input is a decimal (0.153 -> 15.3%)."""
    return f"{value * 100:.{decimals}f}%"


def format_large_number(value: float) -> str:
    """Format with M/B suffix: $1.2B, $345.6M."""
    abs_val = abs(value)
    sign = "-" if value < 0 else ""
    if abs_val >= 1_000_000_000:
        return f"{sign}${abs_val / 1_000_000_000:.1f}B"
    if abs_val >= 1_000_000:
        return f"{sign}${abs_val / 1_000_000:.1f}M"
    if abs_val >= 1_000:
        return f"{sign}${abs_val / 1_000:.1f}K"
    return f"{sign}${abs_val:,.0f}"


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Division with zero-denominator protection."""
    if denominator == 0:
        return default
    return numerator / denominator


def today_str() -> str:
    """Return today's date as YYYY-MM-DD string."""
    return date.today().isoformat()


def parse_date(date_input: Any) -> Optional[date]:
    """Flexibly parse a date from string, datetime, or date object."""
    if date_input is None:
        return None
    if isinstance(date_input, date):
        return date_input
    if isinstance(date_input, datetime):
        return date_input.date()
    if isinstance(date_input, str):
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"):
            try:
                return datetime.strptime(date_input, fmt).date()
            except ValueError:
                continue
    return None


def pct_change(old_value: float, new_value: float) -> Optional[float]:
    """Calculate percentage change as a decimal. Returns None if old_value is 0."""
    if old_value == 0:
        return None
    return (new_value - old_value) / abs(old_value)
