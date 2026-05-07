"""Unit tests for the scoring models (no DB, no LLM, no network)."""

from datetime import date, timedelta

import pytest

from aloha.agents.scoring.models import score_lien_certificate, score_tax_deed


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def base_parcel():
    return {
        "parcel_id": "123-456-789",
        "property_type": "residential",
        "assessed_total": 200_000,
        "market_value_est": 250_000,
        "year_built": 2005,
        "acreage": 0.25,
    }


@pytest.fixture
def base_lien():
    return {
        "instrument_type": "lien_certificate",
        "lien_status": "active",
        "principal_amount": 3_500.0,
        "total_owed": 4_200.0,
        "certificate_interest_rate": 0.18,
        "tax_year": 2023,
        "years_delinquent": 2,
        "redemption_deadline": (date.today() + timedelta(days=45)).isoformat(),
    }


@pytest.fixture
def base_owner():
    return {
        "owner_of_record": "SMITH, JOHN",
        "owner_type": "individual",
        "is_absentee": True,
        "mailing_address": "456 Oak St",
        "best_phone": "555-1234",
        "best_email": None,
    }


@pytest.fixture
def base_deed_lien():
    return {
        "instrument_type": "tax_deed",
        "lien_status": "active",
        "principal_amount": 15_000.0,
        "total_owed": 18_000.0,
        "opening_bid": 85_000.0,
        "auction_date": (date.today() + timedelta(days=30)).isoformat(),
        "auction_platform": "bid4assets",
        "title_risk_level": "minor",
        "post_sale_redemption_days": 0,
    }


# ── Lien certificate tests ────────────────────────────────────────────────────

class TestLienCertificateModel:
    def test_returns_lien_certificate_type(self, base_parcel, base_lien, base_owner):
        result = score_lien_certificate(base_parcel, base_lien, base_owner)
        assert result.instrument_type == "lien_certificate"
        assert result.score_model_version == "lien_v1"

    def test_score_within_range(self, base_parcel, base_lien, base_owner):
        result = score_lien_certificate(base_parcel, base_lien, base_owner)
        assert 0 <= result.overall_score <= 100

    def test_high_rate_yields_more_points(self, base_parcel, base_lien, base_owner):
        high_rate = {**base_lien, "certificate_interest_rate": 0.18}
        low_rate = {**base_lien, "certificate_interest_rate": 0.06}
        high = score_lien_certificate(base_parcel, high_rate, base_owner, state_cert_rate_cap=0.18)
        low = score_lien_certificate(base_parcel, low_rate, base_owner, state_cert_rate_cap=0.18)
        assert high.overall_score > low.overall_score

    def test_urgent_deadline_increases_score(self, base_parcel, base_lien, base_owner):
        urgent = {**base_lien, "redemption_deadline": (date.today() + timedelta(days=10)).isoformat()}
        far = {**base_lien, "redemption_deadline": (date.today() + timedelta(days=365)).isoformat()}
        score_urgent = score_lien_certificate(base_parcel, urgent, base_owner)
        score_far = score_lien_certificate(base_parcel, far, base_owner)
        assert score_urgent.overall_score > score_far.overall_score

    def test_low_ltv_yields_high_ltv_score(self, base_parcel, base_lien, base_owner):
        # 4200/200000 = 2.1% LTV → should get near max LTV points
        result = score_lien_certificate(base_parcel, base_lien, base_owner)
        assert result.lien_to_value_ratio is not None
        assert result.lien_to_value_ratio < 0.03

    def test_government_owner_adds_flag(self, base_parcel, base_lien):
        gov_owner = {
            "owner_type": "government",
            "is_absentee": False,
            "mailing_address": None,
            "best_phone": None,
            "best_email": None,
        }
        result = score_lien_certificate(base_parcel, base_lien, gov_owner)
        assert "government_owned" in result.risk_flags

    def test_absentee_entity_boosts_motivation(self, base_parcel, base_lien):
        absentee_llc = {
            "owner_type": "llc",
            "is_absentee": True,
            "mailing_address": "123 Elm St",
            "best_phone": None,
            "best_email": None,
        }
        individual = {
            "owner_type": "individual",
            "is_absentee": False,
            "mailing_address": "123 Elm St",
            "best_phone": None,
            "best_email": None,
        }
        r_llc = score_lien_certificate(base_parcel, base_lien, absentee_llc)
        r_ind = score_lien_certificate(base_parcel, base_lien, individual)
        assert r_llc.owner_motivation > r_ind.owner_motivation

    def test_no_contact_info_adds_flag(self, base_parcel, base_lien):
        no_contact = {
            "owner_type": "individual",
            "is_absentee": False,
            "mailing_address": None,
            "best_phone": None,
            "best_email": None,
        }
        result = score_lien_certificate(base_parcel, base_lien, no_contact)
        assert "no_contact_info" in result.risk_flags

    def test_unknown_assessed_value(self, base_lien, base_owner):
        no_av_parcel = {"property_type": "residential", "assessed_total": None}
        result = score_lien_certificate(no_av_parcel, base_lien, base_owner)
        assert "assessed_value_unknown" in result.risk_flags
        assert 0 <= result.overall_score <= 100

    def test_years_delinquent_captured(self, base_parcel, base_lien, base_owner):
        result = score_lien_certificate(base_parcel, base_lien, base_owner)
        assert result.years_delinquent == 2


