"""The billing seam."""

from __future__ import annotations

import pytest
from jobapply_shared.billing import (
    PLANS,
    NoopBillingService,
    build_billing_service,
    limits_for,
)
from jobapply_shared.enums import SubscriptionPlan


def test_the_default_provider_is_a_no_op():
    service = build_billing_service(type("S", (), {"billing_backend": "noop"})())
    assert isinstance(service, NoopBillingService)
    session = service.create_checkout(
        user_id="u", email="e@example.com", plan=SubscriptionPlan.PRO, return_url="/billing"
    )
    assert session.immediate is True
    assert session.url is None


def test_plan_limits_increase_with_the_plan():
    free, pro, premium = (limits_for(plan) for plan in ("free", "pro", "premium"))
    assert free.applications_per_day < pro.applications_per_day < premium.applications_per_day
    assert free.ai_tailoring is False
    assert pro.ai_tailoring and premium.ai_tailoring


def test_an_unknown_plan_falls_back_to_free():
    assert limits_for("enterprise").plan == SubscriptionPlan.FREE


def test_every_declared_plan_has_limits():
    for plan in SubscriptionPlan:
        assert plan in PLANS


def test_stripe_requires_a_key():
    from jobapply_shared.billing import StripeBillingService

    with pytest.raises(ValueError, match="STRIPE_SECRET_KEY"):
        StripeBillingService("")
