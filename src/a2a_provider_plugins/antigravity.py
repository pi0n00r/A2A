"""Google Antigravity SDK provider plugin for A2A 1.0."""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .adapter import ProviderAdapter, ProviderReply


class AntigravityProvider(ProviderAdapter):
    """Map A2A contexts to durable Antigravity conversations."""

    def __init__(
        self,
        config: Any,
        *,
        state_path: Path,
        agent_factory: Callable[[Any], Any] | None = None,
    ) -> None:
        if agent_factory is None:
            from google.antigravity import Agent

            agent_factory = Agent
        self._base_config = config
        self._agent_factory = agent_factory
        self._state_path = state_path
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, asyncio.Lock] = {}
        self._active: dict[str, Any] = {}
        self._initialize_state()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._state_path, timeout=10)

    def _initialize_state(self) -> None:
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS conversations (
                    context_id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL
                )"""
            )

    def _get_conversation(self, context_id: str) -> str | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT conversation_id FROM conversations WHERE context_id=?",
                (context_id,),
            ).fetchone()
        return row[0] if row else None

    def _set_conversation(self, context_id: str, conversation_id: str) -> None:
        with self._connect() as db:
            db.execute(
                """INSERT INTO conversations(context_id, conversation_id) VALUES (?, ?)
                ON CONFLICT(context_id) DO UPDATE SET conversation_id=excluded.conversation_id""",
                (context_id, conversation_id),
            )

    def _config_for(self, conversation_id: str | None) -> Any:
        if hasattr(self._base_config, "model_copy"):
            return self._base_config.model_copy(
                deep=True, update={"conversation_id": conversation_id}
            )
        raise TypeError("Antigravity config must support model_copy")

    async def send(self, text: str, *, context_id: str, task_id: str) -> ProviderReply:
        lock = self._locks.setdefault(context_id, asyncio.Lock())
        async with lock:
            conversation_id = self._get_conversation(context_id)
            config = self._config_for(conversation_id)
            async with self._agent_factory(config) as agent:
                response = await agent.chat(text)
                self._active[task_id] = response
                try:
                    response_text = await response.text()
                finally:
                    self._active.pop(task_id, None)
                new_conversation_id = agent.conversation_id
                if not isinstance(new_conversation_id, str) or not new_conversation_id:
                    raise RuntimeError("Antigravity did not return a conversation identifier")
                self._set_conversation(context_id, new_conversation_id)
        return ProviderReply(
            text=response_text,
            provider_task_id=new_conversation_id,
            metadata={"conversationResumable": True},
        )

    async def cancel(self, *, task_id: str) -> None:
        response = self._active.get(task_id)
        if response is not None:
            await response.cancel()

