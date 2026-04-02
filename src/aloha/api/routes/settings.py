"""User settings routes — BYOK API key management and LLM preferences."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from aloha.api.deps import get_db, require_user
from aloha.api.schemas.settings import (
    ApiKeysResponse,
    DeleteApiKeyRequest,
    LlmPreferenceRequest,
    LlmStatusResponse,
    MessageResponse,
    SaveApiKeyRequest,
)
from aloha.services.api_key_service import ApiKeyService

router = APIRouter(prefix="/settings", tags=["settings"])


def _api_key_service(db: AsyncSession = Depends(get_db)) -> ApiKeyService:
    return ApiKeyService(db)


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

    # Check if a server-level LLM is available
    has_server_llm = get_model() is not None

    return LlmStatusResponse(
        has_user_key=has_user_key,
        has_server_llm=has_server_llm,
        server_provider=settings.llm_provider if has_server_llm else None,
    )
