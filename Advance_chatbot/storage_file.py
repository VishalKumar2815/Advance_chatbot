"""In-DB blob storage for converted files. No local folder, no scanning —
a conversion result is a DB row you fetch by token."""
import os, sqlite3, uuid, threading
from datetime import datetime

DB_PATH = os.environ.get("CONVERTED_FILES_DB", "converted_files.db")
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