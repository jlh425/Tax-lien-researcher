"""CRUD service for per-user LLM API keys stored in User.settings JSONB."""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone
from uuid import UUID

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from aloha.core.crypto import decrypt, encrypt
from aloha.db.models.user import User
from aloha.services.base import BaseService

log = structlog.get_logger().bind(service="ApiKeyService")

# Prefix validation — quick sanity check, not exhaustive.
_PROVIDER_PREFIXES: dict[str, list[str]] = {
    "anthropic": ["sk-ant-"],
    "openai": ["sk-"],
    "groq": ["gsk_"],
}


def _mask_key(key: str) -> str:
    """Return first 7 + last 4 characters with dots in between."""
    if len(key) <= 11:
        return key[:3] + "..." + key[-2:]
    return key[:7] + "..." + key[-4:]


class ApiKeyService(BaseService):
    """Manage encrypted LLM API keys inside ``User.settings``."""

    async def _get_user(self, user_id: UUID) -> User:
        user = await self._session.get(User, user_id)
        if user is None:
            raise ValueError(f"User {user_id} not found")
        return user

    async def save_key(self, user_id: UUID, provider: str, api_key: str) -> None:
        """Validate, encrypt, and store an API key for *provider*."""
        prefixes = _PROVIDER_PREFIXES.get(provider, [])
        if prefixes and not any(api_key.startswith(p) for p in prefixes):
            expected = " or ".join(f"'{p}'" for p in prefixes)
            raise ValueError(
                f"Invalid {provider} API key — expected prefix {expected}"
            )

        user = await self._get_user(user_id)
        settings = dict(user.settings)  # shallow copy to trigger SA dirty flag
        llm_keys = dict(settings.get("llm_keys", {}))
        llm_keys[provider] = encrypt(api_key)
        settings["llm_keys"] = llm_keys
        user.settings = settings
        await self._session.flush()
        self.log.info("api_key_saved", user_id=str(user_id), provider=provider)

    async def delete_key(self, user_id: UUID, provider: str) -> None:
        """Remove the stored key for *provider*."""
        user = await self._get_user(user_id)
        settings = dict(user.settings)
        llm_keys = dict(settings.get("llm_keys", {}))
        llm_keys.pop(provider, None)
        settings["llm_keys"] = llm_keys
        user.settings = settings
        await self._session.flush()
        self.log.info("api_key_deleted", user_id=str(user_id), provider=provider)

    async def get_keys_masked(self, user_id: UUID) -> dict:
        """Return masked key previews and current LLM preference."""
        user = await self._get_user(user_id)
        llm_keys: dict = user.settings.get("llm_keys", {})
        masked = []
        for provider, ciphertext in llm_keys.items():
            try:
                plaintext = decrypt(ciphertext)
                masked.append({"provider": provider, "masked_key": _mask_key(plaintext)})
            except Exception:
                masked.append({"provider": provider, "masked_key": "***invalid***"})
        return {
            "keys": masked,
            "llm_provider": user.settings.get("llm_provider"),
            "llm_model": user.settings.get("llm_model"),
            "ollama_base_url": user.settings.get("ollama_base_url"),
        }

    async def get_decrypted_key(self, user_id: UUID, provider: str) -> str | None:
        """Return the plaintext key for *provider*, or None if not set.

        Internal use only — never expose via API.
        """
        user = await self._get_user(user_id)
        llm_keys: dict = user.settings.get("llm_keys", {})
        ciphertext = llm_keys.get(provider)
        if not ciphertext:
            return None
        return decrypt(ciphertext)

    async def save_llm_preference(
        self,
        user_id: UUID,
        provider: str,
        model: str,
        base_url: str | None = None,
    ) -> None:
        """Store the user's preferred LLM provider and model."""
        user = await self._get_user(user_id)
        settings = dict(user.settings)
        settings["llm_provider"] = provider
        settings["llm_model"] = model
        if provider == "ollama":
            settings["ollama_base_url"] = base_url or "http://localhost:11434"
        user.settings = settings
        await self._session.flush()
        self.log.info(
            "llm_preference_saved",
            user_id=str(user_id),
            provider=provider,
            model=model,
        )

    # ── Configured LLMs (unified flow) ──────────────────────────────────────

    @staticmethod
    def _sync_active_to_legacy(settings: dict, entry: dict) -> None:
        """Keep legacy flat fields in sync with the active configured LLM."""
        settings["llm_provider"] = entry["provider"]
        settings["llm_model"] = entry["model"]
        if entry["provider"] == "ollama":
            settings["ollama_base_url"] = entry.get(
                "base_url", "http://localhost:11434"
            )
        else:
            settings.pop("ollama_base_url", None)

    async def test_llm_connection(
        self,
        provider: str,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> tuple[bool, str, str | None]:
        """Test an LLM connection with a tiny completion call.

        For Ollama, first checks ``/api/tags`` to verify the model exists.
        Returns ``(success, message, response_text)``.
        """
        from pydantic_ai import Agent

        from aloha.core.llm import _build_model_with_key

        # Ollama: verify model is available via /api/tags
        if provider == "ollama":
            ollama_url = (base_url or "http://localhost:11434").rstrip("/")
            try:
                async with httpx.AsyncClient(timeout=10) as http:
                    resp = await http.get(f"{ollama_url}/api/tags")
                    resp.raise_for_status()
                    tags = resp.json()
                    available = [m["name"] for m in tags.get("models", [])]
                    # Ollama models can have :latest suffix
                    model_matches = [
                        m for m in available
                        if m == model or m.startswith(f"{model}:")
                           or model.startswith(f"{m.split(':')[0]}:")
                    ]
                    if not model_matches:
                        avail_str = ", ".join(available[:10]) or "(none)"
                        return (
                            False,
                            f"Model '{model}' not found. Available: {avail_str}",
                            None,
                        )
            except httpx.ConnectError:
                return (
                    False,
                    f"Cannot connect to Ollama at {ollama_url}. Is Ollama running?",
                    None,
                )
            except Exception as exc:
                return (False, f"Ollama check failed: {exc}", None)

        try:
            llm_model = _build_model_with_key(provider, model, api_key, base_url)
            agent = Agent(llm_model)
            result = await agent.run("Say hello in exactly 5 words.")
            return (True, "Connection successful", result.data)
        except Exception as exc:
            return (False, f"LLM call failed: {exc}", None)

    async def add_configured_llm(
        self,
        user_id: UUID,
        provider: str,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> dict:
        """Save a tested LLM configuration. Returns the new entry dict."""
        user = await self._get_user(user_id)
        settings = dict(user.settings)

        # Save/update the API key if provided
        if api_key:
            llm_keys = dict(settings.get("llm_keys", {}))
            llm_keys[provider] = encrypt(api_key)
            settings["llm_keys"] = llm_keys

        configured: list[dict] = list(settings.get("configured_llms", []))
        entry = {
            "id": str(_uuid.uuid4()),
            "provider": provider,
            "model": model,
            "added_at": datetime.now(timezone.utc).isoformat(),
        }
        if provider == "ollama":
            entry["base_url"] = base_url or "http://localhost:11434"

        configured.append(entry)
        settings["configured_llms"] = configured

        # Auto-activate if this is the first entry
        if len(configured) == 1 or not settings.get("active_llm_id"):
            settings["active_llm_id"] = entry["id"]
            self._sync_active_to_legacy(settings, entry)

        user.settings = settings
        await self._session.flush()
        self.log.info(
            "configured_llm_added",
            user_id=str(user_id),
            llm_id=entry["id"],
            provider=provider,
            model=model,
        )
        return entry

    async def set_active_llm(self, user_id: UUID, llm_id: str) -> None:
        """Switch the active configured LLM."""
        user = await self._get_user(user_id)
        settings = dict(user.settings)
        configured: list[dict] = settings.get("configured_llms", [])
        entry = next((e for e in configured if e["id"] == llm_id), None)
        if entry is None:
            raise ValueError(f"Configured LLM '{llm_id}' not found")
        settings["active_llm_id"] = llm_id
        self._sync_active_to_legacy(settings, entry)
        user.settings = settings
        await self._session.flush()
        self.log.info(
            "active_llm_changed",
            user_id=str(user_id),
            llm_id=llm_id,
        )

    async def delete_configured_llm(self, user_id: UUID, llm_id: str) -> None:
        """Remove a configured LLM. Auto-promotes next if active was deleted."""
        user = await self._get_user(user_id)
        settings = dict(user.settings)
        configured: list[dict] = list(settings.get("configured_llms", []))
        new_list = [e for e in configured if e["id"] != llm_id]
        if len(new_list) == len(configured):
            raise ValueError(f"Configured LLM '{llm_id}' not found")

        settings["configured_llms"] = new_list

        # If we deleted the active one, auto-promote
        if settings.get("active_llm_id") == llm_id:
            if new_list:
                settings["active_llm_id"] = new_list[0]["id"]
                self._sync_active_to_legacy(settings, new_list[0])
            else:
                settings.pop("active_llm_id", None)
                settings.pop("llm_provider", None)
                settings.pop("llm_model", None)
                settings.pop("ollama_base_url", None)

        user.settings = settings
        await self._session.flush()
        self.log.info(
            "configured_llm_deleted",
            user_id=str(user_id),
            llm_id=llm_id,
        )

    async def get_configured_llms(self, user_id: UUID) -> list[dict]:
        """Return configured LLMs with masked keys and active status."""
        user = await self._get_user(user_id)
        settings: dict = user.settings or {}
        configured: list[dict] = settings.get("configured_llms", [])
        active_id: str | None = settings.get("active_llm_id")
        llm_keys: dict = settings.get("llm_keys", {})

        result = []
        for entry in configured:
            provider = entry["provider"]
            masked_key: str | None = None
            if provider != "ollama" and provider in llm_keys:
                try:
                    plaintext = decrypt(llm_keys[provider])
                    masked_key = _mask_key(plaintext)
                except Exception:
                    masked_key = "***invalid***"

            result.append({
                "id": entry["id"],
                "provider": provider,
                "model": entry["model"],
                "base_url": entry.get("base_url"),
                "masked_key": masked_key,
                "is_active": entry["id"] == active_id,
                "added_at": entry["added_at"],
            })
        return result
