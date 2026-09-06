"""Local sample source.

Reads clearly-labelled fixture postings from disk so the whole pipeline can be
developed and tested without network access. The data is sample data and is marked as
such — the platform never fabricates a real job.
"""

from __future__ import annotations

import json
from pathlib import Path

from jobapply_shared.text import normalize_text

from jobapply_jobs.models import JobQuery, RawJob

DEFAULT_FIXTURE_DIR = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "jobs"


class SampleFeedSource:
    slug = "sample"
    name = "Sample postings (local fixture data)"
    kind = "feed"

    def __init__(self, fixture_dir: Path | str | None = None) -> None:
        self.fixture_dir = Path(fixture_dir or DEFAULT_FIXTURE_DIR)

    async def fetch(self, query: JobQuery) -> list[RawJob]:
        if not self.fixture_dir.exists():
            return []
        jobs: list[RawJob] = []
        for path in sorted(self.fixture_dir.glob("*.json")):
            payload = json.loads(path.read_text())
            records = payload if isinstance(payload, list) else [payload]
            for record in records:
                jobs.append(
                    RawJob(
                        source_slug=self.slug,
                        source_job_id=str(record["id"]),
                        company=record["company"],
                        title=record["title"],
                        location=record.get("location"),
                        description=record.get("description"),
                        apply_url=record.get("apply_url"),
                        posting_url=record.get("posting_url"),
                        employment_type=record.get("employment_type"),
                        remote_hint=record.get("remote"),
                        salary_text=record.get("salary"),
                        payload={"sample_data": True, **record},
                    )
                )
        return _filter(jobs, query)


def _filter(jobs: list[RawJob], query: JobQuery) -> list[RawJob]:
    """Apply the query's coarse filters locally, the way a remote source would."""
    results = []
    for job in jobs:
        haystack = normalize_text(f"{job.title} {job.location or ''} {job.description or ''}")
        if query.titles and not any(normalize_text(title) in haystack for title in query.titles):
            continue
        if query.keywords and not any(
            normalize_text(keyword) in haystack for keyword in query.keywords
        ):
            continue
        if query.remote_only and "remote" not in haystack:
            continue
        if query.locations and not any(
            normalize_text(location) in haystack for location in query.locations
        ):
            continue
        results.append(job)
    return results[: query.limit]
