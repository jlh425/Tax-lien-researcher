# Feature: Property Images — Multi-Provider Capture + Vision Analysis + RAG

The following plan should be complete, but it is important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils types and models. Import from the right files etc.

---

## Feature Description

**Strategic answer to "Google Maps API vs RAG the map":**

You can't meaningfully RAG raw raster map tiles (they don't embed semantically). But you CAN:
1. **Capture images cheaply** — use Mapbox free tier (50k satellite images/month) as primary provider, Google Maps as optional paid fallback
2. **RAG the AI-extracted description** — run captured images through a multimodal LLM (Claude vision) to extract a structured `PropertyConditionReport`, store the condition text as a `DocumentChunk` with a pgvector embedding, and query by semantic similarity

This gives you free satellite imagery for most use cases, paid Street View when the key is configured, and a searchable property condition layer baked into the existing RAG infrastructure (`document_chunks` + HNSW index) — all at zero schema changes.

---

## User Story

As a tax lien researcher
I want to see satellite and street-level images of every researched property alongside an AI-extracted condition summary
So that I can visually assess property condition and search for "abandoned properties" or "distressed assets" without manually reviewing every image

---

## Problem Statement

- `capture_satellite` and `capture_street_view` in `image_capture/server.py` return a hard error (`"GOOGLE_MAPS_API_KEY not configured"`) when the key is absent — most dev/test environments have no Google key
- No free fallback exists for satellite imagery (Mapbox costs nothing for <50k req/month)
- Images are captured and stored but never analyzed — the `document_chunks` pgvector table is empty with no write path
- `ParcelDetail` API response has no `images` field — the frontend can't display them
- `ReportAgent` doesn't include property condition in investment memos

---

## Solution Statement

Four-part implementation:
1. **Multi-provider image fetching** — `providers.py` with `MapboxSatelliteProvider` (free) → `GoogleSatelliteProvider` (paid fallback) and `GoogleStreetViewProvider`. Refactor `server.py` to use this chain.
2. **Embedding utility** — `core/embeddings.py` wrapping OpenAI `text-embedding-3-small` (1536 dims, matches existing schema) with graceful None fallback when unconfigured.
3. **Vision analysis agent** — `agents/enrichment/agent.py` loads the parcel's images, calls a multimodal LLM, extracts `PropertyConditionReport`, saves result text as `DocumentChunk` with embedding, and saves condition summary to `Parcel.zoning_notes` as a quick-access field.
4. **API + pipeline wiring** — `PropertyImageRepository`, `PropertyImageOut` schema, update `ParcelDetail`, update `ParcelResearchAgent` to enqueue image capture as the final step.

---

## Feature Metadata

**Feature Type**: New Capability + Enhancement
**Estimated Complexity**: Medium
**Primary Systems Affected**: `mcp_servers/image_capture/`, `agents/enrichment/`, `api/schemas/`, `api/routes/`, `core/`, `db/repositories/`
**Dependencies**:
- `mapbox` — no SDK needed; pure REST API via `httpx`
- `openai>=1.50` (already in optional extras) — text-embedding-3-small
- No new DB schema changes needed — `document_chunks.embedding vector(1536)` already exists

---

## CONTEXT REFERENCES

### Relevant Codebase Files — MUST READ BEFORE IMPLEMENTING

- `src/aloha/mcp_servers/image_capture/server.py` (full file, 299 lines) — existing capture tools; `_save_image()` helper at lines 246–290; `_GOOGLE_STATIC_URL` / `_GOOGLE_STREETVIEW_URL` constants at lines 24–25
- `src/aloha/db/models/property_image.py` (full file) — `PropertyImage` model: `id`, `parcel_id`, `image_type`, `file_path`, `source_url`, `width`, `height`, `captured_at`, `overlays`; **unique constraint `(parcel_id, image_type)`**; valid `image_type` values: `gis_parcel_map|street_view|satellite|zillow_listing`
- `src/aloha/db/models/document_chunk.py` (full file) — `DocumentChunk`: `id`, `parcel_id`, `entity_id`, `source_type`, `source_url`, `content` (Text), `embedding` (Vector(1536)), `created_at`; pgvector optional import pattern at lines 14–19
- `src/aloha/db/repositories/parcel.py` (full file) — `ParcelRepository.upsert()` pattern; mirror for `PropertyImageRepository`
- `src/aloha/db/repositories/queue.py` (full file) — `enqueue()` signature at lines 40–63
- `src/aloha/agents/parcel_research/agent.py` (full file) — where to add image capture enqueue; `run()` method; final action at the end of `run()` that enqueues `owner_research`
- `src/aloha/agents/base.py` (lines 13–80) — `BaseAgent` interface; constructor, `run()` abstract method
- `src/aloha/core/llm.py` (lines 83–122) — `get_agent_model(agent_name)` factory; returns pydantic-ai Model
- `src/aloha/api/schemas/parcels.py` (full file) — `ParcelDetail` schema to update; `TaxLienOut`, `OwnerOut` as reference for field naming
- `src/aloha/api/routes/parcels.py` (full file) — `GET /parcels/{parcel_id}` endpoint; how to load and eagerly join new data
- `src/aloha/agents/__init__.py` (full file) — `AGENT_REGISTRY` dict to update
- `src/aloha/config.py` (lines 69–80) — `google_maps_api_key` at line 73; `mapbox_api_key` to add here

