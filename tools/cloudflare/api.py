"""Aegis tools that delegate to Cloudflare's API MCP server.

Pass a Cloudflare API token on each call. The token is sent only as a bearer
credential to the MCP endpoint and is not included in the returned payload.
Future Cloudflare operations can use ``cloudflare_call`` without a new Aegis
tool, or call ``CloudflareMcpClient`` directly from a dedicated module.
"""

from __future__ import annotations

import json
from typing import Any

import requests

from tools.cloudflare.client import CloudflareMcpClient, CloudflareMcpError


def cloudflare_whoami(
    api_token: str = "",
    endpoint: str = "",
    http: requests.Session | None = None,
) -> dict[str, Any]:
    """Return the Cloudflare user or account authenticated by this token."""
    return _client(api_token, endpoint, http).call_tool("whoami", {})


def cloudflare_docs(
    query: str,
    api_token: str = "",
    endpoint: str = "",
    http: requests.Session | None = None,
) -> dict[str, Any]:
    """Search Cloudflare developer documentation."""
    if not (query or "").strip():
        raise CloudflareMcpError("A documentation query is required")
    return _client(api_token, endpoint, http).call_tool("docs", {"query": query})


def cloudflare_search(
    code: str,
    api_token: str = "",
    truncate: bool | None = None,
    endpoint: str = "",
    http: requests.Session | None = None,
) -> dict[str, Any]:
    """Run JavaScript against the Cloudflare OpenAPI spec.

    ``code`` is an async arrow function. It can read ``spec.paths`` and must
    not call the network. Use this to find an endpoint before ``execute``.
    """
    return _client(api_token, endpoint, http).call_tool("search", _code_arguments(code, truncate))


def cloudflare_execute(
    code: str,
    api_token: str = "",
    account_id: str = "",
    truncate: bool | None = None,
    endpoint: str = "",
    http: requests.Session | None = None,
) -> dict[str, Any]:
    """Run JavaScript that calls the Cloudflare API.

    Inside ``code``, call ``cloudflare.request({ method, path })``. Pass
    ``account_id`` for user tokens. Account tokens can omit it.
    """
    arguments = _code_arguments(code, truncate)
    if account_id.strip():
        arguments["account_id"] = account_id.strip()
    return _client(api_token, endpoint, http).call_tool("execute", arguments)


def cloudflare_call(
    tool_name: str,
    arguments_json: str = "{}",
    api_token: str = "",
    endpoint: str = "",
    http: requests.Session | None = None,
) -> dict[str, Any]:
    """Call any tool on the Cloudflare MCP server.

    ``arguments_json`` is a JSON object. Use this for tools added later, or
    for direct endpoint tools when the server is opened with ``?codemode=false``.
    """
    arguments = _parse_arguments(arguments_json)
    return _client(api_token, endpoint, http).call_tool(tool_name, arguments)


def _client(api_token: str, endpoint: str, http: requests.Session | None) -> CloudflareMcpClient:
    return CloudflareMcpClient(api_token, endpoint=endpoint, http=http)


def _code_arguments(code: str, truncate: bool | None) -> dict[str, Any]:
    if not (code or "").strip():
        raise CloudflareMcpError("JavaScript code is required")
    arguments: dict[str, Any] = {"code": code}
    if truncate is not None:
        arguments["truncate"] = truncate
    return arguments


def _parse_arguments(arguments_json: str) -> dict[str, Any]:
    raw = (arguments_json or "").strip() or "{}"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CloudflareMcpError(f"arguments_json must be a JSON object: {exc}") from exc
    if not isinstance(parsed, dict):
        raise CloudflareMcpError("arguments_json must be a JSON object")
    return parsed


def cloudflare_generate_report(
    zone: str,
    days: int = 30,
    output_pdf: str = "",
    output_html: str = "",
    api_token: str = "",
    timezone: str = "SGT",
) -> dict[str, Any]:
    """Generate a comprehensive executive PDF & HTML report for a Cloudflare zone."""
    from tools.cloudflare.report import generate_cloudflare_report

    return generate_cloudflare_report(
        zone_identifier=zone,
        days=days,
        output_pdf=output_pdf,
        output_html=output_html,
        token=api_token,
        timezone=timezone,
    )
