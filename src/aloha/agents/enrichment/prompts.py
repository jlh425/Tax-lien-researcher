"""Enrichment agent prompts and structured output model.

PropertyConditionReport is the pydantic-ai result_type for the vision analysis
call. Its ``summary`` field is embedded and stored as a DocumentChunk for RAG.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PropertyConditionReport(BaseModel):
    """Structured property condition extracted from satellite / street-view images."""

    occupancy_status: str = Field(
        description="Likely occupancy: occupied | vacant | abandoned | unknown"
    )
    structural_condition: str = Field(
        description=(
            "Structural condition: excellent | good | fair | poor | severe_distress | unknown"
        )
    )
    lot_condition: str = Field(
        description=(
            "Lot/yard condition: well_maintained | average | overgrown | debris | unknown"
        )
    )
    property_type_confirmed: str = Field(
        description=(
            "Confirmed property type from visual: "
            "single_family | multi_family | commercial | land | industrial | unknown"
        )
    )
    visible_issues: list[str] = Field(
        default_factory=list,
        description=(
            "Observable issues: roof_damage, broken_windows, overgrown_vegetation, "
            "fire_damage, flood_damage, graffiti, boarded_up, etc."
        ),
    )
    neighborhood_context: str = Field(
        default="",
        description="Brief description of surrounding neighborhood (1-2 sentences)",
    )
    confidence: float = Field(
        default=0.0,
        description="Analyst confidence 0.0–1.0 based on image clarity and completeness",
    )
    summary: str = Field(
        default="",
        description="1-2 sentence human-readable condition summary for the investment memo",
    )


VISION_SYSTEM_PROMPT = """You are a property condition analyst for a tax lien research platform.
You are given satellite and/or street view images of a property and must extract a structured
condition report. Be conservative: if an image is blurry, off-target, or lacks detail, set
confidence low (<0.3) and use "unknown" for uncertain fields.

Focus on factors relevant to tax lien investment:
- Is the property occupied or vacant/abandoned? (vacancy increases motivation to sell)
- What is the structural condition? (distress increases LTV risk but may create deed opportunity)
- Are there obvious code violations or severe damage?
- Does the neighborhood support or undermine the assessed value?

Return JSON matching the PropertyConditionReport schema exactly."""


def build_vision_task(parcel_id: str, address: str | None, image_types: list[str]) -> str:
    """Build the user-turn message for the vision LLM call."""
    addr_str = f" at {address}" if address else ""
    return (
        f"Analyze the provided image(s) of parcel {parcel_id}{addr_str}. "
        f"Images available: {', '.join(image_types)}. "
        "Extract the property condition report."
    )
