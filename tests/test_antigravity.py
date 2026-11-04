from __future__ import annotations

from dataclasses import dataclass, replace

from a2a_provider_plugins.antigravity import AntigravityProvider


@dataclass(frozen=True)
class FakeConfig:
    conversation_id: str | None = None

    def model_copy(self, *, deep: bool, update: dict):
        return replace(self, **update)


class FakeResponse:
    def __init__(self, text: str) -> None:
        self.value = text
        self.cancelled = False

    async def text(self) -> str:
        return self.value

    async def cancel(self) -> None:
        self.cancelled = True


class FakeAgent:
    seen: list[str | None] = []

    def __init__(self, config: FakeConfig) -> None:
        self.config = config
        self.conversation_id = config.conversation_id or "conversation-1"

    async def __aenter__(self):
        self.seen.append(self.config.conversation_id)
        return self

    async def __aexit__(self, *_):
        return None

    async def chat(self, text: str) -> FakeResponse:
        return FakeResponse(f"agent:{text}")


async def test_resumes_provider_conversation_for_same_a2a_context(tmp_path) -> None:
    FakeAgent.seen.clear()
    provider = AntigravityProvider(
        FakeConfig(), state_path=tmp_path / "state.sqlite", agent_factory=FakeAgent
    )
    first = await provider.send("one", context_id="ctx-1", task_id="task-1")
    second = await provider.send("two", context_id="ctx-1", task_id="task-2")
    assert first.text == "agent:one"
    assert second.text == "agent:two"
    assert FakeAgent.seen == [None, "conversation-1"]


async def test_different_a2a_context_starts_new_conversation(tmp_path) -> None:
    FakeAgent.seen.clear()
    provider = AntigravityProvider(
        FakeConfig(), state_path=tmp_path / "state.sqlite", agent_factory=FakeAgent
    )
    await provider.send("one", context_id="ctx-1", task_id="task-1")
    await provider.send("two", context_id="ctx-2", task_id="task-2")
    assert FakeAgent.seen == [None, None]

