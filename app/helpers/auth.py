"""Authentication helper functions."""

import bleach
import re


def validate_email(raw_email: str) -> str:
    """Validate and sanitize email input.

    Args:
        raw_email: User provided email

    Returns
    -------
        Cleaned email string

    Raises
    ------
        ValueError: If email is invalid
    """
    if not raw_email:
        raise ValueError("Email is required")

    # Sanitize input
    clean_email = bleach.clean(raw_email.lower(), tags=[], strip=True)

    # Basic email format validation
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(email_pattern, clean_email):
        raise ValueError("Invalid email format")

    return clean_email


def validate_api_key(raw_key: str) -> str:
    """Validate and sanitize API key input.

    Args:
        raw_key: User provided API key

    Returns
    -------
        Cleaned API key string

    Raises
    ------
        ValueError: If API key is invalid
    """
    if not raw_key:
        raise ValueError("API key is required")

    # Sanitize input
    clean_key = bleach.clean(raw_key, tags=[], strip=True)

    # Validate key format (adjust pattern based on your API key format)
    if not re.match(r"^[a-zA-Z0-9_-]{32,}$", clean_key):
        raise ValueError("Invalid API key format")

    return clean_key
