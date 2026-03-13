#!/usr/bin/env python3
"""Generate a realistic AWS CUR 2.0 sample CSV for testing.

Creates ~5000 rows covering 90 days of multi-service AWS usage
with realistic cost patterns, tags, regions, and anomalies.

Usage:
    python generate_cur2_sample.py [--output /path/to/output.csv] [--rows 5000]
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

# CUR 2.0 column headers (underscore-separated, no slashes)
CUR2_COLUMNS = [
    "identity_line_item_id",
    "identity_time_interval",
    "bill_bill_type",
    "bill_billing_entity",
    "bill_billing_period_end_date",
    "bill_billing_period_start_date",
    "bill_invoice_id",
    "bill_invoicing_entity",
    "bill_payer_account_id",
    "bill_payer_account_name",
    "line_item_availability_zone",
    "line_item_blended_cost",
    "line_item_blended_rate",
    "line_item_currency_code",
    "line_item_line_item_description",
    "line_item_line_item_type",
    "line_item_net_unblended_cost",
    "line_item_net_unblended_rate",
    "line_item_operation",
    "line_item_product_code",
    "line_item_resource_id",
    "line_item_usage_account_id",
    "line_item_usage_account_name",
    "line_item_usage_amount",
    "line_item_usage_end_date",
    "line_item_usage_start_date",
    "line_item_usage_type",
    "pricing_public_on_demand_cost",
    "pricing_public_on_demand_rate",
    "pricing_term",
    "pricing_unit",
    "product_product_name",
    "product_region",
    "product_instance_type",
    "product_instance_type_family",
    "product_operating_system",
    "product_vcpu",
    "product_memory",
    "resource_tags",
]

# Realistic AWS service configurations
SERVICES = [
    {
        "product_code": "AmazonEC2",
        "product_name": "Amazon Elastic Compute Cloud",
        "instances": [
            {"type": "m5.xlarge", "family": "General purpose", "vcpu": "4", "memory": "16 GiB", "base_cost": 4.608, "os": "Linux"},
            {"type": "m5.2xlarge", "family": "General purpose", "vcpu": "8", "memory": "32 GiB", "base_cost": 9.216, "os": "Linux"},
            {"type": "c5.xlarge", "family": "Compute optimized", "vcpu": "4", "memory": "8 GiB", "base_cost": 4.08, "os": "Linux"},
            {"type": "c5.4xlarge", "family": "Compute optimized", "vcpu": "16", "memory": "32 GiB", "base_cost": 16.32, "os": "Linux"},
            {"type": "r5.large", "family": "Memory optimized", "vcpu": "2", "memory": "16 GiB", "base_cost": 3.024, "os": "Linux"},
            {"type": "t3.medium", "family": "General purpose", "vcpu": "2", "memory": "4 GiB", "base_cost": 1.0, "os": "Linux"},
            {"type": "t3.large", "family": "General purpose", "vcpu": "2", "memory": "8 GiB", "base_cost": 1.997, "os": "Windows"},
        ],
        "operation": "RunInstances",
        "usage_type_prefix": "BoxUsage",
        "pricing_unit": "Hrs",
    },
    {
        "product_code": "AmazonRDS",
        "product_name": "Amazon Relational Database Service",
        "instances": [
            {"type": "db.r5.large", "family": "Memory optimized", "vcpu": "2", "memory": "16 GiB", "base_cost": 5.76, "os": ""},
            {"type": "db.r5.xlarge", "family": "Memory optimized", "vcpu": "4", "memory": "32 GiB", "base_cost": 11.52, "os": ""},
            {"type": "db.m5.large", "family": "General purpose", "vcpu": "2", "memory": "8 GiB", "base_cost": 4.176, "os": ""},
        ],
        "operation": "CreateDBInstance",
        "usage_type_prefix": "InstanceUsage",
        "pricing_unit": "Hrs",
    },
    {
        "product_code": "AmazonS3",
        "product_name": "Amazon Simple Storage Service",
        "instances": [
            {"type": "Standard", "family": "", "vcpu": "", "memory": "", "base_cost": 0.50, "os": ""},
            {"type": "Glacier", "family": "", "vcpu": "", "memory": "", "base_cost": 0.10, "os": ""},
        ],
        "operation": "PutObject",
        "usage_type_prefix": "TimedStorage-ByteHrs",
        "pricing_unit": "GB-Mo",
    },
    {
        "product_code": "AmazonCloudFront",
        "product_name": "Amazon CloudFront",
        "instances": [
            {"type": "Distribution", "family": "", "vcpu": "", "memory": "", "base_cost": 2.50, "os": ""},
        ],
        "operation": "GET",
        "usage_type_prefix": "DataTransfer-Out-Bytes",
        "pricing_unit": "GB",
    },
    {
        "product_code": "AWSLambda",
        "product_name": "AWS Lambda",
        "instances": [
            {"type": "Function", "family": "", "vcpu": "", "memory": "512 MB", "base_cost": 0.80, "os": ""},
            {"type": "Function", "family": "", "vcpu": "", "memory": "1024 MB", "base_cost": 1.50, "os": ""},
        ],
        "operation": "Invoke",
        "usage_type_prefix": "Lambda-GB-Second",
        "pricing_unit": "Lambda-GB-Second",
    },
    {
        "product_code": "AmazonDynamoDB",
        "product_name": "Amazon DynamoDB",
        "instances": [
            {"type": "PayPerRequest", "family": "", "vcpu": "", "memory": "", "base_cost": 1.20, "os": ""},
        ],
        "operation": "GetItem",
        "usage_type_prefix": "PayPerRequestThroughput",
        "pricing_unit": "ReadRequestUnits",
    },
    {
        "product_code": "AmazonEKS",
        "product_name": "Amazon Elastic Kubernetes Service",
        "instances": [
            {"type": "Cluster", "family": "", "vcpu": "", "memory": "", "base_cost": 7.20, "os": ""},
        ],
        "operation": "CreateCluster",
        "usage_type_prefix": "AmazonEKS-Hours:perCluster",
        "pricing_unit": "Hrs",
    },
    {
        "product_code": "AmazonElastiCache",
        "product_name": "Amazon ElastiCache",
        "instances": [
            {"type": "cache.r5.large", "family": "Memory optimized", "vcpu": "2", "memory": "13.07 GiB", "base_cost": 4.58, "os": ""},
            {"type": "cache.m5.large", "family": "General purpose", "vcpu": "2", "memory": "6.38 GiB", "base_cost": 3.84, "os": ""},
        ],
        "operation": "CreateCacheCluster",
        "usage_type_prefix": "NodeUsage",
        "pricing_unit": "Hrs",
    },
    {
        "product_code": "AmazonRedshift",
        "product_name": "Amazon Redshift",
        "instances": [
            {"type": "ra3.xlplus", "family": "RA3", "vcpu": "4", "memory": "32 GiB", "base_cost": 26.208, "os": ""},
        ],
        "operation": "CreateCluster",
        "usage_type_prefix": "Node",
        "pricing_unit": "Hrs",
    },
    {
        "product_code": "AmazonSageMaker",
        "product_name": "Amazon SageMaker",
        "instances": [
            {"type": "ml.m5.xlarge", "family": "General purpose", "vcpu": "4", "memory": "16 GiB", "base_cost": 5.52, "os": ""},
            {"type": "ml.g4dn.xlarge", "family": "Accelerated computing", "vcpu": "4", "memory": "16 GiB", "base_cost": 15.89, "os": ""},
        ],
        "operation": "CreateNotebookInstance",
        "usage_type_prefix": "Notebook",
        "pricing_unit": "Hrs",
    },
    {
        "product_code": "AmazonKinesisFirehose",
        "product_name": "Amazon Kinesis Data Firehose",
        "instances": [
            {"type": "DeliveryStream", "family": "", "vcpu": "", "memory": "", "base_cost": 1.80, "os": ""},
        ],
        "operation": "PutRecord",
        "usage_type_prefix": "DataIngested",
        "pricing_unit": "GB",
    },
    {
        "product_code": "AmazonSNS",
        "product_name": "Amazon Simple Notification Service",
        "instances": [
            {"type": "Topic", "family": "", "vcpu": "", "memory": "", "base_cost": 0.15, "os": ""},
        ],
        "operation": "Publish",
        "usage_type_prefix": "DeliveryAttempts-SMTP",
        "pricing_unit": "Requests",
    },
]

REGIONS = [
    ("us-east-1", "USE1"),
    ("us-west-2", "USW2"),
    ("eu-west-1", "EUW1"),
    ("eu-central-1", "EUC1"),
    ("ap-southeast-1", "APS1"),
]

ACCOUNTS = [
    ("111222333444", "Production"),
    ("555666777888", "Staging"),
    ("999000111222", "Data Platform"),
]

TAG_SETS = [
    {"Environment": "production", "Team": "platform-engineering", "CostCenter": "CC-1001", "Project": "core-api"},
    {"Environment": "production", "Team": "data-engineering", "CostCenter": "CC-2001", "Project": "data-pipeline"},
    {"Environment": "production", "Team": "ml-ops", "CostCenter": "CC-3001", "Project": "recommendation-engine"},
    {"Environment": "staging", "Team": "platform-engineering", "CostCenter": "CC-1001", "Project": "core-api"},
    {"Environment": "staging", "Team": "frontend", "CostCenter": "CC-4001", "Project": "web-app"},
    {"Environment": "dev", "Team": "data-engineering", "CostCenter": "CC-2001"},
    {"Environment": "dev", "Team": "ml-ops"},
    {},  # Untagged
    {},  # Untagged
]


def generate_sample(n_days: int = 90, output_path: str = "sample_cur2.csv") -> None:
    """Generate a realistic CUR 2.0 CSV file."""
    random.seed(42)
    start_date = datetime(2025, 10, 1)
    bill_period_start = start_date.strftime("%Y-%m-%dT00:00:00Z")
    bill_period_end = (start_date + timedelta(days=n_days)).strftime("%Y-%m-%dT00:00:00Z")

    rows = []
    line_id_counter = 0

    for day_offset in range(n_days):
        current_date = start_date + timedelta(days=day_offset)
        usage_start = current_date.strftime("%Y-%m-%dT00:00:00Z")
        usage_end = (current_date + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z")
        time_interval = f"{usage_start}/{usage_end}"

        for svc in SERVICES:
            for inst in svc["instances"]:
                # Each instance can appear in multiple regions/accounts
                n_entries = random.choices([1, 2, 3], weights=[0.6, 0.3, 0.1])[0]

                for _ in range(n_entries):
                    line_id_counter += 1
                    region, region_code = random.choice(REGIONS)
                    account_id, account_name = random.choice(ACCOUNTS)
                    tags = random.choice(TAG_SETS)

                    # Base daily cost with variance
                    base = inst["base_cost"]
                    # Slight upward trend over time
                    trend = 1 + 0.001 * day_offset
                    # Weekend dip for non-production
                    weekend_factor = 0.6 if current_date.weekday() >= 5 and account_name != "Production" else 1.0
                    # Random variance
                    variance = random.gauss(1.0, 0.12)

                    cost = base * trend * weekend_factor * variance
                    cost = max(cost, 0.001)

                    # Anomaly spikes
                    if day_offset == 42 and svc["product_code"] == "AmazonEC2" and inst["type"] == "c5.4xlarge":
                        cost *= 5.2  # Forgot to terminate a batch job
                    if day_offset == 67 and svc["product_code"] == "AmazonS3":
                        cost *= 8.0  # Data migration spike
                    if day_offset == 78 and svc["product_code"] == "AmazonSageMaker":
                        cost *= 4.0  # Training run

                    usage_amount = cost / max(float(inst["base_cost"]) / 24, 0.01) if inst["base_cost"] > 0 else random.uniform(100, 10000)

                    az = f"{region}{random.choice(['a', 'b', 'c'])}" if svc["product_code"] not in ("AmazonS3", "AmazonCloudFront") else ""
                    resource_id = (
                        f"arn:aws:{svc['product_code'].lower().replace('amazon', '').replace('aws', '')}:"
                        f"{region}:{account_id}:{inst['type'].replace('.', '-')}-{random.randint(1000, 9999)}"
                    )

                    blended_rate = cost / max(usage_amount, 0.001)

                    row = {
                        "identity_line_item_id": f"lid-{line_id_counter:08d}",
                        "identity_time_interval": time_interval,
                        "bill_bill_type": "Anniversary",
                        "bill_billing_entity": "AWS",
                        "bill_billing_period_end_date": bill_period_end,
                        "bill_billing_period_start_date": bill_period_start,
                        "bill_invoice_id": f"INV-{start_date.strftime('%Y%m')}-001",
                        "bill_invoicing_entity": "Amazon Web Services, Inc.",
                        "bill_payer_account_id": "111222333444",
                        "bill_payer_account_name": "Acme Corp Master",
                        "line_item_availability_zone": az,
                        "line_item_blended_cost": f"{cost:.10f}",
                        "line_item_blended_rate": f"{blended_rate:.10f}",
                        "line_item_currency_code": "USD",
                        "line_item_line_item_description": f"${blended_rate:.4f} per {svc['pricing_unit']} for {inst['type']} in {region}",
                        "line_item_line_item_type": "Usage",
                        "line_item_net_unblended_cost": f"{cost * 0.95:.10f}",
                        "line_item_net_unblended_rate": f"{blended_rate * 0.95:.10f}",
                        "line_item_operation": svc["operation"],
                        "line_item_product_code": svc["product_code"],
                        "line_item_resource_id": resource_id,
                        "line_item_usage_account_id": account_id,
                        "line_item_usage_account_name": account_name,
                        "line_item_usage_amount": f"{usage_amount:.10f}",
                        "line_item_usage_end_date": usage_end,
                        "line_item_usage_start_date": usage_start,
                        "line_item_usage_type": f"{region_code}-{svc['usage_type_prefix']}:{inst['type']}",
                        "pricing_public_on_demand_cost": f"{cost * 1.15:.10f}",
                        "pricing_public_on_demand_rate": f"{blended_rate * 1.15:.10f}",
                        "pricing_term": "OnDemand",
                        "pricing_unit": svc["pricing_unit"],
                        "product_product_name": svc["product_name"],
                        "product_region": region,
                        "product_instance_type": inst["type"],
                        "product_instance_type_family": inst["family"],
                        "product_operating_system": inst["os"],
                        "product_vcpu": inst["vcpu"],
                        "product_memory": inst["memory"],
                        "resource_tags": json.dumps(tags) if tags else "{}",
                    }
                    rows.append(row)

    # Shuffle to make it realistic (real CUR files aren't perfectly ordered)
    random.shuffle(rows)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CUR2_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(rows)} rows → {output}")
    print(f"  Period: {start_date.strftime('%Y-%m-%d')} to {(start_date + timedelta(days=n_days)).strftime('%Y-%m-%d')}")
    print(f"  Services: {len(SERVICES)}")
    print(f"  Accounts: {len(ACCOUNTS)}")
    print(f"  Regions: {len(REGIONS)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate sample AWS CUR 2.0 CSV")
    parser.add_argument("--output", default=None, help="Output CSV path")
    parser.add_argument("--days", type=int, default=90, help="Number of days to generate")
    args = parser.parse_args()

    output = args.output or str(Path(__file__).resolve().parent.parent / "resources" / "sample_data" / "sample_cur2.csv")
    generate_sample(n_days=args.days, output_path=output)
