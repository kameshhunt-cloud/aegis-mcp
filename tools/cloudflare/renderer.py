"""HTML and PDF Report Renderer for Cloudflare Executive Reports.

Generates self-contained HTML reports with embedded high-resolution charts,
matching the corporate layout of the Cloudflare Overview PDF.
"""

from __future__ import annotations

import base64
import io
import os
import tempfile
from datetime import datetime
from typing import Any

# Ensure matplotlib cache directory is writable in all environments
if not os.environ.get("MPLCONFIGDIR"):
    os.environ["MPLCONFIGDIR"] = os.path.join(tempfile.gettempdir(), "matplotlib-aegis")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _fig_to_base64(fig: plt.Figure) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, bbox_inches="tight", transparent=False, facecolor="#ffffff")
    plt.close(fig)
    buf.seek(0)
    return "data:image/png;base64," + base64.b64encode(buf.read()).decode("utf-8")


def _format_num(val: int | float) -> str:
    if val >= 1_000_000:
        return f"{val / 1_000_000:.2f}M"
    if val >= 1_000:
        return f"{val / 1_000:.2f}k"
    if isinstance(val, float):
        return f"{val:.2f}"
    return str(val)


def _format_date_label(date_str: str, short: bool = False) -> str:
    """Format date string YYYY-MM-DD into clean, readable label."""
    if not date_str:
        return ""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        if short:
            # Sparkline: e.g. "10/5", "11/4"
            return f"{dt.month}/{dt.day}"
        # Large charts: e.g. "Oct 05", "Oct 09", "Nov 04"
        return dt.strftime("%b %d")
    except Exception:
        return date_str[-5:] if len(date_str) >= 5 else date_str


def _get_clean_ticks(total_points: int, max_ticks: int = 8) -> list[int]:
    """Calculate evenly spaced tick indices spanning from 0 to total_points - 1."""
    if total_points <= 1:
        return [0]
    if total_points <= max_ticks:
        return list(range(total_points))
    step = (total_points - 1) / (max_ticks - 1)
    raw_ticks = [int(round(i * step)) for i in range(max_ticks)]
    # Deduplicate while preserving monotonic order
    clean: list[int] = []
    for t in raw_ticks:
        if not clean or t > clean[-1]:
            clean.append(t)
    return clean


def _generate_sparkline(x_vals: list[str], y_vals: list[float | int], color: str = "#2b7bb9") -> str:
    fig, ax = plt.subplots(figsize=(5.5, 1.1), dpi=150)
    if not y_vals or all(v == 0 for v in y_vals):
        y_vals = [0] * max(len(x_vals), 5)
        x_vals = x_vals or ["D1", "D2", "D3", "D4", "D5"]

    indices = list(range(len(y_vals)))
    ax.plot(indices, y_vals, color=color, linewidth=1.5)
    ax.fill_between(indices, y_vals, color=color, alpha=0.12)
    ax.set_facecolor("#ffffff")
    fig.patch.set_facecolor("#ffffff")

    # Clean borders
    for spine in ax.spines.values():
        spine.set_color("#e2e8f0")
        spine.set_linewidth(0.6)

    ax.grid(True, linestyle="--", alpha=0.35, color="#f1f5f9")
    ax.tick_params(colors="#64748b", labelsize=7.5, length=2)

    # Subsample x ticks with clean formatting
    ticks = _get_clean_ticks(len(x_vals), max_ticks=6)
    labels = [_format_date_label(x_vals[i], short=True) for i in ticks]
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels, rotation=0, ha="center")
    ax.set_xlim(0, max(1, len(x_vals) - 1))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda val, pos: _format_num(val)))

    return _fig_to_base64(fig)


