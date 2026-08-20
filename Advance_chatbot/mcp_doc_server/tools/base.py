"""Shared result type returned by every converter function."""

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ConversionResult:
    success: bool
    output_path: str | None = None
    input_format: str | None = None
    output_format: str | None = None
    size_bytes: int | None = None
    meta: dict = field(default_factory=dict)
    error: str | None = None

    @classmethod
    def ok(cls, output_path: Path, input_format: str, output_format: str, **meta) -> "ConversionResult":
        return cls(
            success=True,
            output_path=str(output_path),
            input_format=input_format,
            output_format=output_format,
            size_bytes=output_path.stat().st_size if output_path.exists() else None,
            meta=meta,
        )

    def to_json(self) -> str:
        return json.dumps(
            {
                "success": self.success,
                "output_path": self.output_path,
                "input_format": self.input_format,
                "output_format": self.output_format,
                "size_bytes": self.size_bytes,
                "meta": self.meta,
                "error": self.error,
            },
            indent=2,
        )
