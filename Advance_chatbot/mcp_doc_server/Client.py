"""
LangChain client for the doc-conversion MCP server.

Connects to mcp-doc-server/server.py over stdio and exposes its 8 tools
(docx_to_pdf, pdf_to_docx, json_to_csv, csv_to_json, html_to_markdown,
markdown_to_html, image_convert, image_compress) as LangChain-compatible tools.

Install:
    pip install langchain-mcp-adapters

Usage:
    from mcp_connector import get_doc_tools

    tools = await get_doc_tools()
"""

from pathlib import Path
import os
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient

# Path to the doc-conversion server's entrypoint script.
# IMPORTANT: set this to wherever your server.py actually lives.
# If Client.py sits in the SAME folder as server.py (flat layout), use:
#     SERVER_SCRIPT = str(Path(__file__).parent / "server.py")
# If server.py is in a subfolder (nested layout), use:
#     SERVER_SCRIPT = str(Path(__file__).parent / "mcp-doc-server" / "server.py")
SERVER_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)),"server.py")

async def get_client():
    client = MultiServerMCPClient({
        "doc_conversion": {
            "command": r"D:\Cursor files\.venv\Scripts\python.exe",
            "args": [SERVER_SCRIPT],
            "transport": "stdio",
            # Critical: server.py does `from tools import ...` / `from utils import ...`.
            # Those only resolve if the subprocess's working directory is the folder
            # containing server.py. Without this, launching the client from anywhere
            # else causes the subprocess to crash on import -> "Connection closed".
        },
    })

    tools = await client.get_tools()
    return tools


if __name__ == "__main__":
    tools=asyncio.run(get_client())
    for t in tools:
        print(f"  - {t.name}") 
        print("="*50)
        # print("Type:", type(t))
        # print("Has 'coroutine' attr:", hasattr(t, "coroutine"))
        # print("Has '_arun' attr:", hasattr(t, "_arun"))
        # print("coroutine value:", getattr(t, "coroutine", "NOT FOUND"))
        # print("func value:", getattr(t, "func", "NOT FOUND"))


#------------------------------------------------------------------------------------------------------------------------------------------
# import asyncio
# import sys
# from pathlib import Path

# from mcp import ClientSession, StdioServerParameters
# from mcp.client.stdio import stdio_client

# SERVER_SCRIPT = str(Path(__file__).parent / "server.py")
# LOG_FILE = str(Path(__file__).parent / "mcp_stderr.log")


# async def main():
#     print(f"Connecting to: {SERVER_SCRIPT}")
#     print(f"Using interpreter: {sys.executable}")
#     print(f"Subprocess stderr will be written to: {LOG_FILE}\n")

#     params = StdioServerParameters(
#         command=sys.executable,
#         args=[SERVER_SCRIPT],
#         cwd=str(Path(SERVER_SCRIPT).parent),
#     )

#     with open(LOG_FILE, "w", encoding="utf-8") as errlog:
#         try:
#             async with stdio_client(params, errlog=errlog) as (read, write):
#                 async with ClientSession(read, write) as session:
#                     print("Sending initialize request...")
#                     await session.initialize()
#                     print("SUCCESS: initialize completed.\n")

#                     tools_result = await session.list_tools()
#                     print(f"Loaded {len(tools_result.tools)} tools:")
#                     for t in tools_result.tools:
#                         print(f"  - {t.name}")
#         except Exception as e:
#             print(f"\nFAILED: {type(e).__name__}: {e}")
#             print(f"\nCheck {LOG_FILE} for the subprocess's actual stderr output.")
#             raise


# if __name__ == "__main__":
#     asyncio.run(main())