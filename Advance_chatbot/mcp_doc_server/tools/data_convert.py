"""Tabular data conversion using pandas: csv, json, excel (xlsx), tsv,
yaml, parquet — any pair, in either direction."""

from pathlib import Path

from tools.base import ConversionResult
from utils.errors import EngineError, ValidationError
from utils.file_io import validate_input_path, resolve_output_path, finalize_output

SUPPORTED_DATA_EXTS = {"json", "csv", "xlsx", "tsv", "yaml", "yml", "parquet"}


def _read_any(src: Path, ext: str):
    """Load any supported tabular/structured format into a DataFrame."""
    import pandas as pd

    if ext == "json":
        try:
            return pd.read_json(src)
        except ValueError:
            # JSON is a single object, not an array of records
            return pd.json_normalize(pd.read_json(src, typ="series"))

    if ext == "csv":
        return pd.read_csv(src)

    if ext == "tsv":
        return pd.read_csv(src, sep="\t")

    if ext == "xlsx":
        try:
            import openpyxl  # noqa: F401
        except ImportError as e:
            raise EngineError("openpyxl not installed. Run: pip install openpyxl") from e
        return pd.read_excel(src)

    if ext in ("yaml", "yml"):
        try:
            import yaml
        except ImportError as e:
            raise EngineError("PyYAML not installed. Run: pip install pyyaml") from e
        with open(src, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return pd.json_normalize(data) if isinstance(data, dict) else pd.DataFrame(data)

    if ext == "parquet":
        try:
            import pyarrow  # noqa: F401
        except ImportError as e:
            raise EngineError("pyarrow not installed. Run: pip install pyarrow") from e
        return pd.read_parquet(src)

    raise ValidationError(f"Unsupported source format '.{ext}'")


def _write_any(df, dest: Path, ext: str):
    """Write a DataFrame out to any supported format."""
    dest.parent.mkdir(parents=True, exist_ok=True)

    if ext == "json":
        df.to_json(dest, orient="records", indent=2)
        return

    if ext == "csv":
        df.to_csv(dest, index=False)
        return

    if ext == "tsv":
        df.to_csv(dest, index=False, sep="\t")
        return

    if ext == "xlsx":
        try:
            import openpyxl  # noqa: F401
        except ImportError as e:
            raise EngineError("openpyxl not installed. Run: pip install openpyxl") from e
        df.to_excel(dest, index=False)
        return

    if ext in ("yaml", "yml"):
        try:
            import yaml
        except ImportError as e:
            raise EngineError("PyYAML not installed. Run: pip install pyyaml") from e
        with open(dest, "w", encoding="utf-8") as f:
            yaml.safe_dump(df.to_dict(orient="records"), f, sort_keys=False, allow_unicode=True)
        return

    if ext == "parquet":
        try:
            import pyarrow  # noqa: F401
        except ImportError as e:
            raise EngineError("pyarrow not installed. Run: pip install pyarrow") from e
        df.to_parquet(dest, index=False)
        return

    raise ValidationError(f"Unsupported target format '.{ext}'")


def convert_data(
    input_path: str, target_format: str, output_path: str | None = None
) -> ConversionResult:
    """Convert between any two supported tabular/structured formats:
    csv, json, xlsx, tsv, yaml, parquet."""
    src = validate_input_path(input_path, SUPPORTED_DATA_EXTS)

    target_format = target_format.lower().lstrip(".")
    if target_format == "yml":
        target_format = "yaml"
    if target_format not in SUPPORTED_DATA_EXTS:
        raise ValidationError(f"Unsupported target_format '{target_format}'")

    src_ext = src.suffix.lstrip(".").lower()
    if src_ext == "yml":
        src_ext = "yaml"

    dest = resolve_output_path(output_path, src, target_format)

    try:
        df = _read_any(src, src_ext)
        _write_any(df, dest, target_format)
    except (EngineError, ValidationError):
        raise
    except Exception as e:  # noqa: BLE001
        raise EngineError(f"convert_data failed ({src_ext} -> {target_format}): {e}") from e

    # local temp file ko DB blob bana ke token/url/filename lo
    info = finalize_output(dest)

    result = ConversionResult.ok(
    dest,
    input_format=src_ext,
    output_format=target_format,
    rows=len(df),
    columns=list(df.columns),
    )

    info = finalize_output(dest)
    result.meta["download_url"] = info["url"]
    result.meta["download_token"] = info["token"]
    result.meta["download_filename"] = info["filename"]

    return result


# Backward-compatible thin wrappers — old call sites keep working unchanged
def json_to_csv(input_path: str, output_path: str | None = None) -> ConversionResult:
    return convert_data(input_path, "csv", output_path)


def csv_to_json(input_path: str, output_path: str | None = None) -> ConversionResult:
    return convert_data(input_path, "json", output_path)