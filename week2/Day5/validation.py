"""
validation.py — Input validation for the Content Research Agent.

Failure scenarios handled:
  1. Empty / whitespace-only query
  2. Query too short  (< 3 chars)
  3. Query too long   (> 1000 chars)
  4. Prompt-injection / jailbreak patterns
"""

MIN_LEN = 3
MAX_LEN = 1000

_BLOCKED_PATTERNS = [
    "ignore previous instructions",
    "ignore all instructions",
    "disregard all",
    "jailbreak",
    "dan mode",
    "prompt injection",
    "bypass your",
    "override your",
    "forget your instructions",
    "new persona",
]


def validate_input(query: str) -> str:
    """
    Validate and return a cleaned query string.
    Raises ValueError with a human-readable message on any failure.
    """
    if not query or not query.strip():
        raise ValueError("Query cannot be empty.")

    cleaned = query.strip()

    if len(cleaned) < MIN_LEN:
        raise ValueError(
            f"Query too short ({len(cleaned)} chars). Minimum is {MIN_LEN} characters."
        )

    if len(cleaned) > MAX_LEN:
        raise ValueError(
            f"Query too long ({len(cleaned)} chars). Maximum is {MAX_LEN} characters."
        )

    lower = cleaned.lower()
    for pattern in _BLOCKED_PATTERNS:
        if pattern in lower:
            raise ValueError(
                f"Query contains a disallowed pattern: '{pattern}'. Please rephrase."
            )

    return cleaned