### New Files to Create

- `src/aloha/mcp_servers/image_capture/providers.py` — Multi-provider image fetch logic
- `src/aloha/core/embeddings.py` — OpenAI text embedding utility (1536 dims)
- `src/aloha/agents/enrichment/agent.py` — `EnrichmentAgent`: vision analysis + DocumentChunk write
- `src/aloha/agents/enrichment/prompts.py` — Vision LLM system prompt + task template
- `src/aloha/db/repositories/image.py` — `PropertyImageRepository`, `DocumentChunkRepository`
- `tests/agents/test_enrichment_agent.py` — Unit tests for enrichment agent

### Files to Update

- `src/aloha/mcp_servers/image_capture/server.py` — Use `ProviderChain` from `providers.py`
- `src/aloha/config.py` — Add `mapbox_api_key: str | None = None`
- `src/aloha/api/schemas/parcels.py` — Add `PropertyImageOut`; update `ParcelDetail.images`
- `src/aloha/api/routes/parcels.py` — Load images via `PropertyImageRepository` in detail endpoint
- `src/aloha/agents/parcel_research/agent.py` — Enqueue `enrichment` after parcel research completes
- `src/aloha/agents/__init__.py` — Register `"enrichment"` in `AGENT_REGISTRY`

### Relevant Documentation — SHOULD READ BEFORE IMPLEMENTING

- Mapbox Static Images API: https://docs.mapbox.com/api/maps/static-images/
  - Section: "Retrieve a static map from a style" — URL format
  - URL pattern: `https://api.mapbox.com/styles/v1/mapbox/satellite-v9/static/{lon},{lat},{zoom}/{width}x{height}?access_token={token}`
  - Why: Primary free satellite provider

- Google Maps Static API: https://developers.google.com/maps/documentation/maps-static/start
  - Section: "Construct a Static Maps API URL" — `maptype=satellite`
  - Why: Optional paid fallback for satellite; already partially implemented

- Google Street View Static API: https://developers.google.com/maps/documentation/streetview/request-streetview
  - Section: "Constructing a Street View URL"
  - Why: Already implemented; only change is to expose `return_error_code=true` handling properly

- OpenAI Embeddings API: https://platform.openai.com/docs/api-reference/embeddings
  - Section: "Create embeddings" — `model=text-embedding-3-small`, `dimensions=1536`
  - Why: Produces 1536-dim vectors matching `document_chunks.embedding vector(1536)`

- Pydantic AI multimodal (image) input: https://ai.pydantic.dev/message-types/#image
  - Section: "ImageUrl / BinaryContent" message types
  - Why: Sending base64-encoded images to the LLM for vision analysis

- pgvector cosine search with SQLAlchemy: https://github.com/pgvector/pgvector-python#sqlalchemy
  - Section: "Querying" — `embedding.cosine_distance(query_vec)`
  - Why: `DocumentChunkRepository.search_similar()` uses this

---

## Patterns to Follow

### Multi-Provider Pattern (new)
```python
# providers.py pattern
class ImageProvider(ABC):
    @abstractmethod
    async def fetch(self, ...) -> bytes | None:
        """Return image bytes or None if unavailable."""

class ProviderChain:
    def __init__(self, providers: list[ImageProvider]) -> None:
        self._providers = providers
    async def fetch(self, ...) -> bytes | None:
        for provider in self._providers:
            result = await provider.fetch(...)
            if result:
                return result
        return None
```

### BaseScraper HTTP Client (mirror from `base.py` lines 41–48)
```python
# Providers use httpx.AsyncClient with context manager, NOT BaseScraper
# (providers are not scrapers, they don't need retry/rate limiting)
async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
    resp = await client.get(url, params=params)
    resp.raise_for_status()
    return resp.content
```

### Repository Pattern (mirror from `parcel.py` lines 23–52)
```python
class PropertyImageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
    async def get_by_parcel(self, parcel_id: str) -> Sequence[PropertyImage]:
        result = await self._session.execute(
            sa_select(PropertyImage).where(PropertyImage.parcel_id == parcel_id)
        )
        return result.scalars().all()
    async def upsert(self, image: PropertyImage) -> PropertyImage:
        return await self._session.merge(image)
```

### Agent Pattern (mirror from `parcel_research/agent.py`)
```python
class EnrichmentAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="enrichment")
    def get_tools(self) -> list[dict[str, Any]]: return []
    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        ...
agent = EnrichmentAgent()  # module-level singleton
```

