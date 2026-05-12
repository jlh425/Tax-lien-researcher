"""Comprehensive tests for the ApiKeyService.

Covers encryption/decryption roundtrip, prefix validation, key CRUD,
masked key retrieval, user isolation, configured LLM management,
LLM preference storage, and connection testing.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import InvalidToken

from aloha.core.crypto import decrypt, encrypt
from aloha.services.api_key_service import ApiKeyService, _mask_key


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_user(
    user_id: uuid.UUID | None = None,
    settings: dict | None = None,
) -> MagicMock:
    """Build a mock User with a mutable settings dict."""
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.settings = settings if settings is not None else {}
    return user


def _make_service(
    session: AsyncMock | None = None,
    user: MagicMock | None = None,
) -> tuple[ApiKeyService, AsyncMock]:
    """Instantiate ApiKeyService with a mocked session.

    If *user* is given, ``session.get`` will return it.
    Returns ``(service, session)``.
    """
    session = session or AsyncMock()
    if user is not None:
        session.get = AsyncMock(return_value=user)
    # session.add is synchronous in SQLAlchemy
    if not hasattr(session, "add") or isinstance(session.add, AsyncMock):
        session.add = MagicMock()
    svc = ApiKeyService(session)
    return svc, session


# ═══════════════════════════════════════════════════════════════════════════════
# Encryption / Decryption
# ═══════════════════════════════════════════════════════════════════════════════


class TestEncryptionDecryption:
    """Tests for the Fernet encrypt/decrypt layer used by the service."""

    def test_roundtrip_returns_original(self) -> None:
        """Encrypt then decrypt produces the original plaintext."""
        key = "sk-ant-api03-abcdefg1234567890"
        assert decrypt(encrypt(key)) == key

    def test_different_keys_produce_different_ciphertexts(self) -> None:
        """Two different plaintexts yield different ciphertexts."""
        ct_a = encrypt("sk-ant-key-AAA")
        ct_b = encrypt("sk-ant-key-BBB")
        assert ct_a != ct_b

    def test_same_key_produces_different_ciphertexts(self) -> None:
        """Fernet uses a random IV, so encrypting the same value twice differs."""
        key = "sk-ant-key-repeated"
        ct1 = encrypt(key)
        ct2 = encrypt(key)
        assert ct1 != ct2
        # But both decrypt to the original
        assert decrypt(ct1) == key
        assert decrypt(ct2) == key

    def test_tampered_ciphertext_raises(self) -> None:
        """Decrypting a tampered ciphertext raises InvalidToken."""
        ct = encrypt("sk-ant-secret")
        tampered = ct[:-4] + "XXXX"
        with pytest.raises(Exception):
            decrypt(tampered)

    def test_garbage_ciphertext_raises(self) -> None:
        """Decrypting total garbage raises an error."""
        with pytest.raises(Exception):
            decrypt("not-a-valid-ciphertext-at-all")

    def test_empty_string_roundtrip(self) -> None:
        """Empty string encrypts and decrypts without error."""
        assert decrypt(encrypt("")) == ""


# ═══════════════════════════════════════════════════════════════════════════════
# _mask_key helper
# ═══════════════════════════════════════════════════════════════════════════════


class TestMaskKey:
    """Tests for the _mask_key utility function."""

    def test_long_key(self) -> None:
        """Standard-length keys show first 7 and last 4."""
        masked = _mask_key("sk-ant-api03-abcdefghijklmnop")
        assert masked.startswith("sk-ant-")
        assert masked.endswith("mnop")
        assert "..." in masked

    def test_short_key(self) -> None:
        """Short keys (<=11 chars) show first 3 and last 2."""
        masked = _mask_key("abcdefgh")
        assert masked == "abc...gh"

    def test_minimum_length(self) -> None:
        """Very short keys still produce a masked version."""
        masked = _mask_key("abc")
        assert "..." in masked


# ═══════════════════════════════════════════════════════════════════════════════
# Prefix Validation
# ═══════════════════════════════════════════════════════════════════════════════


class TestPrefixValidation:
    """Tests that save_key validates provider-specific key prefixes."""

    @pytest.mark.asyncio
    async def test_valid_anthropic_prefix_accepted(self) -> None:
        """An Anthropic key starting with 'sk-ant-' is accepted."""
        user = _make_user()
        svc, session = _make_service(user=user)
        await svc.save_key(user.id, "anthropic", "sk-ant-api03-real-key-value")
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_valid_openai_prefix_accepted(self) -> None:
        """An OpenAI key starting with 'sk-' is accepted."""
        user = _make_user()
        svc, session = _make_service(user=user)
        await svc.save_key(user.id, "openai", "sk-proj-abcdef1234567890")
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_valid_groq_prefix_accepted(self) -> None:
        """A Groq key starting with 'gsk_' is accepted."""
        user = _make_user()
        svc, session = _make_service(user=user)
        await svc.save_key(user.id, "groq", "gsk_1234567890abcdef")
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_invalid_anthropic_prefix_rejected(self) -> None:
        """An Anthropic key with wrong prefix raises ValueError."""
        user = _make_user()
        svc, _ = _make_service(user=user)
        with pytest.raises(ValueError, match="Invalid anthropic API key"):
            await svc.save_key(user.id, "anthropic", "wrong-prefix-key")

    @pytest.mark.asyncio
    async def test_invalid_openai_prefix_rejected(self) -> None:
        """An OpenAI key with wrong prefix raises ValueError."""
        user = _make_user()
        svc, _ = _make_service(user=user)
        with pytest.raises(ValueError, match="Invalid openai API key"):
            await svc.save_key(user.id, "openai", "not-sk-prefix")

    @pytest.mark.asyncio
    async def test_invalid_groq_prefix_rejected(self) -> None:
        """A Groq key with wrong prefix raises ValueError."""
        user = _make_user()
        svc, _ = _make_service(user=user)
        with pytest.raises(ValueError, match="Invalid groq API key"):
            await svc.save_key(user.id, "groq", "bad-prefix-key")

    @pytest.mark.asyncio
    async def test_unknown_provider_skips_validation(self) -> None:
        """An unknown provider with no prefix list skips validation."""
        user = _make_user()
        svc, session = _make_service(user=user)
        await svc.save_key(user.id, "ollama", "any-value-is-fine")
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty_key_rejected_for_known_provider(self) -> None:
        """Empty string fails prefix check for known providers."""
        user = _make_user()
        svc, _ = _make_service(user=user)
        with pytest.raises(ValueError, match="Invalid anthropic API key"):
            await svc.save_key(user.id, "anthropic", "")


# ═══════════════════════════════════════════════════════════════════════════════
# Key Storage CRUD
# ═══════════════════════════════════════════════════════════════════════════════


class TestKeyCRUD:
    """Tests for save_key, get_decrypted_key, delete_key."""

    @pytest.mark.asyncio
    async def test_save_key_persists_encrypted_value(self) -> None:
        """save_key stores an encrypted (non-plaintext) value in settings."""
        user = _make_user()
        svc, _ = _make_service(user=user)
        raw_key = "sk-ant-api03-my-secret-key-12345"
        await svc.save_key(user.id, "anthropic", raw_key)

        stored = user.settings["llm_keys"]["anthropic"]
        # The stored value must NOT be the plaintext
        assert stored != raw_key
        # But it must decrypt back to the original
        assert decrypt(stored) == raw_key

    @pytest.mark.asyncio
    async def test_get_decrypted_key_returns_plaintext(self) -> None:
        """get_decrypted_key decrypts a stored key correctly."""
        raw_key = "sk-proj-openai-key-abcdef"
        user = _make_user(settings={"llm_keys": {"openai": encrypt(raw_key)}})
        svc, _ = _make_service(user=user)

        result = await svc.get_decrypted_key(user.id, "openai")
        assert result == raw_key

    @pytest.mark.asyncio
    async def test_get_decrypted_key_missing_provider_returns_none(self) -> None:
        """get_decrypted_key returns None when the provider has no key."""
        user = _make_user(settings={"llm_keys": {}})
        svc, _ = _make_service(user=user)
        assert await svc.get_decrypted_key(user.id, "anthropic") is None

    @pytest.mark.asyncio
    async def test_get_decrypted_key_no_llm_keys_returns_none(self) -> None:
        """get_decrypted_key returns None when llm_keys section is absent."""
        user = _make_user(settings={})
        svc, _ = _make_service(user=user)
        assert await svc.get_decrypted_key(user.id, "openai") is None

    @pytest.mark.asyncio
    async def test_update_existing_key_overwrites(self) -> None:
        """Saving a key for an existing provider overwrites the old value."""
        old_key = "sk-ant-old-key-12345"
        new_key = "sk-ant-new-key-67890"
        user = _make_user(settings={"llm_keys": {"anthropic": encrypt(old_key)}})
        svc, _ = _make_service(user=user)

        await svc.save_key(user.id, "anthropic", new_key)
        result = decrypt(user.settings["llm_keys"]["anthropic"])
        assert result == new_key

    @pytest.mark.asyncio
    async def test_delete_key_removes_record(self) -> None:
        """delete_key removes the provider's key from settings."""
        user = _make_user(settings={
            "llm_keys": {"anthropic": encrypt("sk-ant-to-delete")}
        })
        svc, session = _make_service(user=user)

        await svc.delete_key(user.id, "anthropic")
        assert "anthropic" not in user.settings["llm_keys"]
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_key_is_noop(self) -> None:
        """delete_key for a missing provider does not raise."""
        user = _make_user(settings={"llm_keys": {}})
        svc, session = _make_service(user=user)

        await svc.delete_key(user.id, "anthropic")
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_multiple_providers(self) -> None:
        """Multiple providers can store keys independently."""
        user = _make_user()
        svc, _ = _make_service(user=user)

        await svc.save_key(user.id, "anthropic", "sk-ant-key-AAA")
        await svc.save_key(user.id, "openai", "sk-key-BBB")
        await svc.save_key(user.id, "groq", "gsk_key-CCC")

        keys = user.settings["llm_keys"]
        assert decrypt(keys["anthropic"]) == "sk-ant-key-AAA"
        assert decrypt(keys["openai"]) == "sk-key-BBB"
        assert decrypt(keys["groq"]) == "gsk_key-CCC"


