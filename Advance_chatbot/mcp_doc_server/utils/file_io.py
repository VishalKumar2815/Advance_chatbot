"""Shared file I/O helpers: temp workspace, path/extension validation,
and finalize_output() — the one place that turns a tool's local temp
file into a DB blob + download token."""

import os
import tempfile
import uuid
import mimetypes
from contextlib import contextmanager
from pathlib import Path

from utils.errors import ValidationError
from utils import storage

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB hard cap per input file

# Scratch space only — files here are transient and deleted right after
# finalize_output() reads them into the DB. Never used for downloads.
SCRATCH_DIR = os.environ.get("DOC_SCRATCH_DIR") or str(Path(tempfile.gettempdir()) / "docconv_scratch")


def validate_input_path(input_path: str, allowed_extensions: set[str]) -> Path:
    """Confirm the input file exists, is readable, has an allowed extension,
    and is within the size limit. Returns a resolved Path on success.
    """
    path = Path(input_path).expanduser().resolve()

    if not path.exists():
        raise ValidationError(f"Input file not found: {path}")
    if not path.is_file():
        raise ValidationError(f"Input path is not a file: {path}")

    ext = path.suffix.lower().lstrip(".")
    if ext not in allowed_extensions:
        raise ValidationError(
            f"Unsupported extension '.{ext}'. Expected one of: {sorted(allowed_extensions)}"
        )

    size = path.stat().st_size
    if size == 0:
        raise ValidationError(f"Input file is empty: {path}")
    if size > MAX_FILE_SIZE_BYTES:
        raise ValidationError(
            f"Input file too large ({size} bytes). Max allowed: {MAX_FILE_SIZE_BYTES} bytes"
        )

    return path


def resolve_output_path(
    output_path: str | None,
    input_path: Path,
    new_extension: str,
    default_dir: str = None,
) -> Path:
    """Determine where a tool writes its output BEFORE it's stored as a
    blob. This is scratch space only, not the download location.
    """
    new_extension = new_extension.lstrip(".")
    default_dir = default_dir or SCRATCH_DIR

    if output_path:
        out = Path(output_path).expanduser().resolve()
        if out.suffix.lower().lstrip(".") != new_extension.lower():
            out = out.with_suffix(f".{new_extension}")
        out.parent.mkdir(parents=True, exist_ok=True)
        return out

    out_dir = Path(default_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = input_path.stem
    # uuid suffix avoids collisions between concurrent conversions of same-named files
    return out_dir / f"{stem}_{uuid.uuid4().hex[:8]}.{new_extension}"


def finalize_output(dest: Path, cleanup: bool = True) -> dict:
    """Read a tool's locally-written output, store it as a DB blob, delete
    the local temp file, and return download info.

    Returns: {"token": str, "url": str, "filename": str}
    """
    data = dest.read_bytes()
    mimetype = mimetypes.guess_type(dest.name)[0] or "application/octet-stream"
    # Use the original stem (strip the collision-avoidance uuid suffix if present)
    token = storage.save_file(dest.name, data, mimetype)
    if cleanup:
        try:
            dest.unlink()
        except OSError:
            pass
    return {"token": token, "url": f"/download/{token}", "filename": dest.name}


@contextmanager
def temp_workspace():
    """Context manager yielding a fresh temp directory, auto-cleaned on exit."""
    tmp_dir = Path(tempfile.mkdtemp(prefix=f"docconv_{uuid.uuid4().hex[:8]}_"))
    try:
        yield tmp_dir
    finally:
        _cleanup_dir(tmp_dir)


def _cleanup_dir(path: Path) -> None:
    if not path.exists():
        return
    for root, dirs, files in os.walk(path, topdown=False):
        for f in files:
            try:
                os.remove(os.path.join(root, f))
            except OSError:
                pass
        for d in dirs:
            try:
                os.rmdir(os.path.join(root, d))
            except OSError:
                pass
    try:
        os.rmdir(path)
    except OSError:
        pass