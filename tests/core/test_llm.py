"""Tests for aloha.core.llm — LLM provider resolution and per-agent overrides."""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from aloha.config import Settings
from aloha.core import llm


# ── Helpers ────────────────────────────────────────────────────────────────────

# All deferred imports inside _build_model do ``from aloha.config import settings``,
# so we patch the module-level singleton in aloha.config.
_SETTINGS_TARGET = "aloha.config.settings"


def _make_settings(**overrides: object) -> Settings:
    """Build a Settings instance with sensible test defaults.

    All API keys are set to dummy values so provider factories succeed.
    Pass keyword args to override any field.
    """
    defaults: dict[str, object] = {
        "llm_provider": "anthropic",
        "llm_model": "claude-sonnet-4-20250514",
        "anthropic_api_key": "sk-ant-test",
        "openai_api_key": "sk-openai-test",
        "groq_api_key": "gsk-groq-test",
        "ollama_base_url": "http://localhost:11434",
        "openai_compatible_base_url": "http://localhost:8080/v1",
        "openai_compatible_api_key": "compat-key",
        "database_url": "postgresql+asyncpg://localhost:5432/test",
        "database_url_sync": "postgresql+psycopg2://localhost:5432/test",
    }
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]


def _rebuild_cached(fn_name: str, maxsize: int) -> object:
    """Get the raw function from the llm module and wrap it in a fresh lru_cache.

    Handles the case where ``tests/agents/conftest.py`` has replaced the module
    attribute with a Mock -- in that case the original lru_cache wrapper is
    stored by unittest.mock internally, but we can recover the raw function from
    the module's ``__spec__`` by reloading.  We use a simpler approach: if the
    attribute still has ``__wrapped__`` it's the real function; otherwise we
    reload the module to get the original.
    """
    from functools import lru_cache

    current = getattr(llm, fn_name)
    if hasattr(current, "__wrapped__"):
        return lru_cache(maxsize=maxsize)(current.__wrapped__)

    # The module attribute has been replaced by a Mock.
    # Reload the module to recover the original.
    import importlib

    reloaded = importlib.reload(importlib.import_module("aloha.core.llm"))
    raw = getattr(reloaded, fn_name).__wrapped__
    return lru_cache(maxsize=maxsize)(raw)


@pytest.fixture(autouse=True)
def _restore_and_clear_caches() -> None:
    """Restore real functions and clear LRU caches between tests.

    ``tests/agents/conftest.py`` patches ``get_agent_model`` at collection time
    and never stops the patch (by design -- agent singletons need it).  To test
    the *real* resolution logic we rebuild fresh lru_cache wrappers around the
    original unwrapped functions and temporarily install them.
    """
    fresh_get_model = _rebuild_cached("get_model", 1)
    fresh_get_agent_model = _rebuild_cached("get_agent_model", 16)

    with patch.object(llm, "get_model", fresh_get_model), \
         patch.object(llm, "get_agent_model", fresh_get_agent_model):
        yield


@pytest.fixture(autouse=True)
def mock_anthropic_module() -> MagicMock:
    """Inject a mock pydantic_ai.models.anthropic module into sys.modules.

    The real module can't be imported due to an anthropic SDK version mismatch
    with the installed pydantic-ai, so we pre-populate sys.modules with a fake
    that exposes a mock AnthropicModel.  This is autouse because several code
    paths (even the "missing key returns None" ones) hit the deferred
    ``from pydantic_ai.models.anthropic import AnthropicModel`` before they
    can short-circuit.
    """
    mod_key = "pydantic_ai.models.anthropic"
    original = sys.modules.get(mod_key)

    fake_mod = ModuleType(mod_key)
    mock_cls = MagicMock(name="AnthropicModel")
    mock_cls.return_value = MagicMock(name="anthropic_instance")
    fake_mod.AnthropicModel = mock_cls  # type: ignore[attr-defined]
    sys.modules[mod_key] = fake_mod

    yield mock_cls

    # Restore original state
    if original is not None:
        sys.modules[mod_key] = original
    else:
        sys.modules.pop(mod_key, None)