# ═══════════════════════════════════════════════════════════════════════════════
# User Not Found
# ═══════════════════════════════════════════════════════════════════════════════


class TestUserNotFound:
    """Verify that operations on non-existent users raise ValueError."""

    @pytest.mark.asyncio
    async def test_save_key_user_not_found(self) -> None:
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)
        svc = ApiKeyService(session)
        with pytest.raises(ValueError, match="not found"):
            await svc.save_key(uuid.uuid4(), "anthropic", "sk-ant-key")

    @pytest.mark.asyncio
    async def test_get_decrypted_key_user_not_found(self) -> None:
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)
        svc = ApiKeyService(session)
        with pytest.raises(ValueError, match="not found"):
            await svc.get_decrypted_key(uuid.uuid4(), "anthropic")

    @pytest.mark.asyncio
    async def test_delete_key_user_not_found(self) -> None:
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)
        svc = ApiKeyService(session)
        with pytest.raises(ValueError, match="not found"):
            await svc.delete_key(uuid.uuid4(), "anthropic")

    @pytest.mark.asyncio
    async def test_get_keys_masked_user_not_found(self) -> None:
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)
        svc = ApiKeyService(session)
        with pytest.raises(ValueError, match="not found"):
            await svc.get_keys_masked(uuid.uuid4())


