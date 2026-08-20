"""Token-based download route.

Converted files live as DB blobs (see storage.py) — never touch disk after
conversion, so there's no folder to scan and no path to mismatch. A tool
calls file_io.finalize_output() to store its result and get back a token;
this route just serves by that token.

Usage:
    from flask import Flask
    from download_file import register_download_route

    app = Flask(__name__)
    register_download_route(app)
    # -> exposes GET /download/<token>
"""
import io
from flask import send_file, abort


def register_download_route(app, route: str = "/download/<token>"):
    from mcp_doc_server.utils import storage

    def download_file(token):
        record = storage.get_file(token)
        if not record:
            abort(404)
        return send_file(
            io.BytesIO(record["data"]),
            mimetype=record["mimetype"],
            as_attachment=True,
            download_name=record["filename"],
        )

    app.add_url_rule(route, endpoint="download_file", view_func=download_file, methods=["GET"])