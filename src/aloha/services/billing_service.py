"""Billing service — tier limits, quota enforcement, Stripe stubs."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select

from aloha.core.exceptions import QuotaExceededError
from aloha.db.models.queue_item import QueueItem
from aloha.services.base import BaseService

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

    # ── Stripe stubs ─────────────────────────────────────────────────────

    async def create_customer(self, user_id: str, email: str) -> str:
        """Create a Stripe customer for the user (stub).

        Returns a placeholder customer ID until Stripe integration is wired up.
        """
        self.log.info("stripe_create_customer_stub", user_id=user_id, email=email)
        return f"cus_stub_{user_id[:8]}"

    async def handle_webhook(self, event: dict) -> None:
        """Process a Stripe webhook event (stub).

        Will handle subscription changes, payment failures, etc.
        """
        self.log.info("stripe_webhook_stub", event_type=event.get("type"))
