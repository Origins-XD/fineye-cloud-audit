"""Azure Cost Management export CSV parser."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from parsers.base import BaseParser


# Azure EA (Enterprise Agreement) column mapping
AZURE_EA_MAP = {
    "Date": "date",
    "MeterCategory": "service",
    "ResourceId": "resource_id",
    "MeterSubCategory": "resource_type",
    "ResourceLocation": "region",
    "CostInBillingCurrency": "cost",
    "Quantity": "usage_quantity",
    "BillingCurrencyCode": "currency",
    "SubscriptionId": "account_id",
    "SubscriptionName": "account_name",
    "ChargeType": "charge_type",
}

# Azure PAYG / MCA column mapping (slightly different names)
AZURE_PAYG_MAP = {
    "UsageDateTime": "date",
    "Date": "date",
    "MeterCategory": "service",
    "InstanceId": "resource_id",
    "ResourceId": "resource_id",
    "MeterSubcategory": "resource_type",
    "MeterSubCategory": "resource_type",
    "ResourceLocation": "region",
    "PreTaxCost": "cost",
    "CostInBillingCurrency": "cost",
    "UsageQuantity": "usage_quantity",
    "Quantity": "usage_quantity",
    "Currency": "currency",
    "BillingCurrency": "currency",
    "BillingCurrencyCode": "currency",
    "SubscriptionGuid": "account_id",
    "SubscriptionId": "account_id",
    "SubscriptionName": "account_name",
    "ChargeType": "charge_type",
}


class AzureCostParser(BaseParser):
    """Parser for Azure Cost Management export CSV files."""

    def parse(self, file_path: Path) -> pd.DataFrame:
        df = pd.read_csv(file_path, low_memory=False, encoding="utf-8-sig")

        # Detect which format we're dealing with and map columns
        column_map = self._detect_and_map(df.columns.tolist())
        df = df.rename(columns=column_map)

        # Parse and normalize the Tags column
        tags_col = self._find_tags_column(df)
        if tags_col:
            df["tags"] = df[tags_col].apply(self._clean_tags)
            if tags_col != "tags":
                df = df.drop(columns=[tags_col], errors="ignore")
        else:
            df["tags"] = "{}"

        # Add static columns
        df["provider"] = "azure"
        if "charge_type" not in df.columns:
            df["charge_type"] = "Usage"
        if "account_name" not in df.columns:
            df["account_name"] = df.get("account_id", "")

        return self._validate_output(df)

    def _detect_and_map(self, columns: list[str]) -> dict[str, str]:
        """Build the best column mapping for the actual CSV columns present."""
        col_set = set(columns)
        col_lower_map = {c.lower(): c for c in columns}

        # Try EA map first, then PAYG — use whichever matches more columns
        ea_matches = {k: v for k, v in AZURE_EA_MAP.items() if k in col_set}
        payg_matches = {k: v for k, v in AZURE_PAYG_MAP.items() if k in col_set}

        if len(ea_matches) >= len(payg_matches):
            return ea_matches
        return payg_matches

    def _find_tags_column(self, df: pd.DataFrame) -> str | None:
        """Find the tags column (Azure uses 'Tags' or 'Tag')."""
        for col in df.columns:
            if col.lower() == "tags" or col.lower() == "tag":
                return col
        return None

    def _clean_tags(self, raw_tags) -> str:
        """Normalize Azure tags to valid JSON string.

        Azure tags come in various formats:
        - Empty: "", NaN, "{}"
        - JSON: '{"env": "prod", "team": "platform"}'
        - Key-value: '"env": "prod", "team": "platform"'
        - Colon-separated: 'env: prod, team: platform'
        """
        if pd.isna(raw_tags) or not str(raw_tags).strip():
            return "{}"

        raw = str(raw_tags).strip()

        # Already valid JSON
        if raw.startswith("{") and raw.endswith("}"):
            try:
                json.loads(raw)
                return raw
            except json.JSONDecodeError:
                pass

        # Try wrapping in braces
        try:
            result = json.loads("{" + raw + "}")
            return json.dumps(result)
        except json.JSONDecodeError:
            pass

        # Parse colon-separated: key: value, key: value
        tags = {}
        pairs = re.split(r",\s*", raw)
        for pair in pairs:
            if ":" in pair:
                key, _, value = pair.partition(":")
                key = key.strip().strip('"').strip("'")
                value = value.strip().strip('"').strip("'")
                if key:
                    tags[key] = value

        return json.dumps(tags)