### Logging Pattern
```python
log = structlog.get_logger().bind(agent="enrichment")
self.log.info("event_name", parcel_id=parcel_id, key=value)
self.log.warning("event_failed", parcel_id=parcel_id, error=str(exc))
```

### Error Handling
```python
try:
    result = await something()
except Exception as exc:
    self.log.warning("thing_failed", parcel_id=parcel_id, error=str(exc))
    return None  # never raise from agents; caller checks result
```

### Vision LLM Call (pydantic-ai with image content)
```python
from pydantic_ai import Agent, BinaryContent
agent: Agent[None, PropertyConditionReport] = Agent(
    model,
    result_type=PropertyConditionReport,
    system_prompt=VISION_SYSTEM_PROMPT,
)
# Build message with image attached
message = f"Analyze this {image_type} image...\n[Image attached]"
# Note: pydantic-ai passes image as BinaryContent in the message list
result = await agent.run(
    [message, BinaryContent(data=image_bytes, media_type="image/jpeg")]
)
```

### Embedding Pattern
```python
# core/embeddings.py
async def embed_text(text: str) -> list[float] | None:
    if not settings.openai_api_key:
        return None
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    resp = await client.embeddings.create(model="text-embedding-3-small", input=text)
    return resp.data[0].embedding  # 1536 floats
```

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation — Providers + Embeddings Utilities

Build the two new utility modules that everything else depends on.

**Tasks:**
- Create `providers.py` with abstract `ImageProvider`, `MapboxSatelliteProvider`, `GoogleSatelliteProvider`, `GoogleStreetViewProvider`, `ProviderChain`
- Create `core/embeddings.py` with `embed_text()` async function
- Add `mapbox_api_key` to `Settings`
- Create `db/repositories/image.py` with `PropertyImageRepository`, `DocumentChunkRepository`

### Phase 2: Core Implementation — Vision Analysis Agent

Build the enrichment agent that ties images to the RAG layer.

**Tasks:**
- Create `agents/enrichment/prompts.py` — `PropertyConditionReport` Pydantic model + system prompt
- Create `agents/enrichment/agent.py` — full `EnrichmentAgent` implementation
- Refactor `image_capture/server.py` to use `ProviderChain`

### Phase 3: Integration

Wire the new components into the existing pipeline and API.

**Tasks:**
- Update `agents/parcel_research/agent.py` to enqueue `enrichment` at the end
- Register `enrichment` in `AGENT_REGISTRY`
- Add `PropertyImageOut` schema and update `ParcelDetail`
- Update `GET /parcels/{parcel_id}` to load and return images

### Phase 4: Testing & Validation

**Tasks:**
- Unit tests for `PropertyImageRepository` (mock session)
- Unit tests for `EnrichmentAgent` (mock LLM + mock images)
- Unit tests for provider chain (mock httpx)

---

## STEP-BY-STEP TASKS

### Task 1: CREATE `src/aloha/mcp_servers/image_capture/providers.py`

- **IMPLEMENT**: Abstract `ImageProvider` + three concrete providers + `ProviderChain`

```python
# Mapbox URL format (satellite-v9 style):
_MAPBOX_URL = "https://api.mapbox.com/styles/v1/mapbox/satellite-v9/static/{lon},{lat},{zoom}/{width}x{height}"
# Params: ?access_token={token}
# Note: Mapbox uses lon,lat order (NOT lat,lon)

class MapboxSatelliteProvider(ImageProvider):
    def __init__(self, access_token: str) -> None: ...
    async def fetch(self, *, latitude: float, longitude: float, zoom: int = 18,
                    width: int = 800, height: int = 600) -> bytes | None:
        url = _MAPBOX_URL.format(lon=longitude, lat=latitude, zoom=zoom, width=width, height=height)
        # GET with ?access_token=...
        # Returns PNG bytes or None on any error

class GoogleSatelliteProvider(ImageProvider):
    # mirrors existing server.py capture_satellite logic
    # URL: _GOOGLE_STATIC_URL with maptype=satellite

class GoogleStreetViewProvider(ImageProvider):
    # mirrors existing server.py capture_street_view logic
    # URL: _GOOGLE_STREETVIEW_URL

class ProviderChain:
    """Try providers in order; return first successful bytes."""
    def __init__(self, providers: list[ImageProvider]) -> None: ...
    async def fetch(self, **kwargs) -> bytes | None:
        for p in self._providers:
            try:
                result = await p.fetch(**kwargs)
                if result:
                    return result
            except Exception:
                continue
        return None
```

- **IMPORTS**: `from abc import ABC, abstractmethod`, `import httpx`, `import structlog`
- **GOTCHA**: Mapbox uses **longitude, latitude** order in URL path (opposite of Google which uses `lat,lng` in params). Do NOT swap these.
- **GOTCHA**: Mapbox free tier returns `{"message": "Not Authorized"}` JSON (not HTTP 401) when token is invalid — check `response.headers["content-type"]`; if JSON, treat as failure
- **VALIDATE**: `python -c "from aloha.mcp_servers.image_capture.providers import ProviderChain; print('ok')"`

