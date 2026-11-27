from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from a2a_provider_plugins.codex import (
    CodexDispatchError,
    CodexProvider,
    CodexTargetState,
    latest_turn_marker,
)


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



def test_latest_turn_marker_honors_codex_home(tmp_path, monkeypatch) -> None:
    codex_home = tmp_path / "custom-codex"
    sessions_dir = codex_home / "sessions" / "2026" / "11" / "27"
    sessions_dir.mkdir(parents=True)
    thread_id = "019f35e6-92d9-77e0-82a2-822ccb310df3"
    rollout = sessions_dir / f"rollout-2026-11-27T00-00-00-{thread_id}.jsonl"
    rollout.write_text(
        json.dumps({"type": "event_msg", "payload": {"type": "task_started", "turn_id": "turn-42"}})
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    assert latest_turn_marker(rollout, thread_id) == ("task_started", "turn-42")

    outside = tmp_path / f"rollout-2026-11-27T00-00-00-{thread_id}.jsonl"
    outside.write_text(rollout.read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(CodexDispatchError):
        latest_turn_marker(outside, thread_id)
