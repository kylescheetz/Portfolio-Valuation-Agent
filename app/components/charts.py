"""Reusable Plotly chart builders for the EV MTM Engine dashboard."""

import plotly.graph_objects as go
import plotly.express as px
from typing import List, Dict, Any

# EV Brand Colors
EV_FOREST = "#26352F"      # Deep Forest Green (primary)
EV_COPPER = "#B06D27"      # Burnished Copper/Gold (accent)
EV_SAGE = "#A2C699"        # Sage Green (secondary)
EV_CREAM = "#F2F1ED"       # Warm Cream (background)
EV_TAN = "#E6E3D4"         # Warm Tan (secondary bg)
EV_RED = "#8B3A3A"         # Muted red (downside, on-brand)

# Pie/bar color sequence
EV_PALETTE = [EV_COPPER, EV_FOREST, EV_SAGE, "#6B8F71", "#D4A96A", EV_TAN]

# Shared layout defaults
_LAYOUT_DEFAULTS = dict(
    template="plotly_white",
    font=dict(family="sans-serif", color=EV_FOREST),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=20, r=20, t=40, b=20),
)


def _apply_layout(fig: go.Figure, **overrides) -> go.Figure:
    layout = {**_LAYOUT_DEFAULTS, **overrides}
    fig.update_layout(**layout)
    fig.update_xaxes(gridcolor=EV_TAN, zerolinecolor=EV_TAN)
    fig.update_yaxes(gridcolor=EV_TAN, zerolinecolor=EV_TAN)
    return fig


def nav_time_series_chart(data: List[Dict[str, Any]]) -> go.Figure:
    """Line chart of NAV over time."""
    dates = [d["snapshot_date"] for d in data]
    navs = [d["nav"] for d in data]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=navs, mode="lines+markers",
        name="NAV", line=dict(color=EV_COPPER, width=2.5),
        marker=dict(size=7, color=EV_COPPER),
        hovertemplate="$%{y:,.0f}<extra>NAV</extra>",
    ))
    return _apply_layout(fig, title="HoldCo NAV Over Time",
                         xaxis_title="Date", yaxis_title="NAV ($)", height=350)


def company_valuation_chart(data: List[Dict[str, Any]], company_name: str) -> go.Figure:
    """Line chart of EV and equity value over time for one company."""
    dates = [d["snapshot_date"] for d in data]
    evs = [d["enterprise_value"] for d in data]
    equities = [d["holdco_equity_value"] for d in data]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=evs, mode="lines+markers", name="Enterprise Value",
        line=dict(color=EV_FOREST, width=2.5),
        marker=dict(size=7, color=EV_FOREST),
        hovertemplate="$%{y:,.0f}<extra>EV</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=dates, y=equities, mode="lines+markers", name="HoldCo Equity",
        line=dict(color=EV_COPPER, width=2.5),
        marker=dict(size=7, color=EV_COPPER),
        hovertemplate="$%{y:,.0f}<extra>Equity</extra>",
    ))
    return _apply_layout(fig, title=f"{company_name} — Valuation History",
                         xaxis_title="Date", yaxis_title="Value ($)", height=350)


def concentration_pie_chart(data: List[Dict[str, Any]]) -> go.Figure:
    """Donut chart showing portfolio company weight breakdown."""
    names = [d["company_name"] for d in data]
    values = [d["holdco_equity_value"] for d in data]

    fig = go.Figure(data=[go.Pie(
        labels=names, values=values, hole=0.45,
        textinfo="label+percent",
        marker=dict(colors=EV_PALETTE[:len(names)]),
        hovertemplate="%{label}: $%{value:,.0f}<br>%{percent}<extra></extra>",
    )])
    return _apply_layout(fig, title="Portfolio Concentration", height=350)


