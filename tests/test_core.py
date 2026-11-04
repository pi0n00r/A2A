from __future__ import annotations

from a2a_provider_plugins import AgentDescription, ProviderAdapter, ProviderReply
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