---

### Task 2: CREATE `src/aloha/core/embeddings.py`

- **IMPLEMENT**: Single async function for OpenAI text embeddings

```python
async def embed_text(text: str) -> list[float] | None:
    """Embed text using OpenAI text-embedding-3-small (1536 dims).
    Returns None if openai_api_key not configured or on any error.
    """
    from aloha.config import settings
    if not settings.openai_api_key:
        return None
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        resp = await client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
            dimensions=1536,
        )
        return resp.data[0].embedding
    except Exception as exc:
        log.warning("embedding_failed", error=str(exc))
        return None
```

- **IMPORTS**: `import structlog`; deferred `from openai import AsyncOpenAI`; `from aloha.config import settings`
- **GOTCHA**: `dimensions=1536` must be explicit — `text-embedding-3-small` defaults to 1536 but being explicit avoids breakage if defaults change. Must match `DocumentChunk.embedding` column which is `vector(1536)`.
- **GOTCHA**: pgvector's `Vector` type in SQLAlchemy needs a plain Python `list[float]`, not a numpy array. `resp.data[0].embedding` already returns `list[float]`.
- **VALIDATE**: `python -c "from aloha.core.embeddings import embed_text; print('ok')"`

---

### Task 3: UPDATE `src/aloha/config.py`

- **ADD** after `google_maps_api_key` line (line 73):
```python
mapbox_api_key: str | None = None                 # Mapbox Static Images API (free tier)
```
- **VALIDATE**: `python -c "from aloha.config import settings; print(settings.mapbox_api_key)"`

---

### Task 4: CREATE `src/aloha/db/repositories/image.py`

- **IMPLEMENT**: Two repositories

```python
class PropertyImageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_parcel(self, parcel_id: str) -> Sequence[PropertyImage]:
        result = await self._session.execute(
            sa_select(PropertyImage).where(PropertyImage.parcel_id == parcel_id)
        )
        return result.scalars().all()

    async def upsert(self, image: PropertyImage) -> PropertyImage:
        return await self._session.merge(image)


class DocumentChunkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, chunk: DocumentChunk) -> DocumentChunk:
        self._session.add(chunk)
        await self._session.flush()
        return chunk

    async def get_by_parcel(self, parcel_id: str) -> Sequence[DocumentChunk]:
        result = await self._session.execute(
            sa_select(DocumentChunk).where(DocumentChunk.parcel_id == parcel_id)
        )
        return result.scalars().all()

    async def search_similar(
        self,
        query_embedding: list[float],
        *,
        limit: int = 10,
        parcel_id: str | None = None,
    ) -> Sequence[DocumentChunk]:
        """Cosine similarity search via pgvector."""
        try:
            from pgvector.sqlalchemy import Vector
        except ImportError:
            return []
        stmt = (
            sa_select(DocumentChunk)
            .order_by(DocumentChunk.embedding.cosine_distance(query_embedding))
            .limit(limit)
        )
        if parcel_id:
            stmt = stmt.where(DocumentChunk.parcel_id == parcel_id)
        result = await self._session.execute(stmt)
        return result.scalars().all()
```

- **IMPORTS**: `from sqlalchemy import select as sa_select`, `from sqlalchemy.ext.asyncio import AsyncSession`, `from sqlalchemy.engine import Sequence`; `from aloha.db.models.property_image import PropertyImage`; `from aloha.db.models.document_chunk import DocumentChunk`
- **GOTCHA**: `DocumentChunk.embedding.cosine_distance(...)` requires the column to be a `pgvector.sqlalchemy.Vector` type. The fallback `JSON` type won't have this method. Wrap in try/except ImportError and return `[]` if pgvector not installed.
- **VALIDATE**: `python -c "from aloha.db.repositories.image import PropertyImageRepository, DocumentChunkRepository; print('ok')"`

---

### Task 5: UPDATE `src/aloha/mcp_servers/image_capture/server.py`

- **REPLACE** `capture_satellite` (lines 198–241) to use `ProviderChain`:

```python
async def capture_satellite(self, parcel_id, latitude, longitude, zoom=18, width=800, height=600):
    from aloha.mcp_servers.image_capture.providers import (
        MapboxSatelliteProvider, GoogleSatelliteProvider, ProviderChain,
    )
    from aloha.config import settings

    providers = []
    if settings.mapbox_api_key:
        providers.append(MapboxSatelliteProvider(access_token=settings.mapbox_api_key))
    if self._google_api_key:
        providers.append(GoogleSatelliteProvider(api_key=self._google_api_key))

    if not providers:
        return {"error": "No satellite image provider configured (set MAPBOX_API_KEY or GOOGLE_MAPS_API_KEY)", "parcel_id": parcel_id}

    chain = ProviderChain(providers)
    png_bytes = await chain.fetch(latitude=latitude, longitude=longitude, zoom=zoom, width=width, height=height)

    if not png_bytes:
        return {"error": "All satellite providers failed", "parcel_id": parcel_id}

    await _save_image(parcel_id, "satellite", png_bytes, "image/png", source_url="multi_provider")
    return {"parcel_id": parcel_id, "image_type": "satellite", "size_bytes": len(png_bytes), "data_b64": base64.b64encode(png_bytes).decode(), "mime_type": "image/png"}
```

