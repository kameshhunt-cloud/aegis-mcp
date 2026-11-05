"""Cloudflare Executive Report Generator.

Orchestrates data fetching, HTML rendering, and PDF compilation for Cloudflare zones.
Can be invoked as a library, an MCP tool, or via command-line interface.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from tools.cloudflare.analytics import fetch_zone_report_data
from tools.cloudflare.renderer import render_html_report


def _find_browser_executable() -> str | None:
    """Find a headless-capable browser binary (Chrome or Edge)."""
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome Beta\Application\chrome.exe",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c

    for cmd in ["chrome", "google-chrome", "chromium", "msedge", "edge"]:
        path = shutil.which(cmd)
        if path:
            return path
    return None


def generate_cloudflare_report(
    zone_identifier: str,
    days: int = 30,
    output_pdf: str = "",
    output_html: str = "",
    token: str = "",
    timezone: str = "SGT",
) -> dict[str, Any]:
    """Generate a comprehensive executive PDF & HTML report for a Cloudflare zone."""
    # 1. Fetch data
    report_data = fetch_zone_report_data(zone_identifier, token=token, days=days, tz_name=timezone)
    zone_name = report_data["zone_name"]

    # 2. Render HTML
    html_content = render_html_report(report_data)

    # 3. Determine file paths
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    timestamp = report_data["date_end"].replace("-", "")
    html_file = Path(output_html) if output_html else reports_dir / f"{zone_name}_cloudflare_overview_{timestamp}.html"
    pdf_file = Path(output_pdf) if output_pdf else reports_dir / f"{zone_name}_cloudflare_overview_{timestamp}.pdf"

    html_file.write_text(html_content, encoding="utf-8")

    # 4. Compile PDF via headless browser
    pdf_generated = False
    browser_exe = _find_browser_executable()
    if browser_exe:
        abs_html = os.path.abspath(str(html_file))
        abs_pdf = os.path.abspath(str(pdf_file))
        cmd = [
            browser_exe,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--no-pdf-header-footer",
            "--run-all-compositor-stages-before-draw",
            f"--print-to-pdf={abs_pdf}",
            abs_html,
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            if res.returncode == 0 and os.path.isfile(abs_pdf):
                pdf_generated = True
        except Exception:
            pdf_generated = False

    return {
        "status": "success",
        "zone_name": zone_name,
        "zone_id": report_data["zone_id"],
        "period": f"{report_data['date_start']} to {report_data['date_end']} ({days} days)",
        "html_report": str(html_file.resolve()),
        "pdf_report": str(pdf_file.resolve()) if pdf_generated else None,
        "pdf_generated": pdf_generated,
        "summary": report_data["summary"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Cloudflare Executive Overview Report")
    parser.add_argument("--zone", required=True, help="Zone name (e.g. sgebiz.com) or Zone ID")
    parser.add_argument("--days", type=int, default=30, help="Lookback window in days (default: 30)")
    parser.add_argument("--output-pdf", default="", help="Custom PDF output path")
    parser.add_argument("--output-html", default="", help="Custom HTML output path")
    parser.add_argument("--token", default="", help="Cloudflare API token (or set CLOUDFLARE_API_TOKEN)")
    parser.add_argument("--tz", "--timezone", default="SGT", help="Timezone label (default: SGT)")

    args = parser.parse_args()

    # Load .env if present
    env_file = ".env"
    if os.path.isfile(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("'\""))

    result = generate_cloudflare_report(
        zone_identifier=args.zone,
        days=args.days,
        output_pdf=args.output_pdf,
        output_html=args.output_html,
        token=args.token,
        timezone=args.tz,
    )

    print(f"\nReport Generated Successfully!")
    print(f"Zone: {result['zone_name']} ({result['zone_id']})")
    print(f"Period: {result['period']}")
    print(f"HTML Report: {result['html_report']}")
    if result["pdf_report"]:
        print(f"PDF Report:  {result['pdf_report']}")
    else:
        print("PDF generation: browser not available or skipped.")


if __name__ == "__main__":
    main()

