"""
PII Redaction module.
Redacts common PII patterns before storing logs/messages.
Uses regex — no paid services required.
"""
import re

# Pattern registry
_PATTERNS = [
    # Email
    (re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"), "[EMAIL]"),
    # Phone (international + US formats)
    (re.compile(r"(\+?\d[\d\s\-().]{7,}\d)"), "[PHONE]"),
    # Credit card (basic Luhn-ish pattern)
    (re.compile(r"\b(?:\d[ -]?){13,16}\b"), "[CARD]"),
    # SSN
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    # IP address
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "[IP]"),
    # API keys / tokens (long hex/base64 strings)
    (re.compile(r"\b[A-Za-z0-9_\-]{32,}\b"), "[TOKEN]"),
]


def redact(text: str) -> str:
    """Apply all PII patterns to text and return redacted version."""
    if not text:
        return text
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact_dict(data: dict) -> dict:
    """Recursively redact PII from string values in a dict."""
    result = {}
    for k, v in data.items():
        if isinstance(v, str):
            result[k] = redact(v)
        elif isinstance(v, dict):
            result[k] = redact_dict(v)
        elif isinstance(v, list):
            result[k] = [redact(i) if isinstance(i, str) else i for i in v]
        else:
            result[k] = v
    return result
