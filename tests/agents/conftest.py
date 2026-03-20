"""Shared fixtures for agent tests.

The module-level singletons in agent.py files call get_agent_model() on import,
which tries to build a real LLM model and fails if the anthropic SDK version
is incompatible.  We patch at module level (before collection) AND via an
autouse fixture (for agents instantiated during tests).
"""

from unittest.mock import patch

import pytest

# ── Collection-time patch ────────────────────────────────────────────────────
# Must be active BEFORE pytest collects test modules that import agent
# singletons.  We intentionally never call stop() — the mock must remain
# active for the entire test-process lifetime.
_llm_patch = patch("aloha.core.llm.get_agent_model", return_value="test-model")
_llm_patch.start()


@pytest.fixture(autouse=True)
def _patch_agent_model():
    """Also patch the base-module reference for agents created in tests."""
    with patch("aloha.agents.base.get_agent_model", return_value="test-model"):
        yield