# ── Tax deed tests ────────────────────────────────────────────────────────────

class TestTaxDeedModel:
    def test_returns_tax_deed_type(self, base_parcel, base_deed_lien, base_owner):
        result = score_tax_deed(base_parcel, base_deed_lien, base_owner)
        assert result.instrument_type == "tax_deed"
        assert result.score_model_version == "deed_v1"

    def test_score_within_range(self, base_parcel, base_deed_lien, base_owner):
        result = score_tax_deed(base_parcel, base_deed_lien, base_owner)
        assert 0 <= result.overall_score <= 100

    def test_high_arv_to_bid_yields_higher_score(self, base_owner):
        parcel_high = {"assessed_total": 300_000, "property_type": "residential"}
        parcel_low = {"assessed_total": 90_000, "property_type": "residential"}
        lien = {
            "opening_bid": 85_000,
            "title_risk_level": "clear",
        }
        r_high = score_tax_deed(parcel_high, lien, base_owner)
        r_low = score_tax_deed(parcel_low, lien, base_owner)
        assert r_high.overall_score > r_low.overall_score

    def test_clouded_title_adds_flag(self, base_parcel, base_owner):
        lien = {"opening_bid": 50_000, "title_risk_level": "clouded"}
        result = score_tax_deed(base_parcel, lien, base_owner)
        assert "title_clouded" in result.risk_flags

    def test_zero_post_sale_redemption_is_best(self, base_parcel, base_deed_lien, base_owner):
        no_redemption = score_tax_deed(base_parcel, base_deed_lien, base_owner, post_sale_redemption_days=0)
        long_redemption = score_tax_deed(base_parcel, base_deed_lien, base_owner, post_sale_redemption_days=730)
        assert no_redemption.overall_score > long_redemption.overall_score

    def test_online_platform_adds_competition_flag(self, base_parcel, base_owner):
        lien = {"opening_bid": 50_000, "title_risk_level": "clear", "auction_platform": "bid4assets"}
        result = score_tax_deed(base_parcel, lien, base_owner)
        assert "online_auction_competition" in result.risk_flags

    def test_bid_exceeds_arv_flags_risk(self, base_owner):
        parcel = {"assessed_total": 50_000, "property_type": "residential"}
        lien = {"opening_bid": 200_000, "title_risk_level": "clear"}
        result = score_tax_deed(parcel, lien, base_owner)
        assert "bid_exceeds_arv" in result.risk_flags

    def test_land_gets_no_year_built_penalty(self, base_owner):
        land_parcel = {"assessed_total": 100_000, "property_type": "land", "year_built": None}
        lien = {"opening_bid": 20_000, "title_risk_level": "clear"}
        result = score_tax_deed(land_parcel, lien, base_owner)
        # Land should have decent condition score (no structure to decay)
        assert result.condition_risk >= 7


# ── Financial health scoring tests (lien certificate) ────────────────────────


