"""Cost breakdown, trends, and anomaly detection."""
from __future__ import annotations

import pandas as pd
import numpy as np

from models import CostSummary


def analyze_costs(df: pd.DataFrame, top_n_services: int = 10, top_n_resources: int = 15, anomaly_threshold: float = 2.0) -> CostSummary:
    """Compute all cost aggregations from the normalized DataFrame."""
    # Filter to usage charges only for main analysis
    usage_df = df[df["cost"] > 0].copy()

    total_cost = usage_df["cost"].sum()
    currency = usage_df["currency"].mode().iloc[0] if len(usage_df) > 0 else "USD"
    date_range_start = usage_df["date"].min().strftime("%Y-%m-%d") if len(usage_df) > 0 else "N/A"
    date_range_end = usage_df["date"].max().strftime("%Y-%m-%d") if len(usage_df) > 0 else "N/A"
    num_days = max((usage_df["date"].max() - usage_df["date"].min()).days + 1, 1) if len(usage_df) > 0 else 1
    daily_average = total_cost / num_days

    return CostSummary(
        total_cost=round(total_cost, 2),
        currency=currency,
        date_range_start=date_range_start,
        date_range_end=date_range_end,
        num_days=num_days,
        daily_average=round(daily_average, 2),
        top_services=_top_services(usage_df, top_n_services, total_cost),
        top_resources=_top_resources(usage_df, top_n_resources),
        cost_by_region=_cost_by_region(usage_df, total_cost),
        daily_costs=_daily_cost_trend(usage_df),
        month_over_month=_month_over_month(usage_df),
        anomalies=_detect_anomalies(usage_df, anomaly_threshold),
    )


def _top_services(df: pd.DataFrame, n: int, total_cost: float) -> list[dict]:
    """Top N services by cost."""
    grouped = df.groupby("service")["cost"].sum().nlargest(n).reset_index()
    result = []
    for _, row in grouped.iterrows():
        pct = (row["cost"] / total_cost * 100) if total_cost > 0 else 0
        result.append({
            "service": row["service"],
            "cost": round(row["cost"], 2),
            "pct": round(pct, 1),
        })
    return result


def _top_resources(df: pd.DataFrame, n: int) -> list[dict]:
    """Top N individual resources by cost."""
    grouped = (
        df.groupby(["resource_id", "resource_type", "service"])["cost"]
        .sum()
        .nlargest(n)
        .reset_index()
    )
    result = []
    for _, row in grouped.iterrows():
        result.append({
            "resource_id": row["resource_id"],
            "resource_type": row["resource_type"],
            "service": row["service"],
            "cost": round(row["cost"], 2),
        })
    return result


def _cost_by_region(df: pd.DataFrame, total_cost: float) -> list[dict]:
    """Cost aggregated by region."""
    grouped = df.groupby("region")["cost"].sum().sort_values(ascending=False).reset_index()
    result = []
    for _, row in grouped.iterrows():
        pct = (row["cost"] / total_cost * 100) if total_cost > 0 else 0
        result.append({
            "region": row["region"],
            "cost": round(row["cost"], 2),
            "pct": round(pct, 1),
        })
    return result


def _daily_cost_trend(df: pd.DataFrame) -> list[dict]:
    """Daily cost time series."""
    daily = df.groupby(df["date"].dt.date)["cost"].sum().sort_index()
    return [
        {"date": str(date), "cost": round(cost, 2)}
        for date, cost in daily.items()
    ]


def _month_over_month(df: pd.DataFrame) -> list[dict]:
    """Month-over-month cost comparison with change percentage."""
    df = df.copy()
    df["month"] = df["date"].dt.to_period("M")
    monthly = df.groupby("month")["cost"].sum().sort_index()

    result = []
    prev_cost = None
    for month, cost in monthly.items():
        change_pct = None
        if prev_cost is not None and prev_cost > 0:
            change_pct = round((cost - prev_cost) / prev_cost * 100, 1)
        result.append({
            "month": str(month),
            "cost": round(cost, 2),
            "change_pct": change_pct,
        })
        prev_cost = cost

    return result


def _detect_anomalies(df: pd.DataFrame, threshold_std: float) -> list[dict]:
    """Flag days where cost deviates significantly from the rolling average."""
    daily = df.groupby(df["date"].dt.date)["cost"].sum().sort_index()

    if len(daily) < 7:
        return []

    mean_cost = daily.mean()
    std_cost = daily.std()

    if std_cost == 0:
        return []

    anomalies = []
    for date, cost in daily.items():
        deviation = (cost - mean_cost) / std_cost
        if abs(deviation) >= threshold_std:
            anomalies.append({
                "date": str(date),
                "cost": round(cost, 2),
                "expected": round(mean_cost, 2),
                "deviation": round(deviation, 2),
            })

    return sorted(anomalies, key=lambda x: abs(x["deviation"]), reverse=True)
