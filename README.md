# A2A Provider Plugins

Thin provider plugins behind the official [Agent2Agent Protocol](https://a2a-protocol.org/)
Python SDK.

This repository keeps the wire contract in the official SDK and limits custom code to the
provider boundary. The `main` branch contains the provider-neutral framework. Provider branches
contain independently usable plugins:

- `codex` - local Codex task delivery with state-aware Queue or Steer selection.
- `antigravity` - Google Antigravity SDK conversations exposed as A2A tasks.

This branch contains the Antigravity plugin. See
[docs/antigravity.md](docs/antigravity.md).

## Protocol surface

- A2A 1.0 Agent Card at `/.well-known/agent-card.json`
- A2A 1.0 JSON-RPC at `/a2a/jsonrpc`
- A2A 1.0 HTTP+JSON at `/a2a/rest`
- `SendMessage`, `GetTask`, and `CancelTask` through the official request handler
- No streaming or push notification claim until a plugin implements and tests those capabilities

The Agent Card is the discovery boundary. Authentication belongs at the deployment boundary and
must match the security declarations added by that deployment; this library does not pretend an
unauthenticated development server is production-ready.

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

