# Common Failure Modes in Local MCP

## 1. Tool hallucination
Model invents a tool name that doesn't exist in the server's tool list.
Example: calls "search" when the tool is named "search_notes".

Detection: Validate tool name before forwarding to MCP server.
Fix: Use exact, distinctive tool names. Avoid generic names like "search", "get", "run".

## 2. Schema non-compliance
Model returns JSON that doesn't match the required schema.
Most common: missing required fields, wrong types, extra fields.

Detection: Validate arguments against tool's inputSchema before calling.
Fix: Add type constraints, mark required fields explicitly, add examples.

## 3. Tool-selection collapse
Model picks the wrong tool for the job, or picks no tool at all.
Common with vague descriptions when multiple tools have similar purposes.

Detection: Log which tool was called vs. which was expected.
Fix: Single-responsibility tools, negative space in descriptions.

## 4. Context window thrash
On long conversations, tool results push earlier context out of window.
Model loses track of which tools exist.

Detection: Model stops calling tools after several turns.
Fix: Keep tool descriptions concise. Summarize tool results before adding to context.

## 5. Capability negotiation mismatch
Client and server on different MCP spec versions.
Server advertises capabilities the client doesn't understand.

Detection: Check initialization handshake logs.
Fix: Pin MCP SDK versions. Test with `mcp dev` inspector first.
