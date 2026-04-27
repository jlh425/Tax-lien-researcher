"""Enrichment Agent — satellite/street-view capture + vision analysis + RAG indexing.

Responsibilities:
1. Trigger image capture (Mapbox satellite → Google fallback; Google Street View optional)
2. Call a multimodal LLM (Claude vision / GPT-4V) to extract PropertyConditionReport
3. Store the condition text as a DocumentChunk with an OpenAI embedding for pgvector RAG
4. Advance parcel research_status to 'enriched' and enqueue 'scoring'
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import Any

import structlog

from aloha.agents.base import BaseAgent
from aloha.agents.enrichment.prompts import (
    VISION_SYSTEM_PROMPT,
    PropertyConditionReport,
    build_vision_task,
)
from aloha.core.embeddings import embed_text
from aloha.db.engine import async_session_factory
from aloha.db.models.document_chunk import DocumentChunk
from aloha.db.repositories import ParcelRepository, QueueRepository
from aloha.db.repositories.image import DocumentChunkRepository, PropertyImageRepository

log = structlog.get_logger().bind(agent="enrichment")

# Image type preference order for vision analysis
_IMAGE_PREFERENCE = ("street_view", "satellite", "gis_parcel_map", "zillow_listing")


class EnrichmentAgent(BaseAgent):
    """Enriches a parcel with visual condition data and adds it to the RAG index.

    Context keys expected in ``run(context)``:
    - ``parcel_id``: APN / assessor parcel number (required)
    - ``state``: two-letter state abbreviation (optional, for logging)
    - ``county``: county name (optional, for logging)
    """

    def __init__(self) -> None:
        super().__init__(name="enrichment")

    def get_tools(self) -> list[dict[str, Any]]:
        return []

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        parcel_id: str = context["parcel_id"]
        state: str = context.get("state", "").upper()
        county: str = context.get("county", "").lower()

        self.log.info("enrichment_started", parcel_id=parcel_id, state=state, county=county)

        # ── Step 1: Load parcel ───────────────────────────────────────────
        async with async_session_factory() as session:
            parcel_repo = ParcelRepository(session)
            parcel = await parcel_repo.get(parcel_id)

        if parcel is None:
            self.log.warning("parcel_not_found", parcel_id=parcel_id)
            return {"status": "failed", "reason": "parcel_not_found"}

        # Skip re-enrichment if already done
        if parcel.research_status in ("enriched", "scoring", "scored", "complete"):
            self.log.info("enrichment_already_done", parcel_id=parcel_id, status=parcel.research_status)
            return {"status": "skipped", "reason": "already_enriched"}

        # ── Step 2: Trigger image capture ─────────────────────────────────
        # Deferred import to avoid circular dependency (server.py imports aloha.db)
        from aloha.mcp_servers.image_capture.server import ImageCaptureMCPServer
        from aloha.config import settings

        image_server = ImageCaptureMCPServer(google_api_key=settings.google_maps_api_key)
        try:
            if parcel.latitude and parcel.longitude:
                await image_server.capture_satellite(
                    parcel_id=parcel_id,
                    latitude=float(parcel.latitude),
                    longitude=float(parcel.longitude),
                )
            if parcel.address and settings.google_maps_api_key:
                await image_server.capture_street_view(
                    parcel_id=parcel_id,
                    address=parcel.address,
                )
        except Exception as exc:
            self.log.warning("image_capture_failed", parcel_id=parcel_id, error=str(exc))
        finally:
            await image_server.close()

        # ── Step 3: Load captured images ──────────────────────────────────
        async with async_session_factory() as session:
            image_repo = PropertyImageRepository(session)
            images = list(await image_repo.get_by_parcel(parcel_id))

        if not images:
            self.log.info("no_images_captured", parcel_id=parcel_id)
            return {"status": "no_images", "parcel_id": parcel_id}

        # ── Step 4: Pick best image for vision analysis ───────────────────
        selected = _pick_best_image(images)
        if selected is None:
            return {"status": "no_images", "parcel_id": parcel_id}

        # Decode data URI → bytes
        image_bytes = _decode_data_uri(selected.file_path)
        if not image_bytes:
            self.log.warning("image_decode_failed", parcel_id=parcel_id, image_id=selected.id)
            return {"status": "failed", "reason": "image_decode_failed"}

        # Determine MIME type from data URI prefix
        mime_type = _mime_from_data_uri(selected.file_path)

        # ── Step 5: Vision LLM analysis ───────────────────────────────────
        condition: PropertyConditionReport | None = None
        try:
            condition = await self._analyse_image(
                image_bytes=image_bytes,
                mime_type=mime_type,
                parcel_id=parcel_id,
                address=parcel.address,
                image_types=[img.image_type for img in images],
            )
        except Exception as exc:
            self.log.warning("vision_analysis_failed", parcel_id=parcel_id, error=str(exc))

        # Fall back to a minimal condition text if LLM call failed
        if condition is None:
            condition_text = json.dumps(
                {"summary": "Vision analysis unavailable.", "confidence": 0.0},
                indent=2,
            )
            condition_summary = "Vision analysis unavailable."
        else:
            condition_text = json.dumps(condition.model_dump(), indent=2)
            condition_summary = condition.summary or condition_text[:200]

        # ── Step 6: Embed and store DocumentChunk ─────────────────────────
        embedding = await embed_text(condition_summary)

        async with async_session_factory() as session:
            chunk_repo = DocumentChunkRepository(session)
            chunk = DocumentChunk(
                parcel_id=parcel_id,
                source_type="vision_analysis",
                source_url=selected.source_url,
                content=condition_text,
                embedding=embedding,
                created_at=datetime.now(tz=timezone.utc),
            )
            await chunk_repo.add(chunk)

            # ── Step 7: Advance status and enqueue scoring ─────────────────
            parcel_repo = ParcelRepository(session)
            queue_repo = QueueRepository(session)

            await parcel_repo.update_status(parcel_id, "enriched")

            await queue_repo.enqueue(
                agent_name="scoring",
                stage="score",
                parcel_id=parcel_id,
                payload={"parcel_id": parcel_id, "state": state, "county": county},
                priority=5,
            )

            await session.commit()

        self.log.info(
            "enrichment_complete",
            parcel_id=parcel_id,
            image_type=selected.image_type,
            confidence=getattr(condition, "confidence", None),
            has_embedding=embedding is not None,
        )
        return {
            "status": "complete",
            "parcel_id": parcel_id,
            "image_type": selected.image_type,
            "condition_summary": condition_summary,
        }

    async def _analyse_image(
        self,
        image_bytes: bytes,
        mime_type: str,
        parcel_id: str,
        address: str | None,
        image_types: list[str],
    ) -> PropertyConditionReport:
        """Call the vision LLM and return a structured PropertyConditionReport."""
        from pydantic_ai import Agent

        # Try pydantic-ai 0.0.30+ import path first, fall back to older path
        try:
            from pydantic_ai.messages import BinaryContent
        except ImportError:
            from pydantic_ai import BinaryContent  # type: ignore[no-redef]

        vision_agent: Agent[None, PropertyConditionReport] = Agent(
            self.model,
            result_type=PropertyConditionReport,
            system_prompt=VISION_SYSTEM_PROMPT,
        )
        task = build_vision_task(parcel_id, address, image_types)
        result = await vision_agent.run(
            [task, BinaryContent(data=image_bytes, media_type=mime_type)]
        )
        return result.data


# ── Module-level singleton ─────────────────────────────────────────────────────

try:
    agent = EnrichmentAgent()
except Exception:
    agent = None  # LLM provider not configured


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pick_best_image(images: list[Any]) -> Any | None:
    """Return the image with the highest-priority type, or None."""
    by_type = {img.image_type: img for img in images}
    for preferred in _IMAGE_PREFERENCE:
        if preferred in by_type:
            return by_type[preferred]
    return images[0] if images else None


def _decode_data_uri(data_uri: str) -> bytes | None:
    """Decode a data URI (``data:<mime>;base64,<b64>``) to raw bytes."""
    try:
        if "," not in data_uri:
            return None
        b64_part = data_uri.split(",", 1)[1]
        return base64.b64decode(b64_part)
    except Exception:
        return None


def _mime_from_data_uri(data_uri: str) -> str:
    """Extract MIME type from a data URI header, defaulting to image/jpeg."""
    try:
        header = data_uri.split(",", 1)[0]  # e.g. "data:image/png;base64"
        mime = header.split(":")[1].split(";")[0]
        return mime
    except Exception:
        return "image/jpeg"
