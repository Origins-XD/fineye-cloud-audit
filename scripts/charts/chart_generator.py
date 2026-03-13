"""Generate professional Plotly charts for the audit report."""
from __future__ import annotations

import json
from pathlib import Path

import plotly.graph_objects as go

from models import CostSummary, TagSummary, ChartPaths


# FinEye brand color palette
DEFAULT_COLORS = [
    "#4F1AD6", "#6B39E0", "#6733FF", "#9B6DFF",
    "#C4A8FF", "#27AE60", "#E67E22", "#E74C3C",
    "#3498DB", "#8E44AD",
]

CHART_WIDTH = 800
CHART_HEIGHT = 450


def generate_all_charts(
    cost_summary: CostSummary,
    tag_summary: TagSummary,
    output_dir: Path,
    config: dict | None = None,
) -> ChartPaths:
    """Generate all chart PNGs and return their paths."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    colors = DEFAULT_COLORS
    width = CHART_WIDTH
    height = CHART_HEIGHT

    if config:
        cs = config.get("chart_settings", {})
        colors = cs.get("color_palette", DEFAULT_COLORS)
        width = cs.get("width", CHART_WIDTH)
        height = cs.get("height", CHART_HEIGHT)

    pie_path = output_dir / "cost_by_service_pie.png"
    _cost_by_service_pie(cost_summary.top_services, pie_path, colors, width, height)

    trend_path = output_dir / "cost_trend_line.png"
    _cost_trend_line(cost_summary.daily_costs, trend_path, colors, width, height)

    resources_path = output_dir / "top_resources_bar.png"
    _top_resources_bar(cost_summary.top_resources, resources_path, colors, width, height)

    tag_path = output_dir / "tag_coverage_donut.png"
    _tag_coverage_donut(tag_summary.tagged_resources, tag_summary.untagged_resources, tag_path, colors, width, height)

    region_path = output_dir / "cost_by_region_bar.png"
    _cost_by_region_bar(cost_summary.cost_by_region, region_path, colors, width, height)

    mom_path = None
    if len(cost_summary.month_over_month) > 1:
        mom_path = output_dir / "month_over_month_bar.png"
        _month_over_month_bar(cost_summary.month_over_month, mom_path, colors, width, height)

    return ChartPaths(
        cost_by_service_pie=str(pie_path.resolve()),
        cost_trend_line=str(trend_path.resolve()),
        top_resources_bar=str(resources_path.resolve()),
        tag_coverage_donut=str(tag_path.resolve()),
        cost_by_region_bar=str(region_path.resolve()),
        month_over_month_bar=str(mom_path.resolve()) if mom_path else None,
    )


def _base_layout(title: str, width: int, height: int) -> dict:
    """Common layout settings for all charts — FinEye brand."""
    return dict(
        title=dict(
            text=title.upper(),
            font=dict(size=14, color="#333333", family="Montserrat, Arial"),
            x=0.0,
            xanchor="left",
        ),
        font=dict(family="Inter, Arial", size=12, color="#555555"),
        plot_bgcolor="white",
        paper_bgcolor="white",
        width=width,
        height=height,
        margin=dict(l=60, r=40, t=60, b=60),
    )


def _cost_by_service_pie(data: list[dict], output_path: Path, colors: list[str], width: int, height: int) -> None:
    """Pie chart of cost breakdown by service."""
    # Show top 8, group the rest as "Other"
    if len(data) > 8:
        top = data[:8]
        other_cost = sum(d["cost"] for d in data[8:])
        other_pct = sum(d["pct"] for d in data[8:])
        top.append({"service": "Other", "cost": round(other_cost, 2), "pct": round(other_pct, 1)})
        data = top

    services = [d["service"] for d in data]
    costs = [d["cost"] for d in data]

    fig = go.Figure(data=[go.Pie(
        labels=services,
        values=costs,
        hole=0.3,
        marker_colors=colors[:len(services)],
        textinfo="label+percent",
        textfont_size=11,
        hoverinfo="label+value+percent",
    )])

    layout = _base_layout("Cost Breakdown by Service", width, height)
    layout["showlegend"] = False
    fig.update_layout(**layout)
    fig.write_image(str(output_path), scale=2)


def _cost_trend_line(data: list[dict], output_path: Path, colors: list[str], width: int, height: int) -> None:
    """Line chart of daily cost trend."""
    dates = [d["date"] for d in data]
    costs = [d["cost"] for d in data]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates,
        y=costs,
        mode="lines+markers",
        line=dict(color=colors[0], width=2),
        marker=dict(size=4, color=colors[0]),
        fill="tozeroy",
        fillcolor="rgba(79, 26, 214, 0.08)",
        hovertemplate="<b>%{x}</b><br>Cost: $%{y:,.2f}<extra></extra>",
    ))

    layout = _base_layout("Daily Cost Trend", width, height)
    layout["xaxis"] = dict(title="Date", showgrid=False)
    layout["yaxis"] = dict(title="Cost ($)", showgrid=True, gridcolor="#eee")
    fig.update_layout(**layout)
    fig.write_image(str(output_path), scale=2)


def _top_resources_bar(data: list[dict], output_path: Path, colors: list[str], width: int, height: int) -> None:
    """Horizontal bar chart of top resources by cost."""
    top_10 = data[:10]
    # Truncate long resource IDs for display
    labels = [_truncate(d.get("resource_id", ""), 40) for d in top_10]
    costs = [d["cost"] for d in top_10]

    fig = go.Figure(data=[go.Bar(
        x=costs,
        y=labels,
        orientation="h",
        marker_color=colors[0],
        hovertemplate="<b>%{y}</b><br>Cost: $%{x:,.2f}<extra></extra>",
    )])

    layout = _base_layout("Top Resources by Cost", width, height + 50)
    layout["xaxis"] = dict(title="Cost ($)", showgrid=True, gridcolor="#eee")
    layout["yaxis"] = dict(autorange="reversed")
    layout["margin"] = dict(l=280, r=40, t=60, b=60)
    fig.update_layout(**layout)
    fig.write_image(str(output_path), scale=2)


def _tag_coverage_donut(tagged: int, untagged: int, output_path: Path, colors: list[str], width: int, height: int) -> None:
    """Donut chart showing tag coverage."""
    fig = go.Figure(data=[go.Pie(
        labels=["Tagged", "Untagged"],
        values=[tagged, untagged],
        hole=0.5,
        marker_colors=["#27AE60", "#E74C3C"],
        textinfo="label+percent",
        textfont_size=14,
    )])

    layout = _base_layout("Resource Tag Coverage", width, height)
    layout["showlegend"] = False
    # Add annotation in the center
    layout["annotations"] = [dict(
        text=f"<b>{round(tagged / max(tagged + untagged, 1) * 100)}%</b><br>Tagged",
        x=0.5, y=0.5, font_size=16, showarrow=False, font_color="#333",
    )]
    fig.update_layout(**layout)
    fig.write_image(str(output_path), scale=2)


def _cost_by_region_bar(data: list[dict], output_path: Path, colors: list[str], width: int, height: int) -> None:
    """Bar chart of cost by region."""
    top_10 = data[:10]
    regions = [d["region"] for d in top_10]
    costs = [d["cost"] for d in top_10]

    fig = go.Figure(data=[go.Bar(
        x=regions,
        y=costs,
        marker_color=colors[:len(regions)],
        hovertemplate="<b>%{x}</b><br>Cost: $%{y:,.2f}<extra></extra>",
    )])

    layout = _base_layout("Cost by Region", width, height)
    layout["xaxis"] = dict(title="Region", showgrid=False, tickangle=-45)
    layout["yaxis"] = dict(title="Cost ($)", showgrid=True, gridcolor="#eee")
    fig.update_layout(**layout)
    fig.write_image(str(output_path), scale=2)


def _month_over_month_bar(data: list[dict], output_path: Path, colors: list[str], width: int, height: int) -> None:
    """Bar chart showing month-over-month cost comparison."""
    months = [d["month"] for d in data]
    costs = [d["cost"] for d in data]

    # Color bars: green if cost decreased, red if increased
    bar_colors = []
    for d in data:
        if d["change_pct"] is None:
            bar_colors.append(colors[0])
        elif d["change_pct"] < 0:
            bar_colors.append("#27AE60")
        else:
            bar_colors.append("#E74C3C")

    fig = go.Figure(data=[go.Bar(
        x=months,
        y=costs,
        marker_color=bar_colors,
        hovertemplate="<b>%{x}</b><br>Cost: $%{y:,.2f}<extra></extra>",
    )])

    layout = _base_layout("Month-over-Month Spend", width, height)
    layout["xaxis"] = dict(title="Month", showgrid=False)
    layout["yaxis"] = dict(title="Cost ($)", showgrid=True, gridcolor="#eee")
    fig.update_layout(**layout)
    fig.write_image(str(output_path), scale=2)


def _truncate(text: str, max_len: int) -> str:
    """Truncate text with ellipsis if too long."""
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."
