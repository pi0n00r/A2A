"""A2A 1.0 HTTP application assembled from the official Python SDK."""

from __future__ import annotations

from dataclasses import dataclass

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    add_a2a_routes_to_fastapi,
    create_agent_card_routes,
    create_jsonrpc_routes,
    create_rest_routes,
)
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from a2a.server.tasks.task_store import TaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentProvider,
    AgentSkill,
    HTTPAuthSecurityScheme,
    SecurityRequirement,
    SecurityScheme,
    StringList,
)
from fastapi import FastAPI

from .adapter import ProviderAdapter
from .executor import ProviderAgentExecutor


@dataclass(frozen=True, slots=True)
class AgentDescription:
    name: str
    description: str
    version: str
    public_url: str
    provider_name: str
    provider_url: str
    skill_id: str
    skill_name: str
    skill_description: str
    auth_scheme: str | None = None


def build_agent_card(description: AgentDescription) -> AgentCard:
    base = description.public_url.rstrip("/")
    security_schemes = None
    security_requirements = None
    if description.auth_scheme and description.auth_scheme.strip().lower() == "bearer":
        security_schemes = {
            "peerBearer": SecurityScheme(
                http_auth_security_scheme=HTTPAuthSecurityScheme(scheme="Bearer")
            )
        }
        security_requirements = [
            SecurityRequirement(schemes={"peerBearer": StringList(list=[])})
        ]

    return AgentCard(
        name=description.name,
        description=description.description,
        provider=AgentProvider(
            organization=description.provider_name,
            url=description.provider_url,
        ),
        version=description.version,
        capabilities=AgentCapabilities(streaming=False, push_notifications=False),
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        skills=[
            AgentSkill(
                id=description.skill_id,
                name=description.skill_name,
                description=description.skill_description,
                tags=["a2a", "provider-adapter"],
                input_modes=["text/plain"],
                output_modes=["text/plain"],
            )
        ],
        supported_interfaces=[
            AgentInterface(
                protocol_binding="JSONRPC",
                protocol_version="1.0",
                url=f"{base}/a2a/jsonrpc",
            ),
            AgentInterface(
                protocol_binding="HTTP+JSON",
                protocol_version="1.0",
                url=f"{base}/a2a/rest",
            ),
        ],
        security_schemes=security_schemes,
        security_requirements=security_requirements,
    )


def build_app(
    adapter: ProviderAdapter,
    description: AgentDescription,
    task_store: TaskStore | None = None,
) -> FastAPI:
    """Create a strict A2A 1.0 app with JSON-RPC and REST bindings."""
    card = build_agent_card(description)
    store = task_store if task_store is not None else InMemoryTaskStore()
    handler = DefaultRequestHandler(
        agent_executor=ProviderAgentExecutor(adapter),
        task_store=store,
        agent_card=card,
    )
    app = FastAPI(title=description.name)
    add_a2a_routes_to_fastapi(
        app,
        agent_card_routes=create_agent_card_routes(agent_card=card),
        jsonrpc_routes=create_jsonrpc_routes(
            request_handler=handler,
            rpc_url="/a2a/jsonrpc",
            enable_v0_3_compat=False,
        ),
        rest_routes=create_rest_routes(
            request_handler=handler,
            path_prefix="/a2a/rest",
            enable_v0_3_compat=False,
        ),
    )
    return app
