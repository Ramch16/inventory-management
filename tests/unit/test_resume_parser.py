"""Resume parsing: extraction, section splitting and structured records."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from jobapply_resume.extract import detect_kind, extract_text
from jobapply_resume.parser import parse_resume, split_sections
from jobapply_shared.errors import ValidationError_

FIXTURE = Path(__file__).parent.parent / "fixtures" / "resumes" / "sample_resume.txt"


@pytest.fixture(scope="module")
def sample_text() -> str:
    return FIXTURE.read_text()


@pytest.fixture(scope="module")
def parsed(sample_text):
    return parse_resume(sample_text)


def test_contact_details_are_extracted(parsed):
    contact = parsed.contact
    assert contact.full_name == "Jordan Rivera"
    assert contact.email == "jordan.rivera@example.com"
    assert contact.phone == "(415) 555-0142"
    assert contact.location == "San Francisco, CA"
    assert contact.linkedin_url == "https://linkedin.com/in/jordanrivera"
    assert contact.github_url == "https://github.com/jrivera"


def test_email_domain_is_not_mistaken_for_a_portfolio(parsed):
    assert parsed.contact.portfolio_url == "https://jordanrivera.dev"


def test_sections_are_split_by_heading(sample_text):
    sections = split_sections(sample_text)
    assert set(sections) >= {
        "header",
        "summary",
        "experience",
        "education",
        "skills",
        "certifications",
        "projects",
    }


def test_positions_include_company_title_dates_and_bullets(parsed):
    assert len(parsed.positions) == 2
    current, previous = parsed.positions
    assert current.company == "Northwind Analytics"
    assert current.title == "Senior Data Engineer"
    assert current.location == "San Francisco, CA"
    assert current.start_date.year == 2021 and current.start_date.month == 3
    assert current.is_current is True
    assert current.end_date is None
    assert len(current.bullets) == 3

    assert previous.company == "Cobalt Software"
    assert previous.is_current is False
    assert previous.end_date.year == 2021 and previous.end_date.month == 2


def test_education_is_extracted_with_gpa(parsed):
    assert len(parsed.education) == 1
    record = parsed.education[0]
    assert record.institution == "University of Texas at Austin"
    assert "Computer Science" in (record.degree or "")
    assert record.gpa == pytest.approx(3.7)


def test_skills_are_split_and_deduplicated(parsed):
    assert "Python" in parsed.skills
    assert "Airflow" in parsed.skills
    assert "Snowflake" in parsed.skills
    # Category labels ("Languages:") must not survive as skills.
    assert not any(skill.lower().startswith("languages") for skill in parsed.skills)
    assert len(parsed.skills) == len(set(parsed.skills))


def test_certifications_keep_their_full_name(parsed):
    names = [item.name for item in parsed.certifications]
    assert "AWS Certified Solutions Architect – Associate" in names
    assert parsed.certifications[0].issued_on.year == 2022


def test_projects_capture_highlights(parsed):
    assert parsed.projects[0].name == "Pipeline Radar"
    assert parsed.projects[0].highlights == ["Used by 300+ GitHub stargazers"]


def test_warnings_flag_a_resume_with_no_experience():
    result = parse_resume("Jane Doe\njane@example.com\n\nSKILLS\nPython, SQL\n")
    assert any("experience" in warning.lower() for warning in result.warnings)


def test_detect_kind_prefers_magic_bytes_over_declared_type():
    assert detect_kind(b"%PDF-1.7 ...", "resume.txt", "text/plain") == "pdf"
    assert detect_kind(b"PK\x03\x04rest", "resume.pdf", "application/pdf") == "docx"
    assert detect_kind(b"plain resume text", "resume.txt", "text/plain") == "txt"


def test_extract_text_rejects_an_empty_file():
    with pytest.raises(ValidationError_) as excinfo:
        extract_text(b"", filename="resume.txt", content_type="text/plain")
    assert excinfo.value.code == "empty_file"


def test_extract_text_rejects_binary_that_is_not_a_document():
    with pytest.raises(ValidationError_):
        extract_text(b"\x00\x01\x02\xff\xfe", filename="resume.bin", content_type=None)


def test_extract_text_reads_a_docx(tmp_path):
    docx = pytest.importorskip("docx")
    document = docx.Document()
    document.add_paragraph("Jordan Rivera")
    document.add_paragraph("EXPERIENCE")
    document.add_paragraph("Northwind Analytics | Senior Data Engineer")
    document.add_paragraph("Mar 2021 - Present")
    buffer = io.BytesIO()
    document.save(buffer)

    text, kind = extract_text(
        buffer.getvalue(),
        filename="resume.docx",
        content_type=("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    )
    assert kind == "docx"
    assert "Northwind Analytics" in text
    assert parse_resume(text).positions[0].company == "Northwind Analytics"
