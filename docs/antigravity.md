# Antigravity plugin

The Antigravity plugin exposes a Google Antigravity **Python SDK** agent (`google.antigravity.Agent`)
through the official A2A 1.0 task lifecycle. It does not implement a parallel private RPC protocol,
and it does not inject messages into an existing Antigravity Desktop GUI conversation (which is a
separate runtime surface from the Python SDK).

Each A2A `contextId` is durably mapped to one opaque Antigravity `conversation_id`. A subsequent
A2A message in the same context resumes that conversation; another context starts independently.
You may optionally pass `initial_conversations={"<context_id>": "<conversation_id>"}` to pre-bind
an existing SDK conversation without overwriting previously persisted mappings. Only one turn per
context runs at a time because the Antigravity SDK does not define concurrent turns for one
conversation.

Cancellation uses the SDK's active `ChatResponse.cancel()` operation. Provider conversation IDs
remain adapter state and never replace A2A task, message, or context identifiers.

Example construction:

```python
import os
from pathlib import Path

from google.antigravity import LocalAgentConfig

from a2a_provider_plugins import AgentDescription, build_app
from a2a_provider_plugins.antigravity import AntigravityProvider

provider = AntigravityProvider(
    LocalAgentConfig(save_dir="./trajectories"),
    state_path=Path("./state/antigravity.sqlite"),
)
app = build_app(
    provider,
    AgentDescription(
        name="Antigravity Agent",
        description="A2A access to an Antigravity agent",
        version="0.3.0",
        public_url="https://agent.example.com",
        provider_name="Example",
        provider_url="https://example.com",
        skill_id="delegate",
        skill_name="Delegate",
        skill_description="Delegate a task to Antigravity",
        auth_scheme="Bearer",
    ),
    bearer_token=os.environ["A2A_BEARER_TOKEN"],
)
```

For production deployments, also pass a durable `task_store` to `build_app()` so `GetTask`
reconciliation survives process restarts.

Credentials are supplied to the Antigravity SDK through its supported environment or Google Cloud
authentication. They are not stored in the A2A task store or Agent Card.
