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
the stable provider contract and A2A surface do not change with that transport.

