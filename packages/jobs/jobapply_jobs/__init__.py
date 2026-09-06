"""Job discovery, normalization, duplicate detection and matching."""

from jobapply_jobs.dedupe import ExistingJob, application_dedupe_hash, find_duplicate
from jobapply_jobs.discovery import DiscoveryReport, JobDiscoveryService
from jobapply_jobs.matching import JobMatchingService
from jobapply_jobs.models import (
    JobQuery,
    MatchProfile,
    MatchResult,
    MatchWeights,
    NormalizedJob,
    RawJob,
)
from jobapply_jobs.normalize import JobNormalizer

__all__ = [
    "DiscoveryReport",
    "ExistingJob",
    "JobDiscoveryService",
    "JobMatchingService",
    "JobNormalizer",
    "JobQuery",
    "MatchProfile",
    "MatchResult",
    "MatchWeights",
    "NormalizedJob",
    "RawJob",
    "application_dedupe_hash",
    "find_duplicate",
]