# ═══════════════════════════════════════════════════════════════════════════════
# Masked Key Retrieval
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetKeysMasked:
    """Tests for get_keys_masked which returns masked previews."""

    @pytest.mark.asyncio
    async def test_returns_masked_keys(self) -> None:
        """Returned keys are masked, not plaintext."""
        raw_key = "sk-ant-api03-real-secret-key-value-1234"
        user = _make_user(settings={
            "llm_keys": {"anthropic": encrypt(raw_key)},
        })
        svc, _ = _make_service(user=user)

        result = await svc.get_keys_masked(user.id)
        assert len(result["keys"]) == 1
        entry = result["keys"][0]
        assert entry["provider"] == "anthropic"
        assert entry["masked_key"] != raw_key
        assert "..." in entry["masked_key"]

    @pytest.mark.asyncio
    async def test_returns_llm_preference(self) -> None:
        """get_keys_masked includes llm_provider, llm_model, ollama_base_url."""
        user = _make_user(settings={
            "llm_keys": {},
            "llm_provider": "anthropic",
            "llm_model": "claude-sonnet-4-20250514",
            "ollama_base_url": "http://localhost:11434",
        })
        svc, _ = _make_service(user=user)

        result = await svc.get_keys_masked(user.id)
        assert result["llm_provider"] == "anthropic"
        assert result["llm_model"] == "claude-sonnet-4-20250514"
        assert result["ollama_base_url"] == "http://localhost:11434"

    @pytest.mark.asyncio
    async def test_invalid_ciphertext_returns_invalid_marker(self) -> None:
        """A corrupted ciphertext yields '***invalid***' instead of crashing."""
        user = _make_user(settings={
            "llm_keys": {"openai": "corrupted-ciphertext-data"},
        })
        svc, _ = _make_service(user=user)

        result = await svc.get_keys_masked(user.id)
        assert result["keys"][0]["masked_key"] == "***invalid***"

    @pytest.mark.asyncio
    async def test_empty_llm_keys(self) -> None:
        """No keys stored returns empty list."""
        user = _make_user(settings={})
        svc, _ = _make_service(user=user)

        result = await svc.get_keys_masked(user.id)
        assert result["keys"] == []
        assert result["llm_provider"] is None
        assert result["llm_model"] is None

    @pytest.mark.asyncio
    async def test_multiple_providers_masked(self) -> None:
        """Multiple providers each get their own masked entry."""
        user = _make_user(settings={
            "llm_keys": {
                "anthropic": encrypt("sk-ant-api03-key-anthropic-xxxx"),
                "openai": encrypt("sk-proj-openai-key-yyyy"),
            },
        })
        svc, _ = _make_service(user=user)

        result = await svc.get_keys_masked(user.id)
        providers = {e["provider"] for e in result["keys"]}
        assert providers == {"anthropic", "openai"}


