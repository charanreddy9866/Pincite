"""Redact sensitive identifiers before text is stored or sent to any model.

Redaction runs once, at ingest. Nothing downstream (database, search index, model prompts,
the UI) ever sees the original values, so there is no second place they can leak from.
"""

import re
from collections import Counter

_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("SSN", re.compile(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")),
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    (
        "ACCOUNT",
        re.compile(
            r"(?i)\b((?:account|acct|routing|aba)\s*(?:no\.?|number|#)?\s*[:#]?\s*)(\d[\d\- ]{4,20}\d)\b"
        ),
    ),
    ("PHONE", re.compile(r"(?<!\d)(?:\+1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?!\d)")),
]

_CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def _luhn_ok(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
        alt = not alt
    return total % 10 == 0


def redact(text: str) -> tuple[str, Counter]:
    """Return (redacted_text, counts_by_kind)."""
    counts: Counter = Counter()

    def card_sub(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            counts["CARD"] += 1
            return "[REDACTED CARD]"
        return m.group(0)

    text = _CARD.sub(card_sub, text)

    for kind, pattern in _PATTERNS:
        def sub(m: re.Match, kind: str = kind) -> str:
            counts[kind] += 1
            if kind == "ACCOUNT":
                return f"{m.group(1)}[REDACTED ACCOUNT]"
            return f"[REDACTED {kind}]"

        text = pattern.sub(sub, text)
    return text, counts
