"""CRUD service for per-user LLM API keys stored in User.settings JSONB."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from aloha.core.crypto import decrypt, encrypt
from aloha.db.models.user import User
from aloha.services.base import BaseService

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
