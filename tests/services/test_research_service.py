"""Comprehensive tests for the ResearchService.

Covers get_parcel_research_status, enqueue_next_stage (all stages, unknown
stage, last stage, optional user_id), and trigger_scan edge cases.

Existing tests in test_services.py cover:
  - trigger_scan (quota check, quota exceeded)
  - get_queue_status (status counts + agent breakdown)
This file covers the remaining uncovered methods.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from aloha.services.billing_service import BillingService
from aloha.services.research_service import ResearchService


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_service(
    session: AsyncMock | None = None,
) -> tuple[ResearchService, AsyncMock, AsyncMock]:
    """Instantiate ResearchService with mocked session and billing."""
    session = session or AsyncMock()
    session.add = MagicMock()
    billing = AsyncMock(spec=BillingService)
    billing.check_quota = AsyncMock(
        return_value={"used": 0, "limit": 100, "remaining": 100}
    )
    svc = ResearchService(session, billing)
    return svc, session, billing


# ═══════════════════════════════════════════════════════════════════════════════
# get_parcel_research_status
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetParcelResearchStatus:
    """Tests for get_parcel_research_status."""

    @pytest.mark.asyncio
    async def test_parcel_not_found(self) -> None:
        """Returns not_found status when parcel doesn't exist."""
        svc, session, _ = _make_service()
        session.get = AsyncMock(return_value=None)

        result = await svc.get_parcel_research_status("NONEXISTENT")

        assert result["parcel_id"] == "NONEXISTENT"
        assert result["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_parcel_with_active_queue_items(self) -> None:
        """Returns research status and active queue items."""
        svc, session, _ = _make_service()

        mock_parcel = MagicMock()
        mock_parcel.research_status = "enriching"
        session.get = AsyncMock(return_value=mock_parcel)

        # Active queue items
        queue_rows = [
            MagicMock(agent_name="enrich", status="processing"),
            MagicMock(agent_name="score", status="pending"),
        ]
        mock_result = MagicMock()
        mock_result.__iter__ = lambda self: iter(queue_rows)
        session.execute.return_value = mock_result

        result = await svc.get_parcel_research_status("P001")

        assert result["parcel_id"] == "P001"
        assert result["research_status"] == "enriching"
        assert len(result["active_queue_items"]) == 2
        assert result["active_queue_items"][0]["agent"] == "enrich"
        assert result["active_queue_items"][0]["status"] == "processing"
        assert result["active_queue_items"][1]["agent"] == "score"

    @pytest.mark.asyncio
    async def test_parcel_with_no_active_items(self) -> None:
        """Returns empty active_queue_items when nothing is pending."""
        svc, session, _ = _make_service()

        mock_parcel = MagicMock()
        mock_parcel.research_status = "complete"
        session.get = AsyncMock(return_value=mock_parcel)

        mock_result = MagicMock()
        mock_result.__iter__ = lambda self: iter([])
        session.execute.return_value = mock_result

        result = await svc.get_parcel_research_status("P002")

        assert result["research_status"] == "complete"
        assert result["active_queue_items"] == []


# ═══════════════════════════════════════════════════════════════════════════════
# enqueue_next_stage
# ═══════════════════════════════════════════════════════════════════════════════


class TestEnqueueNextStage:
    """Tests for enqueue_next_stage."""

    @pytest.mark.asyncio
    async def test_discover_enqueues_parcel(self) -> None:
        """After 'discover' stage, enqueues 'parcel'."""
        svc, session, _ = _make_service()

        added_objects: list = []
        session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        await svc.enqueue_next_stage("P001", "discover")

        assert len(added_objects) == 1
        item = added_objects[0]
        assert item.agent_name == "parcel"
        assert item.stage == "parcel"
        assert item.parcel_id == "P001"
        assert item.status == "pending"
        assert item.priority == 5
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_parcel_enqueues_owner(self) -> None:
        """After 'parcel' stage, enqueues 'owner'."""
        svc, session, _ = _make_service()

        added_objects: list = []
        session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        await svc.enqueue_next_stage("P001", "parcel")

        assert added_objects[0].agent_name == "owner"

    @pytest.mark.asyncio
    async def test_owner_enqueues_entity(self) -> None:
        """After 'owner' stage, enqueues 'entity'."""
        svc, session, _ = _make_service()

        added_objects: list = []
        session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        await svc.enqueue_next_stage("P001", "owner")

        assert added_objects[0].agent_name == "entity"

    @pytest.mark.asyncio
    async def test_entity_enqueues_contact(self) -> None:
        """After 'entity' stage, enqueues 'contact'."""
        svc, session, _ = _make_service()

        added_objects: list = []
        session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        await svc.enqueue_next_stage("P001", "entity")

        assert added_objects[0].agent_name == "contact"

    @pytest.mark.asyncio
    async def test_contact_enqueues_enrich(self) -> None:
        """After 'contact' stage, enqueues 'enrich'."""
        svc, session, _ = _make_service()

        added_objects: list = []
        session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        await svc.enqueue_next_stage("P001", "contact")

        assert added_objects[0].agent_name == "enrich"

    @pytest.mark.asyncio
    async def test_enrich_enqueues_score(self) -> None:
        """After 'enrich' stage, enqueues 'score'."""
        svc, session, _ = _make_service()

        added_objects: list = []
        session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        await svc.enqueue_next_stage("P001", "enrich")

        assert added_objects[0].agent_name == "score"

    @pytest.mark.asyncio
    async def test_score_is_last_stage(self) -> None:
        """After 'score' stage (last), no new item is enqueued."""
        svc, session, _ = _make_service()

        await svc.enqueue_next_stage("P001", "score")

        session.add.assert_not_called()
        session.flush.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_unknown_stage_is_noop(self) -> None:
        """Unknown stage name does not enqueue anything."""
        svc, session, _ = _make_service()

        await svc.enqueue_next_stage("P001", "nonexistent_stage")

        session.add.assert_not_called()
        session.flush.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_enqueue_with_user_id(self) -> None:
        """When user_id is provided, it's included in the payload."""
        svc, session, _ = _make_service()

        added_objects: list = []
        session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        await svc.enqueue_next_stage("P001", "discover", user_id="user-42")

        item = added_objects[0]
        assert item.payload == {"user_id": "user-42"}

    @pytest.mark.asyncio
    async def test_enqueue_without_user_id(self) -> None:
        """When user_id is None, payload is None."""
        svc, session, _ = _make_service()

        added_objects: list = []
        session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        await svc.enqueue_next_stage("P001", "discover")

        item = added_objects[0]
        assert item.payload is None

    @pytest.mark.asyncio
    async def test_enqueue_sets_timestamps(self) -> None:
        """Enqueued items have created_at and updated_at set."""
        svc, session, _ = _make_service()

        added_objects: list = []
        session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        await svc.enqueue_next_stage("P001", "discover")

        item = added_objects[0]
        assert item.created_at is not None
        assert item.updated_at is not None


# ═══════════════════════════════════════════════════════════════════════════════
# trigger_scan — additional edge cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestTriggerScan:
    """Additional trigger_scan tests beyond test_services.py."""

    @pytest.mark.asyncio
    async def test_trigger_scan_normalizes_state_and_county(self) -> None:
        """trigger_scan uppercases state and lowercases county."""
        svc, session, billing = _make_service()

        result = await svc.trigger_scan(
            user_id="user-1",
            tier="pro",
            state="fl",
            county="Miami-Dade",
        )

        assert result.state == "FL"
        assert result.county == "miami-dade"

    @pytest.mark.asyncio
    async def test_trigger_scan_message_format(self) -> None:
        """trigger_scan message includes state/county."""
        svc, session, billing = _make_service()

        result = await svc.trigger_scan(
            user_id="user-1",
            tier="free",
            state="TX",
            county="harris",
        )

        assert "TX" in result.message
        assert "harris" in result.message

    @pytest.mark.asyncio
    async def test_trigger_scan_with_instrument_filter(self) -> None:
        """trigger_scan accepts optional instrument_filter."""
        svc, session, billing = _make_service()

        result = await svc.trigger_scan(
            user_id="user-1",
            tier="pro",
            state="FL",
            county="orange",
            instrument_filter="tax_deed",
        )

        assert result.status == "queued"
        billing.check_quota.assert_awaited_once()


# ═══════════════════════════════════════════════════════════════════════════════
# get_queue_status — additional edge cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetQueueStatus:
    """Additional get_queue_status tests."""

    @pytest.mark.asyncio
    async def test_empty_queue(self) -> None:
        """get_queue_status returns zeros when queue is empty."""
        svc, session, _ = _make_service()

        # No status rows
        status_result = MagicMock()
        status_result.__iter__ = lambda self: iter([])
        # No agent rows
        agent_result = MagicMock()
        agent_result.__iter__ = lambda self: iter([])

        session.execute.side_effect = [status_result, agent_result]

        result = await svc.get_queue_status()

        assert result.pending == 0
        assert result.processing == 0
        assert result.failed == 0
        assert result.complete == 0
        assert result.agents == {}

    @pytest.mark.asyncio
    async def test_queue_status_with_user_id(self) -> None:
        """get_queue_status accepts optional user_id parameter."""
        svc, session, _ = _make_service()

        status_rows = [MagicMock(status="pending", cnt=3)]
        agent_rows = [MagicMock(agent_name="discover", cnt=3)]

        session.execute.side_effect = [
            MagicMock(__iter__=lambda s: iter(status_rows)),
            MagicMock(__iter__=lambda s: iter(agent_rows)),
        ]

        result = await svc.get_queue_status(user_id="user-1")
        assert result.pending == 3
