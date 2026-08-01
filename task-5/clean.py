"""Clean stage: turn the raw strings from parse.py into typed, trustworthy
values. Every function here is defensive -- the source is a webpage, not a
schema, so missing or oddly-formatted text shouldn't crash the pipeline.
"""
from __future__ import annotations

import re

RATING_WORDS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}

_AVAILABLE_RE = re.compile(r"(\d+)\s+available", re.IGNORECASE)
_PRICE_RE = re.compile(r"[\d.]+")


def clean_price(text: str | None) -> float | None:
    if not text:
        return None
    match = _PRICE_RE.search(text)
    return float(match.group()) if match else None


def clean_rating(word: str | None) -> int | None:
    return RATING_WORDS.get(word) if word else None


def clean_availability(text: str | None) -> tuple[bool, int | None]:
    """"In stock (22 available)" -> (True, 22). "Out of stock" -> (False, None)."""
    if not text:
        return False, None
    in_stock = "in stock" in text.lower()
    match = _AVAILABLE_RE.search(text)
    stock_count = int(match.group(1)) if match else None
    return in_stock, stock_count


def clean_int(text: str | None) -> int | None:
    if text is None:
        return None
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else None


def clean_text(text: str | None) -> str:
    """Collapse internal whitespace/newlines picked up from the page layout."""
    return re.sub(r"\s+", " ", text).strip() if text else ""
