from langchain.agents import create_agent
from langchain.tools import tool
from langchain_tavily import TavilySearch
from Retriever import DOCRetriever
import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from mcp_doc_server.Client import get_client
import asyncio
from langchain_core.tools import StructuredTool


load_dotenv()

os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY")
os.environ["TAVILY_API_KEY"] = os.getenv("TAVILY_API_KEY")


@tool("calculator", description="Performs arithmetic calculations. Use this for any maths operation.")
def calc(expression: str) -> str:
    try:
        return str(eval(expression, {"__builtins__": {}}))
    except Exception as e:
        return f"Calculation error: {e}"


def _make_document_search_tool(retriever):
    @tool("document_search", description=(
        "Search the currently uploaded document for information relevant to a query. "
        "Use this whenever the user's question could be answered from an uploaded file. "
        "If no document has been uploaded yet, this tool will say so."
    ))
    def document_search(query: str) -> str:
        results = retriever.retrieve(query)
        return "\n".join(f"{r['content']}" for r in results)
    return document_search


@tool("code_executor", description="""Executes Python code and returns output or errors.
      Use this AFTER retrieving code from document_search.
      Input must be complete, runnable Python code as a string.""")
def code_executor(code: str) -> str:
    import subprocess
    result = subprocess.run(["python3", "-c", code], capture_output=True, text=True, timeout=10)
    return result.stdout if result.stdout else result.stderr


def _make_sync(async_tool):
    def sync_run(*args, **kwargs):
        return asyncio.run(async_tool.coroutine(*args, **kwargs))
    return StructuredTool(
        name=async_tool.name,
        description=async_tool.description,
        args_schema=async_tool.args_schema,
        func=sync_run,
    )


def _build_agent():
    """Everything heavy (MCP subprocess spawn, tool registration, agent build)
    lives here — runs ONLY on first actual use, not at worker boot / import time."""
    retriever = DOCRetriever()

    model = ChatGroq(
        model="qwen/qwen3.6-27b",
        temperature=0,
    )

    websearch_tool = TavilySearch(max_results=5, topic="general")

    mcp_tools = asyncio.run(get_client())
    mcp_tool_list = [_make_sync(t) for t in mcp_tools]

    tools = [websearch_tool, calc, _make_document_search_tool(retriever), code_executor, *mcp_tool_list]

    for t in tools:
        print(t.name)

    return create_agent(
        model=model,
        tools=tools,
        system_prompt="""
            You are an intelligent AI assistant.

            Rules:
            - Use document_search whenever the question could relate to an uploaded document.
            - Use calculator for arithmetic.
            - Use web_search for current information not in any document.
            - If document_search says no document is loaded, tell the user to upload one.
            - When a document is first loaded, give a short overview of it.

            Document conversion tools (docx_to_pdf, pdf_to_docx, json_to_csv, csv_to_json,
            html_to_markdown, markdown_to_html, image_convert, image_compress):
            - Use these ONLY when the user explicitly asks to convert, compress, or change
              the format of a file, and has given you a file path.
            - Never guess a file path — if the user hasn't provided one, ask for it.
            - After a successful conversion, tell the user the output file path plainly;
              don't restate the raw JSON result.
            - If a tool returns an error (e.g. LibreOffice not found, unsupported file,
              scanned PDF with no extractable text), explain the error to the user in plain
              language and suggest a fix if one is known, rather than retrying blindly.
        """,
    )


class _LazyAgent:
    """Transparent proxy — behaves exactly like the real agent object, but only
    builds it on first actual use (first .invoke() call), not on import."""
    def __init__(self):
        self._real_agent = None

    def _ensure(self):
        if self._real_agent is None:
            self._real_agent = _build_agent()
        return self._real_agent

    def __getattr__(self, name):
        return getattr(self._ensure(), name)


agent = _LazyAgent()   # Main.py's `from Agent import agent` keeps working unchanged
