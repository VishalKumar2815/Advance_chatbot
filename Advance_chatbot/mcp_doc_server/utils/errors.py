"""Standard error types used across all converter modules."""


class ConversionError(Exception):
    """Raised when a conversion fails for a known, expected reason
    (bad input, missing file, unsupported format, engine failure, etc).
    Caught by server.py and returned to the client as a clean error message.
    """

    def __init__(self, message: str, tool: str | None = None, cause: Exception | None = None):
        self.tool = tool
        self.cause = cause
        super().__init__(message)


class ValidationError(ConversionError):
    """Raised when input fails validation (bad extension, missing file, size limit)."""
    pass


class EngineError(ConversionError):
    """Raised when an underlying conversion engine (LibreOffice, Pillow, pandas) fails."""
    pass
