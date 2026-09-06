"""Detecting the points where a person must take over.

The platform never solves these — it recognises them and stops.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from jobapply_browser.verification import redact_html, scan_page
from jobapply_shared.enums import InterventionType

SITES = Path(__file__).parent.parent / "mock_ats" / "sites"


@pytest.mark.parametrize(
    "html",
    [
        '<div class="g-recaptcha" data-sitekey="x"></div>',
        '<script src="https://www.google.com/recaptcha/api.js"></script>',
        '<div class="h-captcha"></div>',
        '<script src="https://challenges.cloudflare.com/turnstile/v0/api.js"></script>',
        "<span>I'm not a robot</span>",
    ],
)
def test_captcha_widgets_are_detected(html):
    assert scan_page(html).blocking.type == InterventionType.CAPTCHA


@pytest.mark.parametrize(
    "html",
    [
        '<input autocomplete="one-time-code">',
        "<p>Enter the code we sent to your phone</p>",
        '<input name="verification_code">',
        "<label>One-time passcode</label>",
    ],
)
def test_otp_prompts_are_detected(html):
    assert scan_page(html).blocking.type == InterventionType.OTP


@pytest.mark.parametrize(
    "html",
    ["<p>Two-factor authentication</p>", "<p>Open your authenticator app</p>", "<p>2FA</p>"],
)
def test_mfa_prompts_are_detected(html):
    assert scan_page(html).blocking.type == InterventionType.MFA


def test_a_captcha_outranks_other_signals():
    html = '<div class="g-recaptcha"></div><input type="password"><p>Two-factor</p>'
    assert scan_page(html).blocking.type == InterventionType.CAPTCHA


def test_a_sign_in_wall_is_reported_not_bypassed():
    signal = scan_page('<input type="password">').blocking
    assert signal.type == InterventionType.AUTHENTICATION_REQUIRED
    assert "yourself" in signal.reason


def test_an_ordinary_form_produces_no_blocking_signal():
    assert scan_page("<form><input name='email'></form>").blocking is None


def test_the_captcha_message_says_we_do_not_solve_it():
    signal = scan_page('<div class="g-recaptcha"></div>').blocking
    assert "does not solve CAPTCHAs" in signal.reason


def test_the_otp_message_promises_the_code_is_not_stored():
    signal = scan_page('<input autocomplete="one-time-code">').blocking
    assert "never stored" in signal.reason


def test_the_mock_sites_trigger_the_expected_stops():
    assert scan_page((SITES / "captcha.html").read_text()).blocking.type == InterventionType.CAPTCHA
    assert scan_page((SITES / "otp.html").read_text()).blocking.type == InterventionType.OTP
    assert (
        scan_page((SITES / "workday.html").read_text()).blocking.type
        == InterventionType.AUTHENTICATION_REQUIRED
    )
    assert scan_page((SITES / "greenhouse.html").read_text()).blocking is None


def test_typed_values_are_redacted_before_page_source_is_stored():
    html = (
        '<input name="email" value="jordan@example.com">'
        "<textarea name='why'>My private answer</textarea>"
    )
    redacted = redact_html(html)
    assert "jordan@example.com" not in redacted
    assert "My private answer" not in redacted
    assert 'name="email"' in redacted