# ═══════════════════════════════════════════════════════════════════════════════
# User Isolation
# ═══════════════════════════════════════════════════════════════════════════════


class TestUserIsolation:
    """Verify that each user's keys are isolated."""

    @pytest.mark.asyncio
    async def test_user_a_cannot_see_user_b_keys(self) -> None:
        """User A's get_decrypted_key returns None for a key only User B has."""
        user_a_id = uuid.uuid4()
        user_b_id = uuid.uuid4()

        user_a = _make_user(user_id=user_a_id, settings={"llm_keys": {}})
        user_b = _make_user(
            user_id=user_b_id,
            settings={"llm_keys": {"anthropic": encrypt("sk-ant-secret")}},
        )

        session = AsyncMock()

        async def get_side_effect(model, uid):
            if uid == user_a_id:
                return user_a
            if uid == user_b_id:
                return user_b
            return None

        session.get = AsyncMock(side_effect=get_side_effect)
        svc = ApiKeyService(session)

        # User A has no anthropic key
        assert await svc.get_decrypted_key(user_a_id, "anthropic") is None
        # User B does
        assert await svc.get_decrypted_key(user_b_id, "anthropic") == "sk-ant-secret"

    @pytest.mark.asyncio
    async def test_list_keys_returns_only_own_keys(self) -> None:
        """get_keys_masked returns only the requesting user's keys."""
        user_a = _make_user(settings={
            "llm_keys": {"anthropic": encrypt("sk-ant-a-key")},
        })
        user_b = _make_user(settings={
            "llm_keys": {
                "openai": encrypt("sk-b-key"),
                "groq": encrypt("gsk_b-key"),
            },
        })

        session_a = AsyncMock()
        session_a.get = AsyncMock(return_value=user_a)
        svc_a = ApiKeyService(session_a)

        session_b = AsyncMock()
        session_b.get = AsyncMock(return_value=user_b)
        svc_b = ApiKeyService(session_b)

        result_a = await svc_a.get_keys_masked(user_a.id)
        result_b = await svc_b.get_keys_masked(user_b.id)

        assert len(result_a["keys"]) == 1
        assert result_a["keys"][0]["provider"] == "anthropic"

        assert len(result_b["keys"]) == 2
        providers_b = {e["provider"] for e in result_b["keys"]}
        assert providers_b == {"openai", "groq"}


