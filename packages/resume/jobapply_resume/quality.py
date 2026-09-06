"""Resume quality scoring.

Run before a tailored resume is rendered and uploaded, so a weak document is caught
here rather than by an employer's parser. Factual consistency is the one component
that can block: the others are advisory.
"""

from __future__ import annotations

from typing import Any

from jobapply_shared.text import normalize_text

from jobapply_resume.models import ResumeScore, TailoredResume, TruthReport

#: An ATS-friendly bullet is a sentence, not a paragraph.
MAX_BULLET_CHARS = 240
MIN_BULLET_CHARS = 25
#: Roughly how much text fits on one page of a standard resume template.
CHARS_PER_PAGE = 3200


def _content_chars(document: TailoredResume) -> int:
    total = len(document.summary or "")
    total += sum(len(bullet.text) for role in document.experience for bullet in role.bullets)
    total += sum(len(skill) + 2 for skill in document.skills)
    total += sum(
        len(highlight.text) for project in document.projects for highlight in project.highlights
    )
    return total


def score_resume(
    document: TailoredResume, job: dict[str, Any], truth: TruthReport | None = None
) -> ResumeScore:
    notes: list[str] = []
    bullets = [bullet.text for role in document.experience for bullet in role.bullets]

    # --- ATS readability -----------------------------------------------------
    ats = 100
    if not document.contact.email:
        ats -= 20
        notes.append("No e-mail address — many parsers key on it.")
    if not document.contact.phone:
        ats -= 8
        notes.append("No phone number.")
    if not document.experience:
        ats -= 30
        notes.append("No experience section.")
    over_long = [text for text in bullets if len(text) > MAX_BULLET_CHARS]
    if over_long:
        ats -= min(15, 3 * len(over_long))
        notes.append(f"{len(over_long)} bullet(s) are long enough to read as paragraphs.")
    too_short = [text for text in bullets if len(text) < MIN_BULLET_CHARS]
    if too_short:
        ats -= min(10, 2 * len(too_short))
        notes.append(f"{len(too_short)} bullet(s) are very short.")

    # --- keyword and skill coverage -----------------------------------------
    job_skills = [normalize_text(skill) for skill in (job.get("skills") or []) if skill]
    resume_text = normalize_text(" ".join([document.summary or "", *bullets, *document.skills]))
    if job_skills:
        covered = [skill for skill in job_skills if skill and skill in resume_text]
        keyword_coverage = round(100 * len(covered) / len(job_skills))
        if keyword_coverage < 60:
            notes.append(
                f"Only {keyword_coverage}% of the posting's listed skills appear in the resume."
            )
    else:
        keyword_coverage = 70

    owned = {normalize_text(skill) for skill in document.skills}
    if job_skills:
        skill_coverage = round(100 * len([s for s in job_skills if s in owned]) / len(job_skills))
    else:
        skill_coverage = 70

    # --- experience relevance ------------------------------------------------
    terms = {
        word
        for word in normalize_text(" ".join(job.get("requirements") or [])).split()
        if len(word) > 3
    }
    if terms and bullets:
        hits = sum(1 for text in bullets if terms & set(normalize_text(text).split()))
        experience_relevance = round(100 * hits / len(bullets))
        if experience_relevance < 40:
            notes.append("Few bullets reference anything the posting asks for.")
    else:
        experience_relevance = 65

    # --- formatting ----------------------------------------------------------
    formatting = 100
    total_chars = _content_chars(document)
    budget = CHARS_PER_PAGE * document.max_pages
    if total_chars > budget:
        overflow = round(100 * (total_chars - budget) / budget)
        formatting -= min(40, overflow)
        notes.append(f"About {overflow}% more content than fits in {document.max_pages} page(s).")
    if total_chars < budget * 0.35:
        formatting -= 15
        notes.append("The resume is sparse for its page budget.")
    if len(document.skills) > 40:
        formatting -= 10
        notes.append("The skills list is long enough to dilute the relevant entries.")

    # --- factual consistency -------------------------------------------------
    if truth is None:
        factual = (
            100
            if all(bullet.source_ids for role in document.experience for bullet in role.bullets)
            else 70
        )
    elif truth.allowed:
        factual = 100
    else:
        factual = max(0, 100 - 25 * len(truth.rejected_statements))
        notes.append(
            f"{len(truth.rejected_statements)} statement(s) could not be traced to your records."
        )

    def clamp(value: int) -> int:
        return max(0, min(100, value))

    ats, formatting = clamp(ats), clamp(formatting)
    overall = round(
        ats * 0.25
        + keyword_coverage * 0.20
        + skill_coverage * 0.15
        + experience_relevance * 0.15
        + formatting * 0.10
        + factual * 0.15
    )

    return ResumeScore(
        ats_readability=ats,
        keyword_coverage=clamp(keyword_coverage),
        skill_coverage=clamp(skill_coverage),
        experience_relevance=clamp(experience_relevance),
        formatting_quality=formatting,
        factual_consistency=clamp(factual),
        overall=clamp(overall),
        notes=notes,
    )