- **REPLACE** `capture_street_view` (lines 155–196) to use `GoogleStreetViewProvider` from providers:
  - Import `GoogleStreetViewProvider` from `providers.py`
  - If no Google key: return graceful error (same as current)
  - This is mostly a refactor to keep logic in the provider class

- **VALIDATE**: `python -c "from aloha.mcp_servers.image_capture.server import ImageCaptureMCPServer; print('ok')"`

---

### Task 6: CREATE `src/aloha/agents/enrichment/prompts.py`

- **IMPLEMENT**: `PropertyConditionReport` Pydantic model + system prompt

```python
from pydantic import BaseModel, Field

class PropertyConditionReport(BaseModel):
    """Structured property condition extracted from satellite/street view images."""
    occupancy_status: str = Field(
        description="Likely occupancy: occupied | vacant | abandoned | unknown"
    )
    structural_condition: str = Field(
        description="Structural condition: excellent | good | fair | poor | severe_distress | unknown"
    )
    lot_condition: str = Field(
        description="Lot/yard condition: well_maintained | average | overgrown | debris | unknown"
    )
    property_type_confirmed: str = Field(
        description="Confirmed property type from visual: single_family | multi_family | commercial | land | industrial | unknown"
    )
    visible_issues: list[str] = Field(
        default_factory=list,
        description="List of observable issues: roof_damage, broken_windows, overgrown_vegetation, fire_damage, flood_damage, graffiti, boarded_up, etc."
    )
    neighborhood_context: str = Field(
        default="",
        description="Brief description of surrounding neighborhood (1-2 sentences)"
    )
    confidence: float = Field(
        default=0.0,
        description="Analyst confidence 0.0-1.0 based on image clarity and completeness"
    )
    summary: str = Field(
        default="",
        description="1-2 sentence human-readable condition summary for the investment memo"
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
    addr_str = f" at {address}" for a in [address] if a else ""
    return (
        f"Analyze the provided image(s) of parcel {parcel_id}{addr_str}. "
        f"Images available: {', '.join(image_types)}. "
        "Extract the property condition report."
    )
```

- **GOTCHA**: The `for a in [address] if a else ""` walrus trick is a typo above — use `f" at {address}" if address else ""`
- **VALIDATE**: `python -c "from aloha.agents.enrichment.prompts import PropertyConditionReport, VISION_SYSTEM_PROMPT; print('ok')"`

---

### Task 7: CREATE `src/aloha/agents/enrichment/agent.py`

- **IMPLEMENT**: `EnrichmentAgent(BaseAgent)` — full vision analysis pipeline

**`run()` context keys expected:**
- `parcel_id` (required)
- `state` (optional, for logging)
- `county` (optional, for logging)

**`run()` flow:**
1. Load `Parcel` from DB (need `address`, `latitude`, `longitude`)
2. Trigger image capture via `ImageCaptureMCPServer`:
   - If `latitude` and `longitude` set: call `capture_satellite`
   - If `address` set: call `capture_street_view` (skips gracefully if no Google key)
3. Load `PropertyImage` records back from DB
4. If no images captured: return early with `{"status": "no_images"}`
5. Pick best image for analysis (prefer `street_view` > `satellite` > `gis_parcel_map`)
6. Decode image from data URI: `data_uri.split(",", 1)[1]` → `base64.b64decode(...)` → bytes
7. Call LLM with image via pydantic-ai `Agent` with `result_type=PropertyConditionReport`
8. Build condition text: `json.dumps(report.model_dump(), indent=2)`
9. Get embedding: `await embed_text(report.summary)` (may return None)
10. Save `DocumentChunk`:
    ```python
    DocumentChunk(
        parcel_id=parcel_id,
        source_type="vision_analysis",
        source_url=selected_image.source_url,
        content=condition_text,
        embedding=embedding,  # None OK if no openai key
        created_at=datetime.now(tz=timezone.utc),
    )
    ```
11. Advance parcel `research_status` to `"enriched"` via `parcel_repo.update_status()`
12. Enqueue `scoring` agent

**Note on LLM vision call:**
```python
from pydantic_ai import Agent
from pydantic_ai.messages import BinaryContent

vision_agent: Agent[None, PropertyConditionReport] = Agent(
    model,
    result_type=PropertyConditionReport,
    system_prompt=VISION_SYSTEM_PROMPT,
)
result = await vision_agent.run(
    [
        build_vision_task(parcel_id, parcel.address, [img.image_type for img in images]),
        BinaryContent(data=image_bytes, media_type=selected_image_mime_type),
    ]
)
condition: PropertyConditionReport = result.data
```

