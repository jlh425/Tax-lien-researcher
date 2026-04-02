"""Base agent class for all Aloha research agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import structlog

from aloha.core.llm import get_agent_model, resolve_user_model


class BaseAgent(ABC):
    """Abstract base class every Aloha agent must inherit from.

    Provides shared logging, error handling, queue helpers, and automatic
    LLM model resolution so concrete agents only need to implement ``run``
    and ``get_tools``.

    The LLM model is resolved per-agent from ``aloha.core.llm.get_agent_model()``.
    Each agent checks for a ``LLM_AGENT_<NAME>`` env var override (format:
    ``provider:model``), falling back to the global ``LLM_PROVIDER`` /
    ``LLM_MODEL`` defaults. This lets you mix providers — e.g. Claude for
    complex agents, Ollama for simple ones.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.log: structlog.stdlib.BoundLogger = structlog.get_logger().bind(
            agent=name,
        )
        self.model = get_agent_model(name)

    # ── Abstract interface ────────────────────────────────────────────────

    @abstractmethod
    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        """Execute the agent's primary task.

        Args:
            context: Arbitrary dict carrying task payload, research IDs, etc.

        Returns:
            Result dict that will be persisted by the orchestrator.
        """

    @abstractmethod
    def get_tools(self) -> list[dict[str, Any]]:
        """Return the tool definitions this agent can invoke."""

    # ── Shared helpers ────────────────────────────────────────────────────

    async def claim_queue_item(self, item_id: int) -> bool:
        """Attempt to claim a queue item (SKIP LOCKED).

        Placeholder -- actual SQL will live in the worker layer.
        """
        self.log.info("claiming_queue_item", item_id=item_id)
        return True

    async def release_queue_item(self, item_id: int, *, success: bool) -> None:
        """Mark a queue item as complete or failed.

        Placeholder -- actual SQL will live in the worker layer.
        """
        status = "complete" if success else "failed"
        self.log.info("releasing_queue_item", item_id=item_id, status=status)

    async def get_user_model(self, context: dict[str, Any]) -> Any | None:
        """Resolve a per-user LLM model from context, or return ``None``.

        Call this in ``run()`` to honour BYOK keys::

            model = (await self.get_user_model(ctx)) or self.model
        """
        user_id = context.get("user_id")
        if not user_id:
            return None
        return await resolve_user_model(user_id, agent_name=self.name)

    async def handle_error(self, error: Exception, context: dict[str, Any]) -> None:
        """Centralised error handling hook.

        Subclasses may override to add custom recovery logic.
        """
        self.log.error(
            "agent_error",
            error=str(error),
            error_type=type(error).__name__,
            context_keys=list(context.keys()),
        )
