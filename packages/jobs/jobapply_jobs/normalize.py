"""Turn a raw posting into the canonical job shape.

Extraction here is deterministic and conservative: a field the posting does not state
stays ``None``. Where a model could add value (a long free-text posting), the
``JOB_EXTRACTION`` prompt runs *after* this and may only fill gaps, never overwrite a
value taken from structured source data.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from jobapply_shared.enums import AtsKind, EmploymentType, RemoteType
from jobapply_shared.text import (
    content_hash,
    normalize_company,
    normalize_location,
    normalize_title,
    seniority_level,
)

from jobapply_jobs.models import NormalizedJob, RawJob

TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"[ \t]+")
BULLET_LINE_RE = re.compile(r"^\s*(?:[-•▪◦·*]|\d{1,2}[.)])\s+(.*\S)\s*$")

REMOTE_PATTERNS: tuple[tuple[re.Pattern[str], RemoteType], ...] = (
    (re.compile(r"(?i)\b(?:fully[\s-]|100%\s*)?remote\b(?!\s*(?:not|un))"), RemoteType.REMOTE),
    (re.compile(r"(?i)\bhybrid\b"), RemoteType.HYBRID),
    (re.compile(r"(?i)\b(?:on[\s-]?site|in[\s-]office)\b"), RemoteType.ONSITE),
)

EMPLOYMENT_PATTERNS: tuple[tuple[re.Pattern[str], EmploymentType], ...] = (
    (re.compile(r"(?i)\bintern(?:ship)?\b"), EmploymentType.INTERNSHIP),
    (re.compile(r"(?i)\bpart[\s-]time\b"), EmploymentType.PART_TIME),
    (
        re.compile(r"(?i)\b(?:contract|contractor|freelance|c2c|w2 contract)\b"),
        EmploymentType.CONTRACT,
    ),
    (re.compile(r"(?i)\b(?:temporary|temp)\b"), EmploymentType.TEMPORARY),
    (re.compile(r"(?i)\bfull[\s-]time\b"), EmploymentType.FULL_TIME),
)

#: Salary written as a range, e.g. "$150,000 - $190,000" or "150k–190k".
SALARY_RANGE_RE = re.compile(
    r"(?i)(?:\$|usd\s*)?(\d{2,3}(?:,\d{3})?|\d{2,3})\s*(k\b)?\s*(?:-|–|—|to)\s*"
    r"(?:\$|usd\s*)?(\d{2,3}(?:,\d{3})?|\d{2,3})\s*(k\b)?"
)
HOURLY_RE = re.compile(r"(?i)per\s+hour|/\s*hour|hourly|/hr\b")

YEARS_REQUIRED_RE = re.compile(
    r"(?i)\b(\d{1,2})\s*\+?\s*(?:-|–|to)?\s*(?:\d{1,2})?\s*(?:years?|yrs?)"
    r"(?:\s+of)?(?:\s+(?:relevant|professional|industry|hands[- ]on))?\s+experience"
)

DEGREE_RE = re.compile(
    r"(?i)\b(bachelor'?s?|master'?s?|ph\.?d|doctorate|associate'?s?|mba|b\.?s\.?|m\.?s\.?)\b"
)

#: Sponsorship language is captured verbatim; the boolean is only set when the
#: posting is unambiguous.
SPONSORSHIP_SENTENCE_RE = re.compile(
    r"(?i)[^.\n]*\b(?:sponsor(?:ship)?|visa|work authorization|h-?1b|opt|cpt|green card)"
    r"\b[^.\n]*[.\n]?"
)
NO_SPONSORSHIP_RE = re.compile(
    r"(?i)\b(?:not|unable to|cannot|will not|do not|does not|no)\b[^.\n]{0,40}\bsponsor"
)
YES_SPONSORSHIP_RE = re.compile(
    r"(?i)\b(?:will|can|do|does|are able to|happy to|open to)\b[^.\n]{0,30}\bsponsor"
)

ATS_URL_PATTERNS: tuple[tuple[re.Pattern[str], AtsKind], ...] = (
    (
        re.compile(r"(?i)(?:job-)?boards?(?:-api)?\.greenhouse\.io|greenhouse\.io/embed"),
        AtsKind.GREENHOUSE,
    ),
    (re.compile(r"(?i)jobs\.lever\.co|api\.lever\.co"), AtsKind.LEVER),
    (re.compile(r"(?i)jobs\.ashbyhq\.com|ashbyhq\.com"), AtsKind.ASHBY),
    (re.compile(r"(?i)myworkdayjobs\.com|/wday/"), AtsKind.WORKDAY),
    (re.compile(r"(?i)\.icims\.com"), AtsKind.ICIMS),
    (re.compile(r"(?i)smartrecruiters\.com"), AtsKind.SMARTRECRUITERS),
)

SECTION_HEADINGS = {
    "requirements": (
        "requirements",
        "qualifications",
        "what you'll need",
        "what you will need",
        "minimum qualifications",
        "basic qualifications",
        "who you are",
        "you have",
    ),
    "preferred": (
        "preferred qualifications",
        "nice to have",
        "nice-to-have",
        "bonus points",
        "preferred",
        "plus",
    ),
}

#: Skills are matched against a vocabulary rather than guessed from prose, so a job
#: never gains a "skill" that is really a stray capitalised word.
from jobapply_resume.vocabulary import TECH_TERMS  # noqa: E402


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"(?is)<(?:script|style).*?</(?:script|style)>", " ", value)
    text = re.sub(r"(?i)<(?:br|/p|/li|/div|/h[1-6])\s*/?>", "\n", text)
    text = re.sub(r"(?i)<li[^>]*>", "\n- ", text)
    text = TAG_RE.sub(" ", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&#39;", "'")
        .replace("&quot;", '"')
    )
    text = WHITESPACE_RE.sub(" ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def detect_remote_type(*sources: str | None) -> RemoteType:
    haystack = " ".join(part for part in sources if part)
    for pattern, kind in REMOTE_PATTERNS:
        if pattern.search(haystack):
            return kind
    return RemoteType.UNKNOWN


def detect_employment_type(*sources: str | None) -> EmploymentType:
    haystack = " ".join(part for part in sources if part)
    for pattern, kind in EMPLOYMENT_PATTERNS:
        if pattern.search(haystack):
            return kind
    return EmploymentType.UNKNOWN


def detect_ats(*urls: str | None) -> str | None:
    for url in urls:
        if not url:
            continue
        for pattern, kind in ATS_URL_PATTERNS:
            if pattern.search(url):
                return str(kind)
    return None


def parse_salary(text: str | None) -> tuple[int | None, int | None, str | None]:
    """Extract an annual salary range. Hourly rates and single figures are ignored:
    a guess here would silently distort matching."""
    if not text:
        return None, None, None
    if HOURLY_RE.search(text):
        return None, None, None
    match = SALARY_RANGE_RE.search(text)
    if not match:
        return None, None, None

    def to_int(raw: str, thousands: str | None) -> int:
        value = int(raw.replace(",", ""))
        return value * 1000 if thousands else value

    low = to_int(match.group(1), match.group(2))
    high = to_int(match.group(3), match.group(4))
    if low > high:
        low, high = high, low
    # Anything below a plausible annual floor is probably not an annual figure.
    if high < 10_000:
        return None, None, None
    currency = "USD" if "$" in text or re.search(r"(?i)\busd\b", text) else None
    return low, high, currency


def extract_sections(description: str) -> tuple[list[str], list[str]]:
    """Pull requirement and preferred-qualification bullets out of a description."""
    requirements: list[str] = []
    preferred: list[str] = []
    current: list[str] | None = None

    for raw_line in description.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        heading = line.lower().strip(":").strip()
        if len(heading) <= 45:
            if any(heading.startswith(alias) for alias in SECTION_HEADINGS["preferred"]):
                current = preferred
                continue
            if any(heading.startswith(alias) for alias in SECTION_HEADINGS["requirements"]):
                current = requirements
                continue
        bullet = BULLET_LINE_RE.match(line)
        if bullet and current is not None:
            current.append(bullet.group(1))
        elif not bullet and len(line) > 120:
            # A prose paragraph ends the bullet run.
            current = None
    return requirements[:40], preferred[:40]


def extract_skills(text: str) -> list[str]:
    lowered = text.lower()
    words = re.findall(r"[a-z0-9][a-z0-9.+#-]*", lowered)
    phrases = set(words) | {f"{a} {b}" for a, b in zip(words, words[1:], strict=False)}
    return sorted(phrases & TECH_TERMS)


def extract_experience_years(text: str) -> float | None:
    matches = [int(match.group(1)) for match in YEARS_REQUIRED_RE.finditer(text)]
    plausible = [value for value in matches if 0 < value <= 30]
    return float(min(plausible)) if plausible else None


def extract_education(text: str) -> str | None:
    match = DEGREE_RE.search(text)
    return match.group(0) if match else None


def extract_sponsorship(text: str) -> tuple[str | None, bool | None]:
    """Return the posting's own sponsorship sentence and, only when unambiguous, a
    boolean. Silence is never read as either answer."""
    match = SPONSORSHIP_SENTENCE_RE.search(text)
    if not match:
        return None, None
    sentence = match.group(0).strip()
    if NO_SPONSORSHIP_RE.search(sentence):
        return sentence, False
    if YES_SPONSORSHIP_RE.search(sentence):
        return sentence, True
    return sentence, None


def build_dedupe_key(company: str, title: str, location: str | None, source_job_id: str) -> str:
    return content_hash(
        normalize_company(company),
        normalize_title(title),
        normalize_location(location),
        source_job_id,
    )


class JobNormalizer:
    """Deterministic RawJob → NormalizedJob conversion."""

    def normalize(self, raw: RawJob) -> NormalizedJob:
        description = strip_html(raw.description)
        haystack = "\n".join(
            part for part in (raw.title, raw.location, raw.remote_hint, description) if part
        )
        requirements, preferred = extract_sections(description)
        salary_min, salary_max, currency = parse_salary(raw.salary_text or description)
        sponsorship_text, sponsorship_offered = extract_sponsorship(description)
        seniority = seniority_level(raw.title)

        return NormalizedJob(
            source_slug=raw.source_slug,
            source_job_id=raw.source_job_id,
            company_name=raw.company.strip(),
            normalized_company=normalize_company(raw.company),
            title=raw.title.strip(),
            normalized_title=normalize_title(raw.title),
            location=raw.location,
            normalized_location=normalize_location(raw.location) or None,
            remote_type=detect_remote_type(raw.remote_hint, raw.location, raw.title, description),
            employment_type=detect_employment_type(raw.employment_type, raw.title, description),
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=currency,
            salary_period="year" if salary_min else None,
            description=description or None,
            requirements=requirements,
            preferred_qualifications=preferred,
            skills=extract_skills(haystack),
            education=extract_education(description),
            experience_required_years=extract_experience_years(description),
            seniority=str(seniority) if seniority is not None else None,
            sponsorship_information=sponsorship_text,
            sponsorship_offered=sponsorship_offered,
            apply_url=raw.apply_url,
            posting_url=raw.posting_url,
            detected_ats=detect_ats(raw.apply_url, raw.posting_url),
            posted_at=raw.posted_at or datetime.now(tz=UTC),
            dedupe_key=build_dedupe_key(raw.company, raw.title, raw.location, raw.source_job_id),
            # Only a substantial body is hashed: short boilerplate descriptions
            # collide between genuinely different roles, and a false duplicate is
            # worse than a missed one.
            content_hash=(
                content_hash(description) if description and len(description) >= 200 else None
            ),
            raw=raw.payload,
        )
