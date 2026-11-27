# Codex plugin

The Codex plugin presents one configured Codex task as one A2A agent. Deploy a separate Agent Card
for each task identity that should be discoverable.

The plugin re-reads the target immediately before dispatch:

- idle target: use Codex Queue;
- active target with a current-turn proof: use Codex Steer against that exact turn;
- any other state: reject without falling back to a different delivery path.

An accepted native dispatch completes the A2A transport task with an explicit
`recipientUptake=not_verified` receipt. A later correlated response is needed to prove substantive
recipient uptake.

The public plugin injects the Codex control-plane transport because that private API can change
independently of A2A. Implementations provide `thread/read`, `turn/steer`, and `turn/interrupt`;
the stable provider contract and A2A surface do not change with that transport. Rollout path
validation defaults to `~/.codex/sessions` and honors `CODEX_HOME` when set.

Example construction:

```python
import os

from a2a_provider_plugins import AgentDescription, build_app
from a2a_provider_plugins.codex import CodexCliBackend, CodexProvider

backend = CodexCliBackend(control=my_codex_control_client)
provider = CodexProvider(thread_id=os.environ["CODEX_THREAD_ID"], backend=backend)
app = build_app(
    provider,
    AgentDescription(
        name="Codex Agent",
        description="A2A access to one configured Codex task",
        version="0.3.0",
        public_url="https://codex.example.com",
        provider_name="Example",
        provider_url="https://example.com",
        skill_id="delegate",
        skill_name="Delegate",
        skill_description="Delegate a bounded handoff to this Codex task",
        auth_scheme="Bearer",
    ),
    bearer_token=os.environ["A2A_BEARER_TOKEN"],
)
```

For production deployments, also pass a durable `task_store` to `build_app()` so `GetTask`
reconciliation survives process restarts.
