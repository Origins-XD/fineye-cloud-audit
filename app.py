#!/usr/bin/env python3
"""
FinEye Cloud Audit — Web UI
Upload a CUR/Azure CSV → get a professional cost audit report.
Run: python app.py (serves on http://localhost:3001)
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import traceback
from datetime import datetime
from pathlib import Path

# Add scripts dir to path
SKILL_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from dotenv import load_dotenv
from flask import Flask, request, jsonify

load_dotenv(SKILL_ROOT / ".env")

from models import ReportData
from parsers import parse_file
from analyzers.cost_analyzer import analyze_costs
from analyzers.tag_analyzer import analyze_tags
from charts.chart_generator import generate_all_charts
from ai.insight_generator import generate_insights, _fallback_insights
from report.pdf_generator import _render_html, _embed_images_as_base64

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500MB for large CURs

# ── CORS for Framer embed ──
ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS",
    "https://finabeo.com,https://www.finabeo.com",
).split(",")


@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin", "")
    if origin in ALLOWED_ORIGINS or "*" in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


# ── Email delivery via Resend ──
def send_report_email(email: str, company: str, report_html: str) -> None:
    """Send report as HTML attachment via Resend. Runs in background thread."""
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        print("RESEND_API_KEY not set, skipping email")
        return

    try:
        import resend
        resend.api_key = api_key

        safe_name = company.replace(" ", "_").lower()
        filename = f"cloud_audit_{safe_name}.html"

        resend.Emails.send({
            "from": os.environ.get("RESEND_FROM", "FinEye <audit@finabeo.com>"),
            "to": [email],
            "subject": f"Your Cloud Cost Audit Report — {company}",
            "html": (
                f"<p>Hi,</p>"
                f"<p>Your FinEye cloud cost audit report for <strong>{company}</strong> is attached.</p>"
                f"<p>Open the .html file in any browser to view the full interactive report "
                f"with charts, cost breakdown, and recommendations.</p>"
                f'<p>Want to discuss the findings? <a href="https://finabeo.com">Book a call with Finabeo</a>.</p>'
                f"<p>Best,<br>The FinEye Team</p>"
            ),
            "attachments": [{"filename": filename, "content": report_html}],
        })
        print(f"Report emailed to {email}")
    except Exception as e:
        print(f"Email send failed: {e}")


def load_config() -> dict:
    config_path = SKILL_ROOT / "resources" / "config" / "report_config.json"
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)
    return {}


def run_pipeline(csv_path: Path, client_name: str, period: str | None, use_ai: bool) -> str:
    """Run the full audit pipeline and return self-contained HTML."""
    config = load_config()
    thresholds = config.get("thresholds", {})

    # Parse
    df, provider = parse_file(csv_path)

    # Analyze
    cost_summary = analyze_costs(
        df,
        top_n_services=thresholds.get("top_services_count", 10),
        top_n_resources=thresholds.get("top_resources_count", 15),
        anomaly_threshold=thresholds.get("anomaly_std_multiplier", 2.0),
    )
    tag_summary = analyze_tags(
        df,
        top_untagged_count=thresholds.get("top_untagged_count", 20),
    )

    # Charts
    with tempfile.TemporaryDirectory() as chart_dir:
        chart_paths = generate_all_charts(cost_summary, tag_summary, Path(chart_dir), config)

        # AI insights
        if use_ai:
            ai_insights = generate_insights(cost_summary, tag_summary, provider, client_name)
        else:
            ai_insights = _fallback_insights(cost_summary, tag_summary)

        # Build report data
        if not period:
            period = f"{cost_summary.date_range_start} to {cost_summary.date_range_end}"

        report_data = ReportData(
            client_name=client_name,
            report_date=datetime.now().strftime("%d %B %Y"),
            reporting_period=period,
            cloud_provider=provider,
            cost_summary=cost_summary,
            tag_summary=tag_summary,
            chart_paths=chart_paths,
            ai_insights=ai_insights,
        )

        # Render HTML with embedded base64 images
        template_dir = SKILL_ROOT / "resources" / "templates"
        html = _render_html(report_data, template_dir)
        return _embed_images_as_base64(html)


def run_demo_pipeline(client_name: str, use_ai: bool) -> str:
    """Run pipeline with synthetic demo data."""
    import pandas as pd
    import numpy as np
    from datetime import timedelta

    config = load_config()
    thresholds = config.get("thresholds", {})

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

            cost = base_cost * (1 + 0.002 * day_offset) + np.random.normal(0, base_cost * 0.15)
            cost = max(cost, 0.01)

            if day_offset == 35 and svc_name == "Amazon EC2":
                cost *= 4.5

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
                "date": date, "service": svc_name, "resource_id": resource_id,
                "resource_type": res_type, "region": region, "cost": round(cost, 4),
                "usage_quantity": round(cost * 2.5, 4), "currency": "USD",
                "tags": tags, "account_id": "123456789012",
                "account_name": "Demo Production Account",
                "charge_type": "Usage", "provider": "aws",
            })

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])

    cost_summary = analyze_costs(
        df,
        top_n_services=thresholds.get("top_services_count", 10),
        top_n_resources=thresholds.get("top_resources_count", 15),
        anomaly_threshold=thresholds.get("anomaly_std_multiplier", 2.0),
    )
    tag_summary = analyze_tags(df, top_untagged_count=thresholds.get("top_untagged_count", 20))

    with tempfile.TemporaryDirectory() as chart_dir:
        chart_paths = generate_all_charts(cost_summary, tag_summary, Path(chart_dir), config)

        if use_ai:
            ai_insights = generate_insights(cost_summary, tag_summary, "aws", client_name)
        else:
            ai_insights = _fallback_insights(cost_summary, tag_summary)

        report_data = ReportData(
            client_name=client_name,
            report_date=datetime.now().strftime("%d %B %Y"),
            reporting_period=f"{cost_summary.date_range_start} to {cost_summary.date_range_end}",
            cloud_provider="aws",
            cost_summary=cost_summary,
            tag_summary=tag_summary,
            chart_paths=chart_paths,
            ai_insights=ai_insights,
        )

        template_dir = SKILL_ROOT / "resources" / "templates"
        html = _render_html(report_data, template_dir)
        return _embed_images_as_base64(html)


# ─────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return jsonify({"status": "ok", "service": "fineye-cloud-audit"})


@app.route("/generate", methods=["POST", "OPTIONS"])
def generate():
    if request.method == "OPTIONS":
        return "", 204

    csv_file = request.files.get("csv")
    if not csv_file or not csv_file.filename:
        return jsonify({"error": "No CSV file uploaded"}), 400

    client = request.form.get("client", "Client")
    email = request.form.get("email", "")
    period = request.form.get("period", "") or None
    use_ai = request.form.get("use_ai", "1") == "1"

    # Save uploaded file to temp
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        csv_file.save(tmp)
        tmp_path = Path(tmp.name)

    try:
        html = run_pipeline(tmp_path, client, period, use_ai)

        # Email report in background
        if email:
            threading.Thread(
                target=send_report_email,
                args=(email, client, html),
                daemon=True,
            ).start()

        return html, 200, {"Content-Type": "text/html"}
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Report generation failed: {str(e)}"}), 500
    finally:
        tmp_path.unlink(missing_ok=True)


@app.route("/demo", methods=["GET", "OPTIONS"])
def demo():
    if request.method == "OPTIONS":
        return "", 204

    client = request.args.get("client", "Demo Corp")
    email = request.args.get("email", "")
    use_ai = request.args.get("use_ai", "1") == "1"

    try:
        html = run_demo_pipeline(client, use_ai)

        if email:
            threading.Thread(
                target=send_report_email,
                args=(email, client, html),
                daemon=True,
            ).start()

        return html, 200, {"Content-Type": "text/html"}
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Demo generation failed: {str(e)}"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3001))
    print(f"\n  FinEye Cloud Cost Audit")
    print(f"  http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
