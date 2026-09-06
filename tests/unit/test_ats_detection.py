"""Platform detection never relies on a single signal."""

from __future__ import annotations

import pytest
from jobapply_browser.detection import MIN_CONFIDENCE, classify_page, detect_ats
from jobapply_shared.enums import AtsKind

GREENHOUSE_HTML = '<div id="grnhse_app"><form id="application_form"></form></div>'
LEVER_HTML = '<form class="application-form" data-qa="application-form"></form>'


@pytest.mark.parametrize(
    ("url", "html", "expected"),
    [
        ("https://boards.greenhouse.io/acme/jobs/1", GREENHOUSE_HTML, AtsKind.GREENHOUSE),
        ("https://job-boards.greenhouse.io/acme/jobs/1", GREENHOUSE_HTML, AtsKind.GREENHOUSE),
        ("https://jobs.lever.co/acme/abc/apply", LEVER_HTML, AtsKind.LEVER),
        (
            "https://jobs.ashbyhq.com/acme/abc",
            '<div data-testid="application-form"></div>',
            AtsKind.ASHBY,
        ),
        (
            "https://acme.wd5.myworkdayjobs.com/careers",
            '<div data-automation-id="applyFlow"></div>',
            AtsKind.WORKDAY,
        ),
        (
            "https://careers-acme.icims.com/jobs/1",
            '<iframe id="icims_content_iframe"></iframe>',
            AtsKind.ICIMS,
        ),
        (
            "https://jobs.smartrecruiters.com/acme/1",
            '<div id="st-app"></div>',
            AtsKind.SMARTRECRUITERS,
        ),
    ],
)
def test_url_plus_dom_identifies_a_platform(url, html, expected):
    result = detect_ats(url=url, html=html)
    assert result.ats == expected
    assert result.confidence >= MIN_CONFIDENCE
    assert len(result.signals) >= 2


def test_a_url_alone_is_never_enough():
    result = detect_ats(url="https://boards.greenhouse.io/acme/jobs/1", html="<html></html>")
    assert result.ats == AtsKind.GENERIC


def test_a_dom_marker_alone_is_never_enough():
    result = detect_ats(url="https://acme.example.com/apply", html=GREENHOUSE_HTML)
    assert result.ats == AtsKind.GENERIC


def test_an_embedded_board_on_an_employer_domain_is_still_recognised():
    result = detect_ats(
        url="https://acme.example.com/careers/1",
        html='<form><input name="job_application[first_name]"></form>',
        meta_generator="Greenhouse",
    )
    assert result.ats == AtsKind.GREENHOUSE
    assert any(signal.startswith("dom:") for signal in result.signals)
    assert any(signal.startswith("meta:") for signal in result.signals)


def test_an_unknown_site_falls_back_to_the_generic_adapter():
    result = detect_ats(url="https://acme.example.com/apply", html="<form></form>")
    assert result.ats == AtsKind.GENERIC
    assert result.signals


def test_weak_metadata_and_a_shared_host_do_not_claim_a_platform():
    """Both signals are weak on their own and can coincide on an unrelated page."""
    result = detect_ats(
        url="https://acme.example.com/blog",
        html="<article>We use Lever internally.</article>",
        meta_generator="Lever",
        network_hosts=["lever.co"],
    )
    assert result.ats == AtsKind.GENERIC


def test_classify_page_recognises_an_application_form():
    html = "<h1>Apply</h1><form><label>First name</label><input><input><input></form>"
    classification = classify_page(html, field_count=4)
    assert classification.is_application_form
    assert not classification.requires_login


def test_classify_page_reports_a_login_wall_rather_than_working_around_it():
    html = '<p>Sign in to apply</p><input type="password">'
    classification = classify_page(html, field_count=2)
    assert classification.requires_login
    assert not classification.is_application_form


def test_classify_page_rejects_a_job_posting_that_is_not_a_form():
    classification = classify_page("<h1>Senior Data Engineer</h1><p>About us…</p>", field_count=0)
    assert not classification.is_application_form