# ── _build_model: provider factory ─────────────────────────────────────────────


class TestBuildModelProviderFactory:
    """Test that _build_model creates the correct model type for each provider."""

    def test_anthropic_creates_anthropic_model(
        self, mock_anthropic_module: MagicMock,
    ) -> None:
        s = _make_settings(anthropic_api_key="sk-ant-test")
        with patch(_SETTINGS_TARGET, s):
            model = llm._build_model("anthropic", "claude-sonnet-4-20250514")

        mock_anthropic_module.assert_called_once_with(
            "claude-sonnet-4-20250514", api_key="sk-ant-test",
        )
        assert model is mock_anthropic_module.return_value

    def test_openai_creates_openai_model(self) -> None:
        s = _make_settings(openai_api_key="sk-openai-test")
        with patch(_SETTINGS_TARGET, s):
            model = llm._build_model("openai", "gpt-4o")
        # OpenAIModel and OpenAIProvider are importable, so real objects created
        assert model is not None

    def test_ollama_creates_openai_model_with_ollama_url(self) -> None:
        s = _make_settings(ollama_base_url="http://myhost:11434")
        with patch(_SETTINGS_TARGET, s):
            model = llm._build_model("ollama", "llama3.1:70b")
        assert model is not None

    def test_groq_creates_openai_model_with_groq_provider(self) -> None:
        s = _make_settings(groq_api_key="gsk-groq-test")
        with patch(_SETTINGS_TARGET, s):
            model = llm._build_model("groq", "llama-3.3-70b-versatile")
        assert model is not None

    def test_openai_compatible_creates_openai_model(self) -> None:
        s = _make_settings(
            openai_compatible_base_url="http://localhost:8080/v1",
            openai_compatible_api_key="compat-key",
        )
        with patch(_SETTINGS_TARGET, s):
            model = llm._build_model("openai-compatible", "my-model")
        assert model is not None

    def test_openai_compatible_without_api_key_uses_no_key(self) -> None:
        s = _make_settings(
            openai_compatible_base_url="http://localhost:8080/v1",
            openai_compatible_api_key=None,
        )
        with patch(_SETTINGS_TARGET, s):
            model = llm._build_model("openai-compatible", "my-model")
        # Should still create a model (api_key defaults to "no-key")
        assert model is not None


class TestBuildModelUnknownProvider:
    """Test that unknown providers raise ValueError."""

    def test_unknown_provider_raises(self) -> None:
        s = _make_settings()
        with patch(_SETTINGS_TARGET, s):
            with pytest.raises(ValueError, match="Unknown LLM provider.*'banana'"):
                llm._build_model("banana", "some-model")


class TestBuildModelMissingApiKey:
    """Test graceful handling when required API keys are missing."""

    def test_anthropic_missing_key_returns_none(self) -> None:
        s = _make_settings(anthropic_api_key=None)
        with patch(_SETTINGS_TARGET, s):
            result = llm._build_model("anthropic", "claude-sonnet-4-20250514")
        assert result is None

    def test_openai_missing_key_returns_none(self) -> None:
        s = _make_settings(openai_api_key=None)
        with patch(_SETTINGS_TARGET, s):
            result = llm._build_model("openai", "gpt-4o")
        assert result is None

    def test_groq_missing_key_returns_none(self) -> None:
        s = _make_settings(groq_api_key=None)
        with patch(_SETTINGS_TARGET, s):
            result = llm._build_model("groq", "llama-3.3-70b-versatile")
        assert result is None

    def test_openai_compatible_missing_base_url_returns_none(self) -> None:
        s = _make_settings(openai_compatible_base_url=None)
        with patch(_SETTINGS_TARGET, s):
            result = llm._build_model("openai-compatible", "my-model")
        assert result is None

    def test_ollama_does_not_require_api_key(self) -> None:
        """Ollama never returns None -- it doesn't need an API key."""
        s = _make_settings()
        with patch(_SETTINGS_TARGET, s):
            result = llm._build_model("ollama", "llama3.1:8b")
        assert result is not None


