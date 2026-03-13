---
name: cloud-cost-audit
description: "Use when generating cloud cost audit reports from AWS CUR or Azure cost export CSV files."
---

# Cloud Cost Audit Report Generator

## Purpose

Generate professional, consulting-firm-quality PDF reports from raw cloud billing data. Supports AWS Cost and Usage Reports (CUR) and Azure Cost Management exports. Includes automated cost analysis, tag coverage assessment, trend detection, anomaly flagging, and AI-powered recommendations via Claude.

## How To Use

```bash
# Navigate to the skill directory
cd skills/finops/cloud-audit

# Install dependencies (first time only)
pip install -r requirements.txt
brew install pango  # macOS — required by WeasyPrint

# Generate a report from real data
python scripts/main.py /path/to/billing.csv --client "Acme Corp" --period "Q1 2026"

# Generate a demo report with synthetic data
python scripts/main.py --demo --client "Demo Corp"

# Skip AI insights (no API key needed)
python scripts/main.py /path/to/billing.csv --client "Acme Corp" --no-ai

# Custom output directory
python scripts/main.py /path/to/billing.csv --client "Acme Corp" --output /path/to/output
```

## Prerequisites

- Python 3.9+
- System dependency: `pango` (macOS: `brew install pango`)
- Optional: `ANTHROPIC_API_KEY` in `.env` for AI-powered insights

## Pipeline

1. **Detect Provider** — Auto-detects AWS or Azure from CSV column headers
2. **Parse & Normalize** — Maps provider-specific columns to a common schema
3. **Analyze Costs** — Top services, daily trends, anomalies, month-over-month
4. **Analyze Tags** — Coverage percentage, key distribution, untagged resources
5. **Generate Charts** — 6 Plotly charts exported as PNGs
6. **AI Insights** — Claude generates executive summary and recommendations
7. **Render PDF** — Jinja2 HTML template converted to PDF via WeasyPrint

## Report Sections

- Cover page with client branding
- Executive summary (AI-generated)
- Cost overview with metric cards and service breakdown
- Cost trend with daily line chart and month-over-month
- Regional cost breakdown
- Tag coverage analysis with compliance status
- Top resources by spend
- Actionable recommendations with estimated impact
- Appendix with methodology and definitions

## Configuration

Edit `resources/config/report_config.json` to customise:
- **Branding**: company name, colors, logo path
- **Thresholds**: anomaly sensitivity, tag coverage warning levels
- **Chart settings**: dimensions, color palette
- **Report sections**: toggle individual sections on/off

## Supported Formats

| Provider | Format | Key Cost Column |
|----------|--------|----------------|
| AWS | Cost and Usage Report (CUR) CSV | lineItem/UnblendedCost |
| Azure | Cost Management export (EA) | CostInBillingCurrency |
| Azure | Cost Management export (PAYG/MCA) | PreTaxCost |

## File Structure

```
cloud-audit/
├── SKILL.md                    # This file
├── requirements.txt            # Python dependencies
├── .env                        # API keys (gitignored)
├── scripts/
│   ├── main.py                 # CLI entry point
│   ├── models.py               # Shared data models
│   ├── parsers/                # CSV parsing (AWS + Azure)
│   ├── analyzers/              # Cost + tag analysis
│   ├── charts/                 # Plotly chart generation
│   ├── ai/                     # Claude API integration
│   └── report/                 # Jinja2 + WeasyPrint PDF
├── resources/
│   ├── config/                 # Report configuration
│   ├── templates/              # HTML + CSS templates
│   └── branding/               # Logo and brand assets
└── output/                     # Generated reports (gitignored)
```

## Extending

To add GCP support: create `scripts/parsers/gcp_billing.py`, implement `BaseParser`, and register it in `parsers/__init__.py`.