class TestLienCertFinancialHealth:
    """Tests for entity financial health signals in lien certificate scoring."""

    @pytest.fixture
    def _parcel(self):
        return {
            "parcel_id": "FH-001",
            "property_type": "residential",
            "assessed_total": 200_000,
        }

    @pytest.fixture
    def _lien(self):
        return {
            "instrument_type": "lien_certificate",
            "total_owed": 4_000,
            "principal_amount": 3_500,
            "certificate_interest_rate": 0.18,
            "years_delinquent": 1,
        }

    @pytest.fixture
    def _owner(self):
        return {
            "owner_type": "llc",
            "is_absentee": False,
            "mailing_address": "123 Elm St",
            "best_phone": "555-1234",
            "best_email": None,
        }

    def test_ucc_filings_boost_motivation(self, _parcel, _lien, _owner):
        entity = {"ucc_filings": [{"debtor": "Acme LLC", "secured": "Bank A"}]}
        result_with = score_lien_certificate(_parcel, _lien, _owner, entity_data=entity)
        result_without = score_lien_certificate(_parcel, _lien, _owner, entity_data=None)
        assert result_with.owner_motivation > result_without.owner_motivation
        assert "entity_ucc_filings" in result_with.risk_flags
        assert result_with.flags_detail["entity_ucc_filing_count"] == 1

    def test_tax_liens_boost_motivation_and_flag(self, _parcel, _lien, _owner):
        entity = {
            "federal_tax_liens": [{"amount": 15_000}],
            "state_tax_liens": [{"amount": 8_000}],
        }
        result = score_lien_certificate(_parcel, _lien, _owner, entity_data=entity)
        without = score_lien_certificate(_parcel, _lien, _owner, entity_data=None)
        assert result.owner_motivation > without.owner_motivation
        assert "entity_tax_liens" in result.risk_flags
        assert result.flags_detail["entity_tax_lien_total"] == 23_000.0

    def test_bankruptcy_adds_flag_and_boosts(self, _parcel, _lien, _owner):
        entity = {"bankruptcy_history": [{"case": "Ch7", "year": 2022}]}
        result = score_lien_certificate(_parcel, _lien, _owner, entity_data=entity)
        assert "entity_bankruptcy" in result.risk_flags
        without = score_lien_certificate(_parcel, _lien, _owner, entity_data=None)
        assert result.owner_motivation > without.owner_motivation

    def test_litigation_summary_adds_flag(self, _parcel, _lien, _owner):
        entity = {"litigation_summary": "2 pending civil cases in Orange County"}
        result = score_lien_certificate(_parcel, _lien, _owner, entity_data=entity)
        assert "entity_active_litigation" in result.risk_flags

    def test_empty_litigation_no_flag(self, _parcel, _lien, _owner):
        entity = {"litigation_summary": ""}
        result = score_lien_certificate(_parcel, _lien, _owner, entity_data=entity)
        assert "entity_active_litigation" not in result.risk_flags

    def test_none_entity_data_backward_compatible(self, _parcel, _lien, _owner):
        """Passing entity_data=None must produce the same result as before."""
        result_none = score_lien_certificate(_parcel, _lien, _owner, entity_data=None)
        result_default = score_lien_certificate(_parcel, _lien, _owner)
        assert result_none.overall_score == result_default.overall_score
        assert result_none.owner_motivation == result_default.owner_motivation
        assert result_none.risk_flags == result_default.risk_flags

    def test_all_financial_signals_combined(self, _parcel, _lien, _owner):
        entity = {
            "ucc_filings": [{"debtor": "X"}, {"debtor": "Y"}],
            "federal_tax_liens": [{"amount": 50_000}],
            "state_tax_liens": [],
            "bankruptcy_history": [{"case": "Ch11"}],
            "litigation_summary": "Breach of contract suit filed 2024",
        }
        result = score_lien_certificate(_parcel, _lien, _owner, entity_data=entity)
        assert "entity_ucc_filings" in result.risk_flags
        assert "entity_tax_liens" in result.risk_flags
        assert "entity_bankruptcy" in result.risk_flags
        assert "entity_active_litigation" in result.risk_flags
        assert "Financial health:" in result.score_rationale

    def test_motivation_capped_at_10(self, _parcel, _lien):
        """Even with all boosts, motivation should never exceed 10."""
        owner = {
            "owner_type": "llc",
            "is_absentee": True,
            "mailing_address": "123 Elm",
            "best_phone": None,
            "best_email": None,
        }
        lien = {**_lien, "years_delinquent": 5}
        entity = {
            "ucc_filings": [{"x": 1}],
            "federal_tax_liens": [{"amount": 100_000}],
            "bankruptcy_history": [{"case": "Ch7"}],
        }
        result = score_lien_certificate(_parcel, lien, owner, entity_data=entity)
        assert result.owner_motivation <= 10


