"""Initial schema — all tables for Aloha v0.1.

Revision ID: 0001
Revises:
Create Date: 2026-03-17 00:00:00 UTC
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users ─────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255)),
        sa.Column("hashed_password", sa.String(255)),
        sa.Column("auth_provider", sa.String(50)),
        sa.Column("auth_provider_id", sa.String(255)),
        sa.Column("tier", sa.String(50), nullable=False, server_default="free"),
        sa.Column("stripe_customer_id", sa.String(255)),
        sa.Column("stripe_subscription_id", sa.String(255)),
        sa.Column("subscription_status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("outreach_mode", sa.String(50), nullable=False, server_default="individual"),
        sa.Column("outreach_email", sa.String(255)),
        sa.Column("outreach_domain", sa.String(255)),
        sa.Column("sendgrid_api_key", sa.Text),
        sa.Column("twilio_account_sid", sa.String(255)),
        sa.Column("twilio_auth_token", sa.Text),
        sa.Column("twilio_phone_number", sa.String(50)),
        sa.Column("physical_address", sa.Text),
        sa.Column("settings", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # ── parcels ───────────────────────────────────────────────────────────
    op.create_table(
        "parcels",
        sa.Column("parcel_id", sa.String(100), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("county", sa.String(100), nullable=False),
        sa.Column("state", sa.String(2), nullable=False),
        sa.Column("address", sa.Text),
        sa.Column("address_normalized", sa.Text),
        sa.Column("legal_description", sa.Text),
        sa.Column("acreage", sa.Numeric(12, 4)),
        sa.Column("land_use_code", sa.String(50)),
        sa.Column("property_type", sa.String(50)),
        sa.Column("zoning", sa.String(50)),
        sa.Column("zoning_notes", sa.Text),
        sa.Column("assessed_land_val", sa.Integer),
        sa.Column("assessed_impr_val", sa.Integer),
        sa.Column("assessed_total", sa.Integer),
        sa.Column("market_value_est", sa.Integer),
        sa.Column("last_sale_date", sa.Date),
        sa.Column("last_sale_price", sa.Integer),
        sa.Column("year_built", sa.Integer),
        sa.Column("latitude", sa.Numeric(10, 7)),
        sa.Column("longitude", sa.Numeric(10, 7)),
        sa.Column("research_status", sa.String(50), nullable=False, server_default="discovered"),
        sa.Column("data_freshness", sa.String(20), nullable=False, server_default="fresh"),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("last_crawled_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("parcel_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_parcels_user_id", "parcels", ["user_id"])
    op.create_index("ix_parcels_county_state", "parcels", ["county", "state"])
    op.create_index("ix_parcels_research_status", "parcels", ["research_status"])

    # ── tax_liens ─────────────────────────────────────────────────────────
    op.create_table(
        "tax_liens",
        sa.Column("id", sa.Integer, autoincrement=True, nullable=False),
        sa.Column("parcel_id", sa.String(100), nullable=False),
        sa.Column("instrument_type", sa.String(30), nullable=False, server_default="lien_certificate"),
        sa.Column("lien_status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("tax_year", sa.Integer),
        sa.Column("years_delinquent", sa.Integer),
        sa.Column("principal_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("interest_amount", sa.Numeric(14, 2)),
        sa.Column("penalty_amount", sa.Numeric(14, 2)),
        sa.Column("total_owed", sa.Numeric(14, 2)),
        sa.Column("filing_date", sa.Date),
        sa.Column("redemption_deadline", sa.Date),
        sa.Column("certificate_number", sa.String(100)),
        sa.Column("certificate_interest_rate", sa.Numeric(6, 4)),
        sa.Column("lien_holder", sa.String(255), nullable=False, server_default="county"),
        sa.Column("auction_date", sa.Date),
        sa.Column("auction_time", sa.String(50)),
        sa.Column("auction_platform", sa.String(100)),
        sa.Column("auction_url", sa.Text),
        sa.Column("opening_bid", sa.Numeric(14, 2)),
        sa.Column("post_sale_redemption_days", sa.Integer),
        sa.Column("title_encumbrances", postgresql.JSONB),
        sa.Column("title_risk_level", sa.String(30)),
        sa.Column("source_url", sa.Text),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.parcel_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("parcel_id", "tax_year", "certificate_number", name="uq_lien_cert"),
    )
    op.create_index("ix_tax_liens_parcel_id", "tax_liens", ["parcel_id"])
    op.create_index("ix_tax_liens_instrument_type", "tax_liens", ["instrument_type"])
    op.create_index("ix_tax_liens_lien_status", "tax_liens", ["lien_status"])
    op.create_index("ix_tax_liens_redemption_deadline", "tax_liens", ["redemption_deadline"])
    op.create_index("ix_tax_liens_auction_date", "tax_liens", ["auction_date"])

    # ── entities ──────────────────────────────────────────────────────────
    op.create_table(
        "entities",
        sa.Column("id", sa.Integer, autoincrement=True, nullable=False),
        sa.Column("entity_name", sa.Text, nullable=False),
        sa.Column("entity_type", sa.String(50)),
        sa.Column("state_of_formation", sa.String(2)),
        sa.Column("sos_status", sa.String(30)),
        sa.Column("formation_date", sa.Date),
        sa.Column("registered_agent", sa.Text),
        sa.Column("registered_agent_address", sa.Text),
        sa.Column("officers", postgresql.JSONB),
        sa.Column("managers_members", postgresql.JSONB),
        sa.Column("sos_filing_url", sa.Text),
        sa.Column("related_entity_ids", postgresql.JSONB),
        sa.Column("ucc_filings", postgresql.JSONB),
        sa.Column("federal_tax_liens", postgresql.JSONB),
        sa.Column("state_tax_liens", postgresql.JSONB),
        sa.Column("bankruptcy_history", postgresql.JSONB),
        sa.Column("litigation_summary", sa.Text),
        sa.Column("pacer_results", postgresql.JSONB),
        sa.Column("website", sa.Text),
        sa.Column("phone", sa.String(30)),
        sa.Column("email", sa.String(255)),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("last_researched_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── owners ────────────────────────────────────────────────────────────
    op.create_table(
        "owners",
        sa.Column("id", sa.Integer, autoincrement=True, nullable=False),
        sa.Column("parcel_id", sa.String(100), nullable=False),
        sa.Column("owner_of_record", sa.Text),
        sa.Column("owner_type", sa.String(30)),
        sa.Column("mailing_address", sa.Text),
        sa.Column("mailing_city", sa.String(100)),
        sa.Column("mailing_state", sa.String(2)),
        sa.Column("mailing_zip", sa.String(10)),
        sa.Column("is_absentee", sa.Boolean),
        sa.Column("deed_type", sa.String(50)),
        sa.Column("acquisition_date", sa.Date),
        sa.Column("acquisition_price", sa.Integer),
        sa.Column("beneficial_owner", sa.Text),
        sa.Column("beneficial_owner_confidence", sa.String(20)),
        sa.Column("best_phone", sa.String(30)),
        sa.Column("best_email", sa.String(255)),
        sa.Column("best_contact_address", sa.Text),
        sa.Column("research_depth", sa.Integer, nullable=False, server_default="0"),
        sa.Column("sources", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.parcel_id"], ondelete="CASCADE"),
    )
    op.create_index("ix_owners_parcel_id", "owners", ["parcel_id"])

    # ── owner_entities ────────────────────────────────────────────────────
    op.create_table(
        "owner_entities",
        sa.Column("owner_id", sa.Integer, nullable=False),
        sa.Column("entity_id", sa.Integer, nullable=False),
        sa.PrimaryKeyConstraint("owner_id", "entity_id"),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], ondelete="CASCADE"),
    )

    # ── scores ────────────────────────────────────────────────────────────
    op.create_table(
        "scores",
        sa.Column("id", sa.Integer, autoincrement=True, nullable=False),
        sa.Column("parcel_id", sa.String(100), nullable=False),
        sa.Column("instrument_type", sa.String(30), nullable=False),
        sa.Column("overall_score", sa.Integer),
        sa.Column("score_model_version", sa.String(30)),
        sa.Column("property_potential", sa.Integer),
        sa.Column("risk_score", sa.Integer),
        sa.Column("lien_to_value_ratio", sa.Numeric(8, 4)),
        sa.Column("certificate_rate", sa.Numeric(6, 4)),
        sa.Column("years_delinquent", sa.Integer),
        sa.Column("owner_motivation", sa.Integer),
        sa.Column("contact_reachability", sa.Integer),
        sa.Column("redemption_urgency", sa.Integer),
        sa.Column("arv_estimate", sa.Numeric(14, 2)),
        sa.Column("opening_bid", sa.Numeric(14, 2)),
        sa.Column("arv_to_bid_ratio", sa.Numeric(8, 2)),
        sa.Column("title_clarity", sa.Integer),
        sa.Column("condition_risk", sa.Integer),
        sa.Column("competition_risk", sa.Integer),
        sa.Column("post_sale_redemption_risk", sa.Integer),
        sa.Column("risk_flags", postgresql.ARRAY(sa.Text)),
        sa.Column("flags_detail", postgresql.JSONB),
        sa.Column("score_rationale", sa.Text),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.parcel_id"], ondelete="CASCADE"),
    )
    op.create_index("ix_scores_parcel_id", "scores", ["parcel_id"])

    # ── queue_items ───────────────────────────────────────────────────────
    op.create_table(
        "queue_items",
        sa.Column("id", sa.Integer, autoincrement=True, nullable=False),
        sa.Column("parcel_id", sa.String(100)),
        sa.Column("agent_name", sa.String(50), nullable=False),
        sa.Column("stage", sa.String(30), nullable=False),
        sa.Column("priority", sa.Integer, nullable=False, server_default="5"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text),
        sa.Column("next_retry_at", sa.DateTime(timezone=True)),
        sa.Column("claimed_by", sa.String(100)),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("payload", postgresql.JSONB),
        sa.Column("result", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.parcel_id"], ondelete="CASCADE"),
    )
    op.create_index("ix_queue_items_parcel_id", "queue_items", ["parcel_id"])
    op.create_index("ix_queue_items_agent_name", "queue_items", ["agent_name"])
    op.create_index("ix_queue_items_status", "queue_items", ["status"])
    op.create_index(
        "idx_queue_pickup",
        "queue_items",
        ["status", "priority", "next_retry_at"],
        postgresql_where=sa.text("status IN ('pending', 'retry')"),
    )

    # ── crawl_log ─────────────────────────────────────────────────────────
    op.create_table(
        "crawl_log",
        sa.Column("id", sa.Integer, autoincrement=True, nullable=False),
        sa.Column("parcel_id", sa.String(100)),
        sa.Column("source_type", sa.String(50)),
        sa.Column("source_url", sa.Text),
        sa.Column("http_status", sa.Integer),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("changed", sa.Boolean),
        sa.Column("error_message", sa.Text),
        sa.Column("crawled_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.parcel_id"], ondelete="SET NULL"),
    )
    op.create_index("ix_crawl_log_parcel_id", "crawl_log", ["parcel_id"])

    # ── property_images ───────────────────────────────────────────────────
    op.create_table(
        "property_images",
        sa.Column("id", sa.Integer, autoincrement=True, nullable=False),
        sa.Column("parcel_id", sa.String(100), nullable=False),
        sa.Column("image_type", sa.String(30), nullable=False),
        sa.Column("file_path", sa.Text, nullable=False),
        sa.Column("source_url", sa.Text),
        sa.Column("width", sa.Integer),
        sa.Column("height", sa.Integer),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("overlays", postgresql.ARRAY(sa.Text)),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.parcel_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("parcel_id", "image_type", name="uq_parcel_image_type"),
    )
    op.create_index("ix_property_images_parcel_id", "property_images", ["parcel_id"])

    # ── source_screenshots ────────────────────────────────────────────────
    op.create_table(
        "source_screenshots",
        sa.Column("id", sa.Integer, autoincrement=True, nullable=False),
        sa.Column("parcel_id", sa.String(100), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_name", sa.Text),
        sa.Column("source_url", sa.Text, nullable=False),
        sa.Column("file_path", sa.Text, nullable=False),
        sa.Column("crop_x", sa.Integer),
        sa.Column("crop_y", sa.Integer),
        sa.Column("crop_w", sa.Integer),
        sa.Column("crop_h", sa.Integer),
        sa.Column("data_extracted", postgresql.ARRAY(sa.Text)),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.parcel_id"], ondelete="CASCADE"),
    )
    op.create_index("idx_screenshots_parcel", "source_screenshots", ["parcel_id"])

    # ── outreach_log ──────────────────────────────────────────────────────
    op.create_table(
        "outreach_log",
        sa.Column("id", sa.Integer, autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parcel_id", sa.String(100)),
        sa.Column("owner_id", sa.Integer),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("contact_value", sa.Text, nullable=False),
        sa.Column("template_name", sa.String(100)),
        sa.Column("subject", sa.Text),
        sa.Column("message_body", sa.Text),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("approved_by", sa.String(255)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("delivery_status", sa.String(50)),
        sa.Column("opened_at", sa.DateTime(timezone=True)),
        sa.Column("replied_at", sa.DateTime(timezone=True)),
        sa.Column("bounce_reason", sa.Text),
        sa.Column("call_duration", sa.Integer),
        sa.Column("call_outcome", sa.String(30)),
        sa.Column("call_notes", sa.Text),
        sa.Column("call_recording_url", sa.Text),
        sa.Column("follow_up_date", sa.Date),
        sa.Column("follow_up_sent", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("provider", sa.String(30)),
        sa.Column("provider_msg_id", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.parcel_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_outreach_parcel", "outreach_log", ["parcel_id"])
    op.create_index("idx_outreach_owner", "outreach_log", ["owner_id"])
    op.create_index(
        "idx_outreach_followup",
        "outreach_log",
        ["follow_up_date"],
        postgresql_where=sa.text("follow_up_sent = FALSE AND follow_up_date IS NOT NULL"),
    )

    # ── do_not_contact ────────────────────────────────────────────────────
    op.create_table(
        "do_not_contact",
        sa.Column("id", sa.Integer, autoincrement=True, nullable=False),
        sa.Column("contact_value", sa.Text, nullable=False),
        sa.Column("contact_type", sa.String(10), nullable=False),
        sa.Column("reason", sa.String(50)),
        sa.Column("source", sa.String(50)),
        sa.Column("owner_id", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("contact_value", "contact_type", name="uq_dnc_contact"),
    )
    op.create_index("idx_dnc_lookup", "do_not_contact", ["contact_value", "contact_type"])

    # ── outreach_templates ────────────────────────────────────────────────
    op.create_table(
        "outreach_templates",
        sa.Column("id", sa.Integer, autoincrement=True, nullable=False),
        sa.Column("template_name", sa.String(100), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("instrument_type", sa.String(30)),
        sa.Column("subject", sa.Text),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("variables", postgresql.ARRAY(sa.Text)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("template_name"),
    )

    # ── document_chunks (vectors stored in Qdrant) ─────────────────────────
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Integer, autoincrement=True, nullable=False),
        sa.Column("parcel_id", sa.String(100)),
        sa.Column("entity_id", sa.Integer),
        sa.Column("source_type", sa.String(50)),
        sa.Column("source_url", sa.Text),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.parcel_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_chunks_parcel", "document_chunks", ["parcel_id"])

    # ── alerts ────────────────────────────────────────────────────────────
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer, autoincrement=True, nullable=False),
        sa.Column("parcel_id", sa.String(100)),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("alert_date", sa.Date),
        sa.Column("message", sa.Text),
        sa.Column("sent", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.parcel_id"], ondelete="CASCADE"),
    )
    op.create_index("ix_alerts_parcel_id", "alerts", ["parcel_id"])
    op.create_index(
        "idx_alerts_unsent",
        "alerts",
        ["alert_date"],
        postgresql_where=sa.text("sent = FALSE"),
    )


def downgrade() -> None:
    op.drop_table("alerts")
    op.drop_table("document_chunks")
    op.drop_table("outreach_templates")
    op.drop_table("do_not_contact")
    op.drop_table("outreach_log")
    op.drop_table("source_screenshots")
    op.drop_table("property_images")
    op.drop_table("crawl_log")
    op.drop_table("queue_items")
    op.drop_table("scores")
    op.drop_table("owner_entities")
    op.drop_table("owners")
    op.drop_table("entities")
    op.drop_table("tax_liens")
    op.drop_table("parcels")
    op.drop_table("users")
