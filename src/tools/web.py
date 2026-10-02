"""Web tools for JARVIS.

Two tools:
    fetch_url   -- real implementation, HTTP(S) GET + HTML-to-text
    web_search  -- documented stub, no provider configured

Everything here uses the standard library. No third-party HTTP
clients, no BeautifulSoup, no requests. HTML is parsed with
html.parser.HTMLParser.

Safety defaults:
    - only http:// and https:// schemes
    - hard timeout per request
    - byte cap on the raw response
    - character cap on the extracted text
    - no Authorization header, no cookies, no .netrc
    - redirect cap
    - honest User-Agent
"""

from __future__ import annotations

import json as _json
import re
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Any

from src.tools.base import Tool


# ---- constants ---------------------------------------------------------

DEFAULT_TIMEOUT_SECONDS = 10
DEFAULT_MAX_BYTES = 2 * 1024 * 1024       # 2 MiB
DEFAULT_MAX_TEXT_LENGTH = 20_000          # chars after extraction
MAX_REDIRECTS = 5

USER_AGENT = "JARVIS/0.4 (+local assistant)"

_ALLOWED_SCHEMES = ("http", "https")
_TEXT_CONTENT_PREFIXES = ("text/",)
_TEXT_CONTENT_TYPES = (
    "application/json",
    "application/xml",
    "application/xhtml+xml",
)


# ---- HTML-to-text ------------------------------------------------------

