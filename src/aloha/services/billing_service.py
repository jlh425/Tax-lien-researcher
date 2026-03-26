"""Billing service — tier limits, quota enforcement, Stripe integration."""

from __future__ import annotations

from datetime import datetime, timezone

import stripe
import structlog
from sqlalchemy import func, select

from aloha.core.exceptions import BillingError, QuotaExceededError
from aloha.db.models.queue_item import QueueItem
from aloha.db.models.user import User
from aloha.services.base import BaseService

log = structlog.get_logger().bind(component="billing")

_TIER_LIMITS: dict[str, dict[str, int | None]] = {
    "free": {"scans_per_month": 10, "max_parcels": 50},
    "pro": {"scans_per_month": 500, "max_parcels": 5000},
    "enterprise": {"scans_per_month": None, "max_parcels": None},  # unlimited
}


class BillingService(BaseService):
    """Tier-based quota enforcement and Stripe integration stubs."""

    # ── Tier limits ──────────────────────────────────────────────────────

    @staticmethod
    def get_tier_limits(tier: str) -> dict[str, int | None]:
        """Return the quota limits for the given subscription tier."""
        return _TIER_LIMITS.get(tier, _TIER_LIMITS["free"])

    # ── Quota checking ───────────────────────────────────────────────────

    async def check_quota(self, user_id: str, tier: str) -> dict:
        """Count scans this month vs tier limit. Raises QuotaExceededError if over.

        Returns a dict with ``used``, ``limit``, and ``remaining`` keys.
        """
        limits = self.get_tier_limits(tier)
        scans_limit = limits["scans_per_month"]

        # Unlimited tier — skip counting
        if scans_limit is None:
            return {"used": 0, "limit": None, "remaining": None}

        now = datetime.now(tz=timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        result = await self._session.execute(
            select(func.count())
            .select_from(QueueItem)
            .where(
                QueueItem.agent_name == "discover",
                QueueItem.created_at >= month_start,
            ),
        )
        used = result.scalar_one()

        remaining = max(0, scans_limit - used)
        if used >= scans_limit:
            self.log.warning(
                "quota_exceeded",
                user_id=user_id,
                tier=tier,
                used=used,
                limit=scans_limit,
            )
            raise QuotaExceededError(
                f"Monthly scan quota exceeded ({used}/{scans_limit}). "
                "Upgrade your plan for more scans.",
            )

        return {"used": used, "limit": scans_limit, "remaining": remaining}

    # ── Stripe integration ───────────────────────────────────────────────

    @staticmethod
    def _get_stripe_client() -> stripe.StripeClient | None:
        """Build a Stripe client from settings. Returns None if not configured."""
        from aloha.config import settings

        if not settings.stripe_secret_key:
            log.warning("stripe_not_configured")
            return None
        return stripe.StripeClient(api_key=settings.stripe_secret_key)

    async def create_customer(self, user_id: str, email: str) -> str:
        """Create a Stripe customer and persist the ID on the user record.

        Falls back to a stub customer ID if Stripe is not configured.
        """
        client = self._get_stripe_client()
        if client is None:
            stub_id = f"cus_stub_{user_id[:8]}"
            self.log.info("stripe_create_customer_stub", user_id=user_id)
            return stub_id

        try:
            customer = client.customers.create(
                params={"email": email, "metadata": {"aloha_user_id": user_id}},
            )
            customer_id = customer.id

            # Persist on user record
            user = await self._session.get(User, user_id)
            if user:
                user.stripe_customer_id = customer_id
                await self._session.flush()

            self.log.info(
                "stripe_customer_created",
                user_id=user_id,
                customer_id=customer_id,
            )
            return customer_id
        except stripe.StripeError as exc:
            self.log.error("stripe_create_customer_failed", error=str(exc))
            raise BillingError(f"Failed to create Stripe customer: {exc}") from exc

    async def create_checkout_session(
        self,
        user_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
    ) -> str:
        """Create a Stripe Checkout session and return the session URL.

        Falls back to a stub URL if Stripe is not configured.
        """
        client = self._get_stripe_client()
        if client is None:
            self.log.info("stripe_checkout_stub", user_id=user_id)
            return f"https://stub.stripe.com/checkout/{user_id}"

        try:
            # Look up existing Stripe customer ID
            user = await self._session.get(User, user_id)
            customer_id = user.stripe_customer_id if user else None

            params: dict = {
                "mode": "subscription",
                "line_items": [{"price": price_id, "quantity": 1}],
                "success_url": success_url,
                "cancel_url": cancel_url,
                "metadata": {"aloha_user_id": user_id},
            }
            if customer_id:
                params["customer"] = customer_id

            session = client.checkout.sessions.create(params=params)
            self.log.info(
                "stripe_checkout_created",
                user_id=user_id,
                session_id=session.id,
            )
            return session.url or ""
        except stripe.StripeError as exc:
            self.log.error("stripe_checkout_failed", error=str(exc))
            raise BillingError(f"Failed to create checkout session: {exc}") from exc

    async def handle_webhook(self, payload: bytes, sig_header: str) -> None:
        """Verify and process a Stripe webhook event.

        Handles ``checkout.session.completed`` (upgrade tier) and
        ``customer.subscription.deleted`` (downgrade to free).
        Falls back to a no-op if Stripe is not configured.
        """
        from aloha.config import settings

        if not settings.stripe_secret_key or not settings.stripe_webhook_secret:
            self.log.info("stripe_webhook_stub")
            return

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.stripe_webhook_secret,
            )
        except (ValueError, stripe.SignatureVerificationError) as exc:
            self.log.warning("stripe_webhook_invalid", error=str(exc))
            raise BillingError(f"Invalid webhook: {exc}") from exc

        event_type = event.type
        self.log.info("stripe_webhook_received", event_type=event_type)

        if event_type == "checkout.session.completed":
            await self._handle_checkout_completed(event.data.object)
        elif event_type == "customer.subscription.deleted":
            await self._handle_subscription_deleted(event.data.object)

    async def _handle_checkout_completed(self, session: object) -> None:
        """Upgrade user tier after successful checkout."""
        user_id = getattr(session, "metadata", {}).get("aloha_user_id")
        if not user_id:
            self.log.warning("checkout_no_user_id")
            return

        user = await self._session.get(User, user_id)
        if user:
            user.tier = "pro"
            customer_id = getattr(session, "customer", None)
            if customer_id:
                user.stripe_customer_id = customer_id
            await self._session.flush()
            self.log.info("user_upgraded", user_id=user_id, tier="pro")

    async def _handle_subscription_deleted(self, subscription: object) -> None:
        """Downgrade user to free tier when subscription is canceled."""
        customer_id = getattr(subscription, "customer", None)
        if not customer_id:
            return

        result = await self._session.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        )
        user = result.scalars().first()
        if user:
            user.tier = "free"
            await self._session.flush()
            self.log.info("user_downgraded", user_id=str(user.id), tier="free")
