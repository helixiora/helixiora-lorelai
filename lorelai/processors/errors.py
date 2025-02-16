"""Error handling utilities for processors."""

from enum import Enum


class ProcessorErrorCode(Enum):
    """Error codes for processor operations."""

    # General errors (1000-1999)
    UNKNOWN_ERROR = 1000
    INVALID_INPUT = 1001
    NO_CONTENT = 1002
    VALIDATION_ERROR = 1003

    # File access errors (2000-2999)
    FILE_NOT_FOUND = 2000
    FILE_EMPTY = 2001
    FILE_TOO_LARGE = 2002
    INSUFFICIENT_PERMISSIONS = 2003

    # Processing errors (3000-3999)
    EXTRACTION_FAILED = 3000
    CHUNKING_FAILED = 3001
    METADATA_ERROR = 3002

    # Content validation errors (4000-4999)
    INVALID_CONTENT = 4000
    CONTENT_TOO_SHORT = 4001
    CONTENT_TOO_LONG = 4002

    # Storage errors (5000-5999)
    DATABASE_ERROR = 5000
    STORAGE_FULL = 5001


class ProcessorError:
    """Structured error information for processor operations."""

    def __init__(
        self,
        code: ProcessorErrorCode,
        message: str,
        details: str | None = None,
        item_id: str | None = None,
    ):
        """Initialize a processor error.

        Parameters
        ----------
        code : ProcessorErrorCode
            The error code
        message : str
            A human-readable error message
        details : Optional[str]
            Additional error details or context
        item_id : Optional[str]
            ID of the item that caused the error
        """
        self.code = code
        self.message = message
        self.details = details
        self.item_id = item_id

    def __str__(self) -> str:
        """Return a string representation of the error."""
        error_str = f"[{self.code.name}] {self.message}"
        if self.details:
            error_str += f" - Details: {self.details}"
        if self.item_id:
            error_str += f" (Item ID: {self.item_id})"
        return error_str

    def to_dict(self) -> dict:
        """Convert the error to a dictionary."""
        return {
            "code": self.code.value,
            "code_name": self.code.name,
            "message": self.message,
            "details": self.details,
            "item_id": self.item_id,
        }
