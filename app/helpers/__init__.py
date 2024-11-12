"""Basic init in order to make this an explicit package."""

import re
from urllib.parse import urlparse


def email_validator(email):
    """Validate an email address."""
    # Basic email validation pattern
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None


def url_validator(url):
    """Validate a URL."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False
