"""Streamable HTTP client for Cloudflare's API MCP server.

Cloudflare exposes the account API at https://mcp.cloudflare.com/mcp through
four tools: ``docs``, ``search``, ``execute``, and ``whoami``. This client
speaks MCP JSON-RPC so Aegis can call those tools, and any later tool on the
same server, with a Cloudflare API token.
"""

from __future__ import annotations

import json
import os
from typing import Any

import requests

DEFAULT_ENDPOINT = "https://mcp.cloudflare.com/mcp"
PROTOCOL_VERSION = "2025-06-18"
_TIMEOUT_SECONDS = 60


class CloudflareMcpError(RuntimeError):
    """Raised when the Cloudflare MCP server cannot complete a call."""


class CloudflareMcpClient:
    """Minimal MCP client for one Cloudflare token and one endpoint."""

    def __init__(
        self,
        api_token: str = "",
        endpoint: str = "",
        http: requests.Session | None = None,
    ) -> None:
        token = (api_token or "").strip() or os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
        if not token:
            raise CloudflareMcpError("Cloudflare API token is required")
        self.api_token = token
        configured = endpoint.strip() or os.getenv("CLOUDFLARE_MCP_URL", "").strip()
        self.endpoint = configured or DEFAULT_ENDPOINT
        self._http = http or requests.Session()
        self._session_id: str | None = None
        self._initialized = False
        self._next_id = 1

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Call one tool on the Cloudflare MCP server and return its content."""
        tool_name = (name or "").strip()
        if not tool_name:
            raise CloudflareMcpError("Cloudflare MCP tool name is required")
        self._ensure_initialized()
        result = self._rpc(
            "tools/call",
            {"name": tool_name, "arguments": arguments or {}},
        )
        return _normalize_tool_result(tool_name, result or {})

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        self._rpc(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "aegis-mcp", "version": "1.0.0"},
            },
        )
        self._notify("notifications/initialized")
        self._initialized = True

    def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any] | None:
        request_id = self._next_id
        self._next_id += 1
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        return self._post(payload, request_id=request_id)

    def _notify(self, method: str) -> None:
        self._post({"jsonrpc": "2.0", "method": method}, request_id=None)

    def _post(self, payload: dict[str, Any], request_id: int | None) -> dict[str, Any] | None:
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": PROTOCOL_VERSION,
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        try:
            response = self._http.post(
                self.endpoint,
                json=payload,
                headers=headers,
                timeout=_TIMEOUT_SECONDS,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            raise CloudflareMcpError(f"Cannot reach Cloudflare MCP at '{self.endpoint}': {exc}") from exc

        session_id = response.headers.get("Mcp-Session-Id") or response.headers.get("mcp-session-id")
        if session_id:
            self._session_id = session_id

        if response.status_code >= 400:
            raise CloudflareMcpError(
                f"Cloudflare MCP returned HTTP {response.status_code}: {_safe_body(response, self.api_token)}"
            )
        if response.status_code == 202 or not response.content:
            return None

        messages = _decode_messages(response)
        if request_id is None:
            return None
        for message in messages:
            if message.get("id") != request_id:
                continue
            if "error" in message:
                error = message["error"]
                detail = error.get("message", error) if isinstance(error, dict) else error
                raise CloudflareMcpError(f"Cloudflare MCP {payload['method']} failed: {detail}")
            result = message.get("result", {})
            return result if isinstance(result, dict) else {"value": result}
        raise CloudflareMcpError(
            f"Cloudflare MCP {payload['method']} returned no result for request {request_id}"
        )


def _decode_messages(response: requests.Response) -> list[dict[str, Any]]:
    content_type = response.headers.get("Content-Type", "")
    if "text/event-stream" in content_type:
        return _parse_sse(response.text)
    try:
        body = response.json()
    except ValueError as exc:
        raise CloudflareMcpError("Cloudflare MCP returned a non-JSON response") from exc
    if isinstance(body, list):
        return [item for item in body if isinstance(item, dict)]
    if isinstance(body, dict):
        return [body]
    raise CloudflareMcpError("Cloudflare MCP returned an unexpected response")


def _parse_sse(body: str) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    data_lines: list[str] = []

    def flush() -> None:
        if not data_lines:
            return
        raw = "\n".join(data_lines).strip()
        data_lines.clear()
        if not raw or raw == "[DONE]":
            return
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return
        if isinstance(parsed, dict):
            messages.append(parsed)

    for line in body.splitlines():
        if line == "":
            flush()
            continue
        if line.startswith(":"):
            continue
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    flush()
    return messages


def _normalize_tool_result(tool_name: str, result: dict[str, Any]) -> dict[str, Any]:
    content = result.get("content") or []
    if not isinstance(content, list):
        content = []
    texts: list[str] = []
    for block in content:
        if isinstance(block, dict) and "text" in block:
            texts.append(str(block.get("text", "")))
    text = "\n".join(texts)
    if result.get("isError"):
        raise CloudflareMcpError(text or f"Cloudflare MCP tool '{tool_name}' failed")
    normalized: dict[str, Any] = {"tool": tool_name, "text": text, "content": content}
    if "structuredContent" in result:
        normalized["structured"] = result["structuredContent"]
    return normalized


def _safe_body(response: requests.Response, api_token: str) -> str:
    text = (response.text or "").replace(api_token, "***")
    text = " ".join(text.split())
    if len(text) > 300:
        return text[:300] + "..."
    return text or response.reason
