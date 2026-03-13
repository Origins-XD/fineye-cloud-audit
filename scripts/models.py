"""Shared data models for the Cloud Cost Audit Report Generator."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# Every parser must produce a DataFrame with exactly these columns
NORMALIZED_COLUMNS = [
    "date",           # datetime64 — usage date
    "service",        # str — e.g. "Amazon EC2", "Virtual Machines"
    "resource_id",    # str — unique resource identifier
    "resource_type",  # str — e.g. "m5.xlarge", "Standard_D2s_v3"
    "region",         # str — e.g. "us-east-1", "eastus"
    "cost",           # float64 — UnblendedCost (AWS) or CostInBillingCurrency (Azure)
    "usage_quantity", # float64 — usage amount
    "currency",       # str — e.g. "USD", "GBP"
    "tags",           # str (JSON) — tag key-value pairs as JSON string
    "account_id",     # str — AWS account ID or Azure subscription ID
    "account_name",   # str — display name
    "charge_type",    # str — "Usage", "Tax", "Fee", "Refund", etc.
    "provider",       # str — "aws" or "azure"
]


@dataclass
class CostSummary:
    """Aggregated cost analysis results."""
    total_cost: float
    currency: str
    date_range_start: str
    date_range_end: str
    num_days: int
    daily_average: float
    top_services: list[dict[str, Any]]      # [{service, cost, pct}]
    top_resources: list[dict[str, Any]]      # [{resource_id, resource_type, service, cost}]
    cost_by_region: list[dict[str, Any]]     # [{region, cost, pct}]
    daily_costs: list[dict[str, Any]]        # [{date, cost}]
    month_over_month: list[dict[str, Any]]   # [{month, cost, change_pct}]
    anomalies: list[dict[str, Any]]          # [{date, cost, expected, deviation}]


@dataclass
class TagSummary:
    """Tag coverage analysis results."""
    total_resources: int
    tagged_resources: int
    untagged_resources: int
    coverage_pct: float
    cost_of_untagged: float
    cost_of_untagged_pct: float
    tag_key_distribution: list[dict[str, Any]]   # [{key, count, pct}]
    top_untagged_resources: list[dict[str, Any]]  # [{resource_id, service, cost}]


@dataclass
class ChartPaths:
    """Paths to generated chart PNG files."""
    cost_by_service_pie: str
    cost_trend_line: str
    top_resources_bar: str
    tag_coverage_donut: str
    cost_by_region_bar: str
    month_over_month_bar: str | None = None


@dataclass
class AIInsights:
    """AI-generated report text."""
    executive_summary: str
    key_findings: list[str]
    recommendations: list[dict[str, str]]  # [{title, description, estimated_impact}]
    methodology_note: str


@dataclass
class ReportData:
    """Everything needed to render the report template."""
    client_name: str
    report_date: str
    reporting_period: str
    cloud_provider: str
    cost_summary: CostSummary
    tag_summary: TagSummary
    chart_paths: ChartPaths
    ai_insights: AIInsights
    notes: str = ""
