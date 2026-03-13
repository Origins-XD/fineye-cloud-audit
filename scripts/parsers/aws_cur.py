"""AWS Cost and Usage Report (CUR) CSV parser — supports CUR 1.0 and CUR 2.0."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from parsers.base import BaseParser


# CUR 1.0 column mapping (slash-separated: lineItem/UnblendedCost)
CUR1_COLUMN_MAP = {
    "lineItem/UsageStartDate": "date",
    "lineItem/ProductCode": "service",
    "lineItem/ResourceId": "resource_id",
    "lineItem/UsageType": "resource_type",
    "product/region": "region",
    "lineItem/UnblendedCost": "cost",
    "lineItem/UsageAmount": "usage_quantity",
    "lineItem/CurrencyCode": "currency",
    "lineItem/UsageAccountId": "account_id",
    "lineItem/LineItemType": "charge_type",
}

CUR1_FALLBACK_MAP = {
    "region": ["product/regionCode", "lineItem/AvailabilityZone"],
    "cost": ["lineItem/BlendedCost"],
    "currency": ["bill/BillingCurrencyCode"],
}

# CUR 2.0 column mapping (underscore-separated: line_item_unblended_cost)
CUR2_COLUMN_MAP = {
    "line_item_usage_start_date": "date",
    "line_item_product_code": "service",
    "line_item_resource_id": "resource_id",
    "line_item_usage_type": "resource_type",
    "product_region": "region",
    "line_item_unblended_cost": "cost",
    "line_item_usage_amount": "usage_quantity",
    "line_item_currency_code": "currency",
    "line_item_usage_account_id": "account_id",
    "line_item_usage_account_name": "account_name",
    "line_item_line_item_type": "charge_type",
}

CUR2_FALLBACK_MAP = {
    "region": ["line_item_availability_zone"],
    "cost": ["line_item_blended_cost", "line_item_net_unblended_cost"],
    "currency": ["bill_currency_code"],
}


def _detect_cur_version(columns: list[str]) -> int:
    """Detect CUR version from column names. Returns 1 or 2."""
    for col in columns:
        if "/" in col and ("lineItem" in col or "product" in col or "bill" in col):
            return 1
    for col in columns:
        if col.startswith("line_item_") or col.startswith("bill_"):
            return 2
    return 1  # default


class AWSCURParser(BaseParser):
    """Parser for AWS Cost and Usage Report CSV files (CUR 1.0 and 2.0)."""

    def parse(self, file_path: Path) -> pd.DataFrame:
        # Read CSV headers to detect CUR version
        all_columns = pd.read_csv(file_path, nrows=0, encoding="utf-8-sig").columns.tolist()
        cur_version = _detect_cur_version(all_columns)

        if cur_version == 2:
            return self._parse_cur2(file_path, all_columns)
        else:
            return self._parse_cur1(file_path, all_columns)

    # ── CUR 1.0 parsing ──────────────────────────────────────────────

    def _parse_cur1(self, file_path: Path, all_columns: list[str]) -> pd.DataFrame:
        needed_columns = self._get_needed_columns_v1(all_columns)

        df = pd.read_csv(
            file_path,
            usecols=needed_columns,
            low_memory=False,
            encoding="utf-8-sig",
        )

        rename_map = {}
        for aws_col, norm_col in CUR1_COLUMN_MAP.items():
            if aws_col in df.columns:
                rename_map[aws_col] = norm_col

        for norm_col, fallbacks in CUR1_FALLBACK_MAP.items():
            if norm_col not in rename_map.values():
                for fallback in fallbacks:
                    if fallback in df.columns:
                        rename_map[fallback] = norm_col
                        break

        df = df.rename(columns=rename_map)

        # Extract resource tags from resourceTags/user:* columns
        df["tags"] = self._extract_tags_v1(df)
        tag_cols = [c for c in df.columns if c.startswith("resourceTags/")]
        df = df.drop(columns=tag_cols, errors="ignore")

        df["provider"] = "aws"
        if "account_name" not in df.columns:
            df["account_name"] = df.get("account_id", "")

        return self._validate_output(df)

    def _get_needed_columns_v1(self, all_columns: list[str]) -> list[str]:
        needed = set()
        for aws_col in CUR1_COLUMN_MAP:
            if aws_col in all_columns:
                needed.add(aws_col)
        for fallbacks in CUR1_FALLBACK_MAP.values():
            for fb in fallbacks:
                if fb in all_columns:
                    needed.add(fb)
        for col in all_columns:
            if col.startswith("resourceTags/"):
                needed.add(col)
        return list(needed)

    def _extract_tags_v1(self, df: pd.DataFrame) -> pd.Series:
        tag_columns = [c for c in df.columns if c.startswith("resourceTags/")]
        if not tag_columns:
            return pd.Series(["{}" for _ in range(len(df))], index=df.index)

        def row_to_tags(row: pd.Series) -> str:
            tags = {}
            for col in tag_columns:
                val = row.get(col)
                if pd.notna(val) and str(val).strip():
                    key = col.split(":")[-1] if ":" in col else col.replace("resourceTags/", "")
                    tags[key] = str(val).strip()
            return json.dumps(tags)

        return df.apply(row_to_tags, axis=1)

    # ── CUR 2.0 parsing ──────────────────────────────────────────────

    def _parse_cur2(self, file_path: Path, all_columns: list[str]) -> pd.DataFrame:
        needed_columns = self._get_needed_columns_v2(all_columns)

        df = pd.read_csv(
            file_path,
            usecols=needed_columns,
            low_memory=False,
            encoding="utf-8-sig",
        )

        rename_map = {}
        for cur_col, norm_col in CUR2_COLUMN_MAP.items():
            if cur_col in df.columns:
                rename_map[cur_col] = norm_col

        for norm_col, fallbacks in CUR2_FALLBACK_MAP.items():
            if norm_col not in rename_map.values():
                for fallback in fallbacks:
                    if fallback in df.columns:
                        rename_map[fallback] = norm_col
                        break

        df = df.rename(columns=rename_map)

        # CUR 2.0 stores tags in a single resource_tags JSON column
        if "resource_tags" in df.columns:
            df["tags"] = df["resource_tags"].apply(self._normalize_tags)
            df = df.drop(columns=["resource_tags"], errors="ignore")
        else:
            df["tags"] = "{}"

        df["provider"] = "aws"
        if "account_name" not in df.columns:
            df["account_name"] = df.get("account_id", "")

        return self._validate_output(df)

    def _get_needed_columns_v2(self, all_columns: list[str]) -> list[str]:
        needed = set()
        for cur_col in CUR2_COLUMN_MAP:
            if cur_col in all_columns:
                needed.add(cur_col)
        for fallbacks in CUR2_FALLBACK_MAP.values():
            for fb in fallbacks:
                if fb in all_columns:
                    needed.add(fb)
        if "resource_tags" in all_columns:
            needed.add("resource_tags")
        return list(needed)

    @staticmethod
    def _normalize_tags(tags_value) -> str:
        """Normalize the resource_tags column to a JSON string."""
        if pd.isna(tags_value) or not str(tags_value).strip():
            return "{}"
        s = str(tags_value).strip()
        # Already valid JSON
        try:
            parsed = json.loads(s)
            if isinstance(parsed, dict):
                return json.dumps(parsed)
        except (json.JSONDecodeError, TypeError):
            pass
        return "{}"