# ── get_model: global default ──────────────────────────────────────────────────


class TestGetModel:
    """Test the cached global default model factory."""

    def test_returns_model_from_settings(self) -> None:
        s = _make_settings(
            llm_provider="openai",
            llm_model="gpt-4o",
            openai_api_key="sk-openai-test",
        )
        with patch(_SETTINGS_TARGET, s):
            model = llm.get_model()
        assert model is not None

    def test_delegates_to_build_model(self) -> None:
        s = _make_settings(
            llm_provider="openai",
            llm_model="gpt-4o",
        )
        sentinel = MagicMock(name="model_sentinel")
        with patch(_SETTINGS_TARGET, s), \
             patch.object(llm, "_build_model", return_value=sentinel) as mock_b:
            model = llm.get_model()
        mock_b.assert_called_once_with("openai", "gpt-4o")
        assert model is sentinel

    def test_is_cached(self) -> None:
        """Calling get_model() twice returns the same object (lru_cache)."""
        s = _make_settings(
            llm_provider="openai",
            llm_model="gpt-4o",
            openai_api_key="sk-openai-test",
        )
        with patch(_SETTINGS_TARGET, s):
            m1 = llm.get_model()
            m2 = llm.get_model()
        assert m1 is m2

    def test_cache_calls_build_model_once(self) -> None:
        s = _make_settings(llm_provider="openai", llm_model="gpt-4o")
        sentinel = MagicMock(name="cached_model")
        with patch(_SETTINGS_TARGET, s), \
             patch.object(llm, "_build_model", return_value=sentinel) as mock_b:
            llm.get_model()
            llm.get_model()
        mock_b.assert_called_once()


# ── get_agent_model: per-agent overrides ───────────────────────────────────────