# ═══════════════════════════════════════════════════════════════════════════════
# LLM Preference Storage
# ═══════════════════════════════════════════════════════════════════════════════


class TestLLMPreference:
    """Tests for save_llm_preference."""

    @pytest.mark.asyncio
    async def test_saves_provider_and_model(self) -> None:
        user = _make_user()
        svc, session = _make_service(user=user)

        await svc.save_llm_preference(user.id, "anthropic", "claude-sonnet-4-20250514")

        assert user.settings["llm_provider"] == "anthropic"
        assert user.settings["llm_model"] == "claude-sonnet-4-20250514"
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ollama_saves_base_url(self) -> None:
        """Ollama provider stores the base_url."""
        user = _make_user()
        svc, _ = _make_service(user=user)

        await svc.save_llm_preference(
            user.id, "ollama", "llama3.1:70b", base_url="http://gpu:11434"
        )

        assert user.settings["llm_provider"] == "ollama"
        assert user.settings["ollama_base_url"] == "http://gpu:11434"

    @pytest.mark.asyncio
    async def test_ollama_default_base_url(self) -> None:
        """Ollama without base_url defaults to localhost."""
        user = _make_user()
        svc, _ = _make_service(user=user)

        await svc.save_llm_preference(user.id, "ollama", "llama3.1:70b")
        assert user.settings["ollama_base_url"] == "http://localhost:11434"


