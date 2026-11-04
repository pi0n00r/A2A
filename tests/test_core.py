from __future__ import annotations

import asyncio

import pytest
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

from a2a_provider_plugins import AgentDescription, ProviderAdapter, ProviderReply, build_app
from a2a_provider_plugins.executor import ProviderAgentExecutor
from a2a_provider_plugins.server import build_agent_card


class FakeAdapter(ProviderAdapter):
    async def send(self, text: str, *, context_id: str, task_id: str) -> ProviderReply:
        if text == "fail":
            raise RuntimeError("synthetic provider crash")
        return ProviderReply(text=f"reply:{text}")

    async def cancel(self, *, task_id: str) -> None:
        return None


def description(*, auth_scheme: str | None = None) -> AgentDescription:
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
        auth_scheme=auth_scheme,
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
    assert len(card.security_schemes) == 0
    assert len(card.security_requirements) == 0


def test_agent_card_declares_bearer_security_scheme() -> None:
    card = build_agent_card(description(auth_scheme="Bearer"))
    assert "peerBearer" in card.security_schemes
    scheme = card.security_schemes["peerBearer"]
    assert scheme.http_auth_security_scheme.scheme == "Bearer"
    assert len(card.security_requirements) == 1
    assert "peerBearer" in card.security_requirements[0].schemes


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
    await asyncio.sleep(0.05)


async def test_executor_failure_transitions_to_failed_state() -> None:
    task_store = InMemoryTaskStore()
    handler = DefaultRequestHandler(
        agent_executor=ProviderAgentExecutor(FakeAdapter()),
        task_store=task_store,
        agent_card=build_agent_card(description()),
    )
    with pytest.raises(RuntimeError, match="synthetic provider crash"):
        await handler.on_message_send(
            SendMessageRequest(
                message=Message(
                    role=Role.ROLE_USER,
                    message_id="message-err",
                    context_id="context-err",
                    parts=[Part(text="fail")],
                ),
                configuration=SendMessageConfiguration(accepted_output_modes=["text/plain"]),
            ),
            ServerCallContext(),
        )
    await asyncio.sleep(0.05)
    call_context = ServerCallContext()
    task_dict = list(task_store._store._store.tasks.values())[0]
    task_id = list(task_dict.keys())[0]
    failed_task = await task_store.get(task_id, call_context)
    assert failed_task is not None
    assert failed_task.status.state == TaskState.TASK_STATE_FAILED
    assert "synthetic provider crash" in failed_task.status.message.parts[0].text


def test_build_app_accepts_custom_task_store() -> None:
    custom_store = InMemoryTaskStore()
    app = build_app(FakeAdapter(), description(), task_store=custom_store)
    assert app.title == "Example provider"
