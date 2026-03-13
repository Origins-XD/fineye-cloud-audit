"""Render the audit report as a professional PDF (or self-contained HTML fallback)."""
from __future__ import annotations

import base64
import re
import tempfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from models import ReportData


def render_report(report_data: ReportData, output_path: Path, template_dir: Path | None = None) -> Path:
    """Render HTML template with data and convert to PDF.

    Uses Playwright (headless Chromium) for PDF generation.
    Falls back to self-contained HTML if Playwright is unavailable.
    Returns the path to the generated file.
    """
    if template_dir is None:
        template_dir = Path(__file__).resolve().parent.parent.parent / "resources" / "templates"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    html_content = _render_html(report_data, template_dir)
    self_contained = _embed_images_as_base64(html_content)

    # Always save HTML version for preview
    html_path = output_path.with_suffix(".html")
    html_path.write_text(self_contained, encoding="utf-8")

    # Try Playwright PDF first, then WeasyPrint, fall back to HTML-only
    try:
        return _html_to_pdf_playwright(html_content, output_path)
    except Exception:
        pass

    try:
        return _html_to_pdf_weasyprint(html_content, output_path, template_dir)
    except (OSError, ImportError):
        pass

    return html_path


def _render_html(report_data: ReportData, template_dir: Path) -> str:
    """Fill the Jinja2 HTML template with report data."""
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=True,
    )

    # Custom filters
    env.filters["format_currency"] = _format_currency
    env.filters["format_pct"] = _format_pct
    env.filters["format_number"] = _format_number

    template = env.get_template("report.html")

    return template.render(
        report=report_data,
        cost=report_data.cost_summary,
        tags=report_data.tag_summary,
        charts=report_data.chart_paths,
        ai=report_data.ai_insights,
    )


def _html_to_pdf_playwright(html_content: str, output_path: Path) -> Path:
    """Convert HTML to PDF using Playwright headless Chromium."""
    from playwright.sync_api import sync_playwright

    # Write self-contained HTML to a temp file so Chromium can load it
    self_contained = _embed_images_as_base64(html_content)

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as f:
        f.write(self_contained)
        tmp_path = f.name

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(f"file://{tmp_path}", wait_until="networkidle")
            page.pdf(
                path=str(output_path),
                format="A4",
                print_background=True,
                margin={"top": "2cm", "bottom": "2.5cm", "left": "2cm", "right": "2cm"},
            )
            browser.close()
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return output_path


def _html_to_pdf_weasyprint(html_content: str, output_path: Path, template_dir: Path) -> Path:
    """Convert HTML string to PDF using WeasyPrint."""
    from weasyprint import HTML

    html = HTML(string=html_content, base_url=str(template_dir))
    html.write_pdf(str(output_path))
    return output_path


def _embed_images_as_base64(html_content: str) -> str:
    """Replace file:// image references with inline base64 data URIs."""

    def replace_file_ref(match):
        file_path = match.group(1)
        path = Path(file_path)
        if path.exists():
            data = base64.b64encode(path.read_bytes()).decode("ascii")
            ext = path.suffix.lstrip(".")
            mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "svg": "image/svg+xml"}.get(ext, "image/png")
            return f'src="data:{mime};base64,{data}"'
        return match.group(0)

    return re.sub(r'src="file://([^"]+)"', replace_file_ref, html_content)


def _format_currency(value: float, symbol: str = "$") -> str:
    """Format number as currency: $1,234.56"""
    return f"{symbol}{value:,.2f}"


def _format_pct(value: float) -> str:
    """Format number as percentage: 85.3%"""
    return f"{value:.1f}%"


def _format_number(value: int | float) -> str:
    """Format number with comma separators: 1,234"""
    return f"{value:,}"
