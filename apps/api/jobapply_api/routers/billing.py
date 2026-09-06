"""Subscription and usage endpoints.

Billing is architecture, not a live charge: the default provider is a no-op and every
account sits on the free plan. Plan limits are real, though — the application policy
reads them, so a plan change has an immediate, visible effect.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from jobapply_db.models import Application, Subscription, UsageRecord
from jobapply_shared.billing import PLANS, build_billing_service, limits_for
from jobapply_shared.enums import (
    SUBMITTED_APPLICATION_STATUSES,
    SubscriptionPlan,
    SubscriptionStatus,
)
from jobapply_shared.errors import ValidationError_
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from jobapply_api.deps import CurrentUser, SessionDep, SettingsDep
from jobapply_api.services import audit

router = APIRouter(prefix="/billing", tags=["billing"])

USAGE_METRIC_APPLICATIONS = "applications_submitted"


class PlanOut(BaseModel):
    plan: str
    applications_per_day: int
    applications_per_month: int
    ai_tailoring: bool
    cover_letters: bool
    current: bool = False


class UsageOut(BaseModel):
    period: str
    applications_submitted: int
    applications_limit: int
    remaining: int


class SubscriptionOut(BaseModel):
    plan: str
    status: str
    provider: str
    cancel_at_period_end: bool = False
    current_period_end: datetime | None = None
    usage: UsageOut
    plans: list[PlanOut]
    #: True when this deployment can actually take a payment.
    checkout_available: bool = False


class PlanChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: SubscriptionPlan


def _subscription_for(db, user) -> Subscription:
    subscription = db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    ).scalar_one_or_none()
    if subscription is None:
        subscription = Subscription(user_id=user.id, plan=SubscriptionPlan.FREE, provider="noop")
        db.add(subscription)
        db.flush()
    return subscription


def _usage(db, user, plan: str) -> UsageOut:
    period = datetime.now(tz=UTC).strftime("%Y-%m")
    submitted = int(
        db.execute(
            select(func.count())
            .select_from(Application)
            .where(
                Application.user_id == user.id,
                Application.deleted_at.is_(None),
                Application.status.in_([str(status) for status in SUBMITTED_APPLICATION_STATUSES]),
                Application.submitted_at.is_not(None),
                Application.submitted_at
                >= datetime.now(tz=UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0),
            )
        ).scalar_one()
    )
    limits = limits_for(plan)
    return UsageOut(
        period=period,
        applications_submitted=submitted,
        applications_limit=limits.applications_per_month,
        remaining=max(0, limits.applications_per_month - submitted),
    )


def _record_usage(db, user, subscription: Subscription, submitted: int) -> None:
    period = datetime.now(tz=UTC).strftime("%Y-%m")
    record = db.execute(
        select(UsageRecord).where(
            UsageRecord.user_id == user.id,
            UsageRecord.period == period,
            UsageRecord.metric == USAGE_METRIC_APPLICATIONS,
        )
    ).scalar_one_or_none()
    if record is None:
        record = UsageRecord(
            user_id=user.id,
            subscription_id=subscription.id,
            period=period,
            metric=USAGE_METRIC_APPLICATIONS,
        )
        db.add(record)
    record.quantity = submitted


@router.get("", response_model=SubscriptionOut)
def get_subscription(user: CurrentUser, db: SessionDep, settings: SettingsDep) -> SubscriptionOut:
    subscription = _subscription_for(db, user)
    usage = _usage(db, user, subscription.plan)
    _record_usage(db, user, subscription, usage.applications_submitted)
    db.commit()

    return SubscriptionOut(
        plan=subscription.plan,
        status=subscription.status,
        provider=subscription.provider,
        cancel_at_period_end=subscription.cancel_at_period_end,
        current_period_end=subscription.current_period_end,
        usage=usage,
        plans=[
            PlanOut(
                plan=str(limits.plan),
                applications_per_day=limits.applications_per_day,
                applications_per_month=limits.applications_per_month,
                ai_tailoring=limits.ai_tailoring,
                cover_letters=limits.cover_letters,
                current=str(limits.plan) == subscription.plan,
            )
            for limits in PLANS.values()
        ],
        checkout_available=settings.billing_backend != "noop",
    )


@router.post("/plan", response_model=SubscriptionOut)
def change_plan(
    payload: PlanChange, user: CurrentUser, db: SessionDep, settings: SettingsDep
) -> SubscriptionOut:
    """Change plan.

    With the no-op provider this records the change directly. With a real provider it
    returns the checkout URL instead of pretending the change already happened.
    """
    subscription = _subscription_for(db, user)
    service = build_billing_service(settings)
    session = service.create_checkout(
        user_id=str(user.id),
        email=user.email,
        plan=payload.plan,
        return_url=f"{settings.frontend_base_url}/billing",
    )

    if not session.immediate:
        raise ValidationError_(
            "Complete checkout to change your plan.",
            code="checkout_required",
            details={"checkout_url": session.url},
        )

    subscription.plan = str(payload.plan)
    subscription.status = str(SubscriptionStatus.ACTIVE)
    subscription.provider = service.provider
    audit.record(
        db,
        action="billing.plan_changed",
        actor_user_id=user.id,
        entity_type="subscription",
        entity_id=subscription.id,
        data={"plan": str(payload.plan)},
    )
    db.commit()
    db.refresh(subscription)
    return get_subscription(user, db, settings)
