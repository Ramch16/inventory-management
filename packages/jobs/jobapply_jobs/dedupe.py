"""Duplicate detection for discovered jobs.

Two layers, because the same role legitimately appears twice with different ids:

1. exact — the ``dedupe_key`` over company, title, location and source job id;
2. similarity — same normalized company, near-identical title and compatible
   location, or an identical description body.
"""

from __future__ import annotations

from dataclasses import dataclass

from jobapply_shared.text import normalize_location, title_similarity

from jobapply_jobs.models import DuplicateVerdict, NormalizedJob

#: Above this, two postings at the same company are treated as the same role.
TITLE_SIMILARITY_THRESHOLD = 0.86


@dataclass(frozen=True)
class ExistingJob:
    """The subset of a stored job needed to compare against a candidate."""

    id: str
    normalized_company: str
    normalized_title: str
    normalized_location: str | None
    dedupe_key: str
    content_hash: str | None


def locations_compatible(left: str | None, right: str | None) -> bool:
    """A missing location on either side is not evidence of a different role."""
    if not left or not right:
        return True
    a, b = normalize_location(left), normalize_location(right)
    if a == b:
        return True
    # "Austin, TX, United States" vs "Austin, TX" — one being a prefix of the other
    # is the same place described at different precision.
    return a.startswith(b) or b.startswith(a)


def find_duplicate(candidate: NormalizedJob, existing: list[ExistingJob]) -> DuplicateVerdict:
    for job in existing:
        if job.dedupe_key == candidate.dedupe_key:
            return DuplicateVerdict(
                is_duplicate=True,
                reason="identical company, title, location and source id",
                similarity=1.0,
                matched_id=job.id,
            )

    for job in existing:
        if job.normalized_company != candidate.normalized_company:
            continue
        if (
            candidate.content_hash
            and job.content_hash
            and job.content_hash == candidate.content_hash
            and locations_compatible(job.normalized_location, candidate.normalized_location)
        ):
            return DuplicateVerdict(
                is_duplicate=True,
                reason="same company and an identical description body",
                similarity=1.0,
                matched_id=job.id,
            )
        similarity = title_similarity(job.normalized_title, candidate.normalized_title)
        if similarity >= TITLE_SIMILARITY_THRESHOLD and locations_compatible(
            job.normalized_location, candidate.normalized_location
        ):
            return DuplicateVerdict(
                is_duplicate=True,
                reason=f"same company and a near-identical title ({similarity:.0%})",
                similarity=similarity,
                matched_id=job.id,
            )

    return DuplicateVerdict(is_duplicate=False)


def application_dedupe_hash(
    *, company: str, title: str, employer_job_id: str | None, apply_url: str | None
) -> str:
    """Key used to guarantee one application per user per role.

    The employer's own job id is the strongest signal; the apply URL is included so
    two postings of the same role on different boards still collapse together when the
    destination is identical.
    """
    from urllib.parse import urlsplit

    from jobapply_shared.text import content_hash, normalize_company, normalize_title

    canonical_url = ""
    if apply_url:
        parts = urlsplit(apply_url)
        canonical_url = f"{parts.netloc.lower()}{parts.path.rstrip('/')}"
    return content_hash(
        normalize_company(company), normalize_title(title), employer_job_id or "", canonical_url
    )