class TestGetAgentModel:
    """Test per-agent override resolution and fallback to global default."""

    def test_agent_without_override_uses_global(self) -> None:
        """Agent with no override falls back to get_model() (global default)."""
        s = _make_settings(
            llm_provider="openai",
            llm_model="gpt-4o",
            openai_api_key="sk-openai-test",
            llm_agent_scoring=None,
        )
        with patch(_SETTINGS_TARGET, s):
            model = llm.get_agent_model("scoring")
        # Should delegate to get_model() which returns a real OpenAIModel
        assert model is not None

    def test_agent_without_override_returns_same_as_get_model(self) -> None:
        s = _make_settings(
            llm_provider="openai",
            llm_model="gpt-4o",
            openai_api_key="sk-openai-test",
            llm_agent_scoring=None,
        )
        with patch(_SETTINGS_TARGET, s):
            global_m = llm.get_model()
            agent_m = llm.get_agent_model("scoring")
        assert global_m is agent_m

    def test_agent_with_override_calls_build_model(self) -> None:
        s = _make_settings(
            llm_provider="openai",
            llm_model="gpt-4o",
            openai_api_key="sk-openai-test",
            groq_api_key="gsk-groq-test",
            llm_agent_scoring="groq:llama-3.3-70b-versatile",
        )
        with patch(_SETTINGS_TARGET, s):
            model = llm.get_agent_model("scoring")
        # Should have built a Groq-based model, not an OpenAI one
        assert model is not None

    def test_agent_override_same_as_global_reuses_get_model(self) -> None:
        """When the override resolves to the same provider:model as the
        global default, get_agent_model should call get_model() to reuse
        the cached instance."""
        s = _make_settings(
            llm_provider="openai",
            llm_model="gpt-4o",
            openai_api_key="sk-openai-test",
            llm_agent_scoring="openai:gpt-4o",
        )
        with patch(_SETTINGS_TARGET, s):
            global_model = llm.get_model()
            agent_model = llm.get_agent_model("scoring")
        assert global_model is agent_model

    def test_agent_override_groq(self) -> None:
        s = _make_settings(
            llm_provider="openai",
            llm_model="gpt-4o",
            openai_api_key="sk-openai-test",
            groq_api_key="gsk-groq-test",
            llm_agent_database="groq:llama-3.3-70b-versatile",
        )
        with patch(_SETTINGS_TARGET, s):
            model = llm.get_agent_model("database")
        assert model is not None

    def test_agent_override_ollama(self) -> None:
        s = _make_settings(
            llm_provider="openai",
            llm_model="gpt-4o",
            openai_api_key="sk-openai-test",
            llm_agent_discovery="ollama:llama3.1:8b",
        )
        with patch(_SETTINGS_TARGET, s):
            model = llm.get_agent_model("discovery")
        assert model is not None

    def test_is_cached_per_agent(self) -> None:
        s = _make_settings(
            llm_provider="openai",
            llm_model="gpt-4o",
            openai_api_key="sk-openai-test",
            groq_api_key="gsk-groq-test",
            llm_agent_scoring="groq:llama-3.3-70b-versatile",
        )
        with patch(_SETTINGS_TARGET, s):
            m1 = llm.get_agent_model("scoring")
            m2 = llm.get_agent_model("scoring")
        assert m1 is m2

    def test_different_agents_get_different_models(self) -> None:
        """Two agents with different overrides get different model instances."""
        s = _make_settings(
            llm_provider="openai",
            llm_model="gpt-4o",
            openai_api_key="sk-openai-test",
            groq_api_key="gsk-groq-test",
            llm_agent_scoring="groq:llama-3.3-70b-versatile",
            llm_agent_database="ollama:llama3.1:8b",
        )
        with patch(_SETTINGS_TARGET, s):
            scoring_model = llm.get_agent_model("scoring")
            db_model = llm.get_agent_model("database")
        assert scoring_model is not db_model


# ── Settings.get_agent_llm: override parsing ──────────────────────────────────


class TestSettingsGetAgentLlm:
    """Test the Settings.get_agent_llm() parsing logic directly."""

    def test_no_override_returns_global_default(self) -> None:
        s = _make_settings(
            llm_provider="anthropic",
            llm_model="claude-sonnet-4-20250514",
            llm_agent_scoring=None,
        )
        provider, model = s.get_agent_llm("scoring")
        assert provider == "anthropic"
        assert model == "claude-sonnet-4-20250514"

    def test_override_with_colon_parsed_correctly(self) -> None:
        s = _make_settings(llm_agent_orchestrator="openai:gpt-4o")
        provider, model = s.get_agent_llm("orchestrator")
        assert provider == "openai"
        assert model == "gpt-4o"

    def test_override_with_model_only_uses_global_provider(self) -> None:
        """When override has no colon, it's treated as just a model name
        and the global provider is used."""
        s = _make_settings(
            llm_provider="anthropic",
            llm_agent_scoring="gpt-4o",
        )
        provider, model = s.get_agent_llm("scoring")
        assert provider == "anthropic"
        assert model == "gpt-4o"

    def test_override_ollama_model_with_colon_in_name(self) -> None:
        """Ollama models have colons in their name (e.g. llama3.1:70b).
        split(':', 1) should handle this correctly."""
        s = _make_settings(llm_agent_discovery="ollama:llama3.1:70b")
        provider, model = s.get_agent_llm("discovery")
        assert provider == "ollama"
        assert model == "llama3.1:70b"

    def test_unknown_agent_name_returns_global_default(self) -> None:
        """An agent name with no corresponding setting attribute
        should fall back to global defaults (getattr returns None)."""
        s = _make_settings(
            llm_provider="anthropic",
            llm_model="claude-sonnet-4-20250514",
        )
        provider, model = s.get_agent_llm("nonexistent_agent")
        assert provider == "anthropic"
        assert model == "claude-sonnet-4-20250514"

    def test_all_12_agents_have_settings_fields(self) -> None:
        """Verify that the Settings class defines a field for each of
        the 12 agents."""
        expected_agents = [
            "orchestrator", "database", "discovery", "parcel_research",
            "owner_research", "entity_research", "contact_research",
            "outreach", "zoning", "enrichment", "scoring", "report",
        ]
        s = _make_settings()
        for agent in expected_agents:
            assert hasattr(s, f"llm_agent_{agent}"), (
                f"Settings missing llm_agent_{agent}"
            )

    def test_each_agent_defaults_to_none(self) -> None:
        """All per-agent override fields should default to None."""
        expected_agents = [
            "orchestrator", "database", "discovery", "parcel_research",
            "owner_research", "entity_research", "contact_research",
            "outreach", "zoning", "enrichment", "scoring", "report",
        ]
        s = _make_settings()
        for agent in expected_agents:
            val = getattr(s, f"llm_agent_{agent}")
            assert val is None, (
                f"llm_agent_{agent} should default to None, got {val}"
            )


