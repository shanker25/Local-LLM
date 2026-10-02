"""Unit tests for the web tools.

No test makes a real network call. urllib.request is exercised via a
mock OpenerDirector that returns controlled byte streams and headers.
"""

from __future__ import annotations

import io
import unittest
import urllib.error
import urllib.request
from typing import Any

from src.tools.web import (
    FetchUrlTool,
    WebSearchTool,
    html_to_text,
)


# ---- fake response / opener -------------------------------------------

class _FakeResponse:
    def __init__(self, body: bytes, status: int = 200, headers: dict | None = None) -> None:
        self._body = io.BytesIO(body)
        self.status = status
        self.headers = _FakeHeaders(headers or {})

    def read(self, n: int = -1) -> bytes:
        return self._body.read(n)

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc: Any) -> None:
        return None


class _FakeHeaders:
    def __init__(self, data: dict[str, str]) -> None:
        self._data = {k.lower(): v for k, v in data.items()}

    def get(self, key: str, default: str | None = None) -> str | None:
        return self._data.get(key.lower(), default)


class _FakeOpener:
    """Minimal stand-in for an OpenerDirector."""

    def __init__(self, response: _FakeResponse | Exception) -> None:
        self._response = response

    def open(self, req, timeout=None):  # noqa: ANN001
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


# ---- html_to_text ------------------------------------------------------

class HtmlToTextTests(unittest.TestCase):
    def test_strips_tags(self) -> None:
        self.assertEqual(html_to_text("<p>Hello</p>"), "Hello")

    def test_keeps_text_from_nested_tags(self) -> None:
        out = html_to_text("<div><span>a</span> <span>b</span></div>")
        self.assertIn("a", out)
        self.assertIn("b", out)

    def test_strips_script(self) -> None:
        out = html_to_text("<p>hi</p><script>alert(1)</script>")
        self.assertIn("hi", out)
        self.assertNotIn("alert", out)

    def test_strips_style(self) -> None:
        out = html_to_text("<style>body{color:red}</style><p>text</p>")
        self.assertIn("text", out)
        self.assertNotIn("color", out)

    def test_decodes_entities(self) -> None:
        out = html_to_text("<p>a &amp; b &lt; c</p>")
        self.assertIn("a & b < c", out)

    def test_block_tags_produce_newlines(self) -> None:
        out = html_to_text("<p>one</p><p>two</p>")
        self.assertIn("one", out)
        self.assertIn("two", out)
        self.assertIn("\n", out)

    def test_collapses_whitespace(self) -> None:
        out = html_to_text("<p>a     b</p>")
        self.assertNotIn("     ", out)

    def test_empty_input(self) -> None:
        self.assertEqual(html_to_text(""), "")

    def test_plain_text_passthrough(self) -> None:
        self.assertIn("just text", html_to_text("just text"))


# ---- URL validation ----------------------------------------------------

class UrlValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tool = FetchUrlTool(opener=_FakeOpener(_FakeResponse(b"ok", headers={"Content-Type": "text/plain"})))

    def test_rejects_empty(self) -> None:
        out = self.tool.execute({"url": ""})
        self.assertFalse(out["success"])

    def test_rejects_no_scheme(self) -> None:
        out = self.tool.execute({"url": "example.com"})
        self.assertFalse(out["success"])

    def test_rejects_file_scheme(self) -> None:
        out = self.tool.execute({"url": "file:///etc/passwd"})
        self.assertFalse(out["success"])

    def test_rejects_ftp_scheme(self) -> None:
        out = self.tool.execute({"url": "ftp://example.com"})
        self.assertFalse(out["success"])

    def test_rejects_data_scheme(self) -> None:
        out = self.tool.execute({"url": "data:text/plain,hi"})
        self.assertFalse(out["success"])

    def test_rejects_javascript_scheme(self) -> None:
        out = self.tool.execute({"url": "javascript:alert(1)"})
        self.assertFalse(out["success"])

    def test_rejects_missing_host(self) -> None:
        out = self.tool.execute({"url": "http:///nohost"})
        self.assertFalse(out["success"])

    def test_rejects_too_long(self) -> None:
        out = self.tool.execute({"url": "https://example.com/" + "a" * 3000})
        self.assertFalse(out["success"])


# ---- fetch_url happy path ---------------------------------------------

class FetchUrlHappyPathTests(unittest.TestCase):
    def _tool(self, body: bytes, headers: dict | None = None) -> FetchUrlTool:
        return FetchUrlTool(opener=_FakeOpener(_FakeResponse(body, headers=headers or {})))

    def test_plain_text(self) -> None:
        tool = self._tool(b"hello world", headers={"Content-Type": "text/plain"})
        out = tool.execute({"url": "https://example.com"})
        self.assertTrue(out["success"])
        self.assertEqual(out["result"]["text"], "hello world")
        self.assertFalse(out["result"]["text_truncated"])
        self.assertFalse(out["result"]["byte_truncated"])

    def test_html_extracted(self) -> None:
        body = b"<html><body><p>Hello</p><script>bad</script></body></html>"
        tool = self._tool(body, headers={"Content-Type": "text/html"})
        out = tool.execute({"url": "https://example.com"})
        self.assertTrue(out["success"])
        self.assertIn("Hello", out["result"]["text"])
        self.assertNotIn("bad", out["result"]["text"])

    def test_metadata_in_result(self) -> None:
        tool = self._tool(b"x", headers={"Content-Type": "text/plain"})
        out = tool.execute({"url": "https://example.com/page"})
        r = out["result"]
        self.assertEqual(r["url"], "https://example.com/page")
        self.assertEqual(r["status"], 200)
        self.assertIn("content_type", r)
        self.assertIn("text_length", r)


