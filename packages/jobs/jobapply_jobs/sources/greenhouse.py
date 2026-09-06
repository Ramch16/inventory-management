"""Greenhouse job board source.

Uses Greenhouse's public job board API, which employers publish specifically so their
openings can be read programmatically:

    https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true

No authentication is involved and no access control is circumvented. The board tokens
to read come from configuration — the employers a user has asked to follow.
"""

from __future__ import annotations

from datetime import datetime

import httpx
from jobapply_shared.logging import get_logger
from jobapply_shared.text import normalize_text

from jobapply_jobs.models import JobQuery, RawJob
from jobapply_jobs.sources.base import SourceError

logger = get_logger(__name__)

API_ROOT = "https://boards-api.greenhouse.io/v1/boards"


class GreenhouseSource:
    kind = "career_page"

    def __init__(self, board_tokens: list[str], *, timeout: float = 20.0) -> None:
        self.board_tokens = board_tokens
        self.timeout = timeout
        self.slug = "greenhouse"
        self.name = "Greenhouse job boards"

    async def fetch(self, query: JobQuery) -> list[RawJob]:
        jobs: list[RawJob] = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for token in self.board_tokens:
                try:
                    response = await client.get(
                        f"{API_ROOT}/{token}/jobs", params={"content": "true"}
                    )
                    response.raise_for_status()
                except httpx.HTTPError as exc:
                    # One unreachable board must not fail the whole discovery run.
                    logger.warning(
                        "jobs.source_error",
                        extra={
                            "context": {
                                "event": "jobs.source_error",
                                "source": self.slug,
                                "board": token,
                                "detail": str(exc)[:200],
                            }
                        },
                    )
                    continue
                jobs.extend(self._parse(token, response.json()))
        return _filter(jobs, query)

    def _parse(self, token: str, payload: dict) -> list[RawJob]:
        results: list[RawJob] = []
        for record in payload.get("jobs", []):
            try:
                results.append(
                    RawJob(
                        source_slug=self.slug,
                        source_job_id=str(record["id"]),
                        company=record.get("company_name") or token,
                        title=record["title"],
                        location=(record.get("location") or {}).get("name"),
                        description=record.get("content"),
                        apply_url=record.get("absolute_url"),
                        posting_url=record.get("absolute_url"),
                        posted_at=_parse_timestamp(record.get("updated_at")),
                        payload={"board_token": token, "greenhouse_id": record["id"]},
                    )
                )
            except KeyError as exc:
                raise SourceError(f"Greenhouse posting missing field {exc}") from exc
        return results


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


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
