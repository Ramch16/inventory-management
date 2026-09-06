"""Billing is architecture, not a charge — and the free plan is real."""

from __future__ import annotations

from jobapply_db.models import Subscription, UsageRecord
from sqlalchemy import select


def test_a_new_account_is_on_the_free_plan(api, registered):
    body = api.get("/billing").json()
    assert body["plan"] == "free"
    assert body["status"] == "active"
    assert body["provider"] == "noop"
    assert body["checkout_available"] is False, "this deployment cannot take a payment"


def test_the_plans_are_listed_with_their_real_limits(api, registered):
    plans = {plan["plan"]: plan for plan in api.get("/billing").json()["plans"]}
    assert set(plans) == {"free", "pro", "premium"}
    assert plans["free"]["current"] is True
    assert plans["free"]["ai_tailoring"] is False
    assert plans["pro"]["ai_tailoring"] is True
    assert plans["premium"]["applications_per_month"] > plans["pro"]["applications_per_month"]


def test_usage_starts_at_zero_and_is_recorded(api, registered, db_session):
    usage = api.get("/billing").json()["usage"]
    assert usage["applications_submitted"] == 0
    assert usage["remaining"] == usage["applications_limit"]

    record = db_session.execute(select(UsageRecord)).scalar_one()
    assert record.metric == "applications_submitted"
    assert record.quantity == 0


def test_the_plan_can_be_changed_while_no_payment_provider_is_configured(
    api, registered, db_session
):
    body = api.post("/billing/plan", json={"plan": "pro"}).json()
    assert body["plan"] == "pro"
    assert body["usage"]["applications_limit"] == 300

    subscription = db_session.execute(select(Subscription)).scalar_one()
    assert subscription.plan == "pro"


def test_billing_requires_authentication(api):
    assert api.get("/billing").status_code == 401


def test_each_user_sees_only_their_own_subscription(api, registered):
    api.post("/billing/plan", json={"plan": "premium"})
    api.post("/auth/logout")
    second = api.post(
        "/auth/register", json={"email": "second@example.com", "password": "Str0ngPassword!"}
    )
    api.set_csrf(second.json()["csrf_token"])
    assert api.get("/billing").json()["plan"] == "free"
