"""Tag coverage analysis for cloud resources."""
from __future__ import annotations

import json
from collections import Counter

import pandas as pd

from models import TagSummary


def analyze_tags(df: pd.DataFrame, top_untagged_count: int = 20) -> TagSummary:
    """Analyze tag coverage across all resources."""
    # De-duplicate to unique resources (use the resource with highest cost)
    resource_df = (
        df[df["resource_id"].str.strip() != ""]
        .groupby("resource_id")
        .agg({"cost": "sum", "service": "first", "tags": "first"})
        .reset_index()
    )

    total_resources = len(resource_df)
    if total_resources == 0:
        return TagSummary(
            total_resources=0,
            tagged_resources=0,
            untagged_resources=0,
            coverage_pct=0.0,
            cost_of_untagged=0.0,
            cost_of_untagged_pct=0.0,
            tag_key_distribution=[],
            top_untagged_resources=[],
        )

    # Determine which resources have tags
    resource_df["has_tags"] = resource_df["tags"].apply(_has_tags)

    tagged = resource_df["has_tags"].sum()
    untagged = total_resources - tagged
    coverage_pct = (tagged / total_resources * 100) if total_resources > 0 else 0

    total_cost = resource_df["cost"].sum()
    untagged_df = resource_df[~resource_df["has_tags"]]
    cost_of_untagged = untagged_df["cost"].sum()
    cost_of_untagged_pct = (cost_of_untagged / total_cost * 100) if total_cost > 0 else 0

    # Tag key distribution
    tag_key_counts = _count_tag_keys(resource_df)
    tag_key_distribution = [
        {"key": key, "count": count, "pct": round(count / total_resources * 100, 1)}
        for key, count in tag_key_counts.most_common(20)
    ]

    # Top untagged resources by cost
    top_untagged = (
        untagged_df.nlargest(top_untagged_count, "cost")[["resource_id", "service", "cost"]]
        .to_dict("records")
    )
    for item in top_untagged:
        item["cost"] = round(item["cost"], 2)

    return TagSummary(
        total_resources=total_resources,
        tagged_resources=int(tagged),
        untagged_resources=int(untagged),
        coverage_pct=round(coverage_pct, 1),
        cost_of_untagged=round(cost_of_untagged, 2),
        cost_of_untagged_pct=round(cost_of_untagged_pct, 1),
        tag_key_distribution=tag_key_distribution,
        top_untagged_resources=top_untagged,
    )


def _has_tags(tags_str: str) -> bool:
    """Check if a tags JSON string contains any actual tags."""
    try:
        tags = json.loads(tags_str)
        return isinstance(tags, dict) and len(tags) > 0
    except (json.JSONDecodeError, TypeError):
        return False


def _count_tag_keys(df: pd.DataFrame) -> Counter:
    """Count how many resources have each tag key."""
    counter: Counter = Counter()
    for tags_str in df["tags"]:
        try:
            tags = json.loads(tags_str)
            if isinstance(tags, dict):
                counter.update(tags.keys())
        except (json.JSONDecodeError, TypeError):
            continue
    return counter
