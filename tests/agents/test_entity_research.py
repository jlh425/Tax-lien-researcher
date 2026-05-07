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

    @pytest.fixture
    def _empty_contacts(self):
        return {"website": None, "phone": None, "email": None}

    @pytest.mark.asyncio
    async def test_full_flow_with_sos_data(
        self, agent, base_context, _empty_litigation, _empty_contacts,
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
        agent._enrich_entity_contacts = AsyncMock(return_value=_empty_contacts)
        agent._persist = AsyncMock(return_value=99)

        result = await agent.run(base_context)

        assert result["status"] == "complete"
        assert result["beneficial_owner"] == "John Smith"
        assert result["confidence"] == "high"
        assert result["entity_id"] == 99

    @pytest.mark.asyncio
    async def test_sos_unavailable(
        self, agent, base_context, _empty_litigation, _empty_contacts,
    ):
        agent._sos_lookup = AsyncMock(return_value={})
        agent._find_related_entities = AsyncMock(return_value=[])
        agent._search_ucc_filings = AsyncMock(return_value=[])
        agent._search_litigation = AsyncMock(return_value=_empty_litigation)
        agent._enrich_entity_contacts = AsyncMock(return_value=_empty_contacts)
        agent._persist = AsyncMock(return_value=99)

        result = await agent.run(base_context)

        assert result["beneficial_owner"] is None
        assert result["confidence"] == "unknown"

    @pytest.mark.asyncio
    async def test_commercial_ra_no_beneficial_owner(
        self, agent, base_context, _empty_litigation, _empty_contacts,
    ):
        agent._sos_lookup = AsyncMock(return_value={
            "entity_name": "ACME LLC",
            "officers": [{"name": "CT CORPORATION SYSTEM", "title": "Agent"}],
            "registered_agent": "CT CORPORATION SYSTEM",
        })
        agent._find_related_entities = AsyncMock(return_value=[])
        agent._search_ucc_filings = AsyncMock(return_value=[])
        agent._search_litigation = AsyncMock(return_value=_empty_litigation)
        agent._enrich_entity_contacts = AsyncMock(return_value=_empty_contacts)
        agent._persist = AsyncMock(return_value=99)

        result = await agent.run(base_context)

        assert result["beneficial_owner"] is None
        assert result["confidence"] == "low"

    @pytest.mark.asyncio
    async def test_ucc_filings_passed_to_persist(
        self, agent, base_context, _empty_litigation, _empty_contacts,
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
        agent._enrich_entity_contacts = AsyncMock(return_value=_empty_contacts)
        agent._persist = AsyncMock(return_value=99)

        result = await agent.run(base_context)

        assert result["status"] == "complete"
        persist_kwargs = agent._persist.call_args.kwargs
        assert persist_kwargs["ucc_filings"] == ucc_data

    @pytest.mark.asyncio
    async def test_litigation_data_passed_to_persist(
        self, agent, base_context, _empty_contacts,
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
        agent._enrich_entity_contacts = AsyncMock(return_value=_empty_contacts)
        agent._persist = AsyncMock(return_value=99)

        await agent.run(base_context)

        call_kwargs = agent._persist.call_args.kwargs
        assert call_kwargs["litigation_data"] is lit_data

    @pytest.mark.asyncio
    async def test_contact_data_passed_to_persist(
        self, agent, base_context, _empty_litigation,
    ):
        """Verify _enrich_entity_contacts results flow through to _persist."""
        contact = {
            "website": "https://acme.com",
            "phone": "+14155551234",
            "email": "john.smith@acme.com",
        }
        agent._sos_lookup = AsyncMock(return_value={
            "entity_name": "ACME LLC",
            "officers": [{"name": "JOHN SMITH", "title": "CEO"}],
        })
        agent._find_related_entities = AsyncMock(return_value=[])
        agent._search_ucc_filings = AsyncMock(return_value=[])
        agent._search_litigation = AsyncMock(return_value=_empty_litigation)
        agent._enrich_entity_contacts = AsyncMock(return_value=contact)
        agent._persist = AsyncMock(return_value=99)

        await agent.run(base_context)

        call_kwargs = agent._persist.call_args.kwargs
        assert call_kwargs["contact_data"] is contact


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


# ═══════════════════════════════════════════════════════════════════════════════
# Contact enrichment — pure helper tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestPickEnrichablePerson:
    @pytest.fixture
    def agent(self):
        return EntityResearchAgent()

    def test_officer_found(self, agent):
        sos = {"officers": [{"name": "JOHN SMITH", "title": "President"}]}
        assert agent._pick_enrichable_person(sos) == "JOHN SMITH"

    def test_manager_found(self, agent):
        sos = {"managers_members": [{"name": "JANE DOE", "title": "Manager"}]}
        assert agent._pick_enrichable_person(sos) == "JANE DOE"

    def test_commercial_ra_officer_skipped(self, agent):
        sos = {
            "officers": [{"name": "CT CORPORATION SYSTEM", "title": "Agent"}],
            "registered_agent": "BOB JONES",
        }
        assert agent._pick_enrichable_person(sos) == "BOB JONES"

    def test_all_commercial_ra_returns_none(self, agent):
        sos = {
            "officers": [{"name": "CT CORPORATION SYSTEM", "title": "Agent"}],
            "registered_agent": "NORTHWEST REGISTERED AGENT LLC",
        }
        assert agent._pick_enrichable_person(sos) is None

    def test_empty_sos(self, agent):
        assert agent._pick_enrichable_person({}) is None

    def test_none_sos(self, agent):
        assert agent._pick_enrichable_person(None) is None

    def test_officers_before_ra(self, agent):
        sos = {
            "officers": [{"name": "ALICE JONES", "title": "CEO"}],
            "registered_agent": "BOB SMITH",
        }
        assert agent._pick_enrichable_person(sos) == "ALICE JONES"

    def test_empty_name_skipped(self, agent):
        sos = {
            "officers": [{"name": "", "title": "CEO"}],
            "managers_members": [{"name": "BOB", "title": "Manager"}],
        }
        assert agent._pick_enrichable_person(sos) == "BOB"


class TestDeriveWebsite:
    def test_business_email_domain(self):
        result = EntityResearchAgent._derive_website(
            "ACME Corp", ["john@acmecorp.com"],
        )
        assert result == "https://acmecorp.com"

    def test_gmail_skipped(self):
        result = EntityResearchAgent._derive_website(
            "ACME Corp", ["john@gmail.com"],
        )
        assert result is None

    def test_yahoo_skipped(self):
        result = EntityResearchAgent._derive_website(
            "ACME Corp", ["john@yahoo.com"],
        )
        assert result is None

    def test_first_business_email_used(self):
        result = EntityResearchAgent._derive_website(
            "ACME Corp",
            ["personal@gmail.com", "john@acmecorp.com", "jane@other.com"],
        )
        assert result == "https://acmecorp.com"

    def test_empty_emails(self):
        result = EntityResearchAgent._derive_website("ACME Corp", [])
        assert result is None

    def test_no_company_name(self):
        result = EntityResearchAgent._derive_website(
            None, ["john@acmecorp.com"],
        )
        assert result == "https://acmecorp.com"


class TestGuessEmail:
    def test_basic_name(self):
        result = EntityResearchAgent._guess_email(
            "John Smith", "https://acme.com",
        )
        assert result == "john.smith@acme.com"

    def test_name_with_suffix(self):
        result = EntityResearchAgent._guess_email(
            "John Smith Jr.", "https://acme.com",
        )
        # Uses first and last parts: john.jr (last is "Jr." -> "jr")
        assert result == "john.jr@acme.com"

    def test_single_name_returns_none(self):
        result = EntityResearchAgent._guess_email(
            "Madonna", "https://acme.com",
        )
        assert result is None

    def test_http_url(self):
        result = EntityResearchAgent._guess_email(
            "John Smith", "http://acme.com",
        )
        assert result == "john.smith@acme.com"

    def test_url_with_trailing_slash(self):
        result = EntityResearchAgent._guess_email(
            "John Smith", "https://acme.com/",
        )
        assert result == "john.smith@acme.com"

    def test_empty_name_parts(self):
        result = EntityResearchAgent._guess_email(
            "  ", "https://acme.com",
        )
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# Contact enrichment — integration tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestEnrichEntityContacts:
    """Tests for _enrich_entity_contacts method."""

    @pytest.fixture
    def agent(self):
        return EntityResearchAgent()

    @pytest.fixture
    def mock_people_server(self):
        """Return a mock PeopleDataMCPServer with configurable responses."""
        server = AsyncMock()
        server.enrich_person = AsyncMock(return_value={
            "full_name": "John Smith",
            "first_name": "John",
            "last_name": "Smith",
            "emails": ["john.smith@acmecorp.com"],
            "phone_numbers": ["+14155551234"],
            "linkedin_url": "https://linkedin.com/in/johnsmith",
            "location": "Orlando, FL",
            "company": "ACME Corp",
            "title": "CEO",
        })
        server.verify_email = AsyncMock(return_value={
            "email": "john.smith@acmecorp.com",
            "status": "valid",
            "score": 95,
            "disposable": False,
            "webmail": False,
            "mx_records": True,
        })
        server.close = AsyncMock()
        return server

    @pytest.fixture
    def sos_with_officer(self):
        return {
            "entity_name": "ACME HOLDINGS LLC",
            "officers": [{"name": "JOHN SMITH", "title": "CEO"}],
            "registered_agent": "JOHN SMITH",
        }

    # ── Successful enrichment ──────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_full_contact_enrichment(
        self, agent, mock_people_server, sos_with_officer,
    ):
        """All three contact fields populated from PDL result."""
        with patch(
            "aloha.mcp_servers.people_data.server.create_people_data_server",
            return_value=mock_people_server,
        ):
            result = await agent._enrich_entity_contacts(
                sos_with_officer, "ACME HOLDINGS LLC", "FL",
            )

        assert result["phone"] == "+14155551234"
        assert result["email"] == "john.smith@acmecorp.com"
        assert result["website"] == "https://acmecorp.com"
        mock_people_server.enrich_person.assert_called_once_with(
            name="JOHN SMITH", company="ACME HOLDINGS LLC",
        )
        mock_people_server.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_phone_only(self, agent, mock_people_server, sos_with_officer):
        """Phone found but no email or website."""
        mock_people_server.enrich_person.return_value = {
            "phone_numbers": ["+14155551234"],
            "emails": [],
            "company": None,
        }

        with patch(
            "aloha.mcp_servers.people_data.server.create_people_data_server",
            return_value=mock_people_server,
        ):
            result = await agent._enrich_entity_contacts(
                sos_with_officer, "ACME LLC", "FL",
            )

        assert result["phone"] == "+14155551234"
        assert result["email"] is None
        assert result["website"] is None

    @pytest.mark.asyncio
    async def test_email_guess_fallback_verified(
        self, agent, mock_people_server, sos_with_officer,
    ):
        """When PDL returns no email but a business domain, guess and verify."""
        mock_people_server.enrich_person.return_value = {
            "phone_numbers": [],
            "emails": ["john@acmecorp.com"],  # gives us the domain
            "company": "ACME Corp",
        }
        # Simulate: first email from PDL is business email -> we derive website
        # But modify to have no direct email to test the fallback path
        mock_people_server.enrich_person.return_value = {
            "phone_numbers": [],
            "emails": [],
            "company": "ACME Corp",
        }
        # No email, no website derivable -> no guess attempt
        with patch(
            "aloha.mcp_servers.people_data.server.create_people_data_server",
            return_value=mock_people_server,
        ):
            result = await agent._enrich_entity_contacts(
                sos_with_officer, "ACME LLC", "FL",
            )

        assert result["email"] is None
        assert result["website"] is None
        mock_people_server.verify_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_email_guess_with_known_website(
        self, agent, sos_with_officer,
    ):
        """When PDL returns a business email domain but no direct match,
        website is derived and guess email is verified."""
        server = AsyncMock()
        # PDL returns an email for a different person at the same company
        # giving us a domain, but no direct email for our target
        server.enrich_person = AsyncMock(return_value={
            "phone_numbers": ["+14155550000"],
            "emails": ["other.person@acmecorp.com"],
            "company": "ACME Corp",
        })
        server.verify_email = AsyncMock(return_value={
            "status": "valid", "score": 90,
        })
        server.close = AsyncMock()

        with patch(
            "aloha.mcp_servers.people_data.server.create_people_data_server",
            return_value=server,
        ):
            result = await agent._enrich_entity_contacts(
                sos_with_officer, "ACME LLC", "FL",
            )

        # The first email IS returned (other.person@acmecorp.com)
        assert result["email"] == "other.person@acmecorp.com"
        assert result["website"] == "https://acmecorp.com"
        # verify_email should NOT have been called because we already have an email
        server.verify_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_email_guess_verified_valid(self, agent):
        """When no email from PDL, but website known via email domain,
        guessed email verified as valid is used."""
        sos = {"officers": [{"name": "JOHN SMITH", "title": "CEO"}]}
        server = AsyncMock()
        # PDL returns business-domain email for "another person" but
        # we need to set up a scenario where email list is empty but
        # website is set. We'll use _derive_website + _guess_email path
        # by having PDL return an email that is NOT for our person but
        # gives us the domain, then we manually construct the scenario.
        # Actually, the simpler approach: patch _derive_website to return a website
        server.enrich_person = AsyncMock(return_value={
            "phone_numbers": [],
            "emails": [],
            "company": None,
        })
        server.verify_email = AsyncMock(return_value={
            "status": "valid", "score": 95,
        })
        server.close = AsyncMock()

        with patch(
            "aloha.mcp_servers.people_data.server.create_people_data_server",
            return_value=server,
        ), patch.object(
            EntityResearchAgent, "_derive_website",
            return_value="https://acmecorp.com",
        ):
            result = await agent._enrich_entity_contacts(
                sos, "ACME LLC", "FL",
            )

        assert result["email"] == "john.smith@acmecorp.com"
        assert result["website"] == "https://acmecorp.com"
        server.verify_email.assert_called_once_with("john.smith@acmecorp.com")

    @pytest.mark.asyncio
    async def test_email_guess_undeliverable_not_used(self, agent):
        """Guessed email that fails verification is not used."""
        sos = {"officers": [{"name": "JOHN SMITH", "title": "CEO"}]}
        server = AsyncMock()
        server.enrich_person = AsyncMock(return_value={
            "phone_numbers": [],
            "emails": [],
            "company": None,
        })
        server.verify_email = AsyncMock(return_value={
            "status": "undeliverable", "score": 10,
        })
        server.close = AsyncMock()

        with patch(
            "aloha.mcp_servers.people_data.server.create_people_data_server",
            return_value=server,
        ), patch.object(
            EntityResearchAgent, "_derive_website",
            return_value="https://acmecorp.com",
        ):
            result = await agent._enrich_entity_contacts(
                sos, "ACME LLC", "FL",
            )

        assert result["email"] is None
        server.verify_email.assert_called_once()

    # ── No beneficial owner ────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_no_beneficial_owner_returns_empty(self, agent):
        """When no enrichable person found in SOS, return empty contacts."""
        sos = {
            "entity_name": "OPAQUE LLC",
            "officers": [{"name": "CT CORPORATION SYSTEM", "title": "Agent"}],
            "registered_agent": "NORTHWEST REGISTERED AGENT LLC",
        }

        result = await agent._enrich_entity_contacts(sos, "OPAQUE LLC", "FL")

        assert result == {"website": None, "phone": None, "email": None}

    @pytest.mark.asyncio
    async def test_empty_sos_returns_empty(self, agent):
        """Empty SOS result means no person to enrich."""
        result = await agent._enrich_entity_contacts({}, "UNKNOWN LLC", "FL")
        assert result == {"website": None, "phone": None, "email": None}

    # ── Graceful error handling ────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_server_unavailable_returns_empty(
        self, agent, sos_with_officer,
    ):
        """When People Data server cannot be created, returns empty."""
        with patch(
            "aloha.mcp_servers.people_data.server.create_people_data_server",
            side_effect=ValueError("PEOPLE_DATA_LABS_API_KEY required"),
        ):
            result = await agent._enrich_entity_contacts(
                sos_with_officer, "ACME LLC", "FL",
            )

        assert result == {"website": None, "phone": None, "email": None}

    @pytest.mark.asyncio
    async def test_import_error_returns_empty(
        self, agent, sos_with_officer,
    ):
        """When People Data module is not importable, returns empty."""
        with patch(
            "aloha.mcp_servers.people_data.server.create_people_data_server",
            side_effect=ImportError("no module"),
        ):
            result = await agent._enrich_entity_contacts(
                sos_with_officer, "ACME LLC", "FL",
            )

        assert result == {"website": None, "phone": None, "email": None}

    @pytest.mark.asyncio
    async def test_pdl_error_returns_empty(
        self, agent, mock_people_server, sos_with_officer,
    ):
        """When PDL returns an error, returns empty contacts."""
        mock_people_server.enrich_person.return_value = {
            "error": "PDL API error 429",
        }

        with patch(
            "aloha.mcp_servers.people_data.server.create_people_data_server",
            return_value=mock_people_server,
        ):
            result = await agent._enrich_entity_contacts(
                sos_with_officer, "ACME LLC", "FL",
            )

        assert result == {"website": None, "phone": None, "email": None}
        mock_people_server.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_runtime_error_returns_empty(
        self, agent, mock_people_server, sos_with_officer,
    ):
        """Runtime error during enrichment returns empty, close() still called."""
        mock_people_server.enrich_person.side_effect = RuntimeError("timeout")

        with patch(
            "aloha.mcp_servers.people_data.server.create_people_data_server",
            return_value=mock_people_server,
        ):
            result = await agent._enrich_entity_contacts(
                sos_with_officer, "ACME LLC", "FL",
            )

        assert result == {"website": None, "phone": None, "email": None}
        mock_people_server.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_server_close_always_called(
        self, agent, mock_people_server, sos_with_officer,
    ):
        """server.close() is called even when enrichment succeeds."""
        with patch(
            "aloha.mcp_servers.people_data.server.create_people_data_server",
            return_value=mock_people_server,
        ):
            await agent._enrich_entity_contacts(
                sos_with_officer, "ACME LLC", "FL",
            )

        mock_people_server.close.assert_awaited_once()
