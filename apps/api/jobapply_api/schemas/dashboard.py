"""Dashboard and notification models."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from jobapply_api.schemas.common import ORMModel


class DashboardCounters(BaseModel):
    jobs_discovered: int = 0
    jobs_matched: int = 0
    applications_total: int = 0
    applications_submitted: int = 0
    applications_this_week: int = 0
    applications_this_month: int = 0
    applications_failed: int = 0
    applications_in_progress: int = 0
    interviews: int = 0
    offers: int = 0
    rejections: int = 0
    open_interventions: int = 0
    average_match_score: float = 0.0
    automation_success_rate: float = 0.0
    failure_rate: float = 0.0


class ProfileReadiness(BaseModel):
    profile_score: int = 0
    has_master_resume: bool = False
    work_authorization_declared: bool = False
    automation_enabled: bool = False
    automation_paused: bool = True
    blockers: list[str] = Field(default_factory=list)


class DashboardResponse(BaseModel):
    counters: DashboardCounters
    readiness: ProfileReadiness
    recent_applications: list[dict] = Field(default_factory=list)
    attention_required: list[dict] = Field(default_factory=list)


class NotificationResponse(ORMModel):
    id: uuid.UUID
    kind: str
    channel: str
    title: str
    body: str | None = None
    link: str | None = None
    read_at: datetime | None = None
    created_at: datetime
