"""Deterministic resume parser.

The parser produces *suggestions*. Nothing it extracts becomes profile data until the
user reviews it in onboarding, and it never attempts to infer legally significant
facts (work authorization, sponsorship, clearances, demographics) — those are asked
explicitly.
"""

from __future__ import annotations

import re
from datetime import date

from jobapply_shared.dates import parse_partial_date
from jobapply_shared.text import normalize_text

from jobapply_resume.models import (
    ContactInfo,
    ParsedCertification,
    ParsedEducation,
    ParsedPosition,
    ParsedProject,
    ParsedResume,
)

# --------------------------------------------------------------------------- patterns
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?:(?:\+\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)|\d{2,4})[\s.-]?\d{3}[\s.-]?\d{3,4})")
URL_RE = re.compile(
    r"(?i)\b((?:https?://|www\.)[^\s,;)]+|[\w-]+\.(?:com|io|dev|me|ai|net|org|co)(?:/[^\s,;)]*)?)"
)
LINKEDIN_RE = re.compile(r"(?i)linkedin\.com/[^\s,;)]+")
GITHUB_RE = re.compile(r"(?i)github\.com/[^\s,;)]+")
GPA_RE = re.compile(r"(?i)\bgpa[:\s]*([0-4](?:\.\d{1,2})?)\s*(?:/\s*([0-5](?:\.\d{1,2})?))?")
BULLET_RE = re.compile(r"^\s*(?:[-•▪◦·*‣●]|\d{1,2}[.)])\s+")

MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
_DATE_TOKEN = rf"(?:{MONTH}\s*'?\d{{2,4}}|\d{{1,2}}/\d{{4}}|\d{{4}})"
DATE_RANGE_RE = re.compile(
    rf"(?i)({_DATE_TOKEN})\s*(?:-|–|—|to|until)\s*({_DATE_TOKEN}|present|current|now|today|ongoing)"
)

SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "summary": ("summary", "professional summary", "profile", "objective", "about me", "about"),
    "experience": (
        "experience",
        "work experience",
        "professional experience",
        "employment",
        "employment history",
        "work history",
        "career history",
        "relevant experience",
    ),
    "education": ("education", "academic background", "academics", "academic history"),
    "skills": (
        "skills",
        "technical skills",
        "core competencies",
        "competencies",
        "technologies",
        "tools",
        "technical proficiencies",
    ),
    "certifications": (
        "certifications",
        "certification",
        "certificates",
        "licenses",
        "licenses and certifications",
    ),
    "projects": ("projects", "personal projects", "selected projects", "side projects"),
    "awards": ("awards", "honors", "achievements", "publications", "interests", "languages"),
}

TITLE_KEYWORDS = {
    "engineer",
    "developer",
    "analyst",
    "manager",
    "scientist",
    "designer",
    "director",
    "intern",
    "consultant",
    "architect",
    "administrator",
    "specialist",
    "lead",
    "president",
    "officer",
    "coordinator",
    "assistant",
    "associate",
    "researcher",
    "programmer",
    "technician",
    "strategist",
    "recruiter",
    "accountant",
    "nurse",
    "teacher",
    "writer",
    "marketer",
    "founder",
    "head",
    "principal",
    "supervisor",
}

DEGREE_KEYWORDS = (
    "bachelor",
    "master",
    "associate",
    "doctor",
    "phd",
    "ph.d",
    "mba",
    "b.s",
    "bs",
    "b.a",
    "ba",
    "m.s",
    "ms",
    "m.a",
    "ma",
    "bsc",
    "msc",
    "beng",
    "meng",
    "diploma",
)

SKILL_LABEL_RE = re.compile(
    r"(?i)^\s*(languages?|frameworks?|databases?|cloud|tools?|technologies|devops|"
    r"analytics|libraries|platforms|methodologies|soft skills)\s*[:\-–]\s*"
)
SPLIT_SKILLS_RE = re.compile(r"[,;|•·/]|\s{3,}")
LOCATION_RE = re.compile(
    r"(?i)(remote|hybrid|on-?site|[A-Z][a-zA-Z .'-]+,\s*(?:[A-Z]{2}|[A-Z][a-zA-Z ]+))$"
)