# ── Financial health scoring tests (tax deed) ────────────────────────────────


class TestTaxDeedFinancialHealth:
    """Tests for entity financial health signals in tax deed scoring."""

    @pytest.fixture
    def _parcel(self):
        return {
            "parcel_id": "FH-002",
            "property_type": "residential",
            "assessed_total": 200_000,
            "market_value_est": 250_000,
            "year_built": 2005,
        }

    @pytest.fixture
    def _lien(self):
        return {
            "instrument_type": "tax_deed",
            "opening_bid": 85_000,
            "title_risk_level": "minor",
            "auction_platform": "bid4assets",
        }

    @pytest.fixture
    def _owner(self):
        return {
            "owner_type": "llc",
            "is_absentee": False,
            "mailing_address": "456 Oak Ave",
            "best_phone": None,
            "best_email": None,
        }

    def test_ucc_filings_boost_motivation(self, _parcel, _lien, _owner):
        entity = {"ucc_filings": [{"debtor": "Acme LLC"}]}
        result = score_tax_deed(_parcel, _lien, _owner, entity_data=entity)
        assert result.owner_motivation >= 2
        assert "entity_ucc_filings" in result.risk_flags

    def test_tax_liens_boost_motivation_and_flag(self, _parcel, _lien, _owner):
        entity = {
            "federal_tax_liens": [{"amount": 20_000}],
            "state_tax_liens": [{"amount": 5_000}],
        }
        result = score_tax_deed(_parcel, _lien, _owner, entity_data=entity)
        assert result.owner_motivation >= 3
        assert "entity_tax_liens" in result.risk_flags
        assert result.flags_detail["entity_tax_lien_total"] == 25_000.0

    def test_bankruptcy_adds_flag(self, _parcel, _lien, _owner):
        entity = {"bankruptcy_history": [{"case": "Ch7", "year": 2023}]}
        result = score_tax_deed(_parcel, _lien, _owner, entity_data=entity)
        assert "entity_bankruptcy" in result.risk_flags

    def test_litigation_summary_adds_flag(self, _parcel, _lien, _owner):
        entity = {"litigation_summary": "Foreclosure action pending"}
        result = score_tax_deed(_parcel, _lien, _owner, entity_data=entity)
        assert "entity_active_litigation" in result.risk_flags

    def test_none_entity_data_backward_compatible(self, _parcel, _lien, _owner):
        result_none = score_tax_deed(_parcel, _lien, _owner, entity_data=None)
        result_default = score_tax_deed(_parcel, _lien, _owner)
        assert result_none.overall_score == result_default.overall_score
        assert result_none.owner_motivation == result_default.owner_motivation
        assert result_none.risk_flags == result_default.risk_flags

    def test_no_entity_motivation_is_zero(self, _parcel, _lien, _owner):
        """Without entity data, tax deed owner_motivation should be 0."""
        result = score_tax_deed(_parcel, _lien, _owner, entity_data=None)
        assert result.owner_motivation == 0

    def test_all_financial_signals_combined(self, _parcel, _lien, _owner):
        entity = {
            "ucc_filings": [{"debtor": "X"}],
            "federal_tax_liens": [{"amount": 10_000}],
            "state_tax_liens": [{"amount": 5_000}],
            "bankruptcy_history": [{"case": "Ch11"}],
            "litigation_summary": "Active breach-of-contract suit",
        }
        result = score_tax_deed(_parcel, _lien, _owner, entity_data=entity)
        assert "entity_ucc_filings" in result.risk_flags
        assert "entity_tax_liens" in result.risk_flags
        assert "entity_bankruptcy" in result.risk_flags
        assert "entity_active_litigation" in result.risk_flags
        assert "Financial health:" in result.score_rationale
        # All boosts: 2+3+2 = 7, capped at 10
        assert result.owner_motivation == 7

    def test_motivation_capped_at_10(self, _parcel, _lien, _owner):
        entity = {
            "ucc_filings": [{"x": 1}] * 5,
            "federal_tax_liens": [{"amount": 100_000}],
            "state_tax_liens": [{"amount": 50_000}],
            "bankruptcy_history": [{"case": "Ch7"}, {"case": "Ch13"}],
        }
        result = score_tax_deed(_parcel, _lien, _owner, entity_data=entity)
        assert result.owner_motivation <= 10


