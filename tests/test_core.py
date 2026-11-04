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
from starlette.testclient import TestClient

from a2a_provider_plugins import AgentDescription, ProviderAdapter, ProviderReply, build_app
from a2a_provider_plugins.executor import ProviderAgentExecutor
from a2a_provider_plugins.server import build_agent_card


class FakeAdapter(ProviderAdapter):
    """Stub adapter returning deterministic replies for testing."""

    async def send(self, text: str, *, context_id: str, task_id: str) -> ProviderReply:
        """Return a predictable response or raise an error with internal diagnostic text."""
        if text == "fail":
            raise RuntimeError("synthetic provider crash: connection=db_secret")
        return ProviderReply(text=f"reply:{text}")

    async def cancel(self, *, task_id: str) -> None:
        """Acknowledge cancellation requests."""
        return None


def description(
    *, auth_scheme: str | None = None, bearer_token: str | None = None
) -> AgentDescription:
    """Generate sample agent metadata for unit tests."""
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
        bearer_token=bearer_token,
    )


def test_agent_card_declares_only_a2a_1_0_interfaces() -> None:
    """Verify that build_agent_card declares only A2A 1.0 JSON-RPC and REST interfaces."""
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
    """Verify that advertising bearer auth attaches peerBearer metadata to the card."""
    card = build_agent_card(description(auth_scheme="Bearer"))
    assert "peerBearer" in card.security_schemes
    scheme = card.security_schemes["peerBearer"]
    assert scheme.http_auth_security_scheme.scheme == "Bearer"
    assert len(card.security_requirements) == 1
    assert "peerBearer" in card.security_requirements[0].schemes


async def test_official_handler_completes_provider_task() -> None:
    """Verify end-to-end task completion using DefaultRequestHandler and ProviderAgentExecutor."""
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


async def test_executor_failure_transitions_to_failed_state_safely() -> None:
    """Ensure exceptions transition tasks to TASK_STATE_FAILED without disclosing raw details."""
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
    # Client-safe error type is retained while internal detail is scrubbed (CWE-209)
    assert "Provider execution failed: RuntimeError" in failed_task.status.message.parts[0].text
    assert "connection=db_secret" not in failed_task.status.message.parts[0].text


def test_build_app_accepts_custom_task_store() -> None:
    """Verify that build_app accepts an injected TaskStore instance."""
    custom_store = InMemoryTaskStore()
    app = build_app(FakeAdapter(), description(), task_store=custom_store)
    assert app.title == "Example provider"


def test_build_app_requires_token_or_verifier_when_bearer_advertised() -> None:
    """Verify that advertising bearer auth without credentials raises a ValueError."""
    for token in (None, "", "   "):
        desc = description(auth_scheme="Bearer", bearer_token=token)
        with pytest.raises(ValueError, match="requires bearer_token or token_verifier"):
            build_app(FakeAdapter(), desc)


def test_build_app_enforces_bearer_authentication_on_protected_routes() -> None:
    """Verify that Bearer tokens are enforced on /a2a routes while leaving agent-card public."""
    desc = description(auth_scheme="Bearer", bearer_token="secret-token-xyz")
    app = build_app(FakeAdapter(), desc)
    client = TestClient(app)

    # 1. Agent card discovery remains public without authentication
    card_resp = client.get("/.well-known/agent-card.json")
    assert card_resp.status_code == 200
    assert card_resp.json()["name"] == "Example provider"

    # 2. Protected A2A routes reject unauthenticated requests
    unauth_resp = client.post("/a2a/rest/tasks")
    assert unauth_resp.status_code == 401

    # 3. Protected A2A routes reject invalid tokens
    invalid_resp = client.post(
        "/a2a/rest/tasks",
        headers={"Authorization": "Bearer bad-token"},
    )
    assert invalid_resp.status_code == 401

    # 4. Protected A2A routes accept valid bearer token (passes auth layer)
    valid_resp = client.post(
        "/a2a/rest/tasks",
        headers={"Authorization": "Bearer secret-token-xyz"},
    )
    # The request passes authentication (does not return 401 Unauthorized)
    assert valid_resp.status_code != 401


def test_build_app_rejects_non_ascii_bearer_token_without_server_error() -> None:
    """Verify that non-ASCII credentials compare safely and return 401."""
    app = build_app(
        FakeAdapter(),
        description(auth_scheme="Bearer", bearer_token="ascii-token"),
    )
    client = TestClient(app)

    invalid_resp = client.post(
        "/a2a/rest/tasks",
        headers=[(b"Authorization", b"Bearer token-\xf1")],
    )
    assert invalid_resp.status_code == 401
