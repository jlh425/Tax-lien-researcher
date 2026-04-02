"""Pydantic schemas for the BYOK settings endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Provider = Literal["anthropic", "openai", "groq", "ollama"]


# ── Requests ──────────────────────────────────────────────────────────────────


class SaveApiKeyRequest(BaseModel):
    provider: Provider
    api_key: str = Field(min_length=10)


class LlmPreferenceRequest(BaseModel):
    provider: Provider
    model: str = Field(min_length=1, max_length=120)
    base_url: str | None = Field(default=None, max_length=500)


class DeleteApiKeyRequest(BaseModel):
    provider: Provider


# ── Responses ─────────────────────────────────────────────────────────────────


class MaskedKeyOut(BaseModel):
    provider: str
    masked_key: str


class ApiKeysResponse(BaseModel):
    keys: list[MaskedKeyOut]
    llm_provider: str | None = None
    llm_model: str | None = None
    ollama_base_url: str | None = None


class MessageResponse(BaseModel):
    message: str


class LlmStatusResponse(BaseModel):
    has_user_key: bool
    has_server_llm: bool
    server_provider: str | None = None
