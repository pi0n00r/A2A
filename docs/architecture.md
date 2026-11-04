# Architecture

The official `a2a-sdk` owns protocol parsing, version negotiation, Agent Card serialization,
task persistence interfaces, transport routes, errors, and task lifecycle validation.

`ProviderAgentExecutor` is the only bridge into provider code:

1. The SDK validates and admits an A2A 1.0 request.
2. The executor creates or resumes the A2A task and marks it working.
3. A provider plugin receives only text plus opaque A2A context and task identifiers.
4. The provider response becomes an A2A artifact and the task completes.
5. Provider errors remain errors; the bridge does not fabricate recipient uptake.

Provider-native conversation identifiers are implementation state. They are never substituted for
A2A task IDs, context IDs, or message IDs.