# ═══════════════════════════════════════════════════════════════════════════════
# Configured LLMs — Add / List / Set Active / Delete
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfiguredLLMs:
    """Tests for the configured LLM CRUD flow."""

    @pytest.mark.asyncio
    async def test_add_configured_llm_returns_entry(self) -> None:
        """add_configured_llm creates and returns the entry dict."""
        user = _make_user()
        svc, session = _make_service(user=user)

        entry = await svc.add_configured_llm(
            user.id, "anthropic", "claude-sonnet-4-20250514",
            api_key="sk-ant-key-12345",
        )

        assert entry["provider"] == "anthropic"
        assert entry["model"] == "claude-sonnet-4-20250514"
        assert "id" in entry
        assert "added_at" in entry
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_first_configured_llm_auto_activates(self) -> None:
        """The first configured LLM is automatically set as active."""
        user = _make_user()
        svc, _ = _make_service(user=user)

        entry = await svc.add_configured_llm(
            user.id, "openai", "gpt-4o", api_key="sk-key-123"
        )

        assert user.settings["active_llm_id"] == entry["id"]
        assert user.settings["llm_provider"] == "openai"
        assert user.settings["llm_model"] == "gpt-4o"

    @pytest.mark.asyncio
    async def test_second_configured_llm_does_not_override_active(self) -> None:
        """Adding a second LLM does not change the active one."""
        user = _make_user()
        svc, _ = _make_service(user=user)

        first = await svc.add_configured_llm(
            user.id, "openai", "gpt-4o", api_key="sk-key-111"
        )
        second = await svc.add_configured_llm(
            user.id, "anthropic", "claude-sonnet-4-20250514",
            api_key="sk-ant-key-222",
        )

        assert user.settings["active_llm_id"] == first["id"]
        assert user.settings["llm_provider"] == "openai"

    @pytest.mark.asyncio
    async def test_add_configured_llm_encrypts_key(self) -> None:
        """add_configured_llm encrypts the provided API key."""
        user = _make_user()
        svc, _ = _make_service(user=user)

        await svc.add_configured_llm(
            user.id, "anthropic", "claude-sonnet-4-20250514",
            api_key="sk-ant-key-secret-value",
        )

        stored = user.settings["llm_keys"]["anthropic"]
        assert stored != "sk-ant-key-secret-value"
        assert decrypt(stored) == "sk-ant-key-secret-value"

    @pytest.mark.asyncio
    async def test_add_ollama_configured_llm_stores_base_url(self) -> None:
        """Ollama entries include a base_url field."""
        user = _make_user()
        svc, _ = _make_service(user=user)

        entry = await svc.add_configured_llm(
            user.id, "ollama", "llama3.1:70b",
            base_url="http://gpu-box:11434",
        )

        assert entry["base_url"] == "http://gpu-box:11434"

    @pytest.mark.asyncio
    async def test_add_configured_llm_without_api_key(self) -> None:
        """add_configured_llm works without an API key (e.g. Ollama)."""
        user = _make_user()
        svc, session = _make_service(user=user)

        entry = await svc.add_configured_llm(
            user.id, "ollama", "llama3.1:70b"
        )

        assert entry["provider"] == "ollama"
        # No llm_keys entry for ollama
        assert "ollama" not in user.settings.get("llm_keys", {})
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_set_active_llm(self) -> None:
        """set_active_llm switches the active configured LLM."""
        user = _make_user()
        svc, _ = _make_service(user=user)

        first = await svc.add_configured_llm(
            user.id, "openai", "gpt-4o", api_key="sk-key-111"
        )
        second = await svc.add_configured_llm(
            user.id, "anthropic", "claude-sonnet-4-20250514",
            api_key="sk-ant-key-222",
        )

        # Initially first is active
        assert user.settings["active_llm_id"] == first["id"]

        await svc.set_active_llm(user.id, second["id"])
        assert user.settings["active_llm_id"] == second["id"]
        assert user.settings["llm_provider"] == "anthropic"
        assert user.settings["llm_model"] == "claude-sonnet-4-20250514"

    @pytest.mark.asyncio
    async def test_set_active_llm_not_found_raises(self) -> None:
        """set_active_llm raises ValueError for a non-existent LLM id."""
        user = _make_user(settings={"configured_llms": []})
        svc, _ = _make_service(user=user)

        with pytest.raises(ValueError, match="not found"):
            await svc.set_active_llm(user.id, "nonexistent-id")

    @pytest.mark.asyncio
    async def test_delete_configured_llm(self) -> None:
        """delete_configured_llm removes the entry from the list."""
        user = _make_user()
        svc, _ = _make_service(user=user)

        entry = await svc.add_configured_llm(
            user.id, "openai", "gpt-4o", api_key="sk-key-111"
        )
        second = await svc.add_configured_llm(
            user.id, "anthropic", "claude-sonnet-4-20250514",
            api_key="sk-ant-key-222",
        )

        await svc.delete_configured_llm(user.id, entry["id"])

        configured = user.settings["configured_llms"]
        assert len(configured) == 1
        assert configured[0]["id"] == second["id"]

    @pytest.mark.asyncio
    async def test_delete_active_llm_auto_promotes(self) -> None:
        """Deleting the active LLM promotes the next one."""
        user = _make_user()
        svc, _ = _make_service(user=user)

        first = await svc.add_configured_llm(
            user.id, "openai", "gpt-4o", api_key="sk-key-111"
        )
        second = await svc.add_configured_llm(
            user.id, "anthropic", "claude-sonnet-4-20250514",
            api_key="sk-ant-key-222",
        )

        assert user.settings["active_llm_id"] == first["id"]

        await svc.delete_configured_llm(user.id, first["id"])

        assert user.settings["active_llm_id"] == second["id"]
        assert user.settings["llm_provider"] == "anthropic"
        assert user.settings["llm_model"] == "claude-sonnet-4-20250514"

    @pytest.mark.asyncio
    async def test_delete_last_llm_clears_active(self) -> None:
        """Deleting the last configured LLM clears all active settings."""
        user = _make_user()
        svc, _ = _make_service(user=user)

        entry = await svc.add_configured_llm(
            user.id, "openai", "gpt-4o", api_key="sk-key-only"
        )

        await svc.delete_configured_llm(user.id, entry["id"])

        assert "active_llm_id" not in user.settings
        assert "llm_provider" not in user.settings
        assert "llm_model" not in user.settings

    @pytest.mark.asyncio
    async def test_delete_nonexistent_llm_raises(self) -> None:
        """delete_configured_llm raises ValueError for unknown id."""
        user = _make_user(settings={"configured_llms": []})
        svc, _ = _make_service(user=user)

        with pytest.raises(ValueError, match="not found"):
            await svc.delete_configured_llm(user.id, "ghost-id")

    @pytest.mark.asyncio
    async def test_get_configured_llms_returns_list_with_active_flag(self) -> None:
        """get_configured_llms marks the active entry correctly."""
        user = _make_user()
        svc, _ = _make_service(user=user)

        first = await svc.add_configured_llm(
            user.id, "openai", "gpt-4o", api_key="sk-key-111"
        )
        second = await svc.add_configured_llm(
            user.id, "anthropic", "claude-sonnet-4-20250514",
            api_key="sk-ant-key-222",
        )

        result = await svc.get_configured_llms(user.id)

        assert len(result) == 2
        active_entries = [e for e in result if e["is_active"]]
        assert len(active_entries) == 1
        assert active_entries[0]["id"] == first["id"]

    @pytest.mark.asyncio
    async def test_get_configured_llms_masks_api_keys(self) -> None:
        """get_configured_llms returns masked keys, not plaintext."""
        raw_key = "sk-ant-api03-real-secret-key-value-9999"
        user = _make_user()
        svc, _ = _make_service(user=user)

        await svc.add_configured_llm(
            user.id, "anthropic", "claude-sonnet-4-20250514",
            api_key=raw_key,
        )

        result = await svc.get_configured_llms(user.id)
        entry = result[0]
        assert entry["masked_key"] is not None
        assert entry["masked_key"] != raw_key
        assert "..." in entry["masked_key"]

    @pytest.mark.asyncio
    async def test_get_configured_llms_ollama_has_no_masked_key(self) -> None:
        """Ollama entries don't have a masked_key (no API key)."""
        user = _make_user()
        svc, _ = _make_service(user=user)

        await svc.add_configured_llm(
            user.id, "ollama", "llama3.1:70b"
        )

        result = await svc.get_configured_llms(user.id)
        assert result[0]["masked_key"] is None

    @pytest.mark.asyncio
    async def test_get_configured_llms_invalid_ciphertext(self) -> None:
        """Corrupted ciphertext in llm_keys yields '***invalid***'."""
        user = _make_user(settings={
            "configured_llms": [{
                "id": "test-id",
                "provider": "openai",
                "model": "gpt-4o",
                "added_at": datetime.now(timezone.utc).isoformat(),
            }],
            "active_llm_id": "test-id",
            "llm_keys": {"openai": "corrupted-data"},
        })
        svc, _ = _make_service(user=user)

        result = await svc.get_configured_llms(user.id)
        assert result[0]["masked_key"] == "***invalid***"

    @pytest.mark.asyncio
    async def test_get_configured_llms_empty(self) -> None:
        """get_configured_llms returns empty list when none configured."""
        user = _make_user(settings={})
        svc, _ = _make_service(user=user)

        result = await svc.get_configured_llms(user.id)
        assert result == []


