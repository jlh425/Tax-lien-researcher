"""Sanity tests for the services layer.

Verifies that all services instantiate, import correctly, and core logic
works with mocked database sessions.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Import tests ─────────────────────────────────────────────────────────────


def test_barrel_imports():
    """All services are importable from the barrel."""
    from aloha.services import (
        AuthService,
        BaseService,
        BillingService,
        ExportService,
        NotificationService,
        OutreachService,
        ParcelService,
        ResearchService,
    )
    assert all([
        AuthService, BaseService, BillingService, ExportService,
        NotificationService, OutreachService, ParcelService, ResearchService,
    ])


def test_exception_imports():
    """New exception classes are importable and extend AlohaError."""
    from aloha.core.exceptions import (
        AlohaError,
        BillingError,
        OutreachBlockedError,
        QuotaExceededError,
    )
    assert issubclass(QuotaExceededError, AlohaError)
    assert issubclass(BillingError, AlohaError)
    assert issubclass(OutreachBlockedError, AlohaError)


# ── BaseService ──────────────────────────────────────────────────────────────


def test_base_service_init():
    """BaseService stores session and creates a bound logger."""
    from aloha.services.base import BaseService

    session = MagicMock()
    svc = BaseService(session)
    assert svc._session is session
    assert svc.log is not None


# ── AuthService ──────────────────────────────────────────────────────────────


def test_auth_hash_password_is_bcrypt():
    """hash_password produces a bcrypt hash (starts with $2b$)."""
    from aloha.services.auth_service import AuthService

    hashed = AuthService.hash_password("test-password-123")
    assert hashed.startswith("$2b$")


def test_auth_verify_password_roundtrip():
    """verify_password returns True for the correct password."""
    from aloha.services.auth_service import AuthService

    hashed = AuthService.hash_password("my-secret")
    assert AuthService.verify_password("my-secret", hashed) is True
    assert AuthService.verify_password("wrong-password", hashed) is False


def test_auth_create_and_decode_token():
    """JWT roundtrip: create_access_token -> decode_token."""
    from aloha.config import Settings
    from aloha.services.auth_service import AuthService

    settings = Settings(secret_key="test-secret-key-for-jwt")
    session = MagicMock()
    svc = AuthService(session, settings)

    token = svc.create_access_token("user-123", "pro")
    payload = svc.decode_token(token)
    assert payload["sub"] == "user-123"
    assert payload["tier"] == "pro"
    assert "exp" in payload


def test_auth_decode_invalid_token_raises():
    """decode_token raises HTTPException for garbage tokens."""
    from fastapi import HTTPException

    from aloha.config import Settings
    from aloha.services.auth_service import AuthService

    settings = Settings(secret_key="test-secret")
    svc = AuthService(MagicMock(), settings)

    with pytest.raises(HTTPException) as exc_info:
        svc.decode_token("not-a-valid-jwt")
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_auth_register_creates_user():
    """register() creates a user and returns a token response."""
    from aloha.config import Settings
    from aloha.services.auth_service import AuthService

    settings = Settings(secret_key="test-secret")
    session = AsyncMock()
    # session.add is synchronous — override with a plain MagicMock
    session.add = MagicMock()
    # Simulate no existing user found
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = None
    session.execute.return_value = mock_result

    svc = AuthService(session, settings)
    result = await svc.register("test@example.com", "password123", "Test User")

    assert result.access_token
    assert result.tier == "free"
    assert result.user_id  # should be a UUID string
    session.add.assert_called_once()
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_auth_register_duplicate_email_raises():
    """register() raises 409 if email already exists."""
    from fastapi import HTTPException

    from aloha.config import Settings
    from aloha.services.auth_service import AuthService

    settings = Settings(secret_key="test-secret")
    session = AsyncMock()
    # Simulate existing user found
    existing_user = MagicMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = existing_user
    session.execute.return_value = mock_result

    svc = AuthService(session, settings)
    with pytest.raises(HTTPException) as exc_info:
        await svc.register("taken@example.com", "password123", "Taken")
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_auth_login_success():
    """login() returns a token for valid credentials."""
    from aloha.config import Settings
    from aloha.services.auth_service import AuthService

    settings = Settings(secret_key="test-secret")
    session = AsyncMock()

    # Create a mock user with a real bcrypt hash
    hashed = AuthService.hash_password("correct-password")
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_user.email = "user@example.com"
    mock_user.hashed_password = hashed
    mock_user.tier = "pro"
    mock_user.is_active = True

    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = mock_user
    session.execute.return_value = mock_result

    svc = AuthService(session, settings)
    result = await svc.login("user@example.com", "correct-password")

    assert result.access_token
    assert result.tier == "pro"


@pytest.mark.asyncio
async def test_auth_login_wrong_password_raises():
    """login() raises 401 for wrong password."""
    from fastapi import HTTPException

    from aloha.config import Settings
    from aloha.services.auth_service import AuthService

    settings = Settings(secret_key="test-secret")
    session = AsyncMock()

    hashed = AuthService.hash_password("correct-password")
    mock_user = MagicMock()
    mock_user.hashed_password = hashed
    mock_user.is_active = True

    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = mock_user
    session.execute.return_value = mock_result

    svc = AuthService(session, settings)
    with pytest.raises(HTTPException) as exc_info:
        await svc.login("user@example.com", "wrong-password")
    assert exc_info.value.status_code == 401


# ── BillingService ───────────────────────────────────────────────────────────


def test_billing_tier_limits():
    """get_tier_limits returns correct limits per tier."""
    from aloha.services.billing_service import BillingService

    free = BillingService.get_tier_limits("free")
    assert free["scans_per_month"] == 10
    assert free["max_parcels"] == 50

    pro = BillingService.get_tier_limits("pro")
    assert pro["scans_per_month"] == 500

    enterprise = BillingService.get_tier_limits("enterprise")
    assert enterprise["scans_per_month"] is None  # unlimited

    # Unknown tier falls back to free
    unknown = BillingService.get_tier_limits("nonexistent")
    assert unknown["scans_per_month"] == 10


@pytest.mark.asyncio
async def test_billing_check_quota_under_limit():
    """check_quota returns remaining when under limit."""
    from aloha.services.billing_service import BillingService

    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 3  # 3 scans used
    session.execute.return_value = mock_result

    svc = BillingService(session)
    quota = await svc.check_quota("user-1", "free")

    assert quota["used"] == 3
    assert quota["limit"] == 10
    assert quota["remaining"] == 7


@pytest.mark.asyncio
async def test_billing_check_quota_exceeded():
    """check_quota raises QuotaExceededError when over limit."""
    from aloha.core.exceptions import QuotaExceededError
    from aloha.services.billing_service import BillingService

    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 10  # at limit
    session.execute.return_value = mock_result

    svc = BillingService(session)
    with pytest.raises(QuotaExceededError):
        await svc.check_quota("user-1", "free")


@pytest.mark.asyncio
async def test_billing_check_quota_unlimited():
    """check_quota skips counting for enterprise tier."""
    from aloha.services.billing_service import BillingService

    session = AsyncMock()
    svc = BillingService(session)
    quota = await svc.check_quota("user-1", "enterprise")

    assert quota["limit"] is None
    assert quota["remaining"] is None
    # Should not have queried the DB at all
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_billing_create_customer_with_stripe():
    """create_customer calls Stripe API and persists customer ID."""
    from aloha.services.billing_service import BillingService

    session = AsyncMock()
    mock_user = MagicMock()
    session.get.return_value = mock_user

    mock_customer = MagicMock()
    mock_customer.id = "cus_real_abc123"

    mock_client = MagicMock()
    mock_client.customers.create.return_value = mock_customer

    mock_settings = MagicMock()
    mock_settings.stripe_secret_key = "sk_test_xxx"

    with (
        patch("aloha.config.settings", mock_settings),
        patch("stripe.StripeClient", return_value=mock_client),
    ):
        svc = BillingService(session)
        result = await svc.create_customer("user-123", "test@example.com")

    assert result == "cus_real_abc123"
    assert mock_user.stripe_customer_id == "cus_real_abc123"
    session.flush.assert_awaited_once()
    mock_client.customers.create.assert_called_once()


@pytest.mark.asyncio
async def test_billing_create_customer_no_stripe_key():
    """create_customer returns stub ID when Stripe is not configured."""
    from aloha.services.billing_service import BillingService

    session = AsyncMock()
    mock_settings = MagicMock()
    mock_settings.stripe_secret_key = None

    with patch("aloha.config.settings", mock_settings):
        svc = BillingService(session)
        result = await svc.create_customer("user-123", "test@example.com")

    assert result.startswith("cus_stub_")


@pytest.mark.asyncio
async def test_billing_create_customer_stripe_error():
    """create_customer raises BillingError on Stripe failures."""
    import stripe as stripe_mod

    from aloha.core.exceptions import BillingError
    from aloha.services.billing_service import BillingService

    session = AsyncMock()
    mock_client = MagicMock()
    mock_client.customers.create.side_effect = stripe_mod.StripeError("API down")

    mock_settings = MagicMock()
    mock_settings.stripe_secret_key = "sk_test_xxx"

    with (
        patch("aloha.config.settings", mock_settings),
        patch("stripe.StripeClient", return_value=mock_client),
    ):
        svc = BillingService(session)
        with pytest.raises(BillingError, match="Failed to create"):
            await svc.create_customer("user-123", "test@example.com")


@pytest.mark.asyncio
async def test_billing_create_checkout_session():
    """create_checkout_session returns the Stripe session URL."""
    from aloha.services.billing_service import BillingService

    session = AsyncMock()
    mock_user = MagicMock()
    mock_user.stripe_customer_id = "cus_existing"
    session.get.return_value = mock_user

    mock_stripe_session = MagicMock()
    mock_stripe_session.id = "cs_test_123"
    mock_stripe_session.url = "https://checkout.stripe.com/pay/cs_test_123"

    mock_client = MagicMock()
    mock_client.checkout.sessions.create.return_value = mock_stripe_session

    mock_settings = MagicMock()
    mock_settings.stripe_secret_key = "sk_test_xxx"

    with (
        patch("aloha.config.settings", mock_settings),
        patch("stripe.StripeClient", return_value=mock_client),
    ):
        svc = BillingService(session)
        url = await svc.create_checkout_session(
            "user-123", "price_pro_monthly",
            "https://app.aloha.com/success", "https://app.aloha.com/cancel",
        )

    assert url == "https://checkout.stripe.com/pay/cs_test_123"
    call_params = mock_client.checkout.sessions.create.call_args.kwargs["params"]
    assert call_params["customer"] == "cus_existing"
    assert call_params["mode"] == "subscription"


@pytest.mark.asyncio
async def test_billing_create_checkout_no_stripe_key():
    """create_checkout_session returns stub URL when not configured."""
    from aloha.services.billing_service import BillingService

    session = AsyncMock()
    mock_settings = MagicMock()
    mock_settings.stripe_secret_key = None

    with patch("aloha.config.settings", mock_settings):
        svc = BillingService(session)
        url = await svc.create_checkout_session(
            "user-123", "price_x", "http://ok", "http://cancel",
        )

    assert "stub.stripe.com" in url


@pytest.mark.asyncio
async def test_billing_webhook_checkout_completed():
    """handle_webhook upgrades user tier on checkout.session.completed."""
    from aloha.services.billing_service import BillingService

    session = AsyncMock()
    mock_user = MagicMock()
    mock_user.tier = "free"
    session.get.return_value = mock_user

    mock_event = MagicMock()
    mock_event.type = "checkout.session.completed"
    mock_event.data.object.metadata = {"aloha_user_id": "user-123"}
    mock_event.data.object.customer = "cus_new"

    mock_settings = MagicMock()
    mock_settings.stripe_secret_key = "sk_test_xxx"
    mock_settings.stripe_webhook_secret = "whsec_test"

    with (
        patch("aloha.config.settings", mock_settings),
        patch("stripe.Webhook.construct_event", return_value=mock_event),
    ):
        svc = BillingService(session)
        await svc.handle_webhook(b"raw-payload", "sig-header")

    assert mock_user.tier == "pro"
    assert mock_user.stripe_customer_id == "cus_new"


@pytest.mark.asyncio
async def test_billing_webhook_subscription_deleted():
    """handle_webhook downgrades user on customer.subscription.deleted."""
    from aloha.services.billing_service import BillingService

    session = AsyncMock()
    mock_user = MagicMock()
    mock_user.tier = "pro"
    mock_user.id = uuid.uuid4()
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = mock_user
    session.execute.return_value = mock_result

    mock_event = MagicMock()
    mock_event.type = "customer.subscription.deleted"
    mock_event.data.object.customer = "cus_existing"

    mock_settings = MagicMock()
    mock_settings.stripe_secret_key = "sk_test_xxx"
    mock_settings.stripe_webhook_secret = "whsec_test"

    with (
        patch("aloha.config.settings", mock_settings),
        patch("stripe.Webhook.construct_event", return_value=mock_event),
    ):
        svc = BillingService(session)
        await svc.handle_webhook(b"raw-payload", "sig-header")

    assert mock_user.tier == "free"


@pytest.mark.asyncio
async def test_billing_webhook_invalid_signature():
    """handle_webhook raises BillingError on invalid signature."""
    import stripe as stripe_mod

    from aloha.core.exceptions import BillingError
    from aloha.services.billing_service import BillingService

    session = AsyncMock()
    mock_settings = MagicMock()
    mock_settings.stripe_secret_key = "sk_test_xxx"
    mock_settings.stripe_webhook_secret = "whsec_test"

    with (
        patch("aloha.config.settings", mock_settings),
        patch(
            "stripe.Webhook.construct_event",
            side_effect=stripe_mod.SignatureVerificationError("bad sig", "header"),
        ),
    ):
        svc = BillingService(session)
        with pytest.raises(BillingError, match="Invalid webhook"):
            await svc.handle_webhook(b"bad-payload", "bad-sig")


@pytest.mark.asyncio
async def test_billing_webhook_no_stripe_config():
    """handle_webhook is a no-op when Stripe is not configured."""
    from aloha.services.billing_service import BillingService

    session = AsyncMock()
    mock_settings = MagicMock()
    mock_settings.stripe_secret_key = None
    mock_settings.stripe_webhook_secret = None

    with patch("aloha.config.settings", mock_settings):
        svc = BillingService(session)
        # Should not raise
        await svc.handle_webhook(b"anything", "any-sig")


# ── ResearchService ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_research_trigger_scan_checks_quota():
    """trigger_scan calls billing check_quota before proceeding."""
    from aloha.services.billing_service import BillingService
    from aloha.services.research_service import ResearchService

    session = AsyncMock()
    billing = AsyncMock(spec=BillingService)
    billing.check_quota = AsyncMock(return_value={"used": 1, "limit": 10, "remaining": 9})

    svc = ResearchService(session, billing)
    result = await svc.trigger_scan(
        user_id="user-1", tier="free",
        state="FL", county="miami-dade",
    )

    billing.check_quota.assert_awaited_once_with("user-1", "free")
    assert result.status == "queued"
    assert result.state == "FL"
    assert result.county == "miami-dade"


@pytest.mark.asyncio
async def test_research_trigger_scan_blocked_by_quota():
    """trigger_scan propagates QuotaExceededError from billing."""
    from aloha.core.exceptions import QuotaExceededError
    from aloha.services.billing_service import BillingService
    from aloha.services.research_service import ResearchService

    session = AsyncMock()
    billing = AsyncMock(spec=BillingService)
    billing.check_quota = AsyncMock(side_effect=QuotaExceededError("over limit"))

    svc = ResearchService(session, billing)
    with pytest.raises(QuotaExceededError):
        await svc.trigger_scan(
            user_id="user-1", tier="free",
            state="FL", county="miami-dade",
        )


@pytest.mark.asyncio
async def test_research_get_queue_status():
    """get_queue_status assembles counts from DB."""
    from aloha.services.billing_service import BillingService
    from aloha.services.research_service import ResearchService

    session = AsyncMock()

    # First call: status counts
    status_rows = [
        MagicMock(status="pending", cnt=5),
        MagicMock(status="processing", cnt=2),
        MagicMock(status="complete", cnt=10),
    ]
    # Second call: agent breakdown
    agent_rows = [
        MagicMock(agent_name="discover", cnt=3),
        MagicMock(agent_name="parcel", cnt=2),
    ]
    session.execute.side_effect = [
        MagicMock(__iter__=lambda s: iter(status_rows)),
        MagicMock(__iter__=lambda s: iter(agent_rows)),
    ]

    billing = AsyncMock(spec=BillingService)
    svc = ResearchService(session, billing)
    result = await svc.get_queue_status()

    assert result.pending == 5
    assert result.processing == 2
    assert result.complete == 10
    assert result.failed == 0
    assert result.agents == {"discover": 3, "parcel": 2}


# ── ParcelService ────────────────────────────────────────────────────────────


def test_parcel_extract_condition_summary_json():
    """_extract_condition_summary parses JSON summary field."""
    from aloha.services.parcel_service import ParcelService

    import json
    content = json.dumps({"summary": "Property in good condition", "details": "..."})
    assert ParcelService._extract_condition_summary(content) == "Property in good condition"


def test_parcel_extract_condition_summary_fallback():
    """_extract_condition_summary falls back to truncated content."""
    from aloha.services.parcel_service import ParcelService

    content = "not valid json" * 20
    result = ParcelService._extract_condition_summary(content)
    assert len(result) <= 200


def test_parcel_to_lien_out():
    """_to_lien_out converts a TaxLien mock to TaxLienOut schema."""
    from aloha.services.parcel_service import ParcelService

    lien = MagicMock()
    lien.id = 1
    lien.instrument_type = "lien_certificate"
    lien.lien_status = "active"
    lien.tax_year = 2024
    lien.years_delinquent = 2
    lien.principal_amount = 5000.0
    lien.interest_amount = 500.0
    lien.penalty_amount = 100.0
    lien.total_owed = 5600.0
    lien.filing_date = date(2024, 1, 15)
    lien.redemption_deadline = date(2025, 1, 15)
    lien.certificate_number = "CERT-001"
    lien.certificate_interest_rate = 0.18
    lien.auction_date = None
    lien.auction_platform = None
    lien.auction_url = None
    lien.opening_bid = None
    lien.post_sale_redemption_days = None
    lien.title_risk_level = None
    lien.source_url = "https://example.com"
    lien.retrieved_at = datetime(2024, 6, 1, tzinfo=timezone.utc)

    result = ParcelService._to_lien_out(lien)
    assert result.id == 1
    assert result.instrument_type == "lien_certificate"
    assert result.principal_amount == 5000.0
    assert result.certificate_interest_rate == 0.18


def test_parcel_to_owner_out():
    """_to_owner_out converts an Owner mock to OwnerOut schema."""
    from aloha.services.parcel_service import ParcelService

    owner = MagicMock()
    owner.id = 42
    owner.owner_of_record = "John Doe"
    owner.owner_type = "individual"
    owner.mailing_address = "123 Main St"
    owner.mailing_city = "Springfield"
    owner.mailing_state = "IL"
    owner.mailing_zip = "62701"
    owner.is_absentee = True
    owner.deed_type = "warranty"
    owner.beneficial_owner = None
    owner.beneficial_owner_confidence = None
    owner.best_phone = "555-1234"
    owner.best_email = "john@example.com"
    owner.research_depth = 3

    result = ParcelService._to_owner_out(owner)
    assert result.id == 42
    assert result.owner_of_record == "John Doe"
    assert result.is_absentee is True
    assert result.research_depth == 3


def test_parcel_to_score_out():
    """_to_score_out converts a Score mock to ScoreOut schema."""
    from aloha.services.parcel_service import ParcelService

    score = MagicMock()
    score.id = 7
    score.instrument_type = "tax_deed"
    score.overall_score = 85
    score.score_model_version = "deed_v1"
    score.property_potential = 8
    score.risk_score = 3
    score.lien_to_value_ratio = None
    score.certificate_rate = None
    score.redemption_urgency = None
    score.owner_motivation = None
    score.contact_reachability = None
    score.arv_estimate = 150000.0
    score.opening_bid = 25000.0
    score.arv_to_bid_ratio = 6.0
    score.title_clarity = 9
    score.condition_risk = 2
    score.competition_risk = 4
    score.post_sale_redemption_risk = 1
    score.risk_flags = ["minor_encumbrance"]
    score.score_rationale = "Strong ARV to bid ratio"
    score.scored_at = datetime(2024, 6, 15, tzinfo=timezone.utc)

    result = ParcelService._to_score_out(score)
    assert result.overall_score == 85
    assert result.arv_to_bid_ratio == 6.0
    assert result.risk_flags == ["minor_encumbrance"]


# ── ExportService ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_export_csv():
    """export_parcels_csv returns valid CSV bytes."""
    from aloha.services.export_service import ExportService

    session = AsyncMock()

    # Mock parcels returned from DB
    parcel1 = MagicMock()
    parcel1.parcel_id = "P001"
    parcel1.state = "FL"
    parcel1.county = "miami-dade"
    parcel1.address = "123 Palm Ave"
    parcel1.property_type = "residential"
    parcel1.acreage = 0.25
    parcel1.assessed_total = 150000
    parcel1.research_status = "scored"

    parcel2 = MagicMock()
    parcel2.parcel_id = "P002"
    parcel2.state = "FL"
    parcel2.county = "broward"
    parcel2.address = "456 Ocean Dr"
    parcel2.property_type = "commercial"
    parcel2.acreage = 1.5
    parcel2.assessed_total = 500000
    parcel2.research_status = "complete"

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [parcel1, parcel2]
    session.execute.return_value = mock_result

    svc = ExportService(session)
    csv_bytes = await svc.export_parcels_csv(["P001", "P002"])

    csv_text = csv_bytes.decode("utf-8")
    lines = csv_text.strip().split("\n")
    assert len(lines) == 3  # header + 2 rows
    assert "parcel_id" in lines[0]
    assert "P001" in lines[1]
    assert "P002" in lines[2]


# ── OutreachService ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_outreach_check_dnc_found():
    """check_dnc returns True when contact is on DNC list."""
    from aloha.services.outreach_service import OutreachService

    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 1
    session.execute.return_value = mock_result

    svc = OutreachService(session)
    assert await svc.check_dnc("blocked@example.com", "email") is True


@pytest.mark.asyncio
async def test_outreach_check_dnc_not_found():
    """check_dnc returns False when contact is not on DNC list."""
    from aloha.services.outreach_service import OutreachService

    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 0
    session.execute.return_value = mock_result

    svc = OutreachService(session)
    assert await svc.check_dnc("ok@example.com", "email") is False


@pytest.mark.asyncio
async def test_outreach_schedule_blocked_by_dnc():
    """schedule_outreach raises OutreachBlockedError when DNC blocks it."""
    from aloha.core.exceptions import OutreachBlockedError
    from aloha.services.outreach_service import OutreachService

    session = AsyncMock()

    # DNC check returns found
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 1
    session.execute.return_value = mock_result

    svc = OutreachService(session)
    with pytest.raises(OutreachBlockedError, match="do-not-contact"):
        await svc.schedule_outreach(
            user_id="user-1",
            parcel_id="P001",
            owner_id=1,
            channel="email",
            contact_value="blocked@example.com",
        )


def test_outreach_render_template():
    """render_template renders Jinja2 variables."""
    from aloha.services.outreach_service import OutreachService

    result = OutreachService.render_template(
        "Hello {{ name }}, your parcel {{ parcel_id }} scored {{ score }}.",
        {"name": "John", "parcel_id": "P001", "score": 85},
    )
    assert result == "Hello John, your parcel P001 scored 85."


# ── NotificationService ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_notification_create_alert():
    """create_alert adds an alert and returns its ID."""
    from aloha.services.notification_service import NotificationService

    session = AsyncMock()
    # session.add is synchronous — override with a plain MagicMock
    added_objects = []
    session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

    # Patch the alert id after flush (simulating DB autoincrement)
    async def fake_flush():
        if added_objects:
            added_objects[-1].id = 99

    session.flush.side_effect = fake_flush

    svc = NotificationService(session)

    alert_id = await svc.create_alert(
        parcel_id="P001",
        alert_type="redemption_deadline",
        message="Deadline in 15 days",
        alert_date=date(2025, 1, 15),
    )
    assert alert_id == 99
    session.add.assert_called_once()
    session.flush.assert_awaited_once()


# ── Deps service factories ──────────────────────────────────────────────────


def test_deps_service_factories_importable():
    """All service factory functions are importable from deps."""
    from aloha.api.deps import (
        get_auth_service,
        get_billing_service,
        get_export_service,
        get_notification_service,
        get_outreach_service,
        get_parcel_service,
        get_research_service,
    )
    assert all([
        get_auth_service, get_billing_service, get_export_service,
        get_notification_service, get_outreach_service,
        get_parcel_service, get_research_service,
    ])


# ── OutreachService — SendGrid/Twilio dispatch ──────────────────────────────


@pytest.mark.asyncio
async def test_outreach_send_email_via_sendgrid():
    """send_outreach dispatches email via SendGrid API."""
    from aloha.services.outreach_service import OutreachService

    session = AsyncMock()
    entry = MagicMock()
    entry.channel = "email"
    entry.status = "approved"
    entry.contact_value = "owner@example.com"
    entry.subject = "Tax Lien Notice"
    entry.message_body = "Hello, we have a lien opportunity."
    session.get.return_value = entry

    mock_settings = MagicMock()
    mock_settings.sendgrid_api_key = "SG.test-key"
    mock_settings.sendgrid_from_email = "noreply@aloha.com"

    mock_response = MagicMock()
    mock_response.headers = {"X-Message-Id": "msg-abc123"}
    mock_response.raise_for_status = MagicMock()

    with (
        patch("aloha.services.outreach_service.settings", mock_settings, create=True),
        patch("aloha.config.settings", mock_settings),
        patch("httpx.AsyncClient") as MockClient,
    ):
        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_client_instance

        svc = OutreachService(session)
        await svc.send_outreach(42)

    assert entry.status == "sent"
    assert entry.provider == "sendgrid"
    assert entry.provider_msg_id == "msg-abc123"
    mock_client_instance.post.assert_awaited_once()
    call_kwargs = mock_client_instance.post.call_args
    assert "sendgrid" in call_kwargs[0][0] or "sendgrid" in str(call_kwargs)


@pytest.mark.asyncio
async def test_outreach_send_sms_via_twilio():
    """send_outreach dispatches SMS via Twilio API."""
    from aloha.services.outreach_service import OutreachService

    session = AsyncMock()
    entry = MagicMock()
    entry.channel = "sms"
    entry.status = "approved"
    entry.contact_value = "+15551234567"
    entry.subject = None
    entry.message_body = "Your lien opportunity is ready."
    session.get.return_value = entry

    mock_settings = MagicMock()
    mock_settings.twilio_account_sid = "ACtest123"
    mock_settings.twilio_auth_token = "auth-token-xyz"
    mock_settings.twilio_phone_number = "+15559876543"

    mock_response = MagicMock()
    mock_response.json.return_value = {"sid": "SM_test_sid"}
    mock_response.raise_for_status = MagicMock()

    with (
        patch("aloha.config.settings", mock_settings),
        patch("httpx.AsyncClient") as MockClient,
    ):
        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_client_instance

        svc = OutreachService(session)
        await svc.send_outreach(43)

    assert entry.status == "sent"
    assert entry.provider == "twilio"
    assert entry.provider_msg_id == "SM_test_sid"


@pytest.mark.asyncio
async def test_outreach_send_email_no_api_key_falls_back_to_stub():
    """send_outreach falls back to stub when SendGrid key is missing."""
    from aloha.services.outreach_service import OutreachService

    session = AsyncMock()
    entry = MagicMock()
    entry.channel = "email"
    entry.status = "approved"
    entry.contact_value = "owner@example.com"
    entry.subject = "Test"
    entry.message_body = "Body"
    session.get.return_value = entry

    mock_settings = MagicMock()
    mock_settings.sendgrid_api_key = None
    mock_settings.sendgrid_from_email = "noreply@aloha.com"

    with patch("aloha.config.settings", mock_settings):
        svc = OutreachService(session)
        await svc.send_outreach(44)

    assert entry.status == "sent"
    assert entry.provider == "sendgrid"
    assert entry.provider_msg_id == "stub_no_sendgrid_key"


@pytest.mark.asyncio
async def test_outreach_send_sms_no_twilio_creds_falls_back():
    """send_outreach falls back to stub when Twilio creds are missing."""
    from aloha.services.outreach_service import OutreachService

    session = AsyncMock()
    entry = MagicMock()
    entry.channel = "sms"
    entry.status = "approved"
    entry.contact_value = "+15551234567"
    entry.message_body = "Body"
    session.get.return_value = entry

    mock_settings = MagicMock()
    mock_settings.twilio_account_sid = None
    mock_settings.twilio_auth_token = None
    mock_settings.twilio_phone_number = None

    with patch("aloha.config.settings", mock_settings):
        svc = OutreachService(session)
        await svc.send_outreach(45)

    assert entry.status == "sent"
    assert entry.provider == "twilio"
    assert entry.provider_msg_id == "stub_no_twilio_creds"


@pytest.mark.asyncio
async def test_outreach_send_unsupported_channel():
    """send_outreach uses stub for unsupported channels."""
    from aloha.services.outreach_service import OutreachService

    session = AsyncMock()
    entry = MagicMock()
    entry.channel = "carrier_pigeon"
    entry.status = "approved"
    entry.contact_value = "loft-42"
    entry.message_body = "Urgent"
    session.get.return_value = entry

    mock_settings = MagicMock()
    with patch("aloha.config.settings", mock_settings):
        svc = OutreachService(session)
        await svc.send_outreach(46)

    assert entry.provider == "stub"
    assert "stub_46" in entry.provider_msg_id


@pytest.mark.asyncio
async def test_outreach_send_not_approved_raises():
    """send_outreach raises ValueError if entry is not approved."""
    from aloha.services.outreach_service import OutreachService

    session = AsyncMock()
    entry = MagicMock()
    entry.status = "pending"
    session.get.return_value = entry

    svc = OutreachService(session)
    with pytest.raises(ValueError, match="not approved"):
        await svc.send_outreach(47)


@pytest.mark.asyncio
async def test_outreach_send_not_found_raises():
    """send_outreach raises ValueError if entry doesn't exist."""
    from aloha.services.outreach_service import OutreachService

    session = AsyncMock()
    session.get.return_value = None

    svc = OutreachService(session)
    with pytest.raises(ValueError, match="not found"):
        await svc.send_outreach(99)


