"""ATS detection.

A platform is only claimed when at least two independent signals agree — a URL
pattern, a DOM marker, page metadata, or a network host the page loaded from. One
signal is never enough: employers proxy boards behind their own domains, and a wrong
adapter fills the wrong fields.

When nothing reaches the threshold the generic adapter takes over, which is
deliberately conservative rather than clever.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from jobapply_shared.enums import AtsKind

from jobapply_browser.models import DetectionResult

#: Weights are chosen so that any two independent signals reach MIN_CONFIDENCE, and
#: no single signal ever does. The one exception is metadata + network host, which are
#: both weak on their own and can coincide on an unrelated page.
URL_WEIGHT = 0.5
DOM_WEIGHT = 0.4
META_WEIGHT = 0.3
NETWORK_WEIGHT = 0.3
MIN_CONFIDENCE = 0.7


@dataclass(frozen=True)
class AtsSignature:
    ats: AtsKind
    url_patterns: tuple[str, ...] = ()
    dom_patterns: tuple[str, ...] = ()
    meta_patterns: tuple[str, ...] = ()
    network_patterns: tuple[str, ...] = ()
    #: CSS selectors an adapter can use to confirm it is on an application form.
    form_selectors: tuple[str, ...] = field(default=())


SIGNATURES: tuple[AtsSignature, ...] = (
    AtsSignature(
        ats=AtsKind.GREENHOUSE,
        url_patterns=(
            r"(?i)//(?:job-)?boards\.greenhouse\.io/",
            r"(?i)//boards-api\.greenhouse\.io/",
            r"(?i)greenhouse\.io/embed/job_app",
        ),
        dom_patterns=(
            r"id=[\"']grnhse_app[\"']",
            r"id=[\"']application_form[\"']",
            r"data-mapped=[\"']true[\"'][^>]*greenhouse",
            r"job_application\[",
        ),
        meta_patterns=(r"(?i)greenhouse",),
        network_patterns=(r"(?i)boards\.greenhouse\.io", r"(?i)greenhouse\.io/embed"),
        form_selectors=("#application_form", "#grnhse_app form", "form#application-form"),
    ),
    AtsSignature(
        ats=AtsKind.LEVER,
        url_patterns=(r"(?i)//jobs\.lever\.co/", r"(?i)//api\.lever\.co/"),
        dom_patterns=(
            r"class=[\"'][^\"']*application-form",
            r"data-qa=[\"']application",
            r"name=[\"']resume[\"'][^>]*lever",
            r"posting-headline",
        ),
        meta_patterns=(r"(?i)lever",),
        network_patterns=(r"(?i)lever\.co",),
        form_selectors=("form.application-form", "form[action*='lever']"),
    ),
    AtsSignature(
        ats=AtsKind.ASHBY,
        url_patterns=(r"(?i)//jobs\.ashbyhq\.com/", r"(?i)ashbyhq\.com/"),
        dom_patterns=(
            r"data-testid=[\"']application-form[\"']",
            r"class=[\"'][^\"']*ashby",
            r"_ashby",
        ),
        meta_patterns=(r"(?i)ashby",),
        network_patterns=(r"(?i)ashbyhq\.com",),
        form_selectors=("[data-testid='application-form']", "form"),
    ),
    AtsSignature(
        ats=AtsKind.WORKDAY,
        url_patterns=(r"(?i)myworkdayjobs\.com", r"(?i)/wday/"),
        dom_patterns=(r"data-automation-id=", r"wd-[A-Za-z]+Widget"),
        meta_patterns=(r"(?i)workday",),
        network_patterns=(r"(?i)myworkdayjobs\.com", r"(?i)workday\.com"),
        form_selectors=("[data-automation-id='applyFlow']", "form"),
    ),
    AtsSignature(
        ats=AtsKind.ICIMS,
        url_patterns=(r"(?i)\.icims\.com",),
        dom_patterns=(r"id=[\"']icims_content_iframe[\"']", r"icims_", r"iCIMS"),
        meta_patterns=(r"(?i)icims",),
        network_patterns=(r"(?i)icims\.com",),
        form_selectors=("#icims_content_iframe", "form"),
    ),
    AtsSignature(
        ats=AtsKind.SMARTRECRUITERS,
        url_patterns=(
            r"(?i)//jobs\.smartrecruiters\.com/",
            r"(?i)//careers\.smartrecruiters\.com/",
            r"(?i)smartrecruiters\.com/",
        ),
        dom_patterns=(r"id=[\"']st-app[\"']", r"smartrecruiters", r"data-test=[\"']application"),
        meta_patterns=(r"(?i)smartrecruiters",),
        network_patterns=(r"(?i)smartrecruiters\.com",),
        form_selectors=("#st-app form", "form"),
    ),
)

SIGNATURES_BY_ATS = {signature.ats: signature for signature in SIGNATURES}


def _matches(patterns: tuple[str, ...], haystack: str) -> list[str]:
    return [pattern for pattern in patterns if re.search(pattern, haystack)]


def detect_ats(
    *,
    url: str,
    html: str = "",
    meta_generator: str = "",
    page_title: str = "",
    network_hosts: list[str] | None = None,
) -> DetectionResult:
    """Score every signature and return the best-supported platform.

    ``html`` is the rendered page source; ``network_hosts`` are the hosts the page
    actually loaded resources from, which catches an embedded board on an employer's
    own domain.
    """
    hosts = " ".join(network_hosts or [])
    metadata = f"{meta_generator} {page_title}"

    best: DetectionResult = DetectionResult(ats=AtsKind.UNKNOWN, confidence=0.0)
    for signature in SIGNATURES:
        signals: list[str] = []
        score = 0.0

        for pattern in _matches(signature.url_patterns, url):
            score += URL_WEIGHT
            signals.append(f"url:{pattern}")
            break  # one URL match is one signal, not several
        for pattern in _matches(signature.dom_patterns, html):
            score += DOM_WEIGHT
            signals.append(f"dom:{pattern}")
            break
        for pattern in _matches(signature.meta_patterns, metadata):
            score += META_WEIGHT
            signals.append(f"meta:{pattern}")
            break
        for pattern in _matches(signature.network_patterns, hosts):
            score += NETWORK_WEIGHT
            signals.append(f"network:{pattern}")
            break

        # A single signal never identifies a platform, however strong it looks.
        if len(signals) < 2:
            continue
        if score > best.confidence:
            best = DetectionResult(
                ats=signature.ats, confidence=round(min(score, 1.0), 3), signals=signals
            )

    if best.ats is AtsKind.UNKNOWN or best.confidence < MIN_CONFIDENCE:
        return DetectionResult(
            ats=AtsKind.GENERIC,
            confidence=best.confidence,
            signals=best.signals or ["no platform reached the confidence threshold"],
        )
    return best


APPLICATION_FORM_HINTS = (
    r"(?i)\bapply\b",
    r"(?i)\bapplication\b",
    r"(?i)submit (?:your )?application",
    r"(?i)first name",
    r"(?i)resume|curriculum vitae",
)

LOGIN_WALL_HINTS = (
    r"(?i)sign in to (?:apply|continue)",
    r"(?i)create an account to apply",
    r"(?i)<input[^>]+type=[\"']password[\"']",
    r"(?i)\blog ?in\b[^<]{0,40}\bto apply\b",
)


@dataclass(frozen=True)
class PageClassification:
    is_application_form: bool
    requires_login: bool
    reasons: list[str]


def classify_page(html: str, *, field_count: int = 0) -> PageClassification:
    """Decide whether the page is an application form, a posting, or a login wall.

    A login wall is reported, never worked around: the platform does not create or
    use employer accounts on the user's behalf unless the user explicitly set one up.
    """
    reasons: list[str] = []
    login = [pattern for pattern in LOGIN_WALL_HINTS if re.search(pattern, html)]
    if login:
        reasons.append("the page asks for sign-in before applying")
        return PageClassification(False, True, reasons)

    hints = [pattern for pattern in APPLICATION_FORM_HINTS if re.search(pattern, html)]
    is_form = field_count >= 3 and len(hints) >= 2
    if is_form:
        reasons.append(f"{field_count} form fields and {len(hints)} application hints")
    else:
        reasons.append(
            f"only {field_count} fields and {len(hints)} application hints — "
            "this does not look like an application form"
        )
    return PageClassification(is_form, False, reasons)