# ═══════════════════════════════════════════════════════════════════════════════
# _sync_active_to_legacy
# ═══════════════════════════════════════════════════════════════════════════════


class TestSyncActiveToLegacy:
    """Tests for the static _sync_active_to_legacy method."""

    def test_non_ollama_provider(self) -> None:
        """Non-ollama providers set llm_provider/llm_model and remove base_url."""
        settings: dict = {"ollama_base_url": "http://old:11434"}
        entry = {"provider": "anthropic", "model": "claude-sonnet-4-20250514"}
        ApiKeyService._sync_active_to_legacy(settings, entry)

        assert settings["llm_provider"] == "anthropic"
        assert settings["llm_model"] == "claude-sonnet-4-20250514"
        assert "ollama_base_url" not in settings

    def test_ollama_provider_with_base_url(self) -> None:
        """Ollama provider preserves the base_url."""
        settings: dict = {}
        entry = {
            "provider": "ollama",
            "model": "llama3.1:70b",
            "base_url": "http://gpu:11434",
        }
        ApiKeyService._sync_active_to_legacy(settings, entry)

        assert settings["llm_provider"] == "ollama"
        assert settings["llm_model"] == "llama3.1:70b"
        assert settings["ollama_base_url"] == "http://gpu:11434"

    def test_ollama_default_base_url(self) -> None:
        """Ollama without base_url defaults to localhost."""
        settings: dict = {}
        entry = {"provider": "ollama", "model": "llama3.1:70b"}
        ApiKeyService._sync_active_to_legacy(settings, entry)

        assert settings["ollama_base_url"] == "http://localhost:11434"


