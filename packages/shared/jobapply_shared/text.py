"""Deterministic text normalization used by dedupe, matching and field mapping.

Everything here is pure and side-effect free so it can be unit-tested exhaustively and
reused identically by the API, the workers and the browser automation.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from difflib import SequenceMatcher

_WS_RE = re.compile(r"\s+")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")

COMPANY_SUFFIXES = {
    "inc",
    "inc.",
    "llc",
    "l.l.c",
    "ltd",
    "limited",
    "corp",
    "corporation",
    "co",
    "company",
    "gmbh",
    "plc",
    "sa",
    "nv",
    "bv",
    "ag",
    "pty",
    "holdings",
    "group",
    "technologies",
    "technology",
    "labs",
}

SENIORITY_LEVELS: dict[str, int] = {
    "intern": 0,
    "trainee": 0,
    "junior": 1,
    "jr": 1,
    "associate": 1,
    "entry": 1,
    "mid": 2,
    "intermediate": 2,
    "senior": 3,
    "sr": 3,
    "staff": 4,
    "lead": 4,
    "principal": 5,
    "manager": 4,
    "head": 5,
    "director": 6,
    "vp": 7,
    "chief": 8,
}

TITLE_SYNONYMS: dict[str, str] = {
    "sr": "senior",
    "jr": "junior",
    "swe": "software engineer",
    "sde": "software engineer",
    "dev": "developer",
    "eng": "engineer",
    "engr": "engineer",
    "mgr": "manager",
    "analyst ii": "analyst",
    "ml": "machine learning",
    "ai": "artificial intelligence",
    "qa": "quality assurance",
}


def strip_accents(value: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFKD", value) if not unicodedata.combining(char)
    )


def normalize_text(value: str | None) -> str:
    """Lowercase, de-accent, collapse whitespace."""
    if not value:
        return ""
    return _WS_RE.sub(" ", strip_accents(value).lower()).strip()


def slugify(value: str | None) -> str:
    return _NON_ALNUM_RE.sub("-", normalize_text(value)).strip("-")


def normalize_company(value: str | None) -> str:
    """Company key used for duplicate detection: ``Acme, Inc.`` -> ``acme``."""
    text = normalize_text(value).replace("&", " and ")
    text = re.sub(r"[.,]", " ", text)
    tokens = [token for token in text.split() if token and token not in COMPANY_SUFFIXES]
    return " ".join(tokens) or normalize_text(value)


def normalize_title(value: str | None) -> str:
    """Title key: expands common abbreviations and drops noise such as req IDs."""
    text = normalize_text(value)
    text = re.sub(r"\((?:remote|hybrid|onsite|on-site|contract|full[- ]time)\)", " ", text)
    text = re.sub(r"\b(?:req|requisition|job)\s*#?\s*\d+\b", " ", text)
    text = re.sub(r"[^a-z0-9+#/ ]+", " ", text)
    tokens = [TITLE_SYNONYMS.get(token, token) for token in text.split()]
    return _WS_RE.sub(" ", " ".join(tokens)).strip()


def normalize_location(value: str | None) -> str:
    text = normalize_text(value)
    text = re.sub(r"\b(united states of america|usa|u s a|u s)\b", "united states", text)
    text = re.sub(r"[^a-z0-9, ]+", " ", text)
    parts = [part.strip() for part in text.split(",") if part.strip()]
    return ", ".join(parts)


def seniority_level(title: str | None) -> int | None:
    """Return a coarse seniority rank, or ``None`` when the title says nothing."""
    tokens = normalize_title(title).split()
    levels = [SENIORITY_LEVELS[token] for token in tokens if token in SENIORITY_LEVELS]
    if not levels:
        return None
    return max(levels)


def similarity(a: str | None, b: str | None) -> float:
    """Ratio in [0, 1] over normalized strings."""
    left, right = normalize_text(a), normalize_text(b)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    return SequenceMatcher(None, left, right).ratio()


def token_overlap(a: str | None, b: str | None) -> float:
    """Jaccard overlap of word tokens — cheaper and more stable than edit distance
    for multi-word titles."""
    left = set(normalize_title(a).split())
    right = set(normalize_title(b).split())
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def title_similarity(a: str | None, b: str | None) -> float:
    """Blend of sequence similarity and token overlap; robust to word ordering."""
    return round(
        0.5 * similarity(normalize_title(a), normalize_title(b)) + 0.5 * token_overlap(a, b), 4
    )


def content_hash(*parts: str | None) -> str:
    joined = "|".join(normalize_text(part) for part in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def truncate(value: str, limit: int, suffix: str = "…") -> str:
    if len(value) <= limit:
        return value
    return value[: max(0, limit - len(suffix))].rstrip() + suffix
