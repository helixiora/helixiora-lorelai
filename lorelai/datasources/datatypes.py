"""Datatype definitions and mappings for datasource configuration fields."""

from enum import Enum
from typing import Any


class DatasourceDataType(str, Enum):
    """Standardized datatypes for datasource configuration fields.

    Available types:
    - TEXT: Short text input (single line)
    - LONG_TEXT: Multi-line text input
    - NUMBER: Numeric input (integers or decimals)
    - SENSITIVE: Password or API key input (masked)
    - BOOLEAN: True/false checkbox
    - EMAIL: Email address input
    - URL: URL input
    """

    TEXT = "text"  # For short text
    LONG_TEXT = "long_text"  # For multi-line text
    NUMBER = "number"  # For any numeric input
    SENSITIVE = "sensitive"  # For passwords, API keys, etc.
    BOOLEAN = "boolean"  # For true/false values
    EMAIL = "email"  # For email addresses
    URL = "url"  # For URLs


# Mapping of datatypes to HTML input types and attributes
DATATYPE_FORM_MAPPING: dict[DatasourceDataType, dict[str, Any]] = {
    DatasourceDataType.TEXT: {
        "type": "text",
        "class": "form-control",
    },
    DatasourceDataType.LONG_TEXT: {
        "type": "textarea",  # Will be handled specially in template
        "class": "form-control",
        "rows": "3",
    },
    DatasourceDataType.NUMBER: {
        "type": "number",
        "class": "form-control",
        "step": "any",  # Allows both integers and decimals
    },
    DatasourceDataType.SENSITIVE: {
        "type": "password",
        "class": "form-control",
        "autocomplete": "new-password",
    },
    DatasourceDataType.BOOLEAN: {
        "type": "checkbox",
        "class": "form-check-input",
    },
    DatasourceDataType.EMAIL: {
        "type": "email",
        "class": "form-control",
    },
    DatasourceDataType.URL: {
        "type": "url",
        "class": "form-control",
        "pattern": "https?://.+",  # Basic URL validation
        "placeholder": "https://",
    },
}


def is_supported_datatype(datatype: str) -> bool:
    """Check if a datatype is supported.

    Args:
        datatype: The datatype to check.

    Returns
    -------
        bool: True if the datatype is supported, False otherwise.
    """
    try:
        DatasourceDataType(datatype.lower())
        return True
    except ValueError:
        return False


def get_form_attributes(datatype: str) -> dict[str, Any]:
    """Get the form control attributes for a datatype.

    Args:
        datatype: The datatype to get form attributes for.

    Returns
    -------
        Dict[str, Any]: The form control attributes.

    Raises
    ------
        ValueError: If the datatype is not supported.
    """
    try:
        dtype = DatasourceDataType(datatype.lower())
        return DATATYPE_FORM_MAPPING[dtype]
    except ValueError:
        raise ValueError(f"Unsupported datatype: {datatype}") from None