class _TextExtractor(HTMLParser):
    """Strip tags, scripts, and styles; keep visible text."""

    #: Tags whose entire subtree is discarded.
    _SKIP_TAGS = {"script", "style", "noscript", "template", "head", "svg"}

    #: Tags that imply a block boundary; a newline is emitted after them.
    _BLOCK_TAGS = {
        "p", "div", "br", "li", "tr", "td", "th",
        "h1", "h2", "h3", "h4", "h5", "h6",
        "section", "article", "header", "footer", "nav",
        "blockquote", "pre", "hr",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
            return
        if tag in self._BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if tag in self._BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and data:
            self._chunks.append(data)

    def get_text(self) -> str:
        raw = "".join(self._chunks)
        # Normalize whitespace: collapse runs of spaces/tabs, trim blank lines.
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n\s*\n+", "\n\n", raw)
        return raw.strip()


def html_to_text(html: str) -> str:
    """Public helper so tests can exercise the extractor directly."""
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    return parser.get_text()


# ---- redirect handling -------------------------------------------------

class _CappedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Limit redirects to MAX_REDIRECTS to avoid loops."""

    max_redirections = MAX_REDIRECTS


def _build_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(_CappedRedirectHandler())


# ---- URL validation ----------------------------------------------------

def _validate_url(url: str) -> tuple[str, str]:
    """Return (scheme, url) or raise ValueError with a useful message."""
    if not isinstance(url, str) or not url.strip():
        raise ValueError("URL must be a non-empty string.")
    url = url.strip()
    if len(url) > 2048:
        raise ValueError("URL too long (max 2048 characters).")

    parsed = urllib.parse.urlparse(url)
    scheme = (parsed.scheme or "").lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise ValueError(
            f"URL scheme {scheme!r} is not allowed. Use http:// or https://."
        )
    if not parsed.netloc:
        raise ValueError("URL must include a host.")
    return scheme, url


def _is_textual_content_type(content_type: str) -> bool:
    ct = (content_type or "").split(";", 1)[0].strip().lower()
    if not ct:
        return False
    if any(ct.startswith(prefix) for prefix in _TEXT_CONTENT_PREFIXES):
        return True
    return ct in _TEXT_CONTENT_TYPES


# ---- tools -------------------------------------------------------------

class FetchUrlTool(Tool):
    name = "fetch_url"
    description = (
        "Fetch an HTTP or HTTPS URL and return the extracted plain text. "
        "Strips HTML tags, scripts, and styles. Refuses binary content "
        "and non-HTTP(S) schemes. No credentials are sent."
    )
    schema = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "Full URL starting with http:// or https://.",
            }
        },
        "required": ["url"],
        "additionalProperties": False,
    }

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        max_bytes: int = DEFAULT_MAX_BYTES,
        max_text_length: int = DEFAULT_MAX_TEXT_LENGTH,
        opener: urllib.request.OpenerDirector | None = None,
    ) -> None:
        self._timeout = int(timeout)
        self._max_bytes = int(max_bytes)
        self._max_text_length = int(max_text_length)
        # Allow tests to inject a mock opener.
        self._opener = opener if opener is not None else _build_opener()

    def execute(self, arguments: dict) -> dict:
        try:
            _scheme, url = _validate_url(arguments.get("url", ""))
        except ValueError as exc:
            return {"success": False, "result": None, "error": str(exc)}

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.1",
            },
            method="GET",
        )

        try:
            with self._opener.open(req, timeout=self._timeout) as resp:
                status = getattr(resp, "status", 200)
                content_type = resp.headers.get("Content-Type", "")

                if not _is_textual_content_type(content_type):
                    return {
                        "success": False,
                        "result": None,
                        "error": (
                            f"Refusing non-text content type: "
                            f"{content_type or 'unknown'}."
                        ),
                    }

                raw = resp.read(self._max_bytes + 1)

        except urllib.error.HTTPError as exc:
            return {
                "success": False,
                "result": None,
                "error": f"HTTP {exc.code}: {exc.reason}",
            }
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            return {
                "success": False,
                "result": None,
                "error": f"Network error: {reason}",
            }
        except TimeoutError:
            return {
                "success": False,
                "result": None,
                "error": f"Request timed out after {self._timeout}s.",
            }
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "result": None, "error": f"Fetch failed: {exc}"}

        byte_truncated = len(raw) > self._max_bytes
        if byte_truncated:
            raw = raw[: self._max_bytes]

        # Decode. Prefer charset from Content-Type, fall back to utf-8.
        charset = "utf-8"
        ct = content_type or ""
        match = re.search(r"charset=([^\s;]+)", ct, flags=re.IGNORECASE)
        if match:
            charset = match.group(1).strip().strip('"').strip("'")

        try:
            body = raw.decode(charset, errors="replace")
        except (LookupError, UnicodeDecodeError):
            body = raw.decode("utf-8", errors="replace")

        # Extract text if HTML, otherwise pass through.
        ct_base = ct.split(";", 1)[0].strip().lower()
        if ct_base in ("text/html", "application/xhtml+xml") or "<html" in body[:1000].lower():
            text = html_to_text(body)
        else:
            text = body

        text_truncated = len(text) > self._max_text_length
        if text_truncated:
            text = text[: self._max_text_length]

        result: dict[str, Any] = {
            "url": url,
            "status": status,
            "content_type": ct or None,
            "byte_truncated": byte_truncated,
            "text_truncated": text_truncated,
            "text": text,
            "text_length": len(text),
        }
        if byte_truncated:
            result["byte_truncated_at"] = self._max_bytes
        if text_truncated:
            result["text_truncated_at"] = self._max_text_length
            result["message"] = (
                f"Extracted text was larger than {self._max_text_length} "
                f"characters; only the first {self._max_text_length} were returned."
            )
        return {"success": True, "result": result, "error": None}


class WebSearchTool(Tool):
    name = "web_search"
    description = (
        "Search the web. NOT CURRENTLY AVAILABLE -- no search provider is "
        "configured. Do not call this tool; use fetch_url with a specific "
        "URL instead, or ask the user to configure a search provider."
    )
    schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query. Not currently supported.",
            }
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    def execute(self, arguments: dict) -> dict:
        return {
            "success": False,
            "result": None,
            "error": (
                "web_search is not available: no search provider is "
                "configured. Use fetch_url with a specific URL, or "
                "configure a provider in .env to enable this tool."
            ),
        }