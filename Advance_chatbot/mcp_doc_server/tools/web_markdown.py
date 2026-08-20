"""html <-> markdown conversion."""

from tools.base import ConversionResult
from utils.errors import EngineError
from utils.file_io import validate_input_path, resolve_output_path


def html_to_markdown(input_path: str, output_path: str | None = None) -> ConversionResult:
    src = validate_input_path(input_path, {"html", "htm"})
    dest = resolve_output_path(output_path, src, "md")

    try:
        from markdownify import markdownify as md
    except ImportError as e:
        raise EngineError("markdownify not installed. Run: pip install markdownify") from e

    html_content = src.read_text(encoding="utf-8", errors="replace")
    try:
        markdown_content = md(html_content, heading_style="ATX")
    except Exception as e:  # noqa: BLE001
        raise EngineError(f"html_to_markdown failed: {e}") from e

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(markdown_content, encoding="utf-8")

    return ConversionResult.ok(dest, input_format=src.suffix.lstrip("."), output_format="md")


def markdown_to_html(input_path: str, output_path: str | None = None) -> ConversionResult:
    src = validate_input_path(input_path, {"md", "markdown"})
    dest = resolve_output_path(output_path, src, "html")

    try:
        import markdown as md_lib
    except ImportError as e:
        raise EngineError("markdown not installed. Run: pip install markdown") from e

    md_content = src.read_text(encoding="utf-8", errors="replace")
    try:
        html_content = md_lib.markdown(
            md_content, extensions=["tables", "fenced_code", "toc"]
        )
    except Exception as e:  # noqa: BLE001
        raise EngineError(f"markdown_to_html failed: {e}") from e

    full_html = (
        "<!DOCTYPE html>\n<html>\n<head>\n<meta charset=\"utf-8\">\n"
        f"<title>{src.stem}</title>\n</head>\n<body>\n{html_content}\n</body>\n</html>\n"
    )

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(full_html, encoding="utf-8")

    return ConversionResult.ok(dest, input_format=src.suffix.lstrip("."), output_format="html")
