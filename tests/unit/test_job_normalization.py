"""Normalization must extract only what a posting actually states."""

from __future__ import annotations

import pytest
from jobapply_jobs.models import RawJob
from jobapply_jobs.normalize import (
    JobNormalizer,
    detect_ats,
    extract_experience_years,
    extract_sections,
    extract_sponsorship,
    parse_salary,
    strip_html,
)
from jobapply_shared.enums import EmploymentType, RemoteType


@pytest.fixture
def normalizer() -> JobNormalizer:
    return JobNormalizer()


def raw(**overrides) -> RawJob:
    base = {
        "source_slug": "sample",
        "source_job_id": "1",
        "company": "Northwind Analytics",
        "title": "Senior Data Engineer",
        "location": "San Francisco, CA",
        "description": "<p>Build pipelines with Python and SQL.</p>",
    }
    base.update(overrides)
    return RawJob(**base)


def test_strip_html_keeps_list_structure():
    text = strip_html("<h3>Requirements</h3><ul><li>Python</li><li>SQL</li></ul>")
    assert "Requirements" in text
    assert "- Python" in text
    assert "<" not in text


def test_strip_html_drops_scripts():
    assert "alert" not in strip_html("<p>Hi</p><script>alert(1)</script>")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("$160,000 - $200,000 per year", (160000, 200000)),
        ("140k–175k", (140000, 175000)),
        ("$120,000 to $150,000", (120000, 150000)),
    ],
)
def test_parse_salary_reads_annual_ranges(text, expected):
    low, high, _ = parse_salary(text)
    assert (low, high) == expected


@pytest.mark.parametrize(
    "text",
    ["$65 per hour", "Competitive salary", "$180,000", "5 - 7 years of experience"],
)
def test_parse_salary_declines_to_guess(text):
    assert parse_salary(text) == (None, None, None)


def test_remote_and_employment_type_detection(normalizer):
    remote = normalizer.normalize(raw(title="Analytics Engineer (Remote)", remote_hint="Remote"))
    assert remote.remote_type == RemoteType.REMOTE

    onsite = normalizer.normalize(raw(remote_hint="On-site", description="<p>In office daily.</p>"))
    assert onsite.remote_type == RemoteType.ONSITE

    contract = normalizer.normalize(raw(employment_type="Contract"))
    assert contract.employment_type == EmploymentType.CONTRACT


def test_sections_split_requirements_from_preferred():
    description = strip_html(
        "<h3>Requirements</h3><ul><li>5 years Python</li><li>SQL</li></ul>"
        "<h3>Nice to have</h3><ul><li>Terraform</li></ul>"
    )
    requirements, preferred = extract_sections(description)
    assert requirements == ["5 years Python", "SQL"]
    assert preferred == ["Terraform"]


def test_experience_requirement_takes_the_lowest_plausible_figure():
    assert (
        extract_experience_years("5+ years of experience; 10 years of experience preferred") == 5.0
    )
    assert extract_experience_years("A great opportunity") is None


def test_sponsorship_is_captured_verbatim_and_only_decided_when_explicit():
    text, offered = extract_sponsorship("We are unable to sponsor work visas for this role.")
    assert offered is False
    assert "unable to sponsor" in text

    text, offered = extract_sponsorship("We will sponsor eligible candidates.")
    assert offered is True

    text, offered = extract_sponsorship("Questions about visa status can be raised in interview.")
    assert offered is None, "ambiguous language must not become a boolean"
    assert text is not None

    assert extract_sponsorship("A normal posting with no such language.") == (None, None)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://boards.greenhouse.io/acme/jobs/1", "greenhouse"),
        ("https://jobs.lever.co/acme/abc/apply", "lever"),
        ("https://jobs.ashbyhq.com/acme/abc", "ashby"),
        ("https://acme.wd1.myworkdayjobs.com/careers", "workday"),
        ("https://careers-acme.icims.com/jobs/1", "icims"),
        ("https://jobs.smartrecruiters.com/acme/1", "smartrecruiters"),
        ("https://acme.example.com/careers/1", None),
    ],
)
def test_ats_detection_from_url(url, expected):
    assert detect_ats(url) == expected


def test_normalize_produces_a_stable_dedupe_key(normalizer):
    first = normalizer.normalize(raw(company="Acme, Inc.", title="Sr. Data Engineer"))
    second = normalizer.normalize(raw(company="ACME Inc", title="Senior Data Engineer"))
    assert first.dedupe_key == second.dedupe_key, "formatting differences must not create a new job"

    different = normalizer.normalize(raw(source_job_id="2"))
    assert different.dedupe_key != first.dedupe_key


def test_skills_come_from_a_vocabulary_not_from_capitalisation(normalizer):
    job = normalizer.normalize(
        raw(description="<p>Work with Python, SQL and our internal Frobnicator platform.</p>")
    )
    assert "python" in job.skills
    assert "sql" in job.skills
    assert not any("frobnicator" in skill for skill in job.skills)
