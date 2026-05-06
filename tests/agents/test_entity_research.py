"""Unit tests for the Entity Research Agent (no DB, no LLM, no network)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

# conftest.py patches get_agent_model globally so these imports work.
from aloha.agents.entity_research.agent import EntityResearchAgent, _is_commercial_ra


# ═══════════════════════════════════════════════════════════════════════════════
# Pure function tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestIsCommercialRA:
    def test_ct_corporation(self):
        assert _is_commercial_ra("CT CORPORATION SYSTEM") is True

    def test_northwest(self):
        assert _is_commercial_ra("NORTHWEST REGISTERED AGENT LLC") is True

    def test_legalzoom(self):
        assert _is_commercial_ra("LEGALZOOM.COM INC") is True

    def test_csc(self):
        assert _is_commercial_ra("CORPORATION SERVICE COMPANY") is True

    def test_harbor_compliance(self):
        assert _is_commercial_ra("HARBOR COMPLIANCE LLC") is True

    def test_individual_name(self):
        assert _is_commercial_ra("JOHN SMITH") is False

    def test_none(self):
        assert _is_commercial_ra(None) is False

    def test_empty(self):
        assert _is_commercial_ra("") is False

    def test_case_insensitive(self):
        assert _is_commercial_ra("ct corporation system") is True

    def test_partial_match(self):
        assert _is_commercial_ra("COGENCY GLOBAL INC") is True


class TestExtractBeneficialOwner:
    @pytest.fixture
    def agent(self):
        return EntityResearchAgent()

    def test_officer_found(self, agent):
        sos = {"officers": [{"name": "JOHN SMITH", "title": "President"}]}
        name, confidence = agent._extract_beneficial_owner(sos)
        assert name == "John Smith"
        assert confidence == "high"

    def test_manager_found(self, agent):
        sos = {"managers_members": [{"name": "JANE DOE", "title": "Manager"}]}
        name, confidence = agent._extract_beneficial_owner(sos)
        assert name == "Jane Doe"
        assert confidence == "high"

    def test_commercial_ra_officer_skipped(self, agent):
        sos = {
            "officers": [{"name": "CT CORPORATION SYSTEM", "title": "Agent"}],
            "registered_agent": "CT CORPORATION SYSTEM",
            "entity_name": "ACME LLC",
        }
        name, confidence = agent._extract_beneficial_owner(sos)
        assert name is None
        assert confidence == "low"

    def test_non_commercial_ra(self, agent):
        sos = {"registered_agent": "JOHN SMITH"}
        name, confidence = agent._extract_beneficial_owner(sos)
        assert name == "John Smith"
        assert confidence == "medium"

    def test_empty_result(self, agent):
        name, confidence = agent._extract_beneficial_owner({})
        assert name is None
        assert confidence == "unknown"

    def test_officers_before_managers(self, agent):
        sos = {
            "officers": [{"name": "ALICE", "title": "CEO"}],
            "managers_members": [{"name": "BOB", "title": "Manager"}],
        }
        name, _ = agent._extract_beneficial_owner(sos)
        assert name == "Alice"

    def test_empty_officer_name_skipped(self, agent):
        sos = {
            "officers": [{"name": "", "title": "CEO"}],
            "managers_members": [{"name": "BOB", "title": "Manager"}],
        }
        name, _ = agent._extract_beneficial_owner(sos)
        assert name == "Bob"


# ═══════════════════════════════════════════════════════════════════════════════
# Agent integration tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestEntityResearchAgent:
    @pytest.fixture
    def agent(self):
        return EntityResearchAgent()

    @pytest.fixture
    def base_context(self):
        return {
            "parcel_id": "TEST-001",
            "owner_id": 42,
            "entity_name": "ACME HOLDINGS LLC",
            "state": "FL",
            "county": "orange",
        }

    @pytest.fixture
    def _empty_litigation(self):
        return {
            "federal_tax_liens": [],
            "state_tax_liens": [],
            "bankruptcy_history": [],
            "litigation_summary": "",
            "pacer_results": [],
        }

    @pytest.mark.asyncio
    async def test_full_flow_with_sos_data(
        self, agent, base_context, _empty_litigation,
    ):
        agent._sos_lookup = AsyncMock(return_value={
            "entity_name": "ACME HOLDINGS LLC",
            "entity_type": "LLC",
            "status": "Active",
            "officers": [{"name": "JOHN SMITH", "title": "Manager"}],
            "registered_agent": "JOHN SMITH",
            "_search_state": "FL",
        })
        agent._find_related_entities = AsyncMock(return_value=["ENT-002", "ENT-003"])
        agent._search_ucc_filings = AsyncMock(return_value=[])
        agent._search_litigation = AsyncMock(return_value=_empty_litigation)
        agent._persist = AsyncMock(return_value=99)

        result = await agent.run(base_context)

        assert result["status"] == "complete"
        assert result["beneficial_owner"] == "John Smith"
        assert result["confidence"] == "high"
        assert result["entity_id"] == 99

    @pytest.mark.asyncio
    async def test_sos_unavailable(
        self, agent, base_context, _empty_litigation,
    ):
        agent._sos_lookup = AsyncMock(return_value={})
        agent._find_related_entities = AsyncMock(return_value=[])
        agent._search_ucc_filings = AsyncMock(return_value=[])
        agent._search_litigation = AsyncMock(return_value=_empty_litigation)
        agent._persist = AsyncMock(return_value=99)

        result = await agent.run(base_context)

        assert result["beneficial_owner"] is None
        assert result["confidence"] == "unknown"

    @pytest.mark.asyncio
    async def test_commercial_ra_no_beneficial_owner(
        self, agent, base_context, _empty_litigation,
    ):
        agent._sos_lookup = AsyncMock(return_value={
            "entity_name": "ACME LLC",
            "officers": [{"name": "CT CORPORATION SYSTEM", "title": "Agent"}],
            "registered_agent": "CT CORPORATION SYSTEM",
        })
        agent._find_related_entities = AsyncMock(return_value=[])
        agent._search_ucc_filings = AsyncMock(return_value=[])
        agent._search_litigation = AsyncMock(return_value=_empty_litigation)
        agent._persist = AsyncMock(return_value=99)

        result = await agent.run(base_context)

        assert result["beneficial_owner"] is None
        assert result["confidence"] == "low"

    @pytest.mark.asyncio
    async def test_ucc_filings_passed_to_persist(
        self, agent, base_context, _empty_litigation,
    ):
        """UCC filings from _search_ucc_filings are forwarded to _persist."""
        ucc_data = [
            {
                "filing_number": "20230001234",
                "debtor_name": "ACME HOLDINGS LLC",
                "secured_party": "FIRST NATIONAL BANK",
                "state": "FL",
            },
        ]
        agent._sos_lookup = AsyncMock(return_value={
            "entity_name": "ACME HOLDINGS LLC",
            "officers": [{"name": "JOHN SMITH", "title": "Manager"}],
            "_search_state": "FL",
        })
        agent._find_related_entities = AsyncMock(return_value=[])
        agent._search_ucc_filings = AsyncMock(return_value=ucc_data)
        agent._search_litigation = AsyncMock(return_value=_empty_litigation)
        agent._persist = AsyncMock(return_value=99)

        result = await agent.run(base_context)

        assert result["status"] == "complete"
        persist_kwargs = agent._persist.call_args.kwargs
        assert persist_kwargs["ucc_filings"] == ucc_data

    @pytest.mark.asyncio
    async def test_litigation_data_passed_to_persist(
        self, agent, base_context,
    ):
        """Verify _search_litigation results flow through to _persist."""
        lit_data = {
            "federal_tax_liens": [{"amount": 5000}],
            "state_tax_liens": [{"amount": 3000}],
            "bankruptcy_history": [{"case_title": "In re ACME"}],
            "litigation_summary": "Summary text",
            "pacer_results": [{"case_id": "1"}],
        }
        agent._sos_lookup = AsyncMock(return_value={
            "entity_name": "ACME LLC",
            "officers": [{"name": "BOB", "title": "CEO"}],
        })
        agent._find_related_entities = AsyncMock(return_value=[])
        agent._search_ucc_filings = AsyncMock(return_value=[])
        agent._search_litigation = AsyncMock(return_value=lit_data)
        agent._persist = AsyncMock(return_value=99)

        await agent.run(base_context)

        call_kwargs = agent._persist.call_args.kwargs
        assert call_kwargs["litigation_data"] is lit_data


# ═══════════════════════════════════════════════════════════════════════════════
# UCC integration tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestUCCIntegration:
    @pytest.fixture
    def agent(self):
        return EntityResearchAgent()

    @pytest.mark.asyncio
    async def test_search_ucc_filings_server_unavailable(self, agent, monkeypatch):
        """Graceful fallback when UCC server cannot be created."""
        def _raise_value_error():
            raise ValueError("No API key")

        monkeypatch.setattr(
            "aloha.mcp_servers.ucc.server.create_ucc_server",
            _raise_value_error,
        )

        result = await agent._search_ucc_filings("ACME LLC", "FL")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_ucc_filings_server_raises_exception(self, agent):
        """Graceful fallback when UCC server search raises an exception."""
        mock_server = AsyncMock()
        mock_server.search_ucc_filings.side_effect = RuntimeError("Connection failed")
        mock_server.close = AsyncMock()

        import aloha.mcp_servers.ucc.server as ucc_module
        original_create = ucc_module.create_ucc_server

        def mock_create():
            return mock_server

        ucc_module.create_ucc_server = mock_create
        try:
            result = await agent._search_ucc_filings("ACME LLC", "FL")
            assert result == []
            mock_server.close.assert_called_once()
        finally:
            ucc_module.create_ucc_server = original_create

    @pytest.mark.asyncio
    async def test_search_ucc_filings_returns_filings(self, agent):
        """Successful UCC search returns the filing list."""
        expected_filings = [
            {
                "filing_number": "20230009999",
                "debtor_name": "ACME HOLDINGS LLC",
                "secured_party": "BANK OF AMERICA",
                "collateral": "Equipment and inventory",
                "state": "FL",
            },
        ]
        mock_server = AsyncMock()
        mock_server.search_ucc_filings.return_value = {"filings": expected_filings}
        mock_server.close = AsyncMock()

        import aloha.mcp_servers.ucc.server as ucc_module
        original_create = ucc_module.create_ucc_server

        def mock_create():
            return mock_server

        ucc_module.create_ucc_server = mock_create
        try:
            result = await agent._search_ucc_filings("ACME HOLDINGS LLC", "FL")
            assert result == expected_filings
            mock_server.search_ucc_filings.assert_called_once_with(
                debtor_name="ACME HOLDINGS LLC", state="FL",
            )
            mock_server.close.assert_called_once()
        finally:
            ucc_module.create_ucc_server = original_create


# ═══════════════════════════════════════════════════════════════════════════════
# Court records / litigation tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestSearchLitigation:
    """Tests for _search_litigation and _build_litigation_summary."""

    @pytest.fixture
    def agent(self):
        return EntityResearchAgent()

    @pytest.fixture
    def mock_court_server(self):
        """Return a mock CourtRecordsMCPServer with configurable responses."""
        server = AsyncMock()
        server.search_federal_cases = AsyncMock(return_value={"cases": []})
        server.search_state_liens = AsyncMock(return_value={"liens": []})
        server.close = AsyncMock()
        return server

    # ── Lien type filtering ───────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_federal_tax_lien_filtering(self, agent, mock_court_server):
        """federal_tax liens go into federal_tax_liens list."""
        mock_court_server.search_state_liens.return_value = {
            "liens": [
                {
                    "filing_number": "FTL-001",
                    "debtor": "ACME LLC",
                    "creditor": "IRS",
                    "amount": 50000,
                    "lien_type": "federal_tax",
                },
            ],
        }

        with patch(
            "aloha.mcp_servers.court_records.server.create_court_records_server",
            return_value=mock_court_server,
        ):
            result = await agent._search_litigation("ACME LLC", "FL")

        assert len(result["federal_tax_liens"]) == 1
        assert result["federal_tax_liens"][0]["creditor"] == "IRS"
        assert result["state_tax_liens"] == []

    @pytest.mark.asyncio
    async def test_state_tax_lien_filtering(self, agent, mock_court_server):
        """state_tax liens go into state_tax_liens list."""
        mock_court_server.search_state_liens.return_value = {
            "liens": [
                {
                    "filing_number": "STL-001",
                    "debtor": "ACME LLC",
                    "creditor": "FL Dept of Revenue",
                    "amount": 12000,
                    "lien_type": "state_tax",
                },
            ],
        }

        with patch(
            "aloha.mcp_servers.court_records.server.create_court_records_server",
            return_value=mock_court_server,
        ):
            result = await agent._search_litigation("ACME LLC", "FL")

        assert len(result["state_tax_liens"]) == 1
        assert result["federal_tax_liens"] == []

    @pytest.mark.asyncio
    async def test_unknown_lien_type_defaults_to_state(
        self, agent, mock_court_server,
    ):
        """Liens with unrecognised types fall into state_tax_liens."""
        mock_court_server.search_state_liens.return_value = {
            "liens": [{"lien_type": "judgment", "amount": 8000}],
        }

        with patch(
            "aloha.mcp_servers.court_records.server.create_court_records_server",
            return_value=mock_court_server,
        ):
            result = await agent._search_litigation("ACME LLC", "FL")

        assert len(result["state_tax_liens"]) == 1
        assert result["federal_tax_liens"] == []

    @pytest.mark.asyncio
    async def test_bankruptcy_case_filtering(self, agent, mock_court_server):
        """Bankruptcy cases go into bankruptcy_history."""
        mock_court_server.search_federal_cases.return_value = {
            "cases": [
                {"case_id": "BK-001", "case_title": "In re ACME", "case_type": "bankruptcy"},
                {"case_id": "CV-001", "case_title": "ACME v. State", "case_type": "civil"},
            ],
        }

        with patch(
            "aloha.mcp_servers.court_records.server.create_court_records_server",
            return_value=mock_court_server,
        ):
            result = await agent._search_litigation("ACME LLC", "FL")

        assert len(result["bankruptcy_history"]) == 1
        assert result["bankruptcy_history"][0]["case_id"] == "BK-001"
        assert len(result["pacer_results"]) == 2

    @pytest.mark.asyncio
    async def test_mixed_results(self, agent, mock_court_server):
        """All categories populated correctly from mixed results."""
        mock_court_server.search_federal_cases.return_value = {
            "cases": [
                {"case_id": "BK-001", "case_title": "In re ACME", "case_type": "bankruptcy"},
                {"case_id": "CV-001", "case_title": "ACME v. State", "case_type": "civil"},
            ],
        }
        mock_court_server.search_state_liens.return_value = {
            "liens": [
                {"lien_type": "federal_tax", "amount": 10000},
                {"lien_type": "state_tax", "amount": 5000},
                {"lien_type": "state_tax", "amount": 3000},
            ],
        }

        with patch(
            "aloha.mcp_servers.court_records.server.create_court_records_server",
            return_value=mock_court_server,
        ):
            result = await agent._search_litigation("ACME LLC", "FL")

        assert len(result["federal_tax_liens"]) == 1
        assert len(result["state_tax_liens"]) == 2
        assert len(result["bankruptcy_history"]) == 1
        assert len(result["pacer_results"]) == 2
        assert "ACME LLC" in result["litigation_summary"]

    # ── Litigation summary text ───────────────────────────────────────

    def test_summary_no_records(self, agent):
        summary = EntityResearchAgent._build_litigation_summary(
            entity_name="CLEAN LLC",
            federal_tax_liens=[],
            state_tax_liens=[],
            bankruptcy_history=[],
            litigation_entries=[],
        )
        assert summary == "No court records found for CLEAN LLC."

    def test_summary_federal_liens_with_amounts(self, agent):
        summary = EntityResearchAgent._build_litigation_summary(
            entity_name="ACME LLC",
            federal_tax_liens=[{"amount": 25000}, {"amount": 15000}],
            state_tax_liens=[],
            bankruptcy_history=[],
            litigation_entries=[],
        )
        assert "2 federal tax lien(s)" in summary
        assert "$40,000" in summary

    def test_summary_state_liens_with_amounts(self, agent):
        summary = EntityResearchAgent._build_litigation_summary(
            entity_name="ACME LLC",
            federal_tax_liens=[],
            state_tax_liens=[{"amount": 7500}],
            bankruptcy_history=[],
            litigation_entries=[],
        )
        assert "1 state tax lien(s)" in summary
        assert "$7,500" in summary

    def test_summary_bankruptcy_with_titles(self, agent):
        summary = EntityResearchAgent._build_litigation_summary(
            entity_name="ACME LLC",
            federal_tax_liens=[],
            state_tax_liens=[],
            bankruptcy_history=[
                {"case_title": "In re ACME Holdings"},
                {"case_title": "In re ACME Properties"},
            ],
            litigation_entries=[],
        )
        assert "2 bankruptcy case(s)" in summary
        assert "In re ACME Holdings" in summary

    def test_summary_litigation_count(self, agent):
        summary = EntityResearchAgent._build_litigation_summary(
            entity_name="ACME LLC",
            federal_tax_liens=[],
            state_tax_liens=[],
            bankruptcy_history=[],
            litigation_entries=[{"case_id": "1"}, {"case_id": "2"}],
        )
        assert "2 other litigation case(s)" in summary

    def test_summary_liens_without_amounts(self, agent):
        """Liens with no amount should not show a total."""
        summary = EntityResearchAgent._build_litigation_summary(
            entity_name="ACME LLC",
            federal_tax_liens=[{"amount": None}],
            state_tax_liens=[],
            bankruptcy_history=[],
            litigation_entries=[],
        )
        assert "1 federal tax lien(s)" in summary
        assert "totaling" not in summary

    # ── Graceful error handling ───────────────────────────────────────

    @pytest.mark.asyncio
    async def test_server_unavailable_returns_empty(self, agent):
        with patch(
            "aloha.mcp_servers.court_records.server.create_court_records_server",
            side_effect=ImportError("no module"),
        ):
            result = await agent._search_litigation("ACME LLC", "FL")

        assert result["federal_tax_liens"] == []
        assert result["state_tax_liens"] == []
        assert result["bankruptcy_history"] == []
        assert result["litigation_summary"] == ""
        assert result["pacer_results"] == []

    @pytest.mark.asyncio
    async def test_server_value_error_returns_empty(self, agent):
        with patch(
            "aloha.mcp_servers.court_records.server.create_court_records_server",
            side_effect=ValueError("API key missing"),
        ):
            result = await agent._search_litigation("ACME LLC", "FL")

        assert result["federal_tax_liens"] == []

    @pytest.mark.asyncio
    async def test_search_federal_cases_exception(self, agent, mock_court_server):
        """Runtime error in search returns empty results, close() still called."""
        mock_court_server.search_federal_cases.side_effect = RuntimeError("timeout")

        with patch(
            "aloha.mcp_servers.court_records.server.create_court_records_server",
            return_value=mock_court_server,
        ):
            result = await agent._search_litigation("ACME LLC", "FL")

        assert result["federal_tax_liens"] == []
        mock_court_server.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_server_close_always_called(self, agent, mock_court_server):
        """server.close() is called even when searches succeed."""
        with patch(
            "aloha.mcp_servers.court_records.server.create_court_records_server",
            return_value=mock_court_server,
        ):
            await agent._search_litigation("ACME LLC", "FL")

        mock_court_server.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_null_case_type_treated_as_litigation(self, agent, mock_court_server):
        mock_court_server.search_federal_cases.return_value = {
            "cases": [{"case_id": "X", "case_title": "Unknown", "case_type": None}],
        }

        with patch(
            "aloha.mcp_servers.court_records.server.create_court_records_server",
            return_value=mock_court_server,
        ):
            result = await agent._search_litigation("ACME LLC", "FL")

        assert result["bankruptcy_history"] == []
        assert len(result["pacer_results"]) == 1

    @pytest.mark.asyncio
    async def test_null_lien_type_defaults_to_state(self, agent, mock_court_server):
        mock_court_server.search_state_liens.return_value = {
            "liens": [{"lien_type": None, "amount": 1000}],
        }

        with patch(
            "aloha.mcp_servers.court_records.server.create_court_records_server",
            return_value=mock_court_server,
        ):
            result = await agent._search_litigation("ACME LLC", "FL")

        assert len(result["state_tax_liens"]) == 1
        assert result["federal_tax_liens"] == []
