"""
WebContentTool: two-function utility class.

1. url_to_markdown()   -> fetches a URL, strips ads/nav/boilerplate, saves clean Markdown
2. explain_content()   -> reads a local Markdown/text file and returns an LLM explanation/summary

Install:
    pip install trafilatura requests anthropic

Requires ANTHROPIC_API_KEY environment variable set for explain_content().
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import requests
import trafilatura

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB cap for local reads
DEFAULT_MODEL = "claude-sonnet-4-6"


class WebContentToolError(Exception):
    """Raised for any expected failure: bad URL, fetch failure, extraction failure, missing file."""
    pass


@dataclass
class ToolResult:
    success: bool
    output_path: str | None = None
    content: str | None = None
    meta: dict = field(default_factory=dict)
    error: str | None = None

    def to_json(self) -> str:
        return json.dumps(
            {
                "success": self.success,
                "output_path": self.output_path,
                "content": self.content,
                "meta": self.meta,
                "error": self.error,
            },
            indent=2,
        )


class WebContentTool:
    def __init__(self, output_dir: str | None = None, anthropic_api_key: str | None = None):
        """
        output_dir: default folder to save markdown when no output_path is given.
                    Defaults to current working directory.
        anthropic_api_key: falls back to ANTHROPIC_API_KEY env var if not passed.
        """
        self.output_dir = Path(output_dir) if output_dir else Path.cwd()
        self.anthropic_api_key = anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")

    # ------------------------------------------------------------------
    # 1. URL -> clean Markdown
    # ------------------------------------------------------------------
    def url_to_markdown(self, url: str, output_path: str | None = None) -> ToolResult:
        """Fetch a URL, strip ads/nav/boilerplate, and save the main content as Markdown."""
        if not url.startswith(("http://", "https://")):
            raise WebContentToolError(f"Invalid URL (must start with http:// or https://): {url}")

        try:
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise WebContentToolError(f"Failed to fetch URL: {e}") from e

        markdown = trafilatura.extract(
            resp.text,
            url=url,
            output_format="markdown",
            include_links=True,
            include_images=True,
            favor_precision=True,  # bias toward cleaner text, less boilerplate
        )

        if not markdown or not markdown.strip():
            raise WebContentToolError(
                "Could not extract readable content from this page (may be JS-rendered, "
                "paywalled, or blocked extraction)."
            )

        dest = self._resolve_output(output_path, url, "md")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(markdown, encoding="utf-8")

        return ToolResult(
            success=True,
            output_path=str(dest),
            content=markdown,
            meta={"source_url": url, "char_count": len(markdown)},
        )

    # ------------------------------------------------------------------
    # 2. Explain saved/local Markdown content
    # ------------------------------------------------------------------
    def explain_content(
        self,
        path: str,
        question: str | None = None,
        model: str = DEFAULT_MODEL,
    ) -> ToolResult:
        """Read a local Markdown/text file and return an LLM explanation or summary.

        question: optional specific question about the content.
                  If omitted, returns a general summary/explanation.
        """
        src = Path(path).expanduser().resolve()
        if not src.exists() or not src.is_file():
            raise WebContentToolError(f"File not found: {src}")

        size = src.stat().st_size
        if size == 0:
            raise WebContentToolError(f"File is empty: {src}")
        if size > MAX_FILE_SIZE_BYTES:
            raise WebContentToolError(f"File too large ({size} bytes). Max: {MAX_FILE_SIZE_BYTES} bytes")

        text = src.read_text(encoding="utf-8", errors="replace")

        if not self.anthropic_api_key:
            raise WebContentToolError(
                "No Anthropic API key found. Pass anthropic_api_key= or set ANTHROPIC_API_KEY."
            )

        try:
            import anthropic
        except ImportError as e:
            raise WebContentToolError("anthropic package not installed. Run: pip install anthropic") from e

        prompt = (
            f"Explain the following content clearly and concisely.\n\n{text}"
            if not question
            else f"Based on the following content, answer this question: {question}\n\nContent:\n{text}"
        )

        try:
            client = anthropic.Anthropic(api_key=self.anthropic_api_key)
            response = client.messages.create(
                model=model,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )
            explanation = "".join(
                block.text for block in response.content if getattr(block, "type", None) == "text"
            )
        except Exception as e:  # noqa: BLE001
            raise WebContentToolError(f"LLM explanation failed: {e}") from e

        return ToolResult(
            success=True,
            content=explanation,
            meta={"source_path": str(src), "question": question, "model": model},
        )

    # ------------------------------------------------------------------
    def _resolve_output(self, output_path: str | None, url: str, ext: str) -> Path:
        if output_path:
            out = Path(output_path).expanduser().resolve()
            if out.suffix.lower().lstrip(".") != ext:
                out = out.with_suffix(f".{ext}")
            return out

        from urllib.parse import urlparse

        slug = urlparse(url).path.strip("/").replace("/", "_") or urlparse(url).netloc
        slug = "".join(c if c.isalnum() or c in "-_" else "_" for c in slug)[:80] or "page"
        return self.output_dir / f"{slug}.{ext}"



