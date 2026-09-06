"""Build the truth layer's source index from a user's approved records.

This module deliberately takes plain dictionaries rather than ORM objects so the
resume package stays independent of the database layer.
"""

from __future__ import annotations

from typing import Any

from jobapply_shared.dates import years_between
from jobapply_shared.text import normalize_text

from jobapply_resume.models import SourceRecord


def _clean(value: Any) -> str:
    return str(value).strip() if value not in (None, "") else ""


def experience_source(record: dict[str, Any]) -> SourceRecord:
    bullets = record.get("accomplishments") or []
    technologies = record.get("technologies") or []
    skills = record.get("skills") or []
    text = " ".join(
        part
        for part in [
            _clean(record.get("title")),
            _clean(record.get("company")),
            _clean(record.get("location")),
            _clean(record.get("description")),
            " ".join(_clean(bullet) for bullet in bullets),
            " ".join(_clean(tech) for tech in technologies),
            " ".join(_clean(skill) for skill in skills),
        ]
        if part
    )
    numbers: dict[str, float] = {}
    start = record.get("start_date")
    if start:
        span = years_between(start, record.get("end_date"))
        for tech in [*technologies, *skills]:
            key = normalize_text(tech)
            if key:
                numbers[key] = max(numbers.get(key, 0.0), span)
    return SourceRecord(
        id=f"experience_{record['id']}",
        kind="experience",
        text=text,
        entities=[
            *(x for x in [_clean(record.get("company")), _clean(record.get("title"))] if x),
            *(_clean(tech) for tech in technologies),
            *(_clean(skill) for skill in skills),
        ],
        numbers=numbers,
    )


def education_source(record: dict[str, Any]) -> SourceRecord:
    text = " ".join(
        part
        for part in [
            _clean(record.get("degree")),
            _clean(record.get("field_of_study")),
            _clean(record.get("institution")),
            " ".join(_clean(course) for course in record.get("relevant_coursework") or []),
        ]
        if part
    )
    return SourceRecord(
        id=f"education_{record['id']}",
        kind="education",
        text=text,
        entities=[
            x
            for x in [
                _clean(record.get("institution")),
                _clean(record.get("degree")),
                _clean(record.get("field_of_study")),
            ]
            if x
        ],
    )


def skill_source(record: dict[str, Any]) -> SourceRecord:
    name = _clean(record.get("name"))
    numbers: dict[str, float] = {}
    years = record.get("years_experience")
    if years is not None:
        numbers[normalize_text(name)] = float(years)
    return SourceRecord(
        id=f"skill_{record['id']}",
        kind="skill",
        text=name,
        entities=[name] if name else [],
        numbers=numbers,
    )


def certification_source(record: dict[str, Any]) -> SourceRecord:
    text = " ".join(
        part for part in [_clean(record.get("name")), _clean(record.get("issuer"))] if part
    )
    return SourceRecord(
        id=f"certification_{record['id']}",
        kind="certification",
        text=text,
        entities=[x for x in [_clean(record.get("name")), _clean(record.get("issuer"))] if x],
    )


def project_source(record: dict[str, Any]) -> SourceRecord:
    highlights = record.get("highlights") or []
    technologies = record.get("technologies") or []
    text = " ".join(
        part
        for part in [
            _clean(record.get("name")),
            _clean(record.get("role")),
            _clean(record.get("description")),
            " ".join(_clean(item) for item in highlights),
            " ".join(_clean(tech) for tech in technologies),
        ]
        if part
    )
    return SourceRecord(
        id=f"project_{record['id']}",
        kind="project",
        text=text,
        entities=[
            *(x for x in [_clean(record.get("name"))] if x),
            *(_clean(tech) for tech in technologies),
        ],
    )


def profile_source(record: dict[str, Any]) -> SourceRecord:
    """The profile itself is a source: name, headline, total years of experience.

    Work-authorization fields are deliberately *not* included. They are answered from
    the explicit profile fields by the question engine, never woven into generated
    prose.
    """
    text = " ".join(
        part
        for part in [
            _clean(record.get("first_name")),
            _clean(record.get("last_name")),
            _clean(record.get("current_title")),
            _clean(record.get("summary")),
            _clean(record.get("city")),
            _clean(record.get("state")),
            _clean(record.get("country")),
        ]
        if part
    )
    numbers: dict[str, float] = {}
    years = record.get("years_experience")
    if years is not None:
        numbers["__total_experience__"] = float(years)
    return SourceRecord(
        id="profile",
        kind="profile",
        text=text,
        entities=[x for x in [_clean(record.get("current_title"))] if x],
        numbers=numbers,
    )


def build_source_records(
    *,
    profile: dict[str, Any] | None = None,
    experiences: list[dict[str, Any]] | None = None,
    education: list[dict[str, Any]] | None = None,
    skills: list[dict[str, Any]] | None = None,
    certifications: list[dict[str, Any]] | None = None,
    projects: list[dict[str, Any]] | None = None,
) -> list[SourceRecord]:
    records: list[SourceRecord] = []
    if profile:
        records.append(profile_source(profile))
    records.extend(experience_source(item) for item in experiences or [])
    records.extend(education_source(item) for item in education or [])
    records.extend(skill_source(item) for item in skills or [])
    records.extend(certification_source(item) for item in certifications or [])
    records.extend(project_source(item) for item in projects or [])
    return records
