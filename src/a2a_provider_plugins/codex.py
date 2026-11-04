"""Codex provider plugin for the official A2A task lifecycle."""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .adapter import ProviderAdapter, ProviderReply


class CodexDispatchError(RuntimeError):
    """The native Codex delivery was rejected or has an unknown outcome."""


@dataclass(frozen=True, slots=True)
class CodexTargetState:
    state: str
    turn_id: str | None = None


class CodexBackend(Protocol):
    def read_target(self, thread_id: str) -> CodexTargetState: ...
    def queue(self, thread_id: str, message: str) -> None: ...
    def steer(self, thread_id: str, turn_id: str, message: str) -> None: ...
    def cancel(self, thread_id: str) -> None: ...


def latest_turn_marker(path: Path, thread_id: str) -> tuple[str, str]:
    """Return the latest bounded task marker from the exact Codex rollout."""
    root = (Path.home() / ".codex/sessions").resolve()
    resolved = path.resolve(strict=True)
    uid = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    expected_name = re.compile(
        rf"^rollout-.+-{re.escape(thread_id)}(?:_{uid})?\.jsonl$", re.IGNORECASE
    )
    if root not in resolved.parents or not expected_name.fullmatch(resolved.name):
        raise CodexDispatchError("Codex returned an unexpected rollout path")
    size = resolved.stat().st_size
    window = 65536
    while window <= 32 * 1024 * 1024:
        offset = max(0, size - window)
        with resolved.open("rb") as handle:
            handle.seek(offset)
            data = handle.read()
        if offset:
            data = data.split(b"\n", 1)[-1]
        for line in reversed(data.splitlines()):
            try:
                event = json.loads(line)
            except (ValueError, UnicodeDecodeError):
                continue
            payload = event.get("payload", {})
            if event.get("type") != "event_msg" or not isinstance(payload, dict):
                continue
            kind = payload.get("type")
            turn_id = payload.get("turn_id")
            if kind in {"task_started", "task_complete"} and isinstance(turn_id, str):
                return kind, turn_id
        if offset == 0:
            break
        window *= 2
    raise CodexDispatchError("No bounded turn proof in Codex rollout tail")


class CodexCliBackend:
    """Native backend using Codex CLI plus an injected control-plane client."""

    def __init__(self, control, cli: Path | None = None) -> None:
        self._control = control
        self._cli = cli or Path(os.environ.get("CODEX_CLI", "codex"))

    def read_target(self, thread_id: str) -> CodexTargetState:
        result = self._control.rpc(
            "thread/read", {"threadId": thread_id, "includeTurns": False}
        )
        thread = result.get("thread") if isinstance(result, dict) else None
        if not isinstance(thread, dict) or thread.get("id") != thread_id:
            raise CodexDispatchError("Codex thread identity mismatch")
        status = thread.get("status")
        state = status.get("type") if isinstance(status, dict) else None
        if state == "idle":
            return CodexTargetState("idle")
        if state != "active" or thread.get("canAcceptDirectInput") is False:
            raise CodexDispatchError("Codex target state is not dispatchable")
        path = thread.get("path")
        if not isinstance(path, str):
            raise CodexDispatchError("Codex target has no rollout path")
        marker, turn_id = latest_turn_marker(Path(path), thread_id)
        if marker != "task_started":
            raise CodexDispatchError("Codex active-turn proof is stale")
        return CodexTargetState("active", turn_id)

    def queue(self, thread_id: str, message: str) -> None:
        result = subprocess.run(
            [str(self._cli), "queue", "--thread", thread_id, "--message", message],
            capture_output=True, text=True, timeout=20, check=False,
        )
        if result.returncode != 0:
            raise CodexDispatchError("Codex queue outcome is unknown; reconcile before retry")

    def steer(self, thread_id: str, turn_id: str, message: str) -> None:
        result = self._control.rpc(
            "turn/steer",
            {"threadId": thread_id, "expectedTurnId": turn_id,
             "input": [{"type": "text", "text": message}]},
        )
        if not isinstance(result, dict) or result.get("turnId") != turn_id:
            raise CodexDispatchError("Codex steer outcome is unknown; reconcile before retry")

    def cancel(self, thread_id: str) -> None:
        self._control.rpc("turn/interrupt", {"threadId": thread_id})


class CodexProvider(ProviderAdapter):
    """Expose one configured Codex task as one discoverable A2A agent."""

    def __init__(self, thread_id: str, backend: CodexBackend) -> None:
        if not thread_id.strip():
            raise ValueError("thread_id is required")
        self._thread_id = thread_id
        self._backend = backend

    async def send(self, text: str, *, context_id: str, task_id: str) -> ProviderReply:
        framed = (
            f"[A2A peer task {task_id}; context {context_id}. "
            "Transport acceptance is not recipient uptake.]\n" + text
        )
        state = await asyncio.to_thread(self._backend.read_target, self._thread_id)
        if state.state == "idle":
            await asyncio.to_thread(self._backend.queue, self._thread_id, framed)
            delivery = "queue"
        elif state.state == "active" and state.turn_id:
            await asyncio.to_thread(
                self._backend.steer, self._thread_id, state.turn_id, framed
            )
            delivery = "steer"
        else:
            raise CodexDispatchError("Codex target state is not dispatchable")
        return ProviderReply(
            text=(f"Codex transport accepted the task via {delivery}. "
                  "Recipient uptake is not yet verified."),
            provider_task_id=self._thread_id,
            metadata={"delivery": delivery, "recipientUptake": "not_verified"},
        )

    async def cancel(self, *, task_id: str) -> None:
        await asyncio.to_thread(self._backend.cancel, self._thread_id)