def sector_bar_chart(data: Dict[str, float]) -> go.Figure:
    """Horizontal bar chart of equity value by sector."""
    sectors = list(data.keys())
    values = list(data.values())
    colors = EV_PALETTE[:len(sectors)]

    fig = go.Figure(data=[go.Bar(
        x=values, y=sectors, orientation="h",
        marker_color=colors,
        hovertemplate="$%{x:,.0f}<extra></extra>",
    )])
    return _apply_layout(fig, title="Sector Allocation",
                         xaxis_title="HoldCo Equity ($)", height=300)


def comp_multiples_bar_chart(comps: List[Dict[str, Any]],
                             median_values: Dict[str, float]) -> go.Figure:
    """Grouped bar chart of EV/Revenue and EV/EBITDA for each comp."""
    tickers = [c["ticker"] for c in comps]
    ev_revs = [c.get("ev_revenue") or 0 for c in comps]
    ev_ebits = [c.get("ev_ebitda") or 0 for c in comps]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=tickers, y=ev_revs, name="EV/Revenue",
        marker_color=EV_COPPER,
        hovertemplate="%{y:.1f}x<extra>EV/Revenue</extra>",
    ))
    fig.add_trace(go.Bar(
        x=tickers, y=ev_ebits, name="EV/EBITDA",
        marker_color=EV_FOREST,
        hovertemplate="%{y:.1f}x<extra>EV/EBITDA</extra>",
    ))

    if median_values.get("median_ev_revenue"):
        fig.add_hline(y=median_values["median_ev_revenue"],
                      line_dash="dash", line_color=EV_COPPER,
                      annotation_text=f"Med EV/Rev: {median_values['median_ev_revenue']:.1f}x",
                      annotation_font_color=EV_COPPER)
    if median_values.get("median_ev_ebitda"):
        fig.add_hline(y=median_values["median_ev_ebitda"],
                      line_dash="dash", line_color=EV_FOREST,
                      annotation_text=f"Med EV/EBITDA: {median_values['median_ev_ebitda']:.1f}x",
                      annotation_font_color=EV_FOREST)

    return _apply_layout(fig, title="Comp Multiples",
                         xaxis_title="Ticker", yaxis_title="Multiple",
                         barmode="group", height=350)


def sensitivity_tornado_chart(company_name: str, base: float,
                              upside: float, downside: float) -> go.Figure:
    """Tornado chart showing sensitivity range for enterprise value."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=["Enterprise Value"],
        x=[upside - base],
        base=[base],
        orientation="h",
        name="Upside",
        marker_color=EV_SAGE,
        hovertemplate="Upside: $%{x:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        y=["Enterprise Value"],
        x=[base - downside],
        base=[downside],
        orientation="h",
        name="Downside",
        marker_color=EV_RED,
        hovertemplate="Downside: $%{x:,.0f}<extra></extra>",
    ))
    return _apply_layout(fig, title=f"{company_name} — Sensitivity Range",
                         xaxis_title="Enterprise Value ($)",
                         barmode="overlay", height=200)


def equity_bridge_waterfall(company_name: str, ev: float, net_debt: float,
                            prefs: float, ownership_adj: float,
                            dilution_adj: float,
                            holdco_equity: float) -> go.Figure:
    """Waterfall chart showing EV -> HoldCo Equity bridge."""
    fig = go.Figure(go.Waterfall(
        name="Equity Bridge",
        orientation="v",
        measure=["absolute", "relative", "relative", "relative", "relative", "total"],
        x=["Enterprise Value", "Net Debt", "Prefs", "Ownership Adj", "Dilution Adj", "HoldCo Equity"],
        y=[ev, -net_debt, -prefs, ownership_adj, dilution_adj, holdco_equity],
        connector={"line": {"color": EV_TAN}},
        increasing={"marker": {"color": EV_SAGE}},
        decreasing={"marker": {"color": EV_RED}},
        totals={"marker": {"color": EV_COPPER}},
        hovertemplate="%{x}: $%{y:,.0f}<extra></extra>",
    ))
    return _apply_layout(fig, title=f"{company_name} — Equity Bridge",
                         yaxis_title="Value ($)", height=350)
