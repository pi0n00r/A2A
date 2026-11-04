# A2A Provider Plugins

**Standards-compliant A2A, designed for agents by agents.**

Thin provider plugins behind the official [Agent2Agent Protocol](https://a2a-protocol.org/)
Python SDK.

This repository keeps the wire contract in the official SDK and limits custom code to the
provider boundary. The `main` branch contains the provider-neutral framework. Provider branches
contain independently usable plugins:

- `codex` - local Codex task delivery with state-aware Queue or Steer selection.
- `antigravity` - Google Antigravity SDK conversations exposed as A2A tasks.

This branch contains the Codex plugin. See [docs/codex.md](docs/codex.md).

## Protocol surface

- A2A 1.0 Agent Card at `/.well-known/agent-card.json`
- A2A 1.0 JSON-RPC at `/a2a/jsonrpc`
- A2A 1.0 HTTP+JSON at `/a2a/rest`
- `SendMessage`, `GetTask`, and `CancelTask` through the official request handler
- No streaming or push notification claim until a plugin implements and tests those capabilities

The Agent Card remains publicly discoverable. To advertise and enforce Bearer authentication,
set `AgentDescription.auth_scheme="Bearer"` and pass either `bearer_token` or `token_verifier` to
`build_app`. The resulting app protects both `/a2a` protocol bindings and refuses to start if the
advertised requirement has no enforcement configuration. Deploy authenticated endpoints behind
TLS. Omitting `auth_scheme` preserves the unauthenticated development behavior.

`build_app` also accepts a `TaskStore`; when omitted, it uses the SDK's in-memory store.

## Development

```bash
uv sync --extra test
uv run pytest
```

## Branch policy

`main` is vendor-neutral. Provider branches are kept rebased on a tagged main release and may add
only provider-specific dependencies, configuration, implementation, and tests.

## License

AGPL-3.0-or-later. The official A2A and provider SDKs remain under their respective licenses.

