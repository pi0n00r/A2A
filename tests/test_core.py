from __future__ import annotations

import asyncio

from a2a.server.context import ServerCallContext
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    Message,
    Part,
    Role,
    SendMessageConfiguration,
    SendMessageRequest,
    Task,
    TaskState,
)

from a2a_provider_plugins import AgentDescription, ProviderAdapter, ProviderReply
from a2a_provider_plugins.executor import ProviderAgentExecutor
from a2a_provider_plugins.server import build_agent_card


class FakeAdapter(ProviderAdapter):
    async def send(self, text: str, *, context_id: str, task_id: str) -> ProviderReply:
        return ProviderReply(text=f"reply:{text}")

    async def cancel(self, *, task_id: str) -> None:
        return None


def description() -> AgentDescription:
    return AgentDescription(
        name="Example provider",
        description="Example A2A provider adapter",
        version="0.1.0",
        public_url="https://agent.example.test",
        provider_name="Example",
        provider_url="https://example.test",
        skill_id="delegate",
        skill_name="Delegate",
        skill_description="Delegate work to the provider",
    )


def test_agent_card_declares_only_a2a_1_0_interfaces() -> None:
    card = build_agent_card(description())
    assert {item.protocol_version for item in card.supported_interfaces} == {"1.0"}
    assert {item.protocol_binding for item in card.supported_interfaces} == {
        "JSONRPC",
        "HTTP+JSON",
    }
    assert card.capabilities.streaming is False
    assert card.capabilities.push_notifications is False


async def test_official_handler_completes_provider_task() -> None:
    handler = DefaultRequestHandler(
        agent_executor=ProviderAgentExecutor(FakeAdapter()),
        task_store=InMemoryTaskStore(),
        agent_card=build_agent_card(description()),
    )
    result = await handler.on_message_send(
        SendMessageRequest(
            message=Message(
                role=Role.ROLE_USER,
                message_id="message-1",
                context_id="context-1",
                parts=[Part(text="hello")],
            ),
            configuration=SendMessageConfiguration(accepted_output_modes=["text/plain"]),
        ),
        ServerCallContext(),
    )
    assert isinstance(result, Task)
    assert result.status.state == TaskState.TASK_STATE_COMPLETED
    assert result.context_id == "context-1"
    assert result.artifacts[0].parts[0].text == "reply:hello"
    # Let the SDK's event source close its producer and consumer tasks.
    await asyncio.sleep(0.05)

