"""Duplicate detection across sources and re-posts."""

from __future__ import annotations

from jobapply_jobs.dedupe import ExistingJob, application_dedupe_hash, find_duplicate
from jobapply_jobs.models import RawJob
from jobapply_jobs.normalize import JobNormalizer

normalizer = JobNormalizer()


def make(**overrides):
    base = {
        "source_slug": "sample",
        "source_job_id": "1",
        "company": "Northwind Analytics",
        "title": "Senior Data Engineer",
        "location": "San Francisco, CA",
        "description": "Build pipelines with Python.",
    }
    base.update(overrides)
    return normalizer.normalize(RawJob(**base))


def existing_from(job) -> ExistingJob:
    return ExistingJob(
        id="stored-1",
        normalized_company=job.normalized_company,
        normalized_title=job.normalized_title,
        normalized_location=job.normalized_location,
        dedupe_key=job.dedupe_key,
        content_hash=job.content_hash,
    )


def test_identical_posting_is_an_exact_duplicate():
    stored = make()
    verdict = find_duplicate(make(), [existing_from(stored)])
    assert verdict.is_duplicate
    assert verdict.similarity == 1.0


def test_same_role_from_a_second_source_is_caught_by_similarity():
    stored = make()
    candidate = make(source_slug="lever", source_job_id="xyz", title="Sr. Data Engineer")
    verdict = find_duplicate(candidate, [existing_from(stored)])
    assert verdict.is_duplicate
    assert "near-identical title" in (verdict.reason or "")


LONG_BODY = (
    "We are hiring a data engineer to own our batch and streaming pipelines. "
    "You will work with analysts to model data, improve reliability and reduce cost. "
    "This description is long enough that an exact match is meaningful evidence that "
    "the two postings are the same role rather than shared boilerplate text."
)


def test_identical_description_body_is_caught_even_with_a_different_title():
    stored = make(description=LONG_BODY)
    candidate = make(source_job_id="99", title="Data Platform Engineer", description=LONG_BODY)
    verdict = find_duplicate(candidate, [existing_from(stored)])
    assert verdict.is_duplicate
    assert "identical description" in (verdict.reason or "")


def test_short_boilerplate_descriptions_do_not_collapse_different_roles():
    stored = make(description="Join our team.")
    candidate = make(
        source_job_id="2", title="Product Marketing Manager", description="Join our team."
    )
    assert not find_duplicate(candidate, [existing_from(stored)]).is_duplicate


def test_a_different_role_at_the_same_company_is_not_a_duplicate():
    stored = make()
    candidate = make(source_job_id="2", title="Product Marketing Manager")
    assert not find_duplicate(candidate, [existing_from(stored)]).is_duplicate


def test_the_same_title_at_a_different_company_is_not_a_duplicate():
    stored = make()
    candidate = make(source_job_id="2", company="Cobalt Software")
    assert not find_duplicate(candidate, [existing_from(stored)]).is_duplicate


def test_location_precision_does_not_split_a_role():
    stored = make(location="Austin, TX, United States")
    candidate = make(source_job_id="2", location="Austin, TX")
    assert find_duplicate(candidate, [existing_from(stored)]).is_duplicate


def test_a_genuinely_different_location_is_a_different_role():
    stored = make(location="Austin, TX")
    candidate = make(source_job_id="2", location="Berlin, Germany")
    assert not find_duplicate(candidate, [existing_from(stored)]).is_duplicate


def test_application_hash_collapses_the_same_role_across_boards():
    first = application_dedupe_hash(
        company="Acme, Inc.",
        title="Senior Data Engineer",
        employer_job_id="1001",
        apply_url="https://boards.greenhouse.io/acme/jobs/1001",
    )
    second = application_dedupe_hash(
        company="ACME Inc",
        title="Sr. Data Engineer",
        employer_job_id="1001",
        apply_url="https://boards.greenhouse.io/acme/jobs/1001/",
    )
    assert first == second

    other_role = application_dedupe_hash(
        company="Acme, Inc.",
        title="Senior Data Engineer",
        employer_job_id="2002",
        apply_url="https://boards.greenhouse.io/acme/jobs/2002",
    )
    assert first != other_role
