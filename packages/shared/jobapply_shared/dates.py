"""Date helpers used by the resume parser and the matching engine."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime

MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

_MONTH_YEAR = re.compile(r"(?i)\b([a-z]{3,9})\.?\s+(\d{4})\b")
_NUMERIC = re.compile(r"\b(\d{1,2})[/-](\d{4})\b")
_YEAR_ONLY = re.compile(r"\b(19|20)(\d{2})\b")
PRESENT_TOKENS = {"present", "current", "now", "today", "ongoing"}


def utcnow() -> datetime:
    return datetime.now(tz=UTC)


def parse_partial_date(value: str | None) -> date | None:
    """Parse the loose date formats that appear on resumes (``Mar 2021``, ``03/2021``,
    ``2021``). Returns the first day of the resolved month."""
    if not value:
        return None
    text = value.strip()
    if text.lower() in PRESENT_TOKENS:
        return None
    match = _MONTH_YEAR.search(text)
    if match:
        month = MONTHS.get(match.group(1).lower())
        if month:
            return date(int(match.group(2)), month, 1)
    match = _NUMERIC.search(text)
    if match:
        month = min(max(int(match.group(1)), 1), 12)
        return date(int(match.group(2)), month, 1)
    match = _YEAR_ONLY.search(text)
    if match:
        return date(int(match.group(0)), 1, 1)
    return None


def is_present(value: str | None) -> bool:
    return bool(value) and value.strip().lower() in PRESENT_TOKENS


def months_between(start: date, end: date | None = None) -> int:
    finish = end or date.today()
    return max((finish.year - start.year) * 12 + (finish.month - start.month), 0)


def years_between(start: date, end: date | None = None) -> float:
    return round(months_between(start, end) / 12, 2)