# ── _build_model_with_key: BYOK factory ──────────────────────────────────────


class TestBuildModelWithKey:
    """Test the BYOK (bring-your-own-key) model builder."""

    def test_anthropic_byok(
        self, mock_anthropic_module: MagicMock,
    ) -> None:
        model = llm._build_model_with_key(
            "anthropic", "claude-sonnet-4-20250514", api_key="my-key",
        )
        mock_anthropic_module.assert_called_once_with(
            "claude-sonnet-4-20250514", api_key="my-key",
        )
        assert model is mock_anthropic_module.return_value

    def test_openai_byok(self) -> None:
        model = llm._build_model_with_key(
            "openai", "gpt-4o", api_key="my-key",
        )
        assert model is not None

    def test_groq_byok(self) -> None:
        model = llm._build_model_with_key(
            "groq", "llama-3.3-70b-versatile", api_key="my-key",
        )
        assert model is not None

    def test_ollama_byok_default_url(self) -> None:
        model = llm._build_model_with_key("ollama", "llama3.1:8b")
        assert model is not None

    def test_ollama_byok_custom_url(self) -> None:
        model = llm._build_model_with_key(
            "ollama", "llama3.1:70b", base_url="http://gpu-server:11434",
        )
        assert model is not None

    def test_ollama_byok_strips_trailing_slash(self) -> None:
        """The base_url trailing slash should be stripped before appending /v1."""
        model = llm._build_model_with_key(
            "ollama", "llama3.1:8b", base_url="http://host:11434/",
        )
        assert model is not None

    def test_unsupported_byok_provider_raises(self) -> None:
        with pytest.raises(
            ValueError, match="BYOK not supported.*'openai-compatible'",
        ):
            llm._build_model_with_key(
                "openai-compatible", "model", api_key="k",
            )

    def test_unsupported_byok_unknown_provider_raises(self) -> None:
        with pytest.raises(ValueError, match="BYOK not supported.*'banana'"):
            llm._build_model_with_key("banana", "model", api_key="k")


# ── resolve_user_model ────────────────────────────────────────────────────────


class TestResolveUserModel:
    """Test resolve_user_model for basic dispatch and error paths.

    Full integration tests require a DB; here we test the non-DB paths.
    """

    @pytest.mark.asyncio
    async def test_returns_none_when_user_id_is_none(self) -> None:
        result = await llm.resolve_user_model(None)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_user_id_is_empty_string(self) -> None:
        result = await llm.resolve_user_model("")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_db_error(self) -> None:
        """When the DB lookup raises, the function returns None gracefully."""
        with patch(
            "aloha.db.engine.async_session_factory",
            side_effect=RuntimeError("no db"),
        ):
            result = await llm.resolve_user_model(
                "some-user-id", agent_name="scoring",
            )
        assert result is None
