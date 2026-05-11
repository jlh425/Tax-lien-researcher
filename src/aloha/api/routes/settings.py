"""User settings routes — BYOK API key management and LLM preferences."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from aloha.api.deps import get_db, require_user
from aloha.api.schemas.settings import (
    AddLlmRequest,
    AddLlmResponse,
    ApiKeysResponse,
    ConfiguredLlmOut,
    ConfiguredLlmsResponse,
    DeleteApiKeyRequest,
    DeleteLlmRequest,
    LlmPreferenceRequest,
    LlmStatusResponse,
    MessageResponse,
    SaveApiKeyRequest,
    ScoringWeightsSchema,
    SetActiveLlmRequest,
    TestLlmRequest,
    TestLlmResponse,
    UserApiKeysSchema,
    UserPreferencesRequest,
    UserPreferencesResponse,
)
from aloha.db.repositories.user_preferences import UserPreferencesRepository
from aloha.services.api_key_service import ApiKeyService

router = APIRouter(prefix="/settings", tags=["settings"])


def _api_key_service(db: AsyncSession = Depends(get_db)) -> ApiKeyService:
    return ApiKeyService(db)


def _preferences_repo(
    db: AsyncSession = Depends(get_db),
) -> UserPreferencesRepository:
    return UserPreferencesRepository(db)


@router.get("/api-keys", response_model=ApiKeysResponse)
async def list_api_keys(
    user: Any = Depends(require_user),
    svc: ApiKeyService = Depends(_api_key_service),
) -> ApiKeysResponse:
    """Return masked previews of the user's stored API keys."""
    data = await svc.get_keys_masked(user.id)
    return ApiKeysResponse(**data)


@router.post("/api-keys", response_model=MessageResponse)
async def save_api_key(
    body: SaveApiKeyRequest,
    user: Any = Depends(require_user),
    svc: ApiKeyService = Depends(_api_key_service),
) -> MessageResponse:
    """Encrypt and store an API key for the given provider."""
    await svc.save_key(user.id, body.provider, body.api_key)
    return MessageResponse(message=f"{body.provider} API key saved")


@router.delete("/api-keys", response_model=MessageResponse)
async def delete_api_key(
    body: DeleteApiKeyRequest,
    user: Any = Depends(require_user),
    svc: ApiKeyService = Depends(_api_key_service),
) -> MessageResponse:
    """Remove a stored API key for the given provider."""
    await svc.delete_key(user.id, body.provider)
    return MessageResponse(message=f"{body.provider} API key removed")


@router.put("/llm-preference", response_model=MessageResponse)
async def set_llm_preference(
    body: LlmPreferenceRequest,
    user: Any = Depends(require_user),
    svc: ApiKeyService = Depends(_api_key_service),
) -> MessageResponse:
    """Set the user's preferred LLM provider and model."""
    await svc.save_llm_preference(user.id, body.provider, body.model, body.base_url)
    return MessageResponse(message=f"LLM preference set to {body.provider}/{body.model}")


@router.get("/llm-status", response_model=LlmStatusResponse)
async def llm_status(
    user: Any = Depends(require_user),
    svc: ApiKeyService = Depends(_api_key_service),
) -> LlmStatusResponse:
    """Check whether the user (or server) has a usable LLM configured."""
    from aloha.config import settings
    from aloha.core.llm import get_model

    # Check if the user has their own key or Ollama configured
    data = await svc.get_keys_masked(user.id)
    has_user_key = len(data["keys"]) > 0 or data.get("llm_provider") == "ollama"

    # Also consider configured_llms as having a user key
    configured = await svc.get_configured_llms(user.id)
    if configured:
        has_user_key = True

    # Check if a server-level LLM is available
    has_server_llm = get_model() is not None

    return LlmStatusResponse(
        has_user_key=has_user_key,
        has_server_llm=has_server_llm,
        server_provider=settings.llm_provider if has_server_llm else None,
    )


# ── Configured LLMs (unified flow) ──────────────────────────────────────────


@router.post("/test-llm", response_model=TestLlmResponse)
async def test_llm(
    body: TestLlmRequest,
    user: Any = Depends(require_user),
    svc: ApiKeyService = Depends(_api_key_service),
) -> TestLlmResponse:
    """Test an LLM connection with a tiny completion call."""
    # For cloud providers, allow omitting api_key if one is already stored
    api_key = body.api_key
    if not api_key and body.provider != "ollama":
        api_key = await svc.get_decrypted_key(user.id, body.provider)
        if not api_key:
            return TestLlmResponse(
                success=False,
                message=f"No API key provided or stored for {body.provider}",
            )

    success, message, response_text = await svc.test_llm_connection(
        body.provider, body.model, api_key, body.base_url,
    )
    return TestLlmResponse(
        success=success, message=message, response_text=response_text,
    )


@router.get("/configured-llms", response_model=ConfiguredLlmsResponse)
async def list_configured_llms(
    user: Any = Depends(require_user),
    svc: ApiKeyService = Depends(_api_key_service),
) -> ConfiguredLlmsResponse:
    """List the user's configured LLMs with masked keys and active status."""
    llms = await svc.get_configured_llms(user.id)
    return ConfiguredLlmsResponse(
        llms=[ConfiguredLlmOut(**entry) for entry in llms],
    )


