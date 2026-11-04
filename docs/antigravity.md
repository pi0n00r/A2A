# Antigravity plugin

The Antigravity plugin exposes a Google Antigravity SDK agent through the official A2A 1.0
task lifecycle. It does not implement a parallel private RPC protocol.

Each A2A `contextId` is durably mapped to one opaque Antigravity `conversation_id`. A subsequent
A2A message in the same context resumes that conversation; another context starts independently.
Only one turn per context runs at a time because the Antigravity SDK does not define concurrent
turns for one conversation.

Cancellation uses the SDK's active `ChatResponse.cancel()` operation. Provider conversation IDs
remain adapter state and never replace A2A task, message, or context identifiers.

Example construction:

```python
from pathlib import Path

from google.antigravity import LocalAgentConfig

from a2a_provider_plugins import AgentDescription, build_app
from a2a_provider_plugins.antigravity import AntigravityProvider

provider = AntigravityProvider(
    LocalAgentConfig(save_dir="./trajectories"),
    state_path=Path("./state/antigravity.sqlite"),
)
app = build_app(provider, AgentDescription(
    name="Antigravity Agent",
    description="A2A access to an Antigravity agent",
    version="0.1.0",
    public_url="https://agent.example.com",
    provider_name="Example",
    provider_url="https://example.com",
    skill_id="delegate",
    skill_name="Delegate",
    skill_description="Delegate a task to Antigravity",
))
```

Credentials are supplied to the Antigravity SDK through its supported environment or Google Cloud
authentication. They are not stored in the A2A task store or Agent Card.