def _is_bullet(line: str) -> bool:
    return bool(BULLET_RE.match(line))


def _strip_bullet(line: str) -> str:
    return BULLET_RE.sub("", line).strip()


def _heading_key(line: str) -> str | None:
    """Return the canonical section name if ``line`` looks like a section heading."""
    stripped = line.strip().strip(":").strip()
    if not stripped or len(stripped) > 45 or _is_bullet(line):
        return None
    if EMAIL_RE.search(stripped) or DATE_RANGE_RE.search(stripped):
        return None
    normalized = normalize_text(stripped.replace("&", "and"))
    normalized = re.sub(r"[^a-z ]+", " ", normalized).strip()
    for key, aliases in SECTION_ALIASES.items():
        if normalized in aliases:
            return key
    return None


def split_sections(text: str) -> dict[str, list[str]]:
    """Split resume text into canonical sections, keeping a ``header`` block for
    everything above the first recognised heading."""
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for raw_line in text.split("\n"):
        key = _heading_key(raw_line)
        if key:
            current = key
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(raw_line)
    return sections


# --------------------------------------------------------------------------- contact
def _first_url(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    if not match:
        return None
    url = match.group(0).rstrip(".,;)")
    return url if url.startswith("http") else f"https://{url}"


def parse_contact(text: str, header_lines: list[str]) -> ContactInfo:
    head = "\n".join(header_lines[:12]) or text[:1200]
    email_match = EMAIL_RE.search(head) or EMAIL_RE.search(text)
    phone_match = PHONE_RE.search(head) or PHONE_RE.search(text)
    linkedin = _first_url(LINKEDIN_RE, text)
    github = _first_url(GITHUB_RE, text)

    portfolio = None
    # Strip e-mail addresses first so their domain is not mistaken for a portfolio.
    head_without_emails = EMAIL_RE.sub(" ", head)
    for candidate in URL_RE.finditer(head_without_emails):
        url = candidate.group(0).rstrip(".,;)")
        if "linkedin.com" in url.lower() or "github.com" in url.lower():
            continue
        portfolio = url if url.startswith("http") else f"https://{url}"
        break

    full_name = None
    for line in header_lines[:6]:
        candidate = line.strip()
        if not candidate or len(candidate) > 60:
            continue
        if EMAIL_RE.search(candidate) or PHONE_RE.search(candidate) or URL_RE.search(candidate):
            continue
        words = candidate.replace(",", " ").split()
        if 1 < len(words) <= 5 and all(word[:1].isalpha() for word in words):
            full_name = " ".join(words)
            break

    location = None
    for line in header_lines[:10]:
        match = LOCATION_RE.search(line.strip().rstrip("|").strip())
        if match and not EMAIL_RE.search(line):
            location = match.group(0).strip()
            break

    return ContactInfo(
        full_name=full_name,
        email=email_match.group(0) if email_match else None,
        phone=phone_match.group(0).strip() if phone_match else None,
        location=location,
        linkedin_url=linkedin,
        github_url=github,
        portfolio_url=portfolio,
    )


# ------------------------------------------------------------------------- experience
def _looks_like_title(part: str) -> bool:
    tokens = set(normalize_text(part).replace("/", " ").split())
    return bool(tokens & TITLE_KEYWORDS)


def _looks_like_location(part: str) -> bool:
    return bool(LOCATION_RE.search(part.strip()))


def _classify_header_parts(parts: list[str]) -> tuple[str | None, str | None, str | None]:
    """Assign header fragments to (company, title, location)."""
    company = title = location = None
    for part in parts:
        cleaned = part.strip(" ,|–—-")
        if not cleaned:
            continue
        if location is None and _looks_like_location(cleaned) and not _looks_like_title(cleaned):
            location = cleaned
        elif title is None and _looks_like_title(cleaned):
            title = cleaned
        elif company is None:
            company = cleaned
        elif title is None:
            title = cleaned
    return company, title, location


def _split_header(line: str) -> list[str]:
    return [part for part in re.split(r"\s*[|•·–—]\s*|\s+[-]\s+|\s+at\s+", line) if part.strip()]


def parse_experience(lines: list[str]) -> list[ParsedPosition]:
    positions: list[ParsedPosition] = []
    pending: list[str] = []
    current: ParsedPosition | None = None

    def flush(header_parts: list[str], date_text: str | None) -> None:
        nonlocal current
        company, title, location = _classify_header_parts(header_parts)
        if not company and not title:
            return
        start_text, end_text = (None, None)
        if date_text:
            match = DATE_RANGE_RE.search(date_text)
            if match:
                start_text, end_text = match.group(1), match.group(2)
        end_lower = (end_text or "").lower()
        current = ParsedPosition(
            company=company,
            title=title,
            location=location,
            start_date=parse_partial_date(start_text),
            end_date=parse_partial_date(end_text),
            is_current=end_lower in {"present", "current", "now", "today", "ongoing"},
            date_text=date_text,
        )
        positions.append(current)

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if _is_bullet(line):
            if current is not None:
                current.bullets.append(_strip_bullet(line))
            continue

        date_match = DATE_RANGE_RE.search(line)
        if date_match:
            remainder = DATE_RANGE_RE.sub("", line).strip(" ,|–—-")
            header_parts = [*[p for chunk in pending for p in _split_header(chunk)]]
            header_parts.extend(_split_header(remainder))
            flush(header_parts, date_match.group(0))
            pending = []
            continue

        # A non-bullet, non-date line: either a header waiting for its dates, or a
        # continuation paragraph of the current position.
        if current is not None and len(line) > 90:
            current.bullets.append(line)
            continue
        pending.append(line)
        if len(pending) > 3:
            pending.pop(0)

    if pending and not positions:
        flush([part for chunk in pending for part in _split_header(chunk)], None)
    return positions


# -------------------------------------------------------------------------- education
def parse_education(lines: list[str]) -> list[ParsedEducation]:
    records: list[ParsedEducation] = []
    block: list[str] = []

    def flush_block(chunk: list[str]) -> None:
        text = " | ".join(part.strip() for part in chunk if part.strip())
        if not text:
            return
        degree = None
        institution = None
        field = None
        for part in re.split(r"\s*[|•·]\s*|,\s*", text):
            cleaned = part.strip()
            if not cleaned:
                continue
            lowered = cleaned.lower()
            if degree is None and any(keyword in lowered for keyword in DEGREE_KEYWORDS):
                degree = cleaned
                match = re.search(r"(?i)\b(?:in|of)\s+([A-Za-z &]+)", cleaned)
                if match:
                    field = match.group(1).strip()
            elif institution is None and re.search(
                r"(?i)university|college|institute|school|academy|polytechnic", cleaned
            ):
                institution = cleaned
        gpa_match = GPA_RE.search(text)
        date_match = DATE_RANGE_RE.search(text)
        end_date = None
        if date_match:
            end_date = parse_partial_date(date_match.group(2))
        else:
            years = re.findall(r"\b(19|20)\d{2}\b", text)
            if years:
                end_date = date(int(re.findall(r"\b(?:19|20)\d{2}\b", text)[-1]), 1, 1)
        if not institution and not degree:
            return
        records.append(
            ParsedEducation(
                institution=institution or (degree or "")[:255],
                degree=degree,
                field_of_study=field,
                end_date=end_date,
                gpa=float(gpa_match.group(1)) if gpa_match else None,
                date_text=date_match.group(0) if date_match else None,
            )
        )

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            if block:
                flush_block(block)
                block = []
            continue
        starts_new = (
            bool(re.search(r"(?i)university|college|institute|school|academy", line)) and block
        )
        if starts_new:
            flush_block(block)
            block = []
        block.append(_strip_bullet(line))
    if block:
        flush_block(block)
    return records


# ----------------------------------------------------------------------------- skills
def parse_skills(lines: list[str]) -> list[str]:
    skills: list[str] = []
    seen: set[str] = set()
    for raw_line in lines:
        line = SKILL_LABEL_RE.sub("", _strip_bullet(raw_line)).strip()
        if not line:
            continue
        for chunk in SPLIT_SKILLS_RE.split(line):
            skill = chunk.strip(" .;:-–—")
            if not skill or len(skill) > 45 or len(skill) < 2:
                continue
            if skill.endswith((".", "!")) and len(skill.split()) > 6:
                continue
            key = normalize_text(skill)
            if key in seen:
                continue
            seen.add(key)
            skills.append(skill)
    return skills


def parse_certifications(lines: list[str]) -> list[ParsedCertification]:
    records: list[ParsedCertification] = []
    for raw_line in lines:
        line = _strip_bullet(raw_line).strip()
        if not line or len(line) < 3:
            continue
        issuer: str | None = None
        issued: date | None = None

        paren_match = re.search(r"\(([^)]*)\)", line)
        if paren_match:
            inner = paren_match.group(1).strip()
            year_match = re.fullmatch(r"(?:19|20)\d{2}", inner)
            if year_match:
                issued = date(int(inner), 1, 1)
            elif inner:
                issuer = inner
            line = line.replace(paren_match.group(0), " ")

        # "Issued by X" / "by X" is an issuer; a plain dash is part of the name
        # ("AWS Certified Solutions Architect - Associate" is one certification).
        issuer_match = re.search(r"(?i)\s*[,\-–—|]?\s*(?:issued by|by)\s+(.+)$", line)
        if issuer_match and issuer is None:
            issuer = issuer_match.group(1).strip()
            line = line[: issuer_match.start()]

        year_match = re.search(r"\b(?:19|20)\d{2}\b", line)
        if year_match and issued is None:
            issued = date(int(year_match.group(0)), 1, 1)
        line = re.sub(r"\b(?:19|20)\d{2}\b", " ", line)

        name = re.sub(r"\s{2,}", " ", line).strip(" ,;:-–—|")
        if not name:
            continue
        records.append(
            ParsedCertification(name=name[:255], issuer=issuer or None, issued_on=issued)
        )
    return records


def parse_projects(lines: list[str]) -> list[ParsedProject]:
    projects: list[ParsedProject] = []
    current: ParsedProject | None = None
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if _is_bullet(line):
            if current is not None:
                current.highlights.append(_strip_bullet(line))
            continue
        parts = re.split(r"\s*[–—:|]\s*", line, maxsplit=1)
        name = parts[0].strip()
        description = parts[1].strip() if len(parts) > 1 else None
        url_match = URL_RE.search(line)
        current = ParsedProject(
            name=name[:255],
            description=description,
            url=url_match.group(0) if url_match else None,
        )
        projects.append(current)
    return projects


# ------------------------------------------------------------------------------- main
def parse_resume(text: str) -> ParsedResume:
    """Parse resume text into structured records."""
    sections = split_sections(text)
    header_lines = sections.get("header", [])
    contact = parse_contact(text, header_lines)

    summary_lines = [line.strip() for line in sections.get("summary", []) if line.strip()]
    summary = " ".join(summary_lines) or None
    if summary is None and header_lines:
        # Some resumes open with an unlabelled summary paragraph under the contact block.
        paragraph = [line.strip() for line in header_lines if len(line.strip()) > 90]
        summary = " ".join(paragraph[:2]) or None

    parsed = ParsedResume(
        contact=contact,
        summary=summary,
        skills=parse_skills(sections.get("skills", [])),
        positions=parse_experience(sections.get("experience", [])),
        education=parse_education(sections.get("education", [])),
        certifications=parse_certifications(sections.get("certifications", [])),
        projects=parse_projects(sections.get("projects", [])),
        raw_text=text,
    )

    if not parsed.positions:
        parsed.warnings.append(
            "No work experience section was detected — add positions manually so "
            "tailoring has grounded facts to work from."
        )
    if not parsed.skills:
        parsed.warnings.append("No skills section was detected.")
    if not parsed.contact.email:
        parsed.warnings.append("No e-mail address was found in the resume.")
    return parsed
