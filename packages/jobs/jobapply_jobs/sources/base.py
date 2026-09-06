"""Job source interface.

A source fetches postings from somewhere the platform is permitted to read: an
official public job-board API, a feed the employer publishes, or data the user pasted
in themselves. Sources never authenticate as the user to a third party, never bypass a
technical access restriction, and never scrape a site whose terms forbid it.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from jobapply_jobs.models import JobQuery, RawJob


@runtime_checkable
class JobSource(Protocol):
    slug: str
    name: str
    #: "feed" (official API/feed), "career_page" (employer's own board), "manual".
    kind: str

    async def fetch(self, query: JobQuery) -> list[RawJob]: ...


class SourceError(Exception):
    """A source could not be read. Discovery continues with the other sources."""
