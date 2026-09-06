"""Billing abstraction.

The architecture is in place and the seam is real, but no money moves: the default
implementation is a no-op that keeps every account on the free plan. Stripe is wired
behind the same interface so enabling it is configuration, not a rewrite.

Plans are enforced through :class:`PlanLimits`, which the application policy reads —
so a plan change takes effect without touching the automation code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from jobapply_shared.enums import SubscriptionPlan, SubscriptionStatus
from jobapply_shared.errors import ProviderError
from jobapply_shared.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class PlanLimits:
    plan: SubscriptionPlan
    applications_per_day: int
    applications_per_month: int
    ai_tailoring: bool
    cover_letters: bool
    #: Which ATS adapters the plan may use; empty means all of them.
    adapters: tuple[str, ...] = ()


PLANS: dict[SubscriptionPlan, PlanLimits] = {
    SubscriptionPlan.FREE: PlanLimits(
        plan=SubscriptionPlan.FREE,
        applications_per_day=5,
        applications_per_month=30,
        ai_tailoring=False,
        cover_letters=False,
    ),
    SubscriptionPlan.PRO: PlanLimits(
        plan=SubscriptionPlan.PRO,
        applications_per_day=25,
        applications_per_month=300,
        ai_tailoring=True,
        cover_letters=True,
    ),
    SubscriptionPlan.PREMIUM: PlanLimits(
        plan=SubscriptionPlan.PREMIUM,
        applications_per_day=50,
        applications_per_month=1000,
        ai_tailoring=True,
        cover_letters=True,
    ),
}


def limits_for(plan: SubscriptionPlan | str) -> PlanLimits:
    """Limits for a plan. An unrecognised plan name falls back to free rather than
    raising: a stale value in the database must not stop a user from applying."""
    try:
        return PLANS[SubscriptionPlan(plan)]
    except (ValueError, KeyError):
        logger.warning(
            "billing.unknown_plan",
            extra={"context": {"event": "billing.unknown_plan", "plan": str(plan)}},
        )
        return PLANS[SubscriptionPlan.FREE]


@dataclass(frozen=True)
class CheckoutSession:
    url: str | None
    provider_session_id: str | None
    #: True when no payment step is required (the no-op provider).
    immediate: bool = False


@dataclass(frozen=True)
class SubscriptionState:
    plan: SubscriptionPlan
    status: SubscriptionStatus
    provider: str
    provider_customer_id: str | None = None
    provider_subscription_id: str | None = None
    cancel_at_period_end: bool = False


class BillingService(Protocol):
    provider: str

    def ensure_customer(self, *, user_id: str, email: str) -> str | None: ...
    def create_checkout(
        self, *, user_id: str, email: str, plan: SubscriptionPlan, return_url: str
    ) -> CheckoutSession: ...
    def cancel(self, *, provider_subscription_id: str) -> SubscriptionState: ...
    def sync_from_event(self, event: dict[str, Any]) -> SubscriptionState | None: ...


class NoopBillingService:
    """Everyone is on the free plan and nothing is charged."""

    provider = "noop"

    def ensure_customer(self, *, user_id: str, email: str) -> str | None:
        return None

    def create_checkout(
        self, *, user_id: str, email: str, plan: SubscriptionPlan, return_url: str
    ) -> CheckoutSession:
        # Nothing to pay: the caller records the plan change directly.
        logger.info(
            "billing.checkout_skipped",
            extra={"context": {"event": "billing.checkout_skipped", "plan": str(plan)}},
        )
        return CheckoutSession(url=None, provider_session_id=None, immediate=True)

    def cancel(self, *, provider_subscription_id: str) -> SubscriptionState:
        return SubscriptionState(
            plan=SubscriptionPlan.FREE, status=SubscriptionStatus.CANCELLED, provider=self.provider
        )

    def sync_from_event(self, event: dict[str, Any]) -> SubscriptionState | None:
        return None


class StripeBillingService:
    """Stripe implementation. Requires the ``stripe`` package and a secret key."""

    provider = "stripe"

    def __init__(self, secret_key: str, price_ids: dict[str, str] | None = None) -> None:
        if not secret_key:
            raise ValueError("STRIPE_SECRET_KEY is required for the Stripe provider")
        try:
            import stripe
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ProviderError(
                "The stripe package is not installed.", code="provider_unavailable"
            ) from exc
        stripe.api_key = secret_key
        self._stripe = stripe
        self._price_ids = price_ids or {}

    def ensure_customer(self, *, user_id: str, email: str) -> str | None:  # pragma: no cover
        customer = self._stripe.Customer.create(email=email, metadata={"user_id": user_id})
        return customer["id"]

    def create_checkout(  # pragma: no cover - exercised against Stripe, not in unit tests
        self, *, user_id: str, email: str, plan: SubscriptionPlan, return_url: str
    ) -> CheckoutSession:
        price_id = self._price_ids.get(str(plan))
        if not price_id:
            raise ProviderError(f"No Stripe price configured for the {plan} plan")
        session = self._stripe.checkout.Session.create(
            mode="subscription",
            customer_email=email,
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{return_url}?checkout=success",
            cancel_url=f"{return_url}?checkout=cancelled",
            metadata={"user_id": user_id, "plan": str(plan)},
        )
        return CheckoutSession(url=session["url"], provider_session_id=session["id"])

    def cancel(self, *, provider_subscription_id: str) -> SubscriptionState:  # pragma: no cover
        self._stripe.Subscription.modify(provider_subscription_id, cancel_at_period_end=True)
        return SubscriptionState(
            plan=SubscriptionPlan.FREE,
            status=SubscriptionStatus.ACTIVE,
            provider=self.provider,
            provider_subscription_id=provider_subscription_id,
            cancel_at_period_end=True,
        )

    def sync_from_event(
        self, event: dict[str, Any]
    ) -> SubscriptionState | None:  # pragma: no cover
        data = (event.get("data") or {}).get("object") or {}
        plan = data.get("metadata", {}).get("plan")
        if not plan:
            return None
        return SubscriptionState(
            plan=SubscriptionPlan(plan),
            status=SubscriptionStatus.ACTIVE
            if data.get("status") in {"active", "trialing"}
            else SubscriptionStatus.PAST_DUE,
            provider=self.provider,
            provider_customer_id=data.get("customer"),
            provider_subscription_id=data.get("id"),
            cancel_at_period_end=bool(data.get("cancel_at_period_end")),
        )


def build_billing_service(settings: object) -> BillingService:
    if getattr(settings, "billing_backend", "noop") == "stripe":
        return StripeBillingService(getattr(settings, "stripe_secret_key", "") or "")
    return NoopBillingService()
