"""In-DB blob storage for converted files. No local folder, no scanning —
a conversion result is a DB row you fetch by token."""
import os, sqlite3, uuid, threading
from pathlib import Path
from datetime import datetime

# Must be an ABSOLUTE path. This module is imported from two different
# processes with two different working directories: the MCP subprocess
# (cwd = mcp_doc_server/) and the Flask app (cwd = project root). A
# relative path means each process silently creates its own separate
# SQLite file — the conversion tool stores a blob in one, Flask looks
# for the token in the other, and every download 404s.
DB_PATH = os.environ.get("CONVERTED_FILES_DB") or str(Path(__file__).resolve().parent / "converted_files.db")
_lock = threading.Lock()


def _conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("""CREATE TABLE IF NOT EXISTS converted_files(
        token TEXT PRIMARY KEY,
        filename TEXT NOT NULL,
        mimetype TEXT NOT NULL,
        data BLOB NOT NULL,
        created_at TEXT NOT NULL
    )""")
    return conn


def save_file(filename: str, data: bytes, mimetype: str) -> str:
    token = uuid.uuid4().hex
    with _lock, _conn() as conn:
        conn.execute(
            "INSERT INTO converted_files(token,filename,mimetype,data,created_at) VALUES(?,?,?,?,?)",
            (token, filename, mimetype, data, datetime.utcnow().isoformat()),
        )
    return token


def get_file(token: str) -> dict | None:
    with _lock, _conn() as conn:
        row = conn.execute(
            "SELECT filename,mimetype,data FROM converted_files WHERE token=?", (token,)
        ).fetchone()
    if not row:
        return None
    filename, mimetype, data = row
    return {"filename": filename, "mimetype": mimetype, "data": data}


def delete_file(token: str) -> None:
    with _lock, _conn() as conn:
        conn.execute("DELETE FROM converted_files WHERE token=?", (token,))