#!/usr/bin/env python3
"""
Cloud Cost Audit Report Generator

Generates professional PDF cloud cost audit reports from AWS CUR
or Azure Cost Management export CSV files.

Usage:
    python main.py <csv_file> --client "Client Name" [--period "Q1 2026"] [--notes "..."]
    python main.py <csv_file> --client "Client Name" --no-ai
    python main.py --demo  # Generate a report using synthetic demo data

Examples:
    python main.py /path/to/aws_cur.csv --client "Acme Corp"
    python main.py /path/to/azure_export.csv --client "TechCo" --period "Jan-Mar 2026"
    python main.py --demo --client "Demo Corp"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add scripts dir to path for module imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from models import ReportData
from parsers import parse_file
from analyzers.cost_analyzer import analyze_costs
from analyzers.tag_analyzer import analyze_tags
from charts.chart_generator import generate_all_charts
from ai.insight_generator import generate_insights
from report.pdf_generator import render_report

console = Console()

# Load env from skill root
SKILL_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(SKILL_ROOT / ".env")


def load_config() -> dict:
    """Load report configuration."""
    config_path = SKILL_ROOT / "resources" / "config" / "report_config.json"
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)
    return {}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate professional PDF cloud cost audit reports.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("csv_file", nargs="?", help="Path to cloud billing CSV file")
    parser.add_argument("--client", default="Client", help="Client name for the report")
    parser.add_argument("--period", default=None, help="Reporting period label (auto-detected if not provided)")
    parser.add_argument("--notes", default="", help="Optional notes for the report")
    parser.add_argument("--output", default=None, help="Output directory (default: skills/finops/cloud-audit/output/)")
    parser.add_argument("--no-ai", action="store_true", help="Skip AI insight generation")
    parser.add_argument("--demo", action="store_true", help="Generate report using synthetic demo data")

    args = parser.parse_args()

    if not args.csv_file and not args.demo:
        parser.error("Either provide a CSV file path or use --demo")

    config = load_config()
    output_dir = Path(args.output) if args.output else SKILL_ROOT / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    console.print(Panel.fit(
        "[bold]Cloud Cost Audit Report Generator[/bold]\n"
        "Powered by Finabeo",
        border_style="blue",
    ))

    # Step 1: Parse data
    if args.demo:
        console.print("\n[yellow]Generating synthetic demo data...[/yellow]")
        df, provider = _generate_demo_data()
    else:
        csv_path = Path(args.csv_file)
        console.print(f"\n[bold]1.[/bold] Parsing {csv_path.name}...")
        df, provider = parse_file(csv_path)

    console.print(f"   Provider: [cyan]{provider.upper()}[/cyan]")
    console.print(f"   Rows loaded: [cyan]{len(df):,}[/cyan]")

    # Read thresholds from config
    thresholds = config.get("thresholds", {})

    # Step 2: Analyze costs
    console.print("[bold]2.[/bold] Analyzing costs...")
    cost_summary = analyze_costs(
        df,
        top_n_services=thresholds.get("top_services_count", 10),
        top_n_resources=thresholds.get("top_resources_count", 15),
        anomaly_threshold=thresholds.get("anomaly_std_multiplier", 2.0),
    )
    console.print(f"   Total spend: [green]{cost_summary.currency} {cost_summary.total_cost:,.2f}[/green]")

    # Step 3: Analyze tags
    console.print("[bold]3.[/bold] Analyzing tag coverage...")
    tag_summary = analyze_tags(
        df,
        top_untagged_count=thresholds.get("top_untagged_count", 20),
    )
    console.print(f"   Coverage: [cyan]{tag_summary.coverage_pct}%[/cyan] ({tag_summary.tagged_resources}/{tag_summary.total_resources})")

    # Step 4: Generate charts
    console.print("[bold]4.[/bold] Generating charts...")
    chart_dir = output_dir / "charts"
    chart_paths = generate_all_charts(cost_summary, tag_summary, chart_dir, config)
    console.print("   6 charts generated")

    # Step 5: Generate AI insights
    if args.no_ai:
        console.print("[bold]5.[/bold] Skipping AI insights (--no-ai flag)")
        from ai.insight_generator import _fallback_insights
        ai_insights = _fallback_insights(cost_summary, tag_summary)
    else:
        console.print("[bold]5.[/bold] Generating AI insights...")
        ai_insights = generate_insights(cost_summary, tag_summary, provider, args.client)
    console.print(f"   {len(ai_insights.recommendations)} recommendations generated")

    # Step 6: Build report data
    period = args.period
    if not period:
        period = f"{cost_summary.date_range_start} to {cost_summary.date_range_end}"

    report_data = ReportData(
        client_name=args.client,
        report_date=datetime.now().strftime("%d %B %Y"),
        reporting_period=period,
        cloud_provider=provider,
        cost_summary=cost_summary,
        tag_summary=tag_summary,
        chart_paths=chart_paths,
        ai_insights=ai_insights,
        notes=args.notes,
    )

    # Step 7: Render PDF
    console.print("[bold]6.[/bold] Rendering PDF report...")
    safe_client = args.client.replace(" ", "_").lower()
    pdf_filename = f"cloud_audit_{safe_client}_{datetime.now().strftime('%Y%m%d')}.pdf"
    pdf_path = output_dir / pdf_filename
    actual_path = render_report(report_data, pdf_path)

    if actual_path.suffix == ".html":
        console.print(f"\n[bold yellow]Note:[/bold yellow] PDF engines unavailable. Report saved as HTML.")
        console.print(f"   For PDF: [dim]pip install playwright && python -m playwright install chromium[/dim]")
    elif actual_path.suffix == ".pdf":
        console.print(f"   [green]PDF generated successfully[/green]")
    console.print(f"\n[bold green]Report generated successfully![/bold green]")
    console.print(f"   {actual_path}")


def _generate_demo_data():
    """Generate synthetic demo data for testing."""
    import pandas as pd
    import numpy as np
    from datetime import timedelta

    np.random.seed(42)
    n_days = 60
    start_date = datetime(2026, 1, 1)

    services = [
        ("Amazon EC2", "m5.xlarge", "us-east-1"),
        ("Amazon EC2", "c5.2xlarge", "eu-west-1"),
        ("Amazon RDS", "db.r5.large", "us-east-1"),
        ("Amazon S3", "Standard", "us-east-1"),
        ("Amazon S3", "Standard", "eu-west-1"),
        ("Amazon CloudFront", "Distribution", "global"),
        ("Amazon Lambda", "Function", "us-east-1"),
        ("Amazon DynamoDB", "Table", "us-east-1"),
        ("Amazon EKS", "Cluster", "us-west-2"),
        ("Amazon ElastiCache", "cache.r5.large", "us-east-1"),
        ("Amazon Redshift", "ra3.xlplus", "us-east-1"),
        ("Amazon SageMaker", "ml.m5.xlarge", "us-west-2"),
    ]

    rows = []
    for day_offset in range(n_days):
        date = start_date + timedelta(days=day_offset)
        for svc_name, res_type, region in services:
            base_cost = {
                "Amazon EC2": 45.0, "Amazon RDS": 30.0, "Amazon S3": 8.0,
                "Amazon CloudFront": 12.0, "Amazon Lambda": 5.0,
                "Amazon DynamoDB": 7.0, "Amazon EKS": 25.0,
                "Amazon ElastiCache": 18.0, "Amazon Redshift": 35.0,
                "Amazon SageMaker": 22.0,
            }.get(svc_name, 10.0)

            # Add some variance and a slight upward trend
            cost = base_cost * (1 + 0.002 * day_offset) + np.random.normal(0, base_cost * 0.15)
            cost = max(cost, 0.01)

            # Random spike for anomaly testing
            if day_offset == 35 and svc_name == "Amazon EC2":
                cost *= 4.5

            # Generate tags (some resources untagged)
            tags = "{}"
            if np.random.random() > 0.3:
                tag_options = [
                    {"Environment": "production", "Team": "platform", "CostCenter": "CC-100"},
                    {"Environment": "staging", "Team": "data", "CostCenter": "CC-200"},
                    {"Environment": "production", "Team": "ml"},
                    {"Environment": "dev"},
                ]
                tags = json.dumps(tag_options[np.random.randint(0, len(tag_options))])

            resource_id = f"arn:aws:{svc_name.split()[-1].lower()}:{region}:123456789:{res_type}-{hash(svc_name + res_type + region) % 10000:04d}"

            rows.append({
                "date": date,
                "service": svc_name,
                "resource_id": resource_id,
                "resource_type": res_type,
                "region": region,
                "cost": round(cost, 4),
                "usage_quantity": round(cost * 2.5, 4),
                "currency": "USD",
                "tags": tags,
                "account_id": "123456789012",
                "account_name": "Demo Production Account",
                "charge_type": "Usage",
                "provider": "aws",
            })

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df, "aws"


if __name__ == "__main__":
    main()
