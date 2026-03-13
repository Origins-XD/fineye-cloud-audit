"""Abstract base parser for cloud billing CSVs."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd

from models import NORMALIZED_COLUMNS


class BaseParser(ABC):
    """Abstract base parser. All cloud parsers inherit from this."""

    @abstractmethod
    def parse(self, file_path: Path) -> pd.DataFrame:
        """Parse CSV file into a normalized DataFrame.

        Must return DataFrame with columns matching NORMALIZED_COLUMNS.
        """
        ...

    def _validate_output(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ensure the DataFrame has all required columns with correct types."""
        defaults = {
            "date": pd.NaT,
            "service": "Unknown",
            "resource_id": "",
            "resource_type": "",
            "region": "Unknown",
            "cost": 0.0,
            "usage_quantity": 0.0,
            "currency": "USD",
            "tags": "{}",
            "account_id": "",
            "account_name": "",
            "charge_type": "Usage",
            "provider": "",
        }

        for col in NORMALIZED_COLUMNS:
            if col not in df.columns:
                df[col] = defaults.get(col, "")

        # Enforce types
        df["cost"] = pd.to_numeric(df["cost"], errors="coerce").fillna(0.0)
        df["usage_quantity"] = pd.to_numeric(df["usage_quantity"], errors="coerce").fillna(0.0)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["tags"] = df["tags"].fillna("{}")

        # Keep only normalized columns in the correct order
        df = df[NORMALIZED_COLUMNS]

        # Drop rows with no date (header rows, summary rows, etc.)
        df = df.dropna(subset=["date"])

        return df
