"""ResumeTruthLayer — provenance and hallucination protection.

Every statement that will reach an employer passes through here. A statement is
allowed only when:

1. every source id it claims resolves to a real, user-approved record;
2. every technology it names appears in the user's own records;
3. every numeric claim ("5 years of Python") is no larger than the profile says;
4. it makes no legally significant claim (authorization, clearance, demographics);
5. its content words overlap the cited sources enough to be a rewrite rather than an
   invention.

Failing any check rejects the statement. The caller may retry with a narrower prompt
and then fall back to the user's own untouched wording.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from jobapply_shared.text import normalize_text

from jobapply_resume.models import (
    SourceRecord,
    TailoredResume,
    TruthReport,
    TruthVerdict,
)
from jobapply_resume.vocabulary import FORBIDDEN_CLAIM_PATTERNS, STOPWORDS, TECH_TERMS

#: "5 years", "5+ years of Python", "over 7 yrs experience in AWS", "3 years of AWS
#: experience". The subject is captured loosely and then cleaned by _claim_subject.
YEARS_CLAIM_RE = re.compile(
    r"(?i)\b(?:over|more than|nearly|about|approx(?:imately)?\.?\s*)?(\d{1,2})\s*\+?\s*"
    r"(?:years?|yrs?)\b([A-Za-z0-9 .#+/'-]{0,45})"
)

_SUBJECT_LEAD_RE = re.compile(
    r"(?i)^\s*(?:of|in|with|using|on|as|a|an|the|hands[- ]on|professional|industry|"
    r"total|combined|overall|relevant)\s+"
)
_SUBJECT_TRAIL_RE = re.compile(r"(?i)\b(?:experience|expertise|background|exp)\b.*$")


def _claim_subject(tail: str | None) -> str | None:
    """Reduce the text after a years claim to the thing being claimed, if any."""
    if not tail:
        return None
    subject = tail
    for _ in range(4):
        stripped = _SUBJECT_LEAD_RE.sub("", subject)
        if stripped == subject:
            break
        subject = stripped
    subject = _SUBJECT_TRAIL_RE.sub("", subject)
    subject = re.sub(
        r"(?i)\b(?:building|developing|working|leading|managing|and|for|at)\b.*$", "", subject
    )
    subject = subject.strip(" .,;:-")
    return subject or None


_WORD_RE = re.compile(r"[a-z0-9][a-z0-9.+#-]*")

#: How much of a generated statement's content must be traceable to the cited sources.
MIN_GROUNDING_OVERLAP = 0.34
#: Tolerance on numeric claims, so "3 years" against a 2.6-year record is not rejected.
YEARS_TOLERANCE = 0.5


def _content_words(text: str) -> set[str]:
    return {
        word
        for word in _WORD_RE.findall(normalize_text(text))
        if word not in STOPWORDS and len(word) > 1
    }


def _phrase_variants(text: str) -> set[str]:
    """Single words plus adjacent word pairs, so ``power bi`` and ``sql server`` match."""
    words = _WORD_RE.findall(normalize_text(text))
    variants = set(words)
    variants.update(f"{a} {b}" for a, b in zip(words, words[1:], strict=False))
    return variants


@dataclass
class SourceIndex:
    """Everything the generator is allowed to draw on, indexed for fast checking."""

    records: dict[str, SourceRecord] = field(default_factory=dict)
    #: Every phrase that appears anywhere in the user's records.
    known_terms: set[str] = field(default_factory=set)
    #: Technologies the user actually claims, drawn from records ∩ vocabulary.
    known_tech: set[str] = field(default_factory=set)
    #: Named numeric facts, e.g. {"python": 5.0, "__total_experience__": 6.0}.
    numbers: dict[str, float] = field(default_factory=dict)

    def resolve(self, source_ids: list[str]) -> tuple[list[str], list[str]]:
        found = [sid for sid in source_ids if sid in self.records]
        missing = [sid for sid in source_ids if sid not in self.records]
        return found, missing

    def text_for(self, source_ids: list[str]) -> str:
        return " ".join(self.records[sid].text for sid in source_ids if sid in self.records)

    def years_for(self, subject: str | None) -> float | None:
        if subject is None:
            return self.numbers.get("__total_experience__")
        key = normalize_text(subject).strip(" .")
        if key in self.numbers:
            return self.numbers[key]
        for token in key.split():
            if token in self.numbers:
                return self.numbers[token]
        return None


def build_source_index(records: list[SourceRecord]) -> SourceIndex:
    index = SourceIndex()
    for record in records:
        index.records[record.id] = record
        variants = _phrase_variants(record.text)
        for entity in record.entities:
            variants |= _phrase_variants(entity)
        index.known_terms |= variants
        index.known_tech |= variants & TECH_TERMS
        for key, value in record.numbers.items():
            normalized = normalize_text(key)
            index.numbers[normalized] = max(index.numbers.get(normalized, 0.0), float(value))
    return index


class ResumeTruthLayer:
    """Verifies generated statements against the user's approved records."""

    def __init__(self, index: SourceIndex, *, min_overlap: float = MIN_GROUNDING_OVERLAP) -> None:
        self.index = index
        self.min_overlap = min_overlap

    # ------------------------------------------------------------------ single check
    def verify_statement(
        self, text: str, claimed_sources: list[str], *, check_grounding: bool = True
    ) -> TruthVerdict:
        reasons: list[str] = []
        matched, missing = self.index.resolve(claimed_sources)

        if not claimed_sources:
            reasons.append("no source records were cited")
        if missing:
            reasons.append(f"cited sources do not exist: {', '.join(sorted(missing))}")

        for pattern, label in FORBIDDEN_CLAIM_PATTERNS:
            if re.search(pattern, text):
                reasons.append(
                    f"makes a {label} claim, which must come from an explicit profile field"
                )
                break

        for tech in _phrase_variants(text) & TECH_TERMS:
            if tech not in self.index.known_tech:
                reasons.append(f"names a technology absent from the profile: {tech}")

        for match in YEARS_CLAIM_RE.finditer(text):
            claimed_years = float(match.group(1))
            subject = _claim_subject(match.group(2))
            allowed = self.index.years_for(subject)
            label = (subject or "overall experience").strip()
            if allowed is None:
                reasons.append(f"claims {claimed_years:g} years of {label}, which is not recorded")
            elif claimed_years > allowed + YEARS_TOLERANCE:
                reasons.append(
                    f"claims {claimed_years:g} years of {label} but the profile records {allowed:g}"
                )

        overlap = 0.0
        if matched:
            statement_words = _content_words(text)
            source_words = _content_words(self.index.text_for(matched))
            if statement_words:
                overlap = len(statement_words & source_words) / len(statement_words)
            if check_grounding and overlap < self.min_overlap:
                reasons.append(
                    f"only {overlap:.0%} of the wording is traceable to the cited records"
                )

        confidence = 0.0 if reasons else round(min(0.6 + overlap * 0.4, 0.99), 4)
        return TruthVerdict(
            allowed=not reasons,
            matched_source_ids=matched,
            reasons=reasons,
            confidence=confidence,
        )

    # ---------------------------------------------------------------- whole document
    def verify_document(self, document: TailoredResume) -> TruthReport:
        verdicts: list[TruthVerdict] = []
        rejected: list[str] = []
        reasons: list[str] = []

        def check(text: str | None, sources: list[str]) -> None:
            if not text:
                return
            verdict = self.verify_statement(text, sources)
            verdicts.append(verdict)
            if not verdict.allowed:
                rejected.append(text)
                reasons.extend(verdict.reasons)

        check(document.summary, document.summary_source_ids)
        for experience in document.experience:
            if experience.experience_id not in self.index.records:
                rejected.append(f"{experience.title} at {experience.company}")
                reasons.append(
                    f"experience record {experience.experience_id} is not an approved source"
                )
            for bullet in experience.bullets:
                check(bullet.text, bullet.source_ids)
        for project in document.projects:
            for highlight in project.highlights:
                check(highlight.text, highlight.source_ids)

        for skill in document.skills:
            if not (_phrase_variants(skill) & self.index.known_terms):
                rejected.append(skill)
                reasons.append(f"skill '{skill}' is not present in the profile")

        for certification in document.certifications:
            if not (_phrase_variants(certification) & self.index.known_terms):
                rejected.append(certification)
                reasons.append(f"certification '{certification}' is not present in the profile")

        return TruthReport(
            allowed=not rejected,
            verdicts=verdicts,
            rejected_statements=rejected,
            reasons=list(dict.fromkeys(reasons)),
        )

    # ------------------------------------------------------------------ answer check
    def verify_answer(self, answer: str, claimed_sources: list[str]) -> TruthVerdict:
        """Same rules, applied to a free-text application answer.

        Word-overlap grounding is not applied here: an answer to "why are you
        interested in this role?" is prose built around the facts rather than a
        rewrite of them. The substantive guards — real sources, no unlisted
        technology, no inflated numbers, no legally significant claims — still apply.
        """
        return self.verify_statement(answer, claimed_sources, check_grounding=False)
