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


# ------------------------------------------------------------------------ analytics
class SeriesPoint(BaseModel):
    date: str
    created: int = 0
    submitted: int = 0


class LabelCount(BaseModel):
    label: str
    count: int = 0


class FunnelStage(BaseModel):
    stage: str
    label: str
    count: int = 0


class Outcomes(BaseModel):
    submitted: int = 0
    responses: int = 0
    interviews: int = 0
    offers: int = 0
    rejections: int = 0
    response_rate: float = 0.0
    interview_rate: float = 0.0


class AutomationHealth(BaseModel):
    succeeded: int = 0
    failed: int = 0
    awaiting_user: int = 0
    unconfirmed: int = 0
    success_rate: float = 0.0
    failure_rate: float = 0.0
    intervention_rate: float = 0.0


class AnalyticsReport(BaseModel):
    range_days: int
    applications_per_day: list[SeriesPoint] = Field(default_factory=list)
    by_company: list[LabelCount] = Field(default_factory=list)
    by_role: list[LabelCount] = Field(default_factory=list)
    by_location: list[LabelCount] = Field(default_factory=list)
    match_score_distribution: list[LabelCount] = Field(default_factory=list)
    funnel: list[FunnelStage] = Field(default_factory=list)
    outcomes: Outcomes = Field(default_factory=Outcomes)
    automation: AutomationHealth = Field(default_factory=AutomationHealth)
