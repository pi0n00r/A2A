from __future__ import annotations

from dataclasses import dataclass

import pytest

from a2a_provider_plugins.codex import CodexProvider, CodexTargetState


@dataclass
class FakeBackend:
    state: CodexTargetState
    effect: tuple[str, str, str | None] | None = None

    def read_target(self, thread_id: str) -> CodexTargetState:
        return self.state

    def queue(self, thread_id: str, message: str) -> None:
        self.effect = ("queue", message, None)

    def steer(self, thread_id: str, turn_id: str, message: str) -> None:
        self.effect = ("steer", message, turn_id)

    def cancel(self, thread_id: str) -> None:
        self.effect = ("cancel", thread_id, None)


@pytest.mark.parametrize(
    ("state", "expected", "turn"),
    [(CodexTargetState("idle"), "queue", None),
     (CodexTargetState("active", "turn-7"), "steer", "turn-7")],
)
async def test_late_binds_native_delivery(state, expected, turn) -> None:
    backend = FakeBackend(state)
    provider = CodexProvider("thread-1", backend)
    reply = await provider.send("review this", context_id="ctx-1", task_id="task-1")
    assert backend.effect is not None
    assert backend.effect[0] == expected
    assert backend.effect[2] == turn
    assert "Recipient uptake is not yet verified" in reply.text


async def test_cancel_uses_native_interrupt() -> None:
    backend = FakeBackend(CodexTargetState("active", "turn-7"))
    provider = CodexProvider("thread-1", backend)
    await provider.cancel(task_id="task-1")
    assert backend.effect == ("cancel", "thread-1", None)

