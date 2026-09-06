"""Job discovery, browsing, matching and preferences."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from jobapply_api.deps import CurrentUser, SessionDep
from jobapply_api.schemas.common import Page
from jobapply_api.schemas.job import (
    DiscoveryResult,
    JobCard,
    JobDecision,
    JobDetail,
    JobPreferenceResponse,
    JobPreferenceUpdate,
    JobSearchRequest,
    JobSourceResponse,
    MatchSummary,
)
from jobapply_api.services.job_service import JobService

router = APIRouter(tags=["jobs"])


def job_service(db: SessionDep) -> JobService:
    return JobService(db)


JobServiceDep = Annotated[JobService, Depends(job_service)]


def _card(job, match, application_status) -> JobCard:
    card = JobCard.model_validate(job)
    card.match = MatchSummary.model_validate(match) if match else None
    card.application_status = application_status
    return card


@router.post("/jobs/search", response_model=DiscoveryResult)
def search_jobs(
    payload: JobSearchRequest,
    user: CurrentUser,
    service: JobServiceDep,
    db: SessionDep,
) -> DiscoveryResult:
    """Run discovery across the enabled sources and store what is new.

    Discovery is synchronous here because it is user-initiated and bounded; the
    scheduled sweep runs the same service from a worker.
    """
    result = service.discover(user.id, payload)
    db.commit()
    return DiscoveryResult(**result)


@router.get("/jobs", response_model=Page[JobCard])
def list_jobs(
    user: CurrentUser,
    service: JobServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    min_score: int | None = Query(default=None, ge=0, le=100),
    recommendation: str | None = Query(default=None, pattern="^(APPLY|REVIEW|SKIP)$"),
    company: str | None = Query(default=None, max_length=200),
) -> Page[JobCard]:
    rows, total = service.list_jobs(
        user.id,
        min_score=min_score,
        recommendation=recommendation,
        company=company,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return Page[JobCard](
        items=[_card(job, match, status) for job, match, status in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/jobs/{job_id}", response_model=JobDetail)
def get_job(job_id: uuid.UUID, user: CurrentUser, service: JobServiceDep) -> JobDetail:
    job, match, application_status = service.get_job_with_match(user.id, job_id)
    detail = JobDetail.model_validate(job)
    detail.match = MatchSummary.model_validate(match) if match else None
    detail.application_status = application_status
    detail.source_slug = job.source.slug if job.source else None
    return detail


@router.post("/jobs/{job_id}/match", response_model=MatchSummary)
def match_job(
    job_id: uuid.UUID, user: CurrentUser, service: JobServiceDep, db: SessionDep
) -> MatchSummary:
    match = service.score_job(user.id, job_id)
    db.commit()
    db.refresh(match)
    return MatchSummary.model_validate(match)


@router.post("/jobs/rescore")
def rescore_jobs(user: CurrentUser, service: JobServiceDep, db: SessionDep) -> dict[str, int]:
    """Re-run matching for every stored job — used after a profile or preference change."""
    count = service.rescore_all(user.id)
    db.commit()
    return {"rescored": count}


@router.post("/jobs/{job_id}/decision", response_model=MatchSummary)
def decide(
    job_id: uuid.UUID,
    payload: JobDecision,
    user: CurrentUser,
    service: JobServiceDep,
    db: SessionDep,
) -> MatchSummary:
    match = service.set_decision(user.id, job_id, payload.decision)
    db.commit()
    db.refresh(match)
    return MatchSummary.model_validate(match)


@router.get("/preferences", response_model=JobPreferenceResponse)
def get_preferences(
    user: CurrentUser, service: JobServiceDep, db: SessionDep
) -> JobPreferenceResponse:
    preference = service.get_preference(user.id)
    db.commit()
    return JobPreferenceResponse.model_validate(preference)


@router.put("/preferences", response_model=JobPreferenceResponse)
def update_preferences(
    payload: JobPreferenceUpdate,
    user: CurrentUser,
    service: JobServiceDep,
    db: SessionDep,
) -> JobPreferenceResponse:
    preference = service.update_preference(user.id, payload)
    db.commit()
    db.refresh(preference)
    return JobPreferenceResponse.model_validate(preference)


@router.get("/job-sources", response_model=list[JobSourceResponse])
def list_sources(
    user: CurrentUser, service: JobServiceDep, db: SessionDep
) -> list[JobSourceResponse]:
    sources = service.ensure_default_sources()
    db.commit()
    return [JobSourceResponse.model_validate(source) for source in sources]
