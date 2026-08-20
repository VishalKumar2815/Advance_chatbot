"""
MCP Document Conversion Server (FastMCP)
Registers conversion tools and dispatches to converter modules.
"""

import logging
import os
from mcp.server.fastmcp import FastMCP

from tools import docx_pdf, data_convert, web_markdown
from tools import image_convert as image_convert_mod
from utils.errors import ConversionError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-doc-server")

mcp = FastMCP("doc-conversion-server")


def _run(tool_name: str, fn, **kwargs) -> str:
    """Common wrapper: call converter, return JSON string, log/convert errors cleanly."""
    try:
        result = fn(**kwargs)
        return result.to_json()
    except ConversionError as e:
        logger.error("Conversion failed for %s: %s", tool_name, e)
        return f'{{"success": false, "error": "{e}"}}'
    except Exception as e:  # noqa: BLE001
        logger.exception("Unexpected error in tool %s", tool_name)
        return f'{{"success": false, "error": "Internal error: {e}"}}'


@mcp.tool()
def docx_to_pdf(input_path: str, output_path: str | None = None) -> str:
    """Convert a .docx file to .pdf using LibreOffice headless."""
    return _run("docx_to_pdf", docx_pdf.docx_to_pdf, input_path=input_path, output_path=output_path)


@mcp.tool()
def pdf_to_docx(input_path: str, output_path: str | None = None) -> str:
    """Convert a .pdf file to .docx using pdf2docx."""
    return _run("pdf_to_docx", docx_pdf._pdf_to_docx_via_pdfplumber, input_path=input_path, output_path=output_path)


@mcp.tool()
def json_to_csv(input_path: str, output_path: str | None = None) -> str:
    """Convert a .json file to .csv using pandas."""
    return _run("json_to_csv", data_convert.json_to_csv, input_path=input_path, output_path=output_path)


@mcp.tool()
def csv_to_json(input_path: str, output_path: str | None = None) -> str:
    """Convert a .csv file to .json using pandas."""
    return _run("csv_to_json", data_convert.csv_to_json, input_path=input_path, output_path=output_path)


@mcp.tool()
def html_to_markdown(input_path: str, output_path: str | None = None) -> str:
    """Convert an .html file to .md using markdownify."""
    return _run("html_to_markdown", web_markdown.html_to_markdown, input_path=input_path, output_path=output_path)


@mcp.tool()
def markdown_to_html(input_path: str, output_path: str | None = None) -> str:
    """Convert a .md file to .html using the markdown library."""
    return _run("markdown_to_html", web_markdown.markdown_to_html, input_path=input_path, output_path=output_path)


@mcp.tool()
def image_convert(input_path: str, target_format: str, output_path: str | None = None) -> str:
    """Convert an image between PNG, JPG/JPEG, and WEBP formats."""
    return _run(
        "image_convert", image_convert_mod.convert_image,
        input_path=input_path, target_format=target_format, output_path=output_path,
    )


@mcp.tool()
def image_compress(
    input_path: str,
    quality: int = 75,
    max_dimension: int | None = None,
    output_path: str | None = None,
) -> str:
    """Compress an image (quality 1-95) and optionally resize to max_dimension px."""
    return _run(
        "image_compress", image_convert_mod.compress_image,
        input_path=input_path, quality=quality, max_dimension=max_dimension, output_path=output_path,
    )


if __name__ == "__main__":
    mcp.run(transport='stdio')
    # result=docx_pdf.docx_to_pdf(r"C:\Users\HP\OneDrive\Desktop\Data analyst.docx")
    # print(result.to_json())
    # result=docx_pdf._pdf_to_docx_via_pdfplumber(input_path=r"C:\Users\HP\OneDrive\Desktop\ibps reciept.pdf")
    # print(result.to_json())
    #result=image_convert_mod.convert_image(r"C:\Users\HP\OneDrive\Desktop\logo.webp",target_format="jpg",output_path=r"C:\Users\HP\OneDrive\Desktop")
    # result=image_convert_mod.compress_image(r"C:\Users\HP\OneDrive\Desktop\logo.webp",output_path=r"C:\Users\HP\OneDrive\Desktop\Documents")
    #print(result.to_json())
    