- **GOTCHA**: `pydantic_ai.messages.BinaryContent` is the correct import path. Do NOT use `ImageContent` — that was renamed in pydantic-ai 0.0.30+.
- **GOTCHA**: Only models that support vision (Claude 3.5 Sonnet / GPT-4V / GPT-4o) can handle `BinaryContent`. If the configured model doesn't support vision, pydantic-ai will raise. Wrap in try/except and fall back to text-only description.
- **GOTCHA**: The data URI format is `"data:{mime_type};base64,{b64data}"`. Split on `","` and take index 1 to get the base64 portion, then `base64.b64decode(b64_portion)` → bytes.
- **GOTCHA**: When `research_status` is already `"enriched"` or beyond, skip re-processing. Check `parcel.research_status` before running.
- **GOTCHA**: Import `ImageCaptureMCPServer` inside `run()` (deferred import) to avoid circular import since `server.py` imports from `aloha.db`.
- **VALIDATE**: `python -c "from aloha.agents.enrichment.agent import agent; print('ok')"`

---

### Task 8: UPDATE `src/aloha/agents/parcel_research/agent.py`

- **ADD** at the end of `run()`, after the existing `enqueue("owner_research")` call, enqueue `enrichment` in parallel:
```python
# Trigger image capture + vision analysis (non-blocking, lower priority)
await queue_repo.enqueue(
    agent_name="enrichment",
    stage="enrich",
    parcel_id=parcel_id,
    payload={"parcel_id": parcel_id, "state": state, "county": county},
    priority=8,  # lower priority than owner/entity research
)
```