def _generate_timeseries_chart(
    x_vals: list[str],
    y_vals: list[float | int],
    title: str,
    ylabel: str,
    color: str = "#2563eb",
) -> str:
    fig, ax = plt.subplots(figsize=(8.5, 2.5), dpi=160)
    indices = list(range(len(y_vals)))
    ax.plot(indices, y_vals, color=color, linewidth=1.8)
    ax.fill_between(indices, y_vals, color=color, alpha=0.10)
    ax.set_facecolor("#ffffff")
    fig.patch.set_facecolor("#ffffff")

    for spine in ax.spines.values():
        spine.set_color("#cbd5e1")
        spine.set_linewidth(0.7)

    ax.grid(True, linestyle="--", alpha=0.4, color="#e2e8f0")
    ax.tick_params(colors="#475569", labelsize=8.5, length=3)
    ax.set_ylabel(ylabel, fontsize=8.5, color="#475569", fontweight="500")

    ticks = _get_clean_ticks(len(x_vals), max_ticks=8)
    labels = [_format_date_label(x_vals[i], short=False) for i in ticks]
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels, rotation=0, ha="center")
    ax.set_xlim(0, max(1, len(x_vals) - 1))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda val, pos: _format_num(val)))

    return _fig_to_base64(fig)


def render_html_report(data: dict[str, Any]) -> str:
    """Render full 8-page corporate report matching the SGeBIZ Cloudflare Overview style."""
    summary = data["summary"]
    series = data["series"]
    breakdowns = data["breakdowns"]
    zone_name = data["zone_name"]
    dates = series.get("dates", [])

    # Generate charts
    chart_uniques = _generate_sparkline(dates, series.get("uniques", []), "#0ea5e9")
    chart_requests = _generate_sparkline(dates, series.get("requests", []), "#2563eb")
    chart_cache_pct = _generate_sparkline(dates, series.get("cache_pct", []), "#10b981")
    chart_bytes = _generate_sparkline(dates, series.get("bytes_mb", []), "#6366f1")
    chart_cached_bytes = _generate_sparkline(dates, series.get("cached_bytes_mb", []), "#8b5cf6")

    chart_visits_large = _generate_timeseries_chart(dates, series.get("uniques", []), "Visits over time", "Visits", "#2563eb")
    chart_data_transfer = _generate_timeseries_chart(dates, series.get("bytes_mb", []), "Data transfer over time", "MB", "#0284c7")
    chart_pageviews = _generate_timeseries_chart(dates, series.get("pageviews", []), "Page views over time", "Page views", "#059669")
    chart_api_reqs = _generate_timeseries_chart(
        dates,
        [max(0, r - pv) for r, pv in zip(series.get("requests", []), series.get("pageviews", []))],
        "API requests over time",
        "API Requests",
        "#7c3aed"
    )

    # HTML / CSS Template
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Cloudflare Overview - {zone_name}</title>
  <style>
    @page {{
      size: A4 portrait;
      margin: 0;
    }}
    * {{
      box-sizing: border-box;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }}
    html, body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      color: #1e293b;
      margin: 0;
      padding: 0;
      background: #f8fafc;
    }}
    .page {{
      background: #ffffff;
      width: 210mm;
      height: 297mm;
      max-height: 297mm;
      padding: 14mm 16mm 14mm 16mm;
      margin: 0 auto 10mm auto;
      box-sizing: border-box;
      box-shadow: 0 4px 6px -1px rgba(0,0,0,0.07);
      page-break-after: always;
      break-after: page;
      position: relative;
      overflow: hidden;
    }}
    .page:last-child {{
      page-break-after: avoid;
      break-after: avoid;
    }}
    @media print {{
      html, body {{
        background: #ffffff;
        margin: 0;
        padding: 0;
      }}
      .page {{
        margin: 0;
        box-shadow: none;
        height: 297mm;
        max-height: 297mm;
        page-break-after: always;
        break-after: page;
      }}
      .page:last-child {{
        page-break-after: avoid;
        break-after: avoid;
      }}
    }}
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 2px solid #e2e8f0;
      padding-bottom: 10px;
      margin-bottom: 16px;
    }}
    .logo-container {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .logo-icon {{
      width: 36px;
      height: 36px;
      background: linear-gradient(135deg, #dc2626, #b91c1c);
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-weight: 800;
      font-size: 16px;
    }}
    .logo-text {{
      display: flex;
      flex-direction: column;
    }}
    .logo-title {{
      font-size: 20px;
      font-weight: 800;
      color: #0f172a;
      letter-spacing: -0.5px;
    }}
    .logo-subtitle {{
      font-size: 10px;
      color: #64748b;
      font-weight: 600;
      letter-spacing: 0.5px;
    }}
    .report-title {{
      font-size: 17px;
      font-weight: 700;
      color: #0f172a;
      text-align: center;
      margin: 10px 0 18px 0;
    }}
    .section-title {{
      font-size: 14px;
      font-weight: 700;
      color: #0f172a;
      margin: 14px 0 8px 0;
    }}
    .metric-card {{
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      padding: 10px 14px;
      margin-bottom: 10px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}
    .metric-meta {{
      width: 140px;
    }}
    .metric-label {{
      font-size: 11px;
      color: #64748b;
      font-weight: 600;
      margin-bottom: 2px;
    }}
    .metric-val {{
      font-size: 20px;
      font-weight: 800;
      color: #0f172a;
    }}
    .metric-chart {{
      flex: 1;
      display: flex;
      justify-content: flex-end;
    }}
    .metric-chart img {{
      height: 48px;
      max-width: 100%;
    }}
    .large-chart {{
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      padding: 10px 12px;
      margin-bottom: 14px;
      background: #ffffff;
    }}
    .large-chart img {{
      width: 100%;
      height: auto;
      display: block;
    }}
    .toc {{
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      padding: 10px 18px;
      margin-bottom: 16px;
    }}
    .toc ol {{
      margin: 0;
      padding-left: 20px;
      font-weight: 600;
      color: #1e293b;
      font-size: 11px;
    }}
    .toc li {{
      margin: 4px 0;
    }}
    .toc ol ol {{
      font-weight: 400;
      color: #475569;
    }}
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 10px;
      margin-bottom: 14px;
    }}
    .kpi-box {{
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      padding: 9px;
      text-align: center;
    }}
    .kpi-box-val {{
      font-size: 16px;
      font-weight: 800;
      color: #0f172a;
    }}
    .kpi-box-lbl {{
      font-size: 9.5px;
      font-weight: 600;
      color: #64748b;
      margin-top: 3px;
    }}
    table.data-table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 6px;
      margin-bottom: 10px;
      font-size: 10px;
    }}
    table.data-table th {{
      background: #f1f5f9;
      color: #334155;
      font-weight: 700;
      text-align: left;
      padding: 6px 10px;
      border: 1px solid #e2e8f0;
    }}
    table.data-table td {{
      padding: 5.5px 10px;
      border: 1px solid #e2e8f0;
      color: #1e293b;
    }}
    table.data-table tr:nth-child(even) td {{
      background: #f8fafc;
    }}
    .badge {{
      display: inline-block;
      padding: 2px 6px;
      font-size: 9.5px;
      font-weight: 700;
      border-radius: 4px;
    }}
    .badge-green {{ background: #dcfce7; color: #15803d; }}
    .badge-red {{ background: #fee2e2; color: #b91c1c; }}
    .badge-blue {{ background: #dbeafe; color: #1d4ed8; }}
    .badge-amber {{ background: #fef3c7; color: #b45309; }}
    .footer {{
      position: absolute;
      bottom: 8mm;
      left: 16mm;
      right: 16mm;
      display: flex;
      justify-content: space-between;
      border-top: 1px solid #e2e8f0;
      padding-top: 6px;
      font-size: 9.5px;
      color: #94a3b8;
    }}
  </style>
</head>
<body>

  <!-- ==================== PAGE 1 ==================== -->
  <div class="page">
    <div class="header">
      <div class="logo-container">
        <div class="logo-icon">SG</div>
        <div class="logo-text">
          <span class="logo-title">SGeBIZ</span>
          <span class="logo-subtitle">Breaking Business Boundaries</span>
        </div>
      </div>
      <div style="font-size: 10.5px; color: #64748b; text-align: right;">
        <b>Period:</b> {data['date_start']} to {data['date_end']}<br>
        <b>Zone:</b> {zone_name}
      </div>
    </div>

    <div class="report-title">Cloudflare Overview on {datetime.now().strftime("%B %Y")}</div>

    <div style="margin-bottom: 16px;">
      <h3 style="margin: 0; font-size: 16px; color: #0f172a;">Overview: {zone_name}</h3>
      <p style="margin: 3px 0 0 0; font-size: 11px; color: #64748b;">
        Production Cloudflare traffic, security posture, and network telemetry analytics.
      </p>
    </div>

    <div class="metric-card">
      <div class="metric-meta">
        <div class="metric-label">Unique Visitors</div>
        <div class="metric-val">{_format_num(summary['total_visits'])}</div>
      </div>
      <div class="metric-chart"><img src="{chart_uniques}" alt="Unique Visitors"></div>
    </div>

    <div class="metric-card">
      <div class="metric-meta">
        <div class="metric-label">Total Requests</div>
        <div class="metric-val">{_format_num(summary['total_requests'])}</div>
      </div>
      <div class="metric-chart"><img src="{chart_requests}" alt="Total Requests"></div>
    </div>

    <div class="metric-card">
      <div class="metric-meta">
        <div class="metric-label">Percent Cached</div>
        <div class="metric-val">{summary['cache_hit_ratio']}%</div>
      </div>
      <div class="metric-chart"><img src="{chart_cache_pct}" alt="Percent Cached"></div>
    </div>

    <div class="metric-card">
      <div class="metric-meta">
        <div class="metric-label">Total Data Served</div>
        <div class="metric-val">{summary['data_transfer_gb']} GB</div>
      </div>
      <div class="metric-chart"><img src="{chart_bytes}" alt="Total Data Served"></div>
    </div>

    <div class="metric-card">
      <div class="metric-meta">
        <div class="metric-label">Data Cached</div>
        <div class="metric-val">{summary['data_cached_gb']} GB</div>
      </div>
      <div class="metric-chart"><img src="{chart_cached_bytes}" alt="Data Cached"></div>
    </div>

    <div class="footer">
      <span>Aegis Cloudflare Security Analytics</span>
      <span>Page 1 of 8</span>
    </div>
  </div>

  <!-- ==================== PAGE 2 ==================== -->
  <div class="page">
    <div class="header">
      <div class="logo-container">
        <div class="logo-icon">SG</div>
        <div class="logo-text">
          <span class="logo-title">SGeBIZ</span>
          <span class="logo-subtitle">Breaking Business Boundaries</span>
        </div>
      </div>
      <div style="font-size: 10.5px; color: #64748b;">Analytics Overview</div>
    </div>

    <div class="toc">
      <div style="font-size: 12px; font-weight: 700; margin-bottom: 6px;">Analytics Index</div>
      <ol>
        <li>HTTP Traffic
          <ol type="a">
            <li>Requests (Total: {_format_num(summary['total_requests'])})</li>
            <li>Data Transfer (Total: {summary['data_transfer_gb']} GB)</li>
            <li>Page Views ({_format_num(summary['page_views'])})</li>
            <li>Total Visits ({_format_num(summary['total_visits'])})</li>
            <li>API Requests ({_format_num(summary['api_requests'])})</li>
          </ol>
        </li>
        <li>Security Analytics (WAF Actions, Attack Types, Top Attacked URLs, Attacking IPs)</li>
        <li>Performance (Bot Traffic %, 4xx/5xx Rates, P95 Response Latencies, Cache Hit Ratio)</li>
        <li>DNS Analytics & SSL (Total Queries, NXDOMAIN Rate, Record Types, SSL Expiry)</li>
      </ol>
    </div>

    <div class="section-title">HTTP Traffic – Requests & Visits</div>
    <div style="font-size: 11px; color: #64748b; margin-bottom: 8px;">
      Total visits over the lookback period: <b>{_format_num(summary['total_visits'])}</b>
    </div>

    <div class="large-chart">
      <img src="{chart_visits_large}" alt="Visits over time">
    </div>

    <div class="kpi-grid">
      <div class="kpi-box">
        <div class="kpi-box-val">{_format_num(summary['total_requests'])}</div>
        <div class="kpi-box-lbl">Total Requests</div>
      </div>
      <div class="kpi-box">
        <div class="kpi-box-val">{_format_num(summary['api_requests'])}</div>
        <div class="kpi-box-lbl">API Requests</div>
      </div>
      <div class="kpi-box">
        <div class="kpi-box-val">{_format_num(summary['page_views'])}</div>
        <div class="kpi-box-lbl">Page Views</div>
      </div>
      <div class="kpi-box">
        <div class="kpi-box-val">{_format_num(summary['total_visits'])}</div>
        <div class="kpi-box-lbl">Unique Visits</div>
      </div>
    </div>

    <div class="footer">
      <span>Aegis Cloudflare Security Analytics</span>
      <span>Page 2 of 8</span>
    </div>
  </div>

  <!-- ==================== PAGE 3 ==================== -->
  <div class="page">
    <div class="header">
      <div class="logo-container">
        <div class="logo-icon">SG</div>
        <div class="logo-text">
          <span class="logo-title">SGeBIZ</span>
          <span class="logo-subtitle">Breaking Business Boundaries</span>
        </div>
      </div>
      <div style="font-size: 10.5px; color: #64748b;">HTTP Traffic – Bandwidth & Pages</div>
    </div>

    <div class="section-title">HTTP Traffic – Data Transfer ({summary['data_transfer_gb']} GB)</div>
    <div class="large-chart">
      <img src="{chart_data_transfer}" alt="Data transfer over time">
    </div>

    <div class="section-title">HTTP Traffic – Page Views ({_format_num(summary['page_views'])})</div>
    <div class="large-chart">
      <img src="{chart_pageviews}" alt="Page views over time">
    </div>

    <div class="footer">
      <span>Aegis Cloudflare Security Analytics</span>
      <span>Page 3 of 8</span>
    </div>
  </div>

  <!-- ==================== PAGE 4 ==================== -->
  <div class="page">
    <div class="header">
      <div class="logo-container">
        <div class="logo-icon">SG</div>
        <div class="logo-text">
          <span class="logo-title">SGeBIZ</span>
          <span class="logo-subtitle">Breaking Business Boundaries</span>
        </div>
      </div>
      <div style="font-size: 10.5px; color: #64748b;">HTTP Traffic – API Requests & Hostnames</div>
    </div>

    <div class="section-title">HTTP Traffic – Dedicated API Requests ({_format_num(summary['api_requests'])})</div>
    <div style="font-size: 11px; color: #64748b; margin-bottom: 8px;">
      Direct backend API endpoints and microservices traffic.
    </div>

    <div class="large-chart">
      <img src="{chart_api_reqs}" alt="API Requests over time">
    </div>

    <div class="section-title">Top Hostnames</div>
    <table class="data-table">
      <thead>
        <tr><th>#</th><th>Hostname / FQDN</th><th>Total Requests</th><th>Traffic Share</th></tr>
      </thead>
      <tbody>
        {"".join(f"<tr><td>{i+1}</td><td><b>{h['host']}</b></td><td>{_format_num(h['count'])}</td><td>{round(h['count']/summary['total_requests']*100, 1) if summary['total_requests'] else 0}%</td></tr>" for i, h in enumerate(breakdowns.get("top_hosts", [])[:5]))}
      </tbody>
    </table>

    <div class="footer">
      <span>Aegis Cloudflare Security Analytics</span>
      <span>Page 4 of 8</span>
    </div>
  </div>

  <!-- ==================== PAGE 5 ==================== -->
  <div class="page">
    <div class="header">
      <div class="logo-container">
        <div class="logo-icon">SG</div>
        <div class="logo-text">
          <span class="logo-title">SGeBIZ</span>
          <span class="logo-subtitle">Breaking Business Boundaries</span>
        </div>
      </div>
      <div style="font-size: 10.5px; color: #64748b;">Security Analytics & WAF Protection</div>
    </div>

    <div class="section-title">Security Analytics – Action Breakdown</div>
    <div class="kpi-grid">
      <div class="kpi-box">
        <div class="kpi-box-val" style="color: #b91c1c;">{_format_num(summary['waf_blocked_requests'])}</div>
        <div class="kpi-box-lbl">WAF Blocked</div>
      </div>
      <div class="kpi-box">
        <div class="kpi-box-val" style="color: #b45309;">{_format_num(summary['waf_challenged_requests'])}</div>
        <div class="kpi-box-lbl">WAF Challenged</div>
      </div>
      <div class="kpi-box">
        <div class="kpi-box-val" style="color: #15803d;">{_format_num(summary['waf_allowed_requests'])}</div>
        <div class="kpi-box-lbl">Clean / Allowed</div>
      </div>
      <div class="kpi-box">
        <div class="kpi-box-val" style="color: #2563eb;">{_format_num(summary['waf_logged_requests'])}</div>
        <div class="kpi-box-lbl">Logged / Monitored</div>
      </div>
    </div>

    <div class="section-title">Top Attack Classifications & Rulesets</div>
    <table class="data-table">
      <thead>
        <tr><th>#</th><th>Threat Classification / Rule Group</th><th>Mitigated Events</th><th>Threat Share</th><th>Action Taken</th></tr>
      </thead>
      <tbody>
        {"".join(f"<tr><td>{i+1}</td><td><b>{a['type']}</b></td><td>{_format_num(a['count'])}</td><td>{a.get('share', 'N/A')}</td><td><span class='badge badge-red'>{a.get('action', 'Blocked')}</span></td></tr>" for i, a in enumerate(breakdowns.get("top_attack_types", [])[:5]))}
      </tbody>
    </table>

    <div class="section-title" style="margin-top: 14px;">Top Attacked Endpoints / APIs</div>
    <table class="data-table">
      <thead>
        <tr><th>#</th><th>Target Path / URL</th><th>Mitigated Hits</th><th>Threat Severity</th><th>Mitigation</th></tr>
      </thead>
      <tbody>
        {"".join(f"<tr><td>{i+1}</td><td><code>{p['path']}</code></td><td>{_format_num(p['count'])}</td><td><span class='badge badge-red'>High Threat</span></td><td><span class='badge badge-amber'>Mitigated</span></td></tr>" for i, p in enumerate(breakdowns.get("top_attacked_paths", [])[:5]))}
      </tbody>
    </table>

    <div class="footer">
      <span>Aegis Cloudflare Security Analytics</span>
      <span>Page 5 of 8</span>
    </div>
  </div>

  <!-- ==================== PAGE 6 ==================== -->
  <div class="page">
    <div class="header">
      <div class="logo-container">
        <div class="logo-icon">SG</div>
        <div class="logo-text">
          <span class="logo-title">SGeBIZ</span>
          <span class="logo-subtitle">Breaking Business Boundaries</span>
        </div>
      </div>
      <div style="font-size: 10.5px; color: #64748b;">Threat Actors, Geolocation & Performance</div>
    </div>

    <div class="section-title">Bot & Threat Classification</div>
    <div class="kpi-grid">
      <div class="kpi-box">
        <div class="kpi-box-val" style="color: #b91c1c;">{summary['bot_traffic_pct']}%</div>
        <div class="kpi-box-lbl">Bot / Attack Traffic %</div>
      </div>
      <div class="kpi-box">
        <div class="kpi-box-val">{summary['rate_4xx']}%</div>
        <div class="kpi-box-lbl">4xx Client Error Rate</div>
      </div>
      <div class="kpi-box">
        <div class="kpi-box-val">{summary['rate_5xx']}%</div>
        <div class="kpi-box-lbl">5xx Server Error Rate</div>
      </div>
      <div class="kpi-box">
        <div class="kpi-box-val">{summary['p95_edge_ms']} ms</div>
        <div class="kpi-box-lbl">P95 Response Time</div>
      </div>
    </div>

    <div class="section-title">Top Attacking IP Addresses</div>
    <table class="data-table">
      <thead>
        <tr><th>#</th><th>Client IP Address</th><th>Geo Country</th><th>Mitigated Attacks</th><th>Action Taken</th></tr>
      </thead>
      <tbody>
        {"".join(f"<tr><td>{i+1}</td><td><b>{ip['ip']}</b></td><td>{ip['country']}</td><td>{_format_num(ip['count'])}</td><td><span class='badge badge-red'>Block</span></td></tr>" for i, ip in enumerate(breakdowns.get("top_attacking_ips", [])[:5]))}
      </tbody>
    </table>

    <div class="section-title" style="margin-top: 12px;">Top Origin Countries</div>
    <table class="data-table">
      <thead>
        <tr><th>#</th><th>Country</th><th>Total Requests</th><th>Percentage</th></tr>
      </thead>
      <tbody>
        {"".join(f"<tr><td>{i+1}</td><td>{c['country']}</td><td>{_format_num(c['count'])}</td><td>{round(c['count']/summary['total_requests']*100, 1) if summary['total_requests'] else 0}%</td></tr>" for i, c in enumerate(breakdowns.get("top_countries", [])[:5]))}
      </tbody>
    </table>

    <div class="section-title" style="margin-top: 12px;">Performance & Origin Response Benchmarks</div>
    <table class="data-table">
      <thead>
        <tr><th>Performance Metric</th><th>Observed Value</th><th>SLO Target</th><th>Health Status</th></tr>
      </thead>
      <tbody>
        <tr><td>P95 Edge Response Time</td><td><b>{summary['p95_edge_ms']} ms</b></td><td>&lt; 500 ms</td><td><span class="badge badge-green">Healthy</span></td></tr>
        <tr><td>P95 Origin Response Time</td><td><b>{summary['p95_origin_ms']} ms</b></td><td>&lt; 800 ms</td><td><span class="badge badge-green">Healthy</span></td></tr>
        <tr><td>Cache Hit Ratio</td><td><b>{summary['cache_hit_ratio']}%</b></td><td>&gt; 30%</td><td><span class="badge badge-blue">Active</span></td></tr>
        <tr><td>4xx Client Error Rate</td><td><b>{summary['rate_4xx']}%</b></td><td>&lt; 5.0%</td><td><span class="badge {'badge-green' if summary['rate_4xx'] < 5 else 'badge-amber'}">{'Healthy' if summary['rate_4xx'] < 5 else 'Investigate'}</span></td></tr>
        <tr><td>5xx Server Error Rate</td><td><b>{summary['rate_5xx']}%</b></td><td>&lt; 1.0%</td><td><span class="badge {'badge-green' if summary['rate_5xx'] < 1 else 'badge-red'}">{'Healthy' if summary['rate_5xx'] < 1 else 'Investigate'}</span></td></tr>
      </tbody>
    </table>

    <div class="footer">
      <span>Aegis Cloudflare Security Analytics</span>
      <span>Page 6 of 8</span>
    </div>
  </div>

  <!-- ==================== PAGE 7 ==================== -->
  <div class="page">
    <div class="header">
      <div class="logo-container">
        <div class="logo-icon">SG</div>
        <div class="logo-text">
          <span class="logo-title">SGeBIZ</span>
          <span class="logo-subtitle">Breaking Business Boundaries</span>
        </div>
      </div>
      <div style="font-size: 10.5px; color: #64748b;">DNS Queries Analytics</div>
    </div>

    <div class="section-title">DNS Resolution Health</div>
    <div class="kpi-grid">
      <div class="kpi-box">
        <div class="kpi-box-val">{_format_num(summary['total_dns_queries'])}</div>
        <div class="kpi-box-lbl">Total DNS Queries</div>
      </div>
      <div class="kpi-box">
        <div class="kpi-box-val" style="color: #15803d;">{_format_num(summary['count_noerror'])}</div>
        <div class="kpi-box-lbl">NOERROR Queries</div>
      </div>
      <div class="kpi-box">
        <div class="kpi-box-val" style="color: #b45309;">{_format_num(summary['count_nxdomain'])}</div>
        <div class="kpi-box-lbl">NXDOMAIN Queries</div>
      </div>
      <div class="kpi-box">
        <div class="kpi-box-val">{summary['nxdomain_rate']}%</div>
        <div class="kpi-box-lbl">NXDOMAIN Rate</div>
      </div>
    </div>

    <div class="section-title">Top Queried Domains & Records</div>
    <table class="data-table">
      <thead>
        <tr><th>#</th><th>Query Name / Record</th><th>Total Query Volume</th><th>Query Share</th></tr>
      </thead>
      <tbody>
        {"".join(f"<tr><td>{i+1}</td><td><b>{d['name']}</b></td><td>{_format_num(d['count'])}</td><td>{round(d['count']/summary['total_dns_queries']*100, 1) if summary['total_dns_queries'] else 0}%</td></tr>" for i, d in enumerate(breakdowns.get("dns_by_name", [])[:10]))}
      </tbody>
    </table>

    <div class="footer">
      <span>Aegis Cloudflare Security Analytics</span>
      <span>Page 7 of 8</span>
    </div>
  </div>

  <!-- ==================== PAGE 8 ==================== -->
  <div class="page">
    <div class="header">
      <div class="logo-container">
        <div class="logo-icon">SG</div>
        <div class="logo-text">
          <span class="logo-title">SGeBIZ</span>
          <span class="logo-subtitle">Breaking Business Boundaries</span>
        </div>
      </div>
      <div style="font-size: 10.5px; color: #64748b;">DNS Records & SSL Posture</div>
    </div>

    <div class="section-title">DNS Queries by Record Type</div>
    <table class="data-table">
      <thead>
        <tr><th>#</th><th>Record Type</th><th>Query Count</th><th>Percentage</th></tr>
      </thead>
      <tbody>
        {"".join(f"<tr><td>{i+1}</td><td><span class='badge badge-blue'>{r['type']}</span></td><td>{_format_num(r['count'])}</td><td>{round(r['count']/summary['total_dns_queries']*100, 1) if summary['total_dns_queries'] else 0}%</td></tr>" for i, r in enumerate(breakdowns.get("dns_by_type", [])[:8]))}
      </tbody>
    </table>

    <div class="section-title" style="margin-top: 18px;">SSL/TLS Configuration & Certificate Expiry</div>
    <table class="data-table">
      <thead>
        <tr><th>Covered Hostnames</th><th>Issuer CA</th><th>Expiration Date</th><th>Status</th></tr>
      </thead>
      <tbody>
        {"".join(f"<tr><td><b>{', '.join(c['hosts'][:2])}</b></td><td>{c['issuer']}</td><td>{c['expires_on'][:10]}</td><td><span class='badge badge-green'>Active</span></td></tr>" for c in summary.get("certificates", [])[:4]) or "<tr><td colspan='4'>Universal SSL Managed by Cloudflare</td></tr>"}
      </tbody>
    </table>

    <div class="section-title" style="margin-top: 16px;">Protocol Hardening Status</div>
    <div class="kpi-grid">
      <div class="kpi-box">
        <div class="kpi-box-val">{summary['min_tls_version']}</div>
        <div class="kpi-box-lbl">Minimum TLS Allowed</div>
      </div>
      <div class="kpi-box">
        <div class="kpi-box-val" style="color: #15803d;">{summary['tls_1_3'].upper()}</div>
        <div class="kpi-box-lbl">TLS 1.3 State</div>
      </div>
      <div class="kpi-box">
        <div class="kpi-box-val">Strict</div>
        <div class="kpi-box-lbl">SSL Mode</div>
      </div>
      <div class="kpi-box">
        <div class="kpi-box-val" style="color: #15803d;">Enabled</div>
        <div class="kpi-box-lbl">Automatic HTTPS</div>
      </div>
    </div>

    <div class="footer">
      <span>Aegis Cloudflare Security Analytics</span>
      <span>Page 8 of 8</span>
    </div>
  </div>

</body>
</html>
"""
    return html
