"""URI utilities for ontology resource identifiers."""

import re
from urllib.parse import urlparse, quote


def sanitize_uri(label: str, namespace: str) -> str:
    """Convert a human-readable label into a valid URI fragment appended to a namespace.

    Applies the following transformations:
      1. Strip leading/trailing whitespace.
      2. Convert to PascalCase (split on non-alphanumeric, capitalise each word).
      3. Remove any remaining characters that are invalid in a URI fragment.
      4. Percent-encode Unicode characters.
      5. Append to the namespace (adds '#' separator if the namespace lacks one).

    Args:
        label: Human-readable name (e.g. "temperature sensor").
        namespace: Base namespace URI (e.g. "http://example.org/onto").

    Returns:
        Full URI string, e.g. "http://example.org/onto#TemperatureSensor".
    """
    if not label or not label.strip():
        raise ValueError("Label must be a non-empty string")
    if not namespace or not namespace.strip():
        raise ValueError("Namespace must be a non-empty string")

    # Split on any non-alphanumeric character and capitalise each word
    words = re.split(r"[^a-zA-Z0-9]+", label.strip())
    fragment = "".join(word.capitalize() for word in words if word)

    if not fragment:
        raise ValueError(f"Label '{label}' produced an empty URI fragment")

    # Ensure fragment starts with a letter (XML/RDF requirement)
    if fragment[0].isdigit():
        fragment = "C" + fragment

    # Percent-encode any non-ASCII characters
    fragment = quote(fragment, safe="")

    # Determine separator
    if namespace.endswith("#") or namespace.endswith("/"):
        return f"{namespace}{fragment}"
    return f"{namespace}#{fragment}"


def validate_uri(uri: str) -> bool:
    """Check whether a string is a syntactically valid absolute URI.

    Uses urllib.parse to verify the URI has both a scheme and a netloc (or
    a recognised scheme like ``urn:`` / ``file:``).

    Args:
        uri: The URI string to validate.

    Returns:
        True if the URI is valid, False otherwise.
    """
    if not uri or not isinstance(uri, str):
        return False

    try:
        parsed = urlparse(uri)
    except Exception:
        return False

    # Must have a scheme
    if not parsed.scheme:
        return False

    # For http/https/ftp, require a netloc
    if parsed.scheme in ("http", "https", "ftp"):
        return bool(parsed.netloc)

    # For urn, file, and other schemes, scheme + path is sufficient
    return bool(parsed.scheme and (parsed.netloc or parsed.path))