# ═══════════════════════════════════════════════════════════════════════════════
# test_llm_connection (mocked)
# ═══════════════════════════════════════════════════════════════════════════════


class TestLLMConnection:
    """Tests for test_llm_connection with mocked external calls."""

    @pytest.mark.asyncio
    async def test_successful_connection(self) -> None:
        """Successful LLM call returns (True, message, response_text)."""
        svc, _ = _make_service()

        mock_result = MagicMock()
        mock_result.output = "Hello there from LLM"

        with (
            patch(
                "aloha.core.llm._build_model_with_key",
                return_value=MagicMock(),
            ),
            patch("pydantic_ai.Agent") as MockAgent,
        ):
            mock_agent_instance = MagicMock()
            mock_agent_instance.run = AsyncMock(return_value=mock_result)
            MockAgent.return_value = mock_agent_instance

            ok, msg, text = await svc.test_llm_connection(
                "anthropic", "claude-sonnet-4-20250514",
                api_key="sk-ant-test-key",
            )

        assert ok is True
        assert "successful" in msg.lower()
        assert text == "Hello there from LLM"

    @pytest.mark.asyncio
    async def test_failed_connection(self) -> None:
        """Failed LLM call returns (False, error message, None)."""
        svc, _ = _make_service()

        with (
            patch(
                "aloha.core.llm._build_model_with_key",
                return_value=MagicMock(),
            ),
            patch("pydantic_ai.Agent") as MockAgent,
        ):
            mock_agent_instance = MagicMock()
            mock_agent_instance.run = AsyncMock(
                side_effect=Exception("Invalid API key")
            )
            MockAgent.return_value = mock_agent_instance

            ok, msg, text = await svc.test_llm_connection(
                "anthropic", "claude-sonnet-4-20250514",
                api_key="sk-ant-bad-key",
            )

        assert ok is False
        assert "failed" in msg.lower()
        assert text is None

    @pytest.mark.asyncio
    async def test_ollama_model_not_found(self) -> None:
        """Ollama returns failure when model is not in /api/tags."""
        svc, _ = _make_service()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "models": [{"name": "mistral:latest"}]
        }

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client

            ok, msg, text = await svc.test_llm_connection(
                "ollama", "llama3.1:70b"
            )

        assert ok is False
        assert "not found" in msg.lower()
        assert text is None

    @pytest.mark.asyncio
    async def test_ollama_connection_error(self) -> None:
        """Ollama returns failure when server is unreachable."""
        import httpx

        svc, _ = _make_service()

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client

            ok, msg, text = await svc.test_llm_connection(
                "ollama", "llama3.1:70b"
            )

        assert ok is False
        assert "cannot connect" in msg.lower()
        assert text is None

    @pytest.mark.asyncio
    async def test_ollama_model_found_then_llm_succeeds(self) -> None:
        """Ollama model exists and LLM call succeeds."""
        svc, _ = _make_service()

        mock_tags_response = MagicMock()
        mock_tags_response.status_code = 200
        mock_tags_response.raise_for_status = MagicMock()
        mock_tags_response.json.return_value = {
            "models": [{"name": "llama3.1:latest"}]
        }

        mock_llm_result = MagicMock()
        mock_llm_result.output = "Hello from Ollama"

        with (
            patch("httpx.AsyncClient") as MockClient,
            patch(
                "aloha.core.llm._build_model_with_key",
                return_value=MagicMock(),
            ),
            patch("pydantic_ai.Agent") as MockAgent,
        ):
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_tags_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client

            mock_agent_instance = MagicMock()
            mock_agent_instance.run = AsyncMock(return_value=mock_llm_result)
            MockAgent.return_value = mock_agent_instance

            ok, msg, text = await svc.test_llm_connection(
                "ollama", "llama3.1:70b"
            )

        assert ok is True
        assert text == "Hello from Ollama"

    @pytest.mark.asyncio
    async def test_ollama_generic_exception(self) -> None:
        """Ollama /api/tags raises a non-ConnectError exception."""
        svc, _ = _make_service()

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=RuntimeError("unexpected"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client

            ok, msg, text = await svc.test_llm_connection(
                "ollama", "llama3.1:70b"
            )

        assert ok is False
        assert "failed" in msg.lower()
        assert text is None