# ---- fetch_url truncation ---------------------------------------------

class FetchUrlTruncationTests(unittest.TestCase):
    def test_byte_truncation(self) -> None:
        body = b"a" * 100
        tool = FetchUrlTool(
            max_bytes=10,
            opener=_FakeOpener(_FakeResponse(body, headers={"Content-Type": "text/plain"})),
        )
        out = tool.execute({"url": "https://example.com"})
        self.assertTrue(out["success"])
        self.assertTrue(out["result"]["byte_truncated"])
        self.assertEqual(out["result"]["byte_truncated_at"], 10)
        self.assertEqual(out["result"]["text"], "a" * 10)

    def test_text_truncation(self) -> None:
        body = b"a" * 1000
        tool = FetchUrlTool(
            max_text_length=50,
            opener=_FakeOpener(_FakeResponse(body, headers={"Content-Type": "text/plain"})),
        )
        out = tool.execute({"url": "https://example.com"})
        self.assertTrue(out["success"])
        self.assertTrue(out["result"]["text_truncated"])
        self.assertEqual(out["result"]["text_truncated_at"], 50)
        self.assertEqual(len(out["result"]["text"]), 50)


# ---- fetch_url refusals -----------------------------------------------

class FetchUrlRefusalTests(unittest.TestCase):
    def test_non_text_content_type_refused(self) -> None:
        tool = FetchUrlTool(
            opener=_FakeOpener(_FakeResponse(b"\x89PNG\r\n", headers={"Content-Type": "image/png"})),
        )
        out = tool.execute({"url": "https://example.com/img.png"})
        self.assertFalse(out["success"])
        self.assertIn("content type", out["error"].lower())

    def test_binary_without_ct_refused(self) -> None:
        tool = FetchUrlTool(opener=_FakeOpener(_FakeResponse(b"\x00\x01")))
        out = tool.execute({"url": "https://example.com/blob"})
        self.assertFalse(out["success"])


# ---- fetch_url errors -------------------------------------------------

class FetchUrlErrorTests(unittest.TestCase):
    def test_http_error(self) -> None:
        err = urllib.error.HTTPError(
            "https://example.com", 404, "Not Found", {}, io.BytesIO(b"")
        )
        tool = FetchUrlTool(opener=_FakeOpener(err))
        out = tool.execute({"url": "https://example.com"})
        self.assertFalse(out["success"])
        self.assertIn("404", out["error"])

    def test_url_error(self) -> None:
        err = urllib.error.URLError("dns failure")
        tool = FetchUrlTool(opener=_FakeOpener(err))
        out = tool.execute({"url": "https://nope.example"})
        self.assertFalse(out["success"])
        self.assertIn("Network error", out["error"])

    def test_timeout(self) -> None:
        tool = FetchUrlTool(opener=_FakeOpener(TimeoutError()))
        out = tool.execute({"url": "https://example.com"})
        self.assertFalse(out["success"])


# ---- web_search stub --------------------------------------------------

class WebSearchStubTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tool = WebSearchTool()

    def test_metadata(self) -> None:
        self.assertEqual(self.tool.name, "web_search")
        self.assertIn("NOT CURRENTLY AVAILABLE", self.tool.description)

    def test_always_returns_failure(self) -> None:
        out = self.tool.execute({"query": "python asyncio"})
        self.assertFalse(out["success"])
        self.assertIsNone(out["result"])
        self.assertIn("no search provider", out["error"].lower())

    def test_no_network_call(self) -> None:
        # Belt and braces: even with bogus args, it must not attempt network.
        out = self.tool.execute({"query": ""})
        self.assertFalse(out["success"])


# ---- User-Agent / header hygiene --------------------------------------

class HeaderTests(unittest.TestCase):
    def test_user_agent_is_set_and_honest(self) -> None:
        captured: dict = {}

        class _CaptureOpener:
            def open(self, req, timeout=None):  # noqa: ANN001
                captured["ua"] = req.get_header("User-agent")
                captured["auth"] = req.get_header("Authorization")
                return _FakeResponse(b"ok", headers={"Content-Type": "text/plain"})

        tool = FetchUrlTool(opener=_CaptureOpener())
        tool.execute({"url": "https://example.com"})
        self.assertIsNotNone(captured["ua"])
        self.assertIn("JARVIS", captured["ua"])
        self.assertIsNone(captured["auth"])


if __name__ == "__main__":
    unittest.main()