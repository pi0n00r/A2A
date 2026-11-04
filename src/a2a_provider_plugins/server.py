"""A2A 1.0 HTTP application assembled from the official Python SDK."""

from __future__ import annotations

import secrets
from collections.abc import Callable
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
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .adapter import ProviderAdapter
from .executor import ProviderAgentExecutor


@dataclass(frozen=True, slots=True)
class AgentDescription:
    """Metadata describing the agent and its exposed interfaces."""

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
    bearer_token: str | None = None


def build_agent_card(description: AgentDescription) -> AgentCard:
    """Build a standards-compliant AgentCard from provider metadata."""
    base = description.public_url.rstrip("/")
    security_schemes = None
    security_requirements = None
    if description.auth_scheme and description.auth_scheme.strip().lower() == "bearer":
        security_schemes = {
            "peerBearer": SecurityScheme(
                http_auth_security_scheme=HTTPAuthSecurityScheme(scheme="Bearer")
            )
        }
        security_requirements = [SecurityRequirement(schemes={"peerBearer": StringList(list=[])})]

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
    *,
    bearer_token: str | None = None,
    token_verifier: Callable[[str], bool] | None = None,
) -> FastAPI:
    """Create a strict A2A 1.0 app with JSON-RPC and REST bindings.

    If Bearer authentication is advertised in the agent card, enforcement is added
    to protect A2A task routes against unauthenticated requests.
    """
    card = build_agent_card(description)
    store = task_store if task_store is not None else InMemoryTaskStore()
    handler = DefaultRequestHandler(
        agent_executor=ProviderAgentExecutor(adapter),
        task_store=store,
        agent_card=card,
    )
    app = FastAPI(title=description.name)

    is_bearer = bool(
        description.auth_scheme and description.auth_scheme.strip().lower() == "bearer"
    )
    if is_bearer:
        active_token = bearer_token if bearer_token is not None else description.bearer_token
        if (active_token is None or not active_token.strip()) and token_verifier is None:
            raise ValueError(
                "Bearer authentication advertised in agent card requires "
                "bearer_token or token_verifier"
            )

        if token_verifier is not None:
            verifier = token_verifier
        else:
            expected = active_token.encode("utf-8")

            def verifier(token: str) -> bool:
                return secrets.compare_digest(token.encode("utf-8"), expected)

        @app.middleware("http")
        async def enforce_bearer_auth(request: Request, call_next):
            # Agent card discovery remains public; protected A2A routes require Bearer token
            if request.url.path.startswith("/a2a"):
                auth_header = request.headers.get("Authorization", "")
                if not auth_header.startswith("Bearer "):
                    return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
                token = auth_header.removeprefix("Bearer ").strip()
                if not verifier(token):
                    return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
            return await call_next(request)

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
