# MCP Document Conversion Server

## Setup
```bash
pip install -r requirements.txt --break-system-packages
```
LibreOffice must be installed separately for docx->pdf (`soffice` on PATH):
```bash
apt-get install libreoffice
```

## Run
```bash
python server.py
```
Runs as an MCP stdio server. Register it with your MCP client (e.g. Claude Desktop config)
pointing to this `server.py`.

## Tools
| Tool | Description |
|---|---|
| docx_to_pdf | .docx -> .pdf (LibreOffice headless) |
| pdf_to_docx | .pdf -> .docx (pdf2docx) |
| json_to_csv | .json -> .csv (pandas) |
| csv_to_json | .csv -> .json (pandas) |
| html_to_markdown | .html -> .md (markdownify) |
| markdown_to_html | .md -> .html (markdown) |
| image_convert | png/jpg/webp <-> png/jpg/webp (Pillow) |
| image_compress | quality/resize compression (Pillow) |

## Structure
```
mcp-doc-server/
├── server.py            # MCP entrypoint, tool registry, dispatch
├── tools/
│   ├── base.py           # ConversionResult
│   ├── docx_pdf.py
│   ├── data_convert.py
│   ├── web_markdown.py
│   └── image_convert.py
└── utils/
    ├── errors.py          # ConversionError, ValidationError, EngineError
    └── file_io.py         # path validation, temp workspace
```
