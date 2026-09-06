"""Job sources. Each reads somewhere the platform is permitted to read."""

from jobapply_jobs.sources.base import JobSource, SourceError
from jobapply_jobs.sources.greenhouse import GreenhouseSource
from jobapply_jobs.sources.lever import LeverSource
from jobapply_jobs.sources.sample import SampleFeedSource

__all__ = ["GreenhouseSource", "JobSource", "LeverSource", "SampleFeedSource", "SourceError"]


def build_source(slug: str, config: dict) -> JobSource:
    """Instantiate a source from its stored ``job_sources.config`` row."""
    if slug == "greenhouse":
        return GreenhouseSource(config.get("board_tokens", []))
    if slug == "lever":
        return LeverSource(config.get("companies", []))
    if slug == "sample":
        return SampleFeedSource(config.get("fixture_dir"))
    raise ValueError(f"Unknown job source: {slug}")
