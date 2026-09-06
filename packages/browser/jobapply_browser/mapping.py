"""Field mapping.

Deterministic rules run first and cover the overwhelming majority of real forms. A
model is consulted only for what is left, and even then it returns a *mapping*, never
a value, and it can never map a sensitive question to anything but that question's own
explicit profile field.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from jobapply_shared.enums import QuestionCategory
from jobapply_shared.text import normalize_text

from jobapply_browser.models import FieldMapping, MappingTarget, NormalizedField

#: Every value the platform is willing to put into a form, and where it comes from.
TARGETS: dict[str, MappingTarget] = {
    target.key: target
    for target in [
        MappingTarget(key="profile.first_name", category=QuestionCategory.IDENTITY),
        MappingTarget(key="profile.last_name", category=QuestionCategory.IDENTITY),
        MappingTarget(key="profile.full_name", category=QuestionCategory.IDENTITY),
        MappingTarget(key="profile.preferred_name", category=QuestionCategory.IDENTITY),
        MappingTarget(key="profile.email", category=QuestionCategory.CONTACT),
        MappingTarget(key="profile.phone", category=QuestionCategory.CONTACT),
        MappingTarget(key="profile.city", category=QuestionCategory.LOCATION),
        MappingTarget(key="profile.state", category=QuestionCategory.LOCATION),
        MappingTarget(key="profile.country", category=QuestionCategory.LOCATION),
        MappingTarget(key="profile.postal_code", category=QuestionCategory.LOCATION),
        MappingTarget(key="profile.location", category=QuestionCategory.LOCATION),
        MappingTarget(key="profile.linkedin_url", category=QuestionCategory.CONTACT),
        MappingTarget(key="profile.github_url", category=QuestionCategory.CONTACT),
        MappingTarget(key="profile.portfolio_url", category=QuestionCategory.CONTACT),
        MappingTarget(key="profile.current_title", category=QuestionCategory.EXPERIENCE),
        MappingTarget(key="profile.current_company", category=QuestionCategory.EXPERIENCE),
        MappingTarget(key="profile.years_experience", category=QuestionCategory.EXPERIENCE),
        MappingTarget(key="profile.education_school", category=QuestionCategory.EDUCATION),
        MappingTarget(key="profile.education_degree", category=QuestionCategory.EDUCATION),
        MappingTarget(key="generated_resume", category=QuestionCategory.FILE_UPLOAD),
        MappingTarget(key="generated_cover_letter", category=QuestionCategory.FILE_UPLOAD),
        MappingTarget(key="answer.start_date", category=QuestionCategory.OTHER),
        MappingTarget(key="answer.why_interested", category=QuestionCategory.MOTIVATION),
        MappingTarget(key="answer.skill_years", category=QuestionCategory.SKILLS),
        # --- sensitive: explicit profile fields only -------------------------
        MappingTarget(
            key="profile.work_authorized",
            sensitive=True,
            category=QuestionCategory.WORK_AUTHORIZATION,
        ),
        MappingTarget(
            key="profile.requires_sponsorship",
            sensitive=True,
            category=QuestionCategory.SPONSORSHIP,
        ),
        MappingTarget(
            key="profile.salary_expectation",
            sensitive=True,
            category=QuestionCategory.COMPENSATION,
        ),
        MappingTarget(
            key="sensitive.disability", sensitive=True, category=QuestionCategory.DISABILITY
        ),
        MappingTarget(key="sensitive.veteran", sensitive=True, category=QuestionCategory.VETERAN),
        MappingTarget(
            key="sensitive.demographic", sensitive=True, category=QuestionCategory.DEMOGRAPHIC
        ),
        MappingTarget(
            key="sensitive.criminal_history",
            sensitive=True,
            category=QuestionCategory.CRIMINAL_HISTORY,
        ),
        MappingTarget(
            key="sensitive.legal_attestation",
            sensitive=True,
            category=QuestionCategory.LEGAL_ATTESTATION,
        ),
    ]
}


@dataclass(frozen=True)
class Rule:
    target: str
    patterns: tuple[str, ...]
    #: Patterns that disqualify a match, e.g. "first name" must not match
    #: "first name of your reference".
    excludes: tuple[str, ...] = ()
    confidence: float = 0.97


#: Order matters: the first matching rule wins, so specific rules precede general ones.
RULES: tuple[Rule, ...] = (
    # --- sensitive first, so a generic rule can never swallow one -------------
    Rule(
        "profile.requires_sponsorship",
        (
            r"require.*sponsor",
            r"need.*sponsor",
            r"will you.*sponsor",
            r"visa sponsor",
            r"sponsorship.*(?:now|future|require)",
        ),
    ),
    Rule(
        "profile.work_authorized",
        (
            r"legally.*authoriz",
            r"authoriz(?:ed|ation).*work",
            r"work authoriz",
            r"eligible to work",
            r"right to work",
        ),
    ),
    Rule(
        "sensitive.disability",
        (r"disabilit", r"self[- ]identif.*disab"),
    ),
    Rule("sensitive.veteran", (r"veteran", r"protected veteran", r"military service")),
    Rule(
        "sensitive.demographic",
        (r"\brace\b", r"ethnicit", r"\bgender\b", r"hispanic", r"latino", r"pronoun"),
    ),
    Rule(
        "sensitive.criminal_history",
        (r"convict", r"criminal (?:record|history|background)", r"felony"),
    ),
    Rule(
        "sensitive.legal_attestation",
        (
            r"certify that",
            r"i (?:hereby )?(?:agree|certify|acknowledge|attest)",
            r"terms and conditions",
            r"privacy (?:policy|notice)",
            r"true and (?:complete|accurate)",
            r"electronic signature",
        ),
    ),
    Rule(
        "profile.salary_expectation",
        (r"salary expectation", r"desired (?:salary|compensation)", r"expected (?:salary|pay)"),
    ),
    # --- identity and contact ------------------------------------------------
    Rule(
        "profile.first_name",
        (r"^first[ _-]?name$", r"\bfirst name\b", r"\bgiven name\b"),
        excludes=(r"reference", r"emergency", r"spouse"),
    ),
    Rule(
        "profile.last_name",
        (r"^last[ _-]?name$", r"\blast name\b", r"\bsurname\b", r"\bfamily name\b"),
        excludes=(r"reference", r"emergency", r"spouse"),
    ),
    Rule("profile.preferred_name", (r"preferred name", r"nickname", r"what should we call you")),
    Rule(
        "profile.full_name",
        (r"^full[ _-]?name$", r"\bfull name\b", r"^name$", r"your name"),
        excludes=(r"company", r"school", r"university", r"reference", r"file"),
    ),
    Rule("profile.email", (r"e-?mail", r"^email$")),
    Rule("profile.phone", (r"phone", r"mobile", r"telephone", r"cell")),
    Rule("profile.linkedin_url", (r"linked ?in",)),
    Rule("profile.github_url", (r"git ?hub",)),
    Rule(
        "profile.portfolio_url",
        (r"portfolio", r"personal (?:web)?site", r"website", r"other website"),
    ),
    # --- location ------------------------------------------------------------
    Rule("profile.city", (r"^city$", r"\bcity\b"), excludes=(r"company", r"birth")),
    Rule("profile.state", (r"^state$", r"\bstate\b", r"\bprovince\b", r"\bregion\b")),
    Rule("profile.country", (r"^country$", r"\bcountry\b"), excludes=(r"citizen", r"authoriz")),
    Rule("profile.postal_code", (r"zip", r"postal code", r"post ?code")),
    Rule(
        "profile.location",
        (r"current location", r"where are you (?:based|located)", r"^location$", r"\baddress\b"),
    ),
    # --- experience and education -------------------------------------------
    Rule(
        "profile.current_title",
        (r"current (?:job )?title", r"^job title$", r"current role", r"^title$"),
        excludes=(r"job you", r"position you.*appl"),
    ),
    Rule("profile.current_company", (r"current (?:employer|company)", r"^company$", r"^employer$")),
    # A question about one technology must be recognised before the career-total
    # rule, which would otherwise swallow "years of experience with Airflow".
    Rule(
        "answer.skill_years",
        (
            r"years? (?:of )?experience (?:with|in|using)\s+\S",
            r"how many years\b.*\b(?:with|in|using)\s+\S",
            # "years of <thing> experience", where <thing> is not one of the generic
            # qualifiers that mean the career total.
            r"years? of (?!total|overall|relevant|work|professional|industry|prior|"
            r"related|direct|experience)[a-z0-9.+#/-]+ experience",
        ),
        confidence=0.88,
    ),
    Rule(
        "profile.years_experience",
        (
            r"years? of (?:total |overall |relevant |professional |industry |work |prior |"
            r"related |direct )?experience",
            r"total experience",
        ),
    ),
    Rule(
        "profile.education_school",
        (r"\bschool\b", r"\buniversity\b", r"\bcollege\b", r"institution"),
    ),
    Rule(
        "profile.education_degree", (r"\bdegree\b", r"field of study", r"\bmajor\b", r"discipline")
    ),
    # --- files ---------------------------------------------------------------
    Rule("generated_resume", (r"resume", r"\bcv\b", r"curriculum vitae")),
    Rule("generated_cover_letter", (r"cover letter", r"letter of interest")),
    # --- open questions ------------------------------------------------------
    Rule(
        "answer.start_date",
        (r"start date", r"when (?:can|could) you start", r"available to start", r"availability"),
        confidence=0.9,
    ),
    Rule(
        "answer.why_interested",
        (
            r"why (?:are you |do you )?(?:interested|want)",
            r"why (?:this|our) (?:role|company|position)",
            r"tell us why",
            r"what (?:interests|excites) you",
        ),
        confidence=0.85,
    ),
)


def field_text(field: NormalizedField) -> str:
    """Everything a human would read when answering this control."""
    parts = [
        field.question,
        field.label,
        field.placeholder,
        field.name,
        field.dom_id,
        field.context_text,
    ]
    return normalize_text(" ".join(part for part in parts if part))


def map_field(field: NormalizedField) -> FieldMapping:
    """Deterministic mapping for one field. Returns an unmapped result rather than a
    guess when no rule is confident."""
    haystack = field_text(field)

    for rule in RULES:
        if any(re.search(pattern, haystack) for pattern in rule.excludes):
            continue
        if any(re.search(pattern, haystack) for pattern in rule.patterns):
            target = TARGETS[rule.target]
            return FieldMapping(
                field_id=field.field_id,
                target=target.key,
                category=target.category,
                is_sensitive=target.sensitive,
                confidence=rule.confidence,
                strategy="deterministic",
                rationale=f"matched rule for {target.key}",
            )

    return FieldMapping(
        field_id=field.field_id,
        target=None,
        category=QuestionCategory.OTHER,
        is_sensitive=False,
        confidence=0.0,
        strategy="unmapped",
        rationale="no deterministic rule matched",
    )


def map_fields(fields: list[NormalizedField]) -> list[FieldMapping]:
    return [map_field(field) for field in fields]


def unmapped(mappings: list[FieldMapping]) -> list[FieldMapping]:
    return [mapping for mapping in mappings if mapping.target is None]


def accept_ai_mapping(
    field: NormalizedField, target: str | None, confidence: float
) -> FieldMapping:
    """Validate a model-proposed mapping before it is allowed to have any effect.

    Three rules: the target must be one we recognise; a sensitive target may only be
    proposed for a field whose own text is sensitive; and an AI mapping never reaches
    the confidence of a deterministic one.
    """
    if not target or target not in TARGETS:
        return FieldMapping(
            field_id=field.field_id,
            target=None,
            confidence=0.0,
            strategy="ai_rejected",
            rationale=f"unknown mapping target: {target!r}",
        )

    resolved = TARGETS[target]
    if resolved.sensitive:
        deterministic = map_field(field)
        if deterministic.target != target:
            # A model must not decide that an unclear question is really about work
            # authorization, salary or a protected characteristic.
            return FieldMapping(
                field_id=field.field_id,
                target=None,
                confidence=0.0,
                strategy="ai_rejected",
                rationale="a sensitive mapping must come from an explicit rule, not a model",
            )

    return FieldMapping(
        field_id=field.field_id,
        target=resolved.key,
        category=resolved.category,
        is_sensitive=resolved.sensitive,
        confidence=min(float(confidence), 0.90),
        strategy="ai",
        rationale="semantic mapping, capped below deterministic confidence",
    )