@router.post("/configured-llms", response_model=AddLlmResponse)
async def add_configured_llm(
    body: AddLlmRequest,
    user: Any = Depends(require_user),
    svc: ApiKeyService = Depends(_api_key_service),
) -> AddLlmResponse:
    """Add a tested LLM configuration (also saves key if provided)."""
    # For cloud providers, allow omitting api_key if one is already stored
    api_key = body.api_key
    if not api_key and body.provider != "ollama":
        existing = await svc.get_decrypted_key(user.id, body.provider)
        if not existing:
            raise ValueError(f"No API key provided or stored for {body.provider}")

    entry = await svc.add_configured_llm(
        user.id, body.provider, body.model, api_key, body.base_url,
    )

    # Build masked key for response
    masked_key: str | None = None
    if api_key and body.provider != "ollama":
        from aloha.services.api_key_service import _mask_key

        masked_key = _mask_key(api_key)
    elif body.provider != "ollama":
        existing = await svc.get_decrypted_key(user.id, body.provider)
        if existing:
            from aloha.services.api_key_service import _mask_key

            masked_key = _mask_key(existing)

    return AddLlmResponse(
        message=f"{body.provider}/{body.model} added",
        llm=ConfiguredLlmOut(
            id=entry["id"],
            provider=entry["provider"],
            model=entry["model"],
            base_url=entry.get("base_url"),
            masked_key=masked_key,
            is_active=True,  # first or auto-activated
            added_at=entry["added_at"],
        ),
    )


@router.put("/configured-llms/active", response_model=MessageResponse)
async def set_active_llm(
    body: SetActiveLlmRequest,
    user: Any = Depends(require_user),
    svc: ApiKeyService = Depends(_api_key_service),
) -> MessageResponse:
    """Switch the active configured LLM."""
    await svc.set_active_llm(user.id, body.llm_id)
    return MessageResponse(message="Active LLM updated")


@router.delete("/configured-llms", response_model=MessageResponse)
async def delete_configured_llm(
    body: DeleteLlmRequest,
    user: Any = Depends(require_user),
    svc: ApiKeyService = Depends(_api_key_service),
) -> MessageResponse:
    """Remove a configured LLM. Auto-promotes next if active was deleted."""
    await svc.delete_configured_llm(user.id, body.llm_id)
    return MessageResponse(message="Configured LLM removed")


# ── User Preferences (scoring weights / external API keys) ───────────────────

_DEFAULT_WEIGHTS = ScoringWeightsSchema()
_DEFAULT_API_KEYS = UserApiKeysSchema()


@router.get("/preferences", response_model=UserPreferencesResponse)
async def get_preferences(
    user: Any = Depends(require_user),
    repo: UserPreferencesRepository = Depends(_preferences_repo),
) -> UserPreferencesResponse:
    """Return the current user's scoring weights and API keys."""
    prefs = await repo.get_by_user_id(user.id)
    if prefs is None:
        return UserPreferencesResponse(
            scoring_weights=_DEFAULT_WEIGHTS,
            api_keys=_DEFAULT_API_KEYS,
            include_screenshots=True,
        )
    return UserPreferencesResponse(
        scoring_weights=ScoringWeightsSchema(**prefs.scoring_weights),
        api_keys=UserApiKeysSchema(**prefs.api_keys),
        include_screenshots=prefs.scoring_weights.get(
            "include_screenshots", True
        ),
    )


@router.put("/preferences", response_model=UserPreferencesResponse)
async def update_preferences(
    body: UserPreferencesRequest,
    user: Any = Depends(require_user),
    repo: UserPreferencesRepository = Depends(_preferences_repo),
) -> UserPreferencesResponse:
    """Create or update scoring weights and/or API keys for the current user."""
    scoring_weights: dict | None = None
    if body.scoring_weights is not None:
        scoring_weights = body.scoring_weights.model_dump()
    # Persist include_screenshots inside the scoring_weights blob
    if body.include_screenshots is not None:
        if scoring_weights is None:
            # Load existing weights so we don't clobber them
            existing = await repo.get_by_user_id(user.id)
            scoring_weights = (
                dict(existing.scoring_weights) if existing else {}
            )
        scoring_weights["include_screenshots"] = body.include_screenshots

    api_keys: dict | None = None
    if body.api_keys is not None:
        api_keys = body.api_keys.model_dump(exclude_none=True)

    prefs = await repo.upsert(
        user.id, scoring_weights=scoring_weights, api_keys=api_keys
    )

    return UserPreferencesResponse(
        scoring_weights=ScoringWeightsSchema(
            **{
                k: v
                for k, v in prefs.scoring_weights.items()
                if k != "include_screenshots"
            }
        ),
        api_keys=UserApiKeysSchema(**prefs.api_keys),
        include_screenshots=prefs.scoring_weights.get(
            "include_screenshots", True
        ),
    )
