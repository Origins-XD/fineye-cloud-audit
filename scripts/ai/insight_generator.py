"""Generate AI-powered insights using the OpenAI API."""
from __future__ import annotations

import json
import os

from models import CostSummary, TagSummary, AIInsights


SYSTEM_PROMPT = """You are a senior FinOps analyst at a top-tier cloud consultancy. You produce executive-level cloud cost audit reports for enterprise clients. Your writing is clear, specific, and actionable. You avoid generic advice — every recommendation must be tied to specific data from the analysis. Write for a CTO/CFO audience."""


def generate_insights(
    cost_summary: CostSummary,
    tag_summary: TagSummary,
    provider: str,
    client_name: str,
) -> AIInsights:
    """Call OpenAI API to generate executive summary, findings, and recommendations."""
    try:
        from openai import OpenAI
    except ImportError:
        return _fallback_insights(cost_summary, tag_summary)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return _fallback_insights(cost_summary, tag_summary)

    prompt = _build_analysis_prompt(cost_summary, tag_summary, provider, client_name)

    client = OpenAI(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=2000,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        response_text = response.choices[0].message.content
        return _parse_response(response_text)
    except Exception:
        return _fallback_insights(cost_summary, tag_summary)


def _build_analysis_prompt(
    cost_summary: CostSummary,
    tag_summary: TagSummary,
    provider: str,
    client_name: str,
) -> str:
    """Build the structured prompt with analysis data."""
    # Format top services table
    services_table = "\n".join(
        f"  - {s['service']}: ${s['cost']:,.2f} ({s['pct']}%)"
        for s in cost_summary.top_services[:10]
    )

    # Format anomalies
    if cost_summary.anomalies:
        anomalies_text = "\n".join(
            f"  - {a['date']}: ${a['cost']:,.2f} (expected: ${a['expected']:,.2f}, deviation: {a['deviation']}x std)"
            for a in cost_summary.anomalies[:5]
        )
    else:
        anomalies_text = "  None detected"

    # Format MoM
    if cost_summary.month_over_month:
        mom_text = "\n".join(
            f"  - {m['month']}: ${m['cost']:,.2f}" + (f" ({m['change_pct']:+.1f}%)" if m['change_pct'] is not None else "")
            for m in cost_summary.month_over_month
        )
    else:
        mom_text = "  Single period only"

    # Top tag keys
    top_tags = ", ".join(t["key"] for t in tag_summary.tag_key_distribution[:5]) or "None"

    return f"""Generate the analysis sections for a cloud cost audit report.

CLIENT: {client_name}
CLOUD PROVIDER: {provider.upper()}
REPORTING PERIOD: {cost_summary.date_range_start} to {cost_summary.date_range_end}
TOTAL SPEND: {cost_summary.currency} {cost_summary.total_cost:,.2f}
DAILY AVERAGE: {cost_summary.currency} {cost_summary.daily_average:,.2f}
NUMBER OF DAYS: {cost_summary.num_days}

TOP SERVICES BY COST:
{services_table}

COST ANOMALIES:
{anomalies_text}

TAG COVERAGE:
  - {tag_summary.tagged_resources}/{tag_summary.total_resources} resources tagged ({tag_summary.coverage_pct}%)
  - Untagged resources account for {cost_summary.currency} {tag_summary.cost_of_untagged:,.2f} ({tag_summary.cost_of_untagged_pct}% of total spend)
  - Most common tag keys: {top_tags}

MONTH-OVER-MONTH:
{mom_text}

Respond with ONLY valid JSON in this exact format (no markdown, no code fences):
{{
  "executive_summary": "3-5 sentences summarizing the audit findings for a CTO/CFO audience.",
  "key_findings": ["finding 1", "finding 2", "finding 3", "finding 4"],
  "recommendations": [
    {{"title": "Short title", "description": "2-3 sentences with specific action", "estimated_impact": "e.g. 15-20% reduction in compute costs"}}
  ],
  "methodology_note": "2-3 sentences explaining how this analysis was performed."
}}"""


def _parse_response(response_text: str) -> AIInsights:
    """Parse the JSON response into AIInsights."""
    # Strip any markdown code fences if present
    text = response_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    data = json.loads(text)
    return AIInsights(
        executive_summary=data.get("executive_summary", ""),
        key_findings=data.get("key_findings", []),
        recommendations=data.get("recommendations", []),
        methodology_note=data.get("methodology_note", ""),
    )


def _fallback_insights(cost_summary: CostSummary, tag_summary: TagSummary) -> AIInsights:
    """Generate basic insights without AI when the API is unavailable."""
    top_service = cost_summary.top_services[0] if cost_summary.top_services else None
    top_svc_text = f"{top_service['service']} ({top_service['pct']}% of total spend)" if top_service else "N/A"

    return AIInsights(
        executive_summary=(
            f"This audit covers {cost_summary.num_days} days of cloud spending "
            f"totalling {cost_summary.currency} {cost_summary.total_cost:,.2f}, "
            f"averaging {cost_summary.currency} {cost_summary.daily_average:,.2f} per day. "
            f"The top spending service is {top_svc_text}. "
            f"Tag coverage stands at {tag_summary.coverage_pct}% across {tag_summary.total_resources} resources."
        ),
        key_findings=[
            f"Total spend: {cost_summary.currency} {cost_summary.total_cost:,.2f} over {cost_summary.num_days} days",
            f"Top service: {top_svc_text}",
            f"Tag coverage: {tag_summary.coverage_pct}% ({tag_summary.untagged_resources} untagged resources)",
            f"Cost anomalies detected: {len(cost_summary.anomalies)}",
        ],
        recommendations=[{
            "title": "Improve tag coverage",
            "description": f"{tag_summary.untagged_resources} resources lack tags, representing {cost_summary.currency} {tag_summary.cost_of_untagged:,.2f} in spend. Implement a tagging policy to enable accurate cost allocation.",
            "estimated_impact": "Improved cost visibility and allocation accuracy",
        }],
        methodology_note=(
            "This report was generated using automated analysis of cloud billing data. "
            "Cost anomalies are detected using statistical deviation from the daily average. "
            "AI-powered insights were not available for this report."
        ),
    )
