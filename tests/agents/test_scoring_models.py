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
