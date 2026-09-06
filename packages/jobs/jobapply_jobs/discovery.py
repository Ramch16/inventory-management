"""Job discovery orchestration.

Runs the enabled sources for one query, normalizes what comes back and drops
duplicates before anything is persisted. A failing source is logged and skipped: one
bad board must not stop a discovery run.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from jobapply_shared.logging import get_logger

from jobapply_jobs.dedupe import ExistingJob, find_duplicate
from jobapply_jobs.models import JobQuery, NormalizedJob
from jobapply_jobs.normalize import JobNormalizer
from jobapply_jobs.sources.base import JobSource

logger = get_logger(__name__)


@dataclass
class DiscoveryReport:
    fetched: int = 0
    normalized: int = 0
    duplicates: int = 0
    errors: list[str] = field(default_factory=list)
    jobs: list[NormalizedJob] = field(default_factory=list)


class JobDiscoveryService:
    def __init__(self, sources: list[JobSource], normalizer: JobNormalizer | None = None) -> None:
        self.sources = sources
        self.normalizer = normalizer or JobNormalizer()

    async def discover(
        self, query: JobQuery, existing: list[ExistingJob] | None = None
    ) -> DiscoveryReport:
        report = DiscoveryReport()
        known = list(existing or [])

        results = await asyncio.gather(
            *(source.fetch(query) for source in self.sources), return_exceptions=True
        )

        for source, result in zip(self.sources, results, strict=True):
            if isinstance(result, BaseException):
                message = f"{source.slug}: {result}"
                report.errors.append(message)
                logger.warning(
                    "jobs.discovery_source_failed",
                    extra={
                        "context": {
                            "event": "jobs.discovery_source_failed",
                            "source": source.slug,
                            "detail": str(result)[:200],
                        }
                    },
                )
                continue

            report.fetched += len(result)
            for raw in result:
                job = self.normalizer.normalize(raw)
                verdict = find_duplicate(job, known)
                if verdict.is_duplicate:
                    report.duplicates += 1
                    continue
                known.append(
                    ExistingJob(
                        id=job.dedupe_key,
                        normalized_company=job.normalized_company,
                        normalized_title=job.normalized_title,
                        normalized_location=job.normalized_location,
                        dedupe_key=job.dedupe_key,
                        content_hash=job.content_hash,
                    )
                )
                report.jobs.append(job)
                report.normalized += 1

        logger.info(
            "jobs.discovery_complete",
            extra={
                "context": {
                    "event": "jobs.discovery_complete",
                    "fetched": report.fetched,
                    "normalized": report.normalized,
                    "duplicates": report.duplicates,
                    "errors": len(report.errors),
                }
            },
        )
        return report
