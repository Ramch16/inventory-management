"""Lever job board source.

Uses Lever's public postings API, published by employers for exactly this purpose:

    https://api.lever.co/v0/postings/{company}?mode=json

No authentication, no access control circumvented.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
from jobapply_shared.logging import get_logger
from jobapply_shared.text import normalize_text

from jobapply_jobs.models import JobQuery, RawJob

logger = get_logger(__name__)

API_ROOT = "https://api.lever.co/v0/postings"


class LeverSource:
    kind = "career_page"

    def __init__(self, companies: list[str], *, timeout: float = 20.0) -> None:
        self.companies = companies
        self.timeout = timeout
        self.slug = "lever"
        self.name = "Lever job boards"

    async def fetch(self, query: JobQuery) -> list[RawJob]:
        jobs: list[RawJob] = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for company in self.companies:
                try:
                    response = await client.get(f"{API_ROOT}/{company}", params={"mode": "json"})
                    response.raise_for_status()
                except httpx.HTTPError as exc:
                    logger.warning(
                        "jobs.source_error",
                        extra={
                            "context": {
                                "event": "jobs.source_error",
                                "source": self.slug,
                                "company": company,
                                "detail": str(exc)[:200],
                            }
                        },
                    )
                    continue
                jobs.extend(self._parse(company, response.json()))
        return _filter(jobs, query)

    def _parse(self, company: str, payload: list[dict]) -> list[RawJob]:
        results: list[RawJob] = []
        for record in payload:
            categories = record.get("categories") or {}
            posted_at = record.get("createdAt")
            results.append(
                RawJob(
                    source_slug=self.slug,
                    source_job_id=str(record.get("id") or record.get("leverId") or ""),
                    company=company,
                    title=record.get("text") or "",
                    location=categories.get("location"),
                    description=record.get("descriptionPlain") or record.get("description"),
                    apply_url=record.get("applyUrl") or record.get("hostedUrl"),
                    posting_url=record.get("hostedUrl"),
                    employment_type=categories.get("commitment"),
                    remote_hint=categories.get("location"),
                    posted_at=(
                        datetime.fromtimestamp(posted_at / 1000, tz=UTC)
                        if isinstance(posted_at, (int, float))
                        else None
                    ),
                    payload={"lever_company": company, "team": categories.get("team")},
                )
            )
        return [job for job in results if job.source_job_id and job.title]


def _filter(jobs: list[RawJob], query: JobQuery) -> list[RawJob]:
    results = []
    for job in jobs:
        haystack = normalize_text(f"{job.title} {job.location or ''}")
        if query.titles and not any(normalize_text(title) in haystack for title in query.titles):
            continue
        if query.locations and not any(
            normalize_text(location) in haystack for location in query.locations
        ):
            continue
        results.append(job)
    return results[: query.limit]
