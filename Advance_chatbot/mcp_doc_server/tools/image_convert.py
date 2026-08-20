"""Image format conversion (png/jpg/webp) and compression using Pillow."""

from pathlib import Path

from tools.base import ConversionResult
from utils.errors import EngineError, ValidationError
from utils.file_io import validate_input_path, resolve_output_path, finalize_output

SUPPORTED_IMAGE_EXTS = {"png", "jpg", "jpeg", "webp"}


def _normalize_ext(ext: str) -> str:
    ext = ext.lower().lstrip(".")
    return "jpeg" if ext == "jpg" else ext


def convert_image(
    input_path: str, target_format: str, output_path: str | None = None
) -> ConversionResult:
    src = validate_input_path(input_path, SUPPORTED_IMAGE_EXTS)

    target_format = target_format.lower().lstrip(".")
    if target_format not in SUPPORTED_IMAGE_EXTS:
        raise ValidationError(f"Unsupported target_format '{target_format}'")

    save_format = _normalize_ext(target_format).upper()
    out_ext = "jpg" if save_format == "JPEG" else target_format
    dest = resolve_output_path(output_path, src, out_ext)

    try:
        from PIL import Image
    except ImportError as e:
        raise EngineError("Pillow not installed. Run: pip install Pillow") from e

    try:
        img = Image.open(src)
        if save_format == "JPEG" and img.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1])
            img = background
        dest.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest, format=save_format)
    except Exception as e:  # noqa: BLE001
        raise EngineError(f"image_convert failed: {e}") from e

    # 1. result build karo JAB TAK file disk pe hai — size_bytes sahi capture ho
    result = ConversionResult.ok(
        dest,
        input_format=src.suffix.lstrip(".").lower(),
        output_format=out_ext,
        original_size=src.stat().st_size,
    )

    # 2. AB finalize karo — DB blob + token, local temp file delete
    info = finalize_output(dest)

    # 3. download info result mein attach karo, output_path ko URL se replace karo
    #    (taaki text-rendering docx tool jaisi hi /download/<token> dikhaye)
    result.output_path = info["url"]
    result.meta["download_url"] = info["url"]
    result.meta["download_token"] = info["token"]
    result.meta["download_filename"] = info["filename"]

    return result


def compress_image(
    input_path: str,
    quality: int = 55,
    max_dimension: int | None = None,
    output_path: str | None = None,
) -> ConversionResult:
    src = validate_input_path(input_path, SUPPORTED_IMAGE_EXTS)

    if not (1 <= quality <= 95):
        raise ValidationError("quality must be between 1 and 95")

    ext = src.suffix.lstrip(".").lower()
    dest = resolve_output_path(output_path, src, ext)

    try:
        from PIL import Image
    except ImportError as e:
        raise EngineError("Pillow not installed. Run: pip install Pillow") from e

    try:
        img = Image.open(src)
        original_dims = img.size

        if max_dimension:
            img.thumbnail((max_dimension, max_dimension), Image.LANCZOS)

        save_format = _normalize_ext(ext).upper()
        save_kwargs = {}
        if save_format in ("JPEG", "WEBP"):
            save_kwargs["quality"] = quality
            save_kwargs["optimize"] = True
        elif save_format == "PNG":
            save_kwargs["optimize"] = True

        if save_format == "JPEG" and img.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1])
            img = background

        dest.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest, format=save_format, **save_kwargs)
    except Exception as e:  # noqa: BLE001
        raise EngineError(f"image_compress failed: {e}") from e

    original_size = src.stat().st_size
    new_size = dest.stat().st_size  # file abhi disk pe hai, safe

    # 1. result build karo file delete hone se pehle
    result = ConversionResult.ok(
        dest,
        input_format=ext,
        output_format=ext,
        original_size=original_size,
        compressed_size=new_size,
        reduction_pct=round((1 - new_size / original_size) * 100, 1) if original_size else 0,
        original_dimensions=original_dims,
        final_dimensions=img.size,
    )

    # 2. ab finalize
    info = finalize_output(dest)

    # 3. download info attach
    result.output_path = info["url"]
    result.meta["download_url"] = info["url"]
    result.meta["download_token"] = info["token"]
    result.meta["download_filename"] = info["filename"]

    return result