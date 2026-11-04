import json
import unittest
from unittest.mock import MagicMock

from tools.cloudflare.api import (
    cloudflare_call,
    cloudflare_docs,
    cloudflare_execute,
    cloudflare_search,
    cloudflare_whoami,
)
from tools.cloudflare.client import CloudflareMcpClient, CloudflareMcpError


def _response(payload: dict | str, content_type: str = "application/json", status: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.headers = {"Content-Type": content_type}
    response.content = b"x"
    response.reason = "OK"
    if isinstance(payload, str):
        response.text = payload
        response.json.side_effect = ValueError("not json")
    else:
        response.text = json.dumps(payload)
        response.json.return_value = payload
    return response


def _session_for(*responses: MagicMock) -> MagicMock:
    queued = list(responses)
    session = MagicMock()
    session.post.side_effect = queued
    return session


def _accepted() -> MagicMock:
    response = _response("", status=202)
    response.content = b""
    return response


def _ok(request_id: int, result: dict, session_id: str = "") -> MagicMock:
    response = _response({"jsonrpc": "2.0", "id": request_id, "result": result})
    if session_id:
        response.headers["Mcp-Session-Id"] = session_id
    return response


class TestCloudflareMcpClient(unittest.TestCase):
    def test_initialize_then_call_tool(self) -> None:
        session = _session_for(
            _ok(1, {"protocolVersion": "2025-06-18"}, session_id="sess-1"),
            _accepted(),
            _ok(2, {"content": [{"type": "text", "text": "user:abc"}]}),
        )
        client = CloudflareMcpClient("cf-token", endpoint="https://mcp.example/mcp", http=session)
        result = client.call_tool("whoami", {})

        self.assertEqual(result["tool"], "whoami")
        self.assertEqual(result["text"], "user:abc")
        self.assertEqual(session.post.call_count, 3)
        tool_call = session.post.call_args_list[2]
        self.assertEqual(tool_call.kwargs["headers"]["Authorization"], "Bearer cf-token")
        self.assertEqual(tool_call.kwargs["headers"]["Mcp-Session-Id"], "sess-1")
        self.assertEqual(tool_call.kwargs["json"]["method"], "tools/call")
        self.assertNotIn("cf-token", json.dumps(result))

    def test_reads_sse_result(self) -> None:
        sse = "\n".join(
            [
                "event: message",
                'data: {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-06-18"}}',
                "",
                ": keep-alive",
                "",
                "event: message",
                'data: {"jsonrpc":"2.0","id":2,"result":{"content":[{"type":"text","text":"docs hit"}]}}',
                "",
            ]
        )
        session = _session_for(
            _response('data: {"jsonrpc":"2.0","id":1,"result":{}}\n\n', "text/event-stream"),
            _accepted(),
            _response(sse, "text/event-stream"),
        )
        client = CloudflareMcpClient("cf-token", http=session)
        result = client.call_tool("docs", {"query": "waf"})
        self.assertEqual(result["text"], "docs hit")

    def test_tool_error_raises(self) -> None:
        session = _session_for(
            _ok(1, {}),
            _accepted(),
            _ok(2, {"isError": True, "content": [{"type": "text", "text": "denied"}]}),
        )
        client = CloudflareMcpClient("cf-token", http=session)
        with self.assertRaises(CloudflareMcpError) as caught:
            client.call_tool("execute", {"code": "async () => 1"})
        self.assertIn("denied", str(caught.exception))

    def test_http_error_hides_token(self) -> None:
        denied = _response({"error": "bad cf-token"}, status=401)
        session = _session_for(denied)
        client = CloudflareMcpClient("cf-token", http=session)
        with self.assertRaises(CloudflareMcpError) as caught:
            client.call_tool("whoami")
        self.assertNotIn("cf-token", str(caught.exception))
        self.assertIn("401", str(caught.exception))

    def test_missing_token_raises(self) -> None:
        with unittest.mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(CloudflareMcpError):
                CloudflareMcpClient("  ")

    def test_token_from_env_fallback(self) -> None:
        with unittest.mock.patch.dict("os.environ", {"CLOUDFLARE_API_TOKEN": "env-token"}):
            client = CloudflareMcpClient("")
            self.assertEqual(client.api_token, "env-token")


class TestCloudflareTools(unittest.TestCase):
    def _client_session(self, text: str, structured: dict | None = None) -> MagicMock:
        result: dict = {"content": [{"type": "text", "text": text}]}
        if structured is not None:
            result["structuredContent"] = structured
        return _session_for(
            _ok(1, {}),
            _accepted(),
            _ok(2, result),
        )

    def test_execute_sends_account_and_code(self) -> None:
        session = self._client_session('{"success":true}')
        cloudflare_execute(
            "async () => cloudflare.request({method:'GET', path:'/zones'})",
            "cf-token",
            account_id="acct-1",
            truncate=False,
            http=session,
        )
        arguments = session.post.call_args_list[2].kwargs["json"]["params"]["arguments"]
        self.assertEqual(arguments["account_id"], "acct-1")
        self.assertFalse(arguments["truncate"])
        self.assertIn("cloudflare.request", arguments["code"])

    def test_search_omits_empty_options(self) -> None:
        session = self._client_session("[]")
        cloudflare_search("async () => Object.keys(spec.paths)", "cf-token", http=session)
        arguments = session.post.call_args_list[2].kwargs["json"]["params"]["arguments"]
        self.assertEqual(set(arguments), {"code"})

    def test_docs_requires_query(self) -> None:
        with self.assertRaises(CloudflareMcpError):
            cloudflare_docs("  ", "cf-token")

    def test_call_parses_arguments(self) -> None:
        session = self._client_session("ok", {"results": []})
        result = cloudflare_call("docs", '{"query":"waf rules"}', "cf-token", http=session)
        params = session.post.call_args_list[2].kwargs["json"]["params"]
        self.assertEqual(params["name"], "docs")
        self.assertEqual(params["arguments"], {"query": "waf rules"})
        self.assertEqual(result["structured"], {"results": []})

    def test_call_rejects_non_object_arguments(self) -> None:
        with self.assertRaises(CloudflareMcpError):
            cloudflare_call("docs", "[]", "cf-token")

    def test_whoami(self) -> None:
        session = self._client_session('{"id":"account:1"}')
        result = cloudflare_whoami("cf-token", endpoint="https://mcp.example/mcp", http=session)
        self.assertEqual(session.post.call_args_list[0].args[0], "https://mcp.example/mcp")
        self.assertIn("account:1", result["text"])


if __name__ == "__main__":
    unittest.main()
