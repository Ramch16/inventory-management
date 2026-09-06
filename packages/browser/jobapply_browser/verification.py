"""Detecting the points where a human must take over.

Nothing in this module attempts to satisfy a challenge. Its entire job is to notice
one early and stop cleanly, so the user can complete it themselves. There is no
CAPTCHA solving, no MFA bypass, no anti-bot evasion and no fingerprint spoofing
anywhere in this codebase.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from jobapply_shared.enums import InterventionType

from jobapply_browser.models import VerificationSignal

#: Markers for the widgets themselves, not for how to defeat them.
CAPTCHA_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"(?i)<[^>]*class=[\"'][^\"']*g-recaptcha", "reCAPTCHA widget"),
    (r"(?i)www\.google\.com/recaptcha", "reCAPTCHA script"),
    (r"(?i)hcaptcha\.com", "hCaptcha script"),
    (r"(?i)<[^>]*class=[\"'][^\"']*h-captcha", "hCaptcha widget"),
    (r"(?i)challenges\.cloudflare\.com/turnstile", "Cloudflare Turnstile"),
    (r"(?i)<[^>]*class=[\"'][^\"']*cf-turnstile", "Turnstile widget"),
    (r"(?i)\bfuncaptcha\b|arkoselabs", "Arkose/FunCaptcha"),
    (r"(?i)>\s*i'?m not a robot\s*<", '"I\'m not a robot" checkbox'),
    (r"(?i)please (?:complete|verify).{0,30}captcha", "CAPTCHA instruction text"),
)

OTP_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"(?i)one[- ]time (?:pass)?code", "one-time code prompt"),
    (r"(?i)verification code", "verification code prompt"),
    (r"(?i)enter the (?:\d[- ])?code we (?:sent|e-?mailed|texted)", "code entry prompt"),
    (r"(?i)\bOTP\b", "OTP label"),
    (r"(?i)name=[\"'](?:otp|one_time_code|verification_code)[\"']", "OTP input"),
    (r"(?i)autocomplete=[\"']one-time-code[\"']", "one-time-code input"),
)

MFA_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"(?i)two[- ]factor", "two-factor prompt"),
    (r"(?i)multi[- ]factor", "multi-factor prompt"),
    (r"(?i)\b2FA\b", "2FA label"),
    (r"(?i)authenticator app", "authenticator app prompt"),
    (r"(?i)approve (?:this )?(?:sign[- ]in|login) (?:request|on your)", "push approval prompt"),
)

LOGIN_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"(?i)<input[^>]+type=[\"']password[\"']", "password field"),
    (r"(?i)sign in to (?:apply|continue)", "sign-in wall"),
    (r"(?i)create an account to (?:apply|continue)", "account-creation wall"),
)

#: Text that indicates the employer's flow has ended somewhere we cannot proceed.
UNSUPPORTED_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"(?i)this (?:job|position) is no longer (?:accepting|available)", "posting closed"),
    (r"(?i)assessment (?:invitation|required)", "assessment step"),
    (r"(?i)you will be redirected to (?:our|the) (?:partner|vendor)", "third-party redirect"),
)


@dataclass(frozen=True)
class VerificationScan:
    signals: list[VerificationSignal]

    @property
    def blocking(self) -> VerificationSignal | None:
        """The first signal that must stop the run, in severity order."""
        order = (
            InterventionType.CAPTCHA,
            InterventionType.MFA,
            InterventionType.OTP,
            InterventionType.AUTHENTICATION_REQUIRED,
            InterventionType.UNSUPPORTED_FORM,
        )
        for kind in order:
            for signal in self.signals:
                if signal.type == kind:
                    return signal
        return None


def _scan(patterns: tuple[tuple[str, str], ...], html: str) -> list[str]:
    return [label for pattern, label in patterns if re.search(pattern, html)]


def scan_page(html: str, *, url: str = "") -> VerificationScan:
    """Look for anything that means a person has to take over."""
    signals: list[VerificationSignal] = []
    haystack = f"{html}\n{url}"

    captcha = _scan(CAPTCHA_PATTERNS, haystack)
    if captcha:
        signals.append(
            VerificationSignal(
                type=InterventionType.CAPTCHA,
                reason=(
                    "This page uses a CAPTCHA. The platform does not solve CAPTCHAs — "
                    "complete it yourself and the run will continue from here."
                ),
                evidence=captcha,
            )
        )

    mfa = _scan(MFA_PATTERNS, haystack)
    if mfa:
        signals.append(
            VerificationSignal(
                type=InterventionType.MFA,
                reason=(
                    "This step needs multi-factor authentication, which only you can complete."
                ),
                evidence=mfa,
            )
        )

    otp = _scan(OTP_PATTERNS, haystack)
    if otp:
        signals.append(
            VerificationSignal(
                type=InterventionType.OTP,
                reason=(
                    "A one-time code was sent to you. Enter it to continue — the code "
                    "is used once and never stored."
                ),
                evidence=otp,
            )
        )

    login = _scan(LOGIN_PATTERNS, haystack)
    if login:
        signals.append(
            VerificationSignal(
                type=InterventionType.AUTHENTICATION_REQUIRED,
                reason=(
                    "This employer requires an account before applying. Sign in "
                    "yourself, or skip this job."
                ),
                evidence=login,
            )
        )

    unsupported = _scan(UNSUPPORTED_PATTERNS, haystack)
    if unsupported:
        signals.append(
            VerificationSignal(
                type=InterventionType.UNSUPPORTED_FORM,
                reason="This application flow is not one the platform can complete.",
                evidence=unsupported,
            )
        )

    return VerificationScan(signals=signals)


def redact_html(html: str) -> str:
    """Strip values a user typed before any page source is stored for debugging."""
    without_input_values = re.sub(
        r"(?i)(<input[^>]*\bvalue=)([\"'])(?:(?!\2).)*\2", r"\1\2[redacted]\2", html
    )
    return re.sub(
        r"(?is)(<textarea[^>]*>).*?(</textarea>)", r"\1[redacted]\2", without_input_values
    )