# ── Owner type classifier tests ───────────────────────────────────────────────

class TestOwnerTypeClassifier:
    def test_llc_detected(self):
        from aloha.agents.owner_research.tools import classify_owner_type
        r = classify_owner_type("SUNSET PROPERTIES LLC")
        assert r["owner_type"] == "llc"
        assert r["is_entity"] is True

    def test_trust_detected(self):
        from aloha.agents.owner_research.tools import classify_owner_type
        r = classify_owner_type("JOHN DOE REVOCABLE TRUST")
        assert r["owner_type"] == "trust"

    def test_individual_last_first(self):
        from aloha.agents.owner_research.tools import classify_owner_type
        r = classify_owner_type("SMITH, JOHN A")
        assert r["owner_type"] == "individual"

    def test_government(self):
        from aloha.agents.owner_research.tools import classify_owner_type
        r = classify_owner_type("COUNTY OF ORANGE")
        assert r["owner_type"] == "government"


# ── Legal description parser tests ───────────────────────────────────────────

class TestLegalDescriptionParser:
    def test_lot_block_parsed(self):
        from aloha.agents.parcel_research.tools import parse_legal_description
        r = parse_legal_description("LOT 5 BLK 3 SUNRISE ESTATES PLAT BOOK 12")
        assert r["format"] == "lot_block"
        assert r["lot"] == "5"
        assert r["block"] == "3"

    def test_metes_bounds_parsed(self):
        from aloha.agents.parcel_research.tools import parse_legal_description
        r = parse_legal_description("COM AT NW COR SEC 14 T2S R3E THENCE EAST 300 FT")
        assert r["format"] == "metes_bounds"
        assert r["section"] == "14"

    def test_condo_parsed(self):
        from aloha.agents.parcel_research.tools import parse_legal_description
        r = parse_legal_description("UNIT 12B BLDG 3 HARBOR TOWERS CONDO")
        assert r["format"] == "condo"
        assert r["unit"] == "12B"

    def test_empty_returns_unknown(self):
        from aloha.agents.parcel_research.tools import parse_legal_description
        r = parse_legal_description("")
        assert r["format"] == "unknown"


# ── Property type classifier tests ───────────────────────────────────────────

class TestPropertyTypeClassifier:
    def test_residential_from_land_use(self):
        from aloha.agents.parcel_research.tools import classify_property_type
        assert classify_property_type("01", None, None) == "residential"

    def test_commercial_from_zoning(self):
        from aloha.agents.parcel_research.tools import classify_property_type
        assert classify_property_type(None, "C2", None) == "commercial"

    def test_land_from_luc(self):
        from aloha.agents.parcel_research.tools import classify_property_type
        assert classify_property_type("VAC", None, None) == "land"

    def test_unknown_when_no_data(self):
        from aloha.agents.parcel_research.tools import classify_property_type
        assert classify_property_type(None, None, None) == "unknown"


# ── Absentee detection tests ──────────────────────────────────────────────────

class TestAbsenteeDetection:
    def test_same_address_not_absentee(self):
        from aloha.agents.owner_research.tools import detect_absentee
        r = detect_absentee("123 Main St Orlando FL", "123 Main St Orlando FL 32801")
        assert r["is_absentee"] is False

    def test_different_address_is_absentee(self):
        from aloha.agents.owner_research.tools import detect_absentee
        r = detect_absentee("123 Main St Orlando FL", "789 Oak Ave Miami FL 33101")
        assert r["is_absentee"] is True

    def test_missing_address_returns_unknown(self):
        from aloha.agents.owner_research.tools import detect_absentee
        r = detect_absentee(None, None)
        assert r["is_absentee"] is None
