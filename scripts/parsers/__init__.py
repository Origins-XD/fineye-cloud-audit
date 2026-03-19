"""Cloud billing CSV parsers with auto-detection."""
from __future__ import annotations

import gzip
from pathlib import Path

import pandas as pd

from parsers.base import BaseParser
from parsers.aws_cur import AWSCURParser
from parsers.azure_cost import AzureCostParser


def _open_csv(file_path: Path):
    """Open a CSV file, auto-detecting gzip from magic bytes."""
    with open(file_path, "rb") as f:
        magic = f.read(2)
    if magic == b"\x1f\x8b":
        return gzip.open(file_path, "rt", encoding="utf-8-sig")
    return open(file_path, "r", encoding="utf-8-sig")


def detect_provider(file_path: Path) -> str:
    """Read CSV headers and determine cloud provider.

    Returns 'aws' or 'azure'. Raises ValueError if unrecognized.
    """
    with _open_csv(file_path) as f:
        header_line = f.readline().strip()

    headers = header_line.lower()

    # AWS CUR 1.0 (slash-separated: lineItem/UnblendedCost)
    if "lineitem/" in headers or "bill/" in headers:
        return "aws"
    # AWS CUR 2.0 (underscore-separated: line_item_unblended_cost)
    elif "line_item_unblended_cost" in headers or "line_item_product_code" in headers:
        return "aws"
    elif "metercategory" in headers or "consumedservice" in headers or "costinbillingcurrency" in headers or "pretaxcost" in headers:
        return "azure"
    else:
        raise ValueError(
            f"Could not detect cloud provider from CSV headers. "
            f"Expected AWS CUR (lineItem/ or line_item_), Azure (MeterCategory). "
            f"First 200 chars of header: {header_line[:200]}"
        )


def get_parser(provider: str) -> BaseParser:
    """Return the correct parser instance for the detected provider."""
    parsers = {
        "aws": AWSCURParser,
        "azure": AzureCostParser,
    }
    if provider not in parsers:
        raise ValueError(f"Unknown provider: {provider}. Supported: {list(parsers.keys())}")
    return parsers[provider]()


def parse_file(file_path: Path) -> tuple[pd.DataFrame, str]:
    """Detect provider and parse CSV in one call.

    Returns (normalized_dataframe, provider_name).
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    provider = detect_provider(file_path)
    parser = get_parser(provider)
    df = parser.parse(file_path)
    return df, provider
