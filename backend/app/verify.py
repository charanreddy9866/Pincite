"""Check that a quoted passage really appears in the cited page.

Models can paraphrase or invent quotes. Here the application, not the model, decides whether a
citation stands: every quote is matched against the stored page text after light normalization.
"""

import re

_TRANSLATE = str.maketrans({
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", " ": " ", "…": "...",
})
_HYPHEN_BREAK = re.compile(r"(\w)-\s+(\w)")  # "manu- facturer" from a PDF line break


def normalize(text: str) -> str:
    text = text.translate(_TRANSLATE)
    text = _HYPHEN_BREAK.sub(r"\1\2", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text.strip(" .,;:\"'")


_LINE_NUMBER = re.compile(r"(?m)^[ \t]*\d{1,2}[ \t]+")  # deposition transcripts number every line


def quote_in_text(quote: str, page_text: str) -> bool:
    """True if the quote (or each part of it, when elided with '...') appears in order on the page.

    Transcript line numbers are tolerated: a quote that runs across lines 11-12 matches whether or
    not the model copied the "12" in the middle of it.
    """
    q = normalize(quote)
    if len(q.split()) < 3:
        return False  # too short to prove anything
    if _find_parts(q, normalize(page_text)):
        return True
    return _find_parts(q, normalize(_LINE_NUMBER.sub("", page_text)))


def _find_parts(q: str, haystack: str) -> bool:
    position = 0
    for part in (p.strip(" .,;:") for p in q.split("...")):
        if not part:
            continue
        found = haystack.find(part, position)
        if found < 0:
            return False
        position = found + len(part)
    return True