- **PATTERN**: Existing `enqueue("owner_research")` call in `parcel_research/agent.py` (look for it in the agent's run method — it calls `queue_repo.enqueue()` with `agent_name="owner_research"`)
- **GOTCHA**: This enqueues enrichment in PARALLEL with `owner_research`, not sequentially after scoring. Enrichment is independent of the owner/entity pipeline.
- **VALIDATE**: `python -c "from aloha.agents.parcel_research.agent import agent; print('ok')"`

---

### Task 9: UPDATE `src/aloha/agents/__init__.py`

- **ADD** to `AGENT_REGISTRY` dict:
```python
"enrichment": "aloha.agents.enrichment.agent",
```
- **VALIDATE**: `python -c "from aloha.agents import AGENT_REGISTRY; assert 'enrichment' in AGENT_REGISTRY; print('ok')"`

---

### Task 10: UPDATE `src/aloha/api/schemas/parcels.py`

- **ADD** new schema class after `ScoreOut`:
```python
class PropertyImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    image_type: str
    file_path: str          # data URI or S3 URL
    source_url: str | None
    width: int | None
    height: int | None
    captured_at: datetime
```

- **UPDATE** `ParcelDetail` to add:
```python
images: list[PropertyImageOut] = []
condition_summary: str | None = None  # from DocumentChunk vision analysis
```

- **IMPORTS**: `from datetime import datetime`; `from pydantic import ConfigDict` (already imported in this file)
- **PATTERN**: `ScoreOut` and `TaxLienOut` in the same file for `from_attributes=True` pattern
- **VALIDATE**: `python -c "from aloha.api.schemas.parcels import PropertyImageOut, ParcelDetail; print('ok')"`

---

### Task 11: UPDATE `src/aloha/api/routes/parcels.py`

- **UPDATE** `GET /parcels/{parcel_id}` handler to load images and condition summary:

```python
# After loading parcel, owners, scores:
from aloha.db.repositories.image import PropertyImageRepository, DocumentChunkRepository

image_repo = PropertyImageRepository(session)
images = await image_repo.get_by_parcel(parcel_id)

# Get latest vision analysis summary from document_chunks
chunk_repo = DocumentChunkRepository(session)
chunks = await chunk_repo.get_by_parcel(parcel_id)
vision_chunks = [c for c in chunks if c.source_type == "vision_analysis"]
condition_summary = vision_chunks[-1].content if vision_chunks else None

# Build ParcelDetail with images
detail = ParcelDetail(
    ...,
    images=[PropertyImageOut.model_validate(img) for img in images],
    condition_summary=condition_summary,
)
```

- **PATTERN**: Existing repository usage in the `GET /parcels/{parcel_id}` handler (read the file before implementing)
- **GOTCHA**: `session` in the route handler comes from `Depends(get_session)` injection. Pass it to `PropertyImageRepository(session)` directly.
- **VALIDATE**: `python -c "from aloha.api.routes.parcels import router; print('ok')"`

---

### Task 12: UPDATE `src/aloha/agents/report/agent.py`

- **ADD** in the `run()` method, after loading parcel data, fetch condition summary from DocumentChunks:
```python
from aloha.db.repositories.image import DocumentChunkRepository
chunk_repo = DocumentChunkRepository(session)
chunks = await chunk_repo.get_by_parcel(parcel_id)
vision_chunks = [c for c in chunks if c.source_type == "vision_analysis"]
condition_summary = vision_chunks[-1].content if vision_chunks else None
```
- **ADD** `"property_condition": condition_summary` to the report dict that gets passed to the LLM narrative builder.
- **PATTERN**: Existing data loading in `report/agent.py` `run()` method
- **VALIDATE**: `python -c "from aloha.agents.report.agent import agent; print('ok')"`

---

### Task 13: CREATE `tests/agents/test_enrichment_agent.py`

- **IMPLEMENT** test class `TestEnrichmentAgent`:

  - `test_condition_report_fields` — Instantiate `PropertyConditionReport` with known data; assert all fields present
  - `test_data_uri_decode` — Given `"data:image/jpeg;base64,{b64}"`, assert decode produces original bytes
  - `test_agent_skips_when_no_images` — Mock DB returning no `PropertyImage` records; assert `run()` returns `{"status": "no_images"}`
  - `test_agent_returns_enriched_on_success` — Mock DB with one image + mock LLM returning valid `PropertyConditionReport`; assert `research_status` set to `"enriched"` and `DocumentChunk.add()` called once
  - `test_provider_chain_skips_failed_provider` — Two providers: first raises, second returns bytes; assert second provider result returned
  - `test_mapbox_uses_lon_lat_order` — Mock httpx; assert Mapbox URL contains `{lon},{lat}` (not `{lat},{lon}`)
  - `test_embed_text_returns_none_without_key` — Call `embed_text("test")` with no openai_api_key in settings; assert returns None

- **PATTERN**: `tests/agents/test_scoring_models.py` — class structure, pytest.mark.asyncio, no external deps
- **VALIDATE**: `python -m pytest tests/agents/test_enrichment_agent.py -v`

---

## TESTING STRATEGY

### Unit Tests

All tests in `tests/agents/test_enrichment_agent.py`. No DB, no network, no real LLM.

- `PropertyConditionReport` model validation
- Data URI → bytes decode logic (pure Python, no deps)
- `ProviderChain` fallback logic (mock httpx)
- `EnrichmentAgent.run()` with mocked DB + mocked LLM
- `embed_text()` graceful None return
- Mapbox URL lon/lat ordering

### Edge Cases

- No image providers configured → return graceful error, no crash
- LLM doesn't support vision (e.g. ollama with non-vision model) → catch exception, store text fallback
- Data URI is malformed or empty → return graceful `{"status": "no_images"}`
- OpenAI API down → `embed_text()` returns None; `DocumentChunk` stored with `embedding=None` (allowed by schema)
- Parcel has no `latitude`/`longitude` set → skip `capture_satellite`, still try `capture_street_view` with address
- Parcel has no `address` set → skip `capture_street_view`, still try `capture_satellite`

---

## VALIDATION COMMANDS

### Level 1: Syntax Check
```bash
python -c "
import ast, os, sys
files = [
    'src/aloha/mcp_servers/image_capture/providers.py',
    'src/aloha/core/embeddings.py',
    'src/aloha/agents/enrichment/agent.py',
    'src/aloha/agents/enrichment/prompts.py',
    'src/aloha/db/repositories/image.py',
    'src/aloha/config.py',
    'src/aloha/api/schemas/parcels.py',
    'src/aloha/api/routes/parcels.py',
    'src/aloha/agents/__init__.py',
    'tests/agents/test_enrichment_agent.py',
]
errors = [f for f in files if not ast.parse(open(f).read()) or False]
print('Syntax OK' if not errors else errors)
"
```

### Level 2: Import Smoke Tests
```bash
python -c "
import sys; sys.path.insert(0, 'src')
from aloha.mcp_servers.image_capture.providers import ProviderChain; print('providers ok')
from aloha.core.embeddings import embed_text; print('embeddings ok')
from aloha.agents.enrichment.agent import agent; print('enrichment_agent ok')
from aloha.agents.enrichment.prompts import PropertyConditionReport; print('condition_report ok')
from aloha.db.repositories.image import PropertyImageRepository, DocumentChunkRepository; print('repos ok')
from aloha.api.schemas.parcels import PropertyImageOut, ParcelDetail; print('schemas ok')
from aloha.agents import AGENT_REGISTRY; assert 'enrichment' in AGENT_REGISTRY; print('registry ok')
"
```

### Level 3: Unit Tests
```bash
python -m pytest tests/agents/test_enrichment_agent.py -v --tb=short
```

### Level 4: Full Test Suite (regression check)
```bash
python -m pytest tests/ -v --tb=short
```

### Level 5: Manual API validation (requires running server)
```bash
# Trigger parcel research which now also enqueues enrichment
curl -X POST http://localhost:8000/run \
  -H "Authorization: Bearer {token}" \
  -d '{"state": "FL", "county": "orange"}'

# After enrichment runs, check detail endpoint for images
curl http://localhost:8000/parcels/{parcel_id} \
  -H "Authorization: Bearer {token}" | jq '.images, .condition_summary'
```

---

## ACCEPTANCE CRITERIA

- [ ] `capture_satellite` succeeds when only `MAPBOX_API_KEY` is set (no Google key needed)
- [ ] `capture_satellite` falls back to Google if Mapbox returns no bytes
- [ ] `capture_satellite` returns graceful error (no crash) if neither provider is configured
- [ ] `EnrichmentAgent.run()` calls `capture_satellite` when parcel has lat/lon
- [ ] `EnrichmentAgent.run()` calls `capture_street_view` when parcel has address and Google key
- [ ] `PropertyConditionReport` stored as `DocumentChunk` with `source_type="vision_analysis"`
- [ ] `DocumentChunk.embedding` is populated when `OPENAI_API_KEY` is set, `None` otherwise
- [ ] `GET /parcels/{parcel_id}` response includes `images` array and `condition_summary`
- [ ] `"enrichment"` is in `AGENT_REGISTRY`
- [ ] `parcel_research` agent enqueues `enrichment` after completing
- [ ] All import smoke tests pass
- [ ] `tests/agents/test_enrichment_agent.py` passes with no failures
- [ ] No regressions in `tests/agents/test_scoring_models.py` and `tests/scrapers/`

---

## COMPLETION CHECKLIST

- [ ] Task 1: `providers.py` created; Mapbox URL lon/lat ordering verified
- [ ] Task 2: `core/embeddings.py` created; returns None without openai key
- [ ] Task 3: `config.py` updated with `mapbox_api_key`
- [ ] Task 4: `db/repositories/image.py` created with both repos
- [ ] Task 5: `server.py` `capture_satellite` refactored to use ProviderChain
- [ ] Task 6: `enrichment/prompts.py` created
- [ ] Task 7: `enrichment/agent.py` created and imports cleanly
- [ ] Task 8: `parcel_research/agent.py` enqueues enrichment
- [ ] Task 9: `AGENT_REGISTRY` updated
- [ ] Task 10: `PropertyImageOut` + `ParcelDetail.images` added to schemas
- [ ] Task 11: `GET /parcels/{parcel_id}` loads and returns images + condition_summary
- [ ] Task 12: `report/agent.py` includes condition_summary in report data
- [ ] Task 13: `test_enrichment_agent.py` created and all tests pass
- [ ] All Level 1–4 validation commands executed and passing

---

## NOTES

### Why Mapbox over Bing/ESRI for the free satellite tier?

- **Bing Maps Static**: Not appropriate for commercial use without Enterprise license
- **ESRI ArcGIS Online**: Requires auth token; tile usage billed per transaction above free tier
- **Mapbox**: 50,000 free Static Image requests/month, commercial OK, no credit card required for free tier, satellite imagery (`satellite-v9` style) is high-quality

### Why not embed raw image tiles for RAG?

Raw raster tiles don't embed meaningfully for text-based semantic search. A multimodal embedding (like CLIP) could embed images but:
1. CLIP embeddings use 512 dims — doesn't match the existing `vector(1536)` column
2. CLIP embeddings for satellite tiles search by *visual similarity*, not by *investor-relevant properties*
3. The investment questions ("is this abandoned?", "what's the structural condition?") are better answered by LLM vision analysis → text description → text embedding

**The correct RAG pattern is: image → LLM vision → text description → text embedding → pgvector.** Not: image → image embedding → pgvector.

### Trade-offs

| Approach | Cost | Quality | RAG-able |
|---|---|---|---|
| Google Maps only | ~$2/1k satellite + $7/1k street view | High | No (raw images) |
| Mapbox free + Google fallback | Free for <50k/month | High | No (raw images) |
| Vision analysis → DocumentChunk | LLM cost only | Analysis-dependent | ✅ Yes |
| **This plan (combined)** | Mapbox free + LLM token cost | High | ✅ Yes |

### pydantic-ai Vision Message Format

As of pydantic-ai 0.0.36+, the correct import is:
```python
from pydantic_ai.messages import BinaryContent
```
If that import fails (older version), try:
```python
from pydantic_ai import BinaryContent
```
Always check the installed version's API before implementing Task 7.

**Confidence Score: 7.5/10**

High confidence because all integration points are traced to exact line numbers and all model/schema field names are verified. Risk factors:
- pydantic-ai vision API may differ slightly from documented pattern (`BinaryContent` import path)
- `DocumentChunk.embedding.cosine_distance()` requires pgvector installed — graceful fallback is planned but should be tested
- `parcel_research/agent.py` internals not fully read in this plan; need to verify exact location to add the enrichment enqueue call