# ── NotificationService — SendGrid email ────────────────────────────────────


@pytest.mark.asyncio
async def test_notification_send_scan_complete_via_sendgrid():
    """send_scan_complete sends email via SendGrid when configured."""
    from aloha.services.notification_service import NotificationService

    session = AsyncMock()
    mock_settings = MagicMock()
    mock_settings.sendgrid_api_key = "SG.test-key"
    mock_settings.sendgrid_from_email = "noreply@aloha.com"

    mock_response = MagicMock()
    mock_response.headers = {"X-Message-Id": "msg-scan-123"}
    mock_response.raise_for_status = MagicMock()

    with (
        patch("aloha.config.settings", mock_settings),
        patch("httpx.AsyncClient") as MockClient,
    ):
        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_client_instance

        svc = NotificationService(session)
        await svc.send_scan_complete("user@example.com", "FL", "orange", 42)

    mock_client_instance.post.assert_awaited_once()
    call_args = mock_client_instance.post.call_args
    payload = call_args.kwargs.get("json") or call_args[1].get("json")
    assert "Orange County" in payload["subject"]
    assert "42" in payload["content"][0]["value"]


@pytest.mark.asyncio
async def test_notification_send_scan_complete_no_api_key():
    """send_scan_complete falls back to log-only when no API key."""
    from aloha.services.notification_service import NotificationService

    session = AsyncMock()
    mock_settings = MagicMock()
    mock_settings.sendgrid_api_key = None

    with (
        patch("aloha.config.settings", mock_settings),
        patch("httpx.AsyncClient") as MockClient,
    ):
        svc = NotificationService(session)
        await svc.send_scan_complete("user@example.com", "FL", "orange", 10)

    # Should not have attempted to create an HTTP client
    MockClient.assert_not_called()


@pytest.mark.asyncio
async def test_notification_send_scan_complete_handles_http_error():
    """send_scan_complete catches HTTP errors gracefully."""
    from aloha.services.notification_service import NotificationService

    session = AsyncMock()
    mock_settings = MagicMock()
    mock_settings.sendgrid_api_key = "SG.test-key"
    mock_settings.sendgrid_from_email = "noreply@aloha.com"

    with (
        patch("aloha.config.settings", mock_settings),
        patch("httpx.AsyncClient") as MockClient,
    ):
        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_client_instance

        svc = NotificationService(session)
        # Should not raise — error is caught internally
        await svc.send_scan_complete("user@example.com", "FL", "orange", 5)
