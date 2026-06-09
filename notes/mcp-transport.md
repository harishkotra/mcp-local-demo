# MCP Transport Options

## STDIO
- Default for local setups
- Server is a subprocess of the client
- No port binding required
- Communication via stdin/stdout
- Best for: single-client, local-only, CLI tools

## HTTP + SSE (Server-Sent Events)
- Server runs independently on a port
- Multiple clients can connect simultaneously
- Better for: web UIs, multi-agent systems, browser-based clients
- Adds latency vs STDIO on constrained machines

## Tradeoffs on constrained hardware (M1/M2 laptops)
- STDIO: zero network overhead, lower latency, simpler process management
- HTTP+SSE: required if you want a browser client or multiple simultaneous agents
- For air-gapped / offline deployments: STDIO is the safer default

## Capability negotiation
MCP handshake includes capability exchange. Small models may not correctly
interpret capability mismatch errors — always validate server and client
versions match before assuming a tool call failure is a model issue.
