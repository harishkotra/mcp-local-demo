"""
HARDENED client — precise descriptions, constrained schemas, examples.
Same model, same server, radically different results.

Patterns applied:
  1. DESCRIBE WITH EXAMPLES  — table schemas, city names, query formats
  2. CONSTRAIN THE SCHEMA    — SELECT-only pattern, city word limit
  3. SINGLE RESPONSIBILITY   — each tool does exactly one thing
  4. NEGATIVE SPACE          — "Does NOT INSERT/UPDATE/DELETE"
  5. SANITIZE TOOL OUTPUT    — strip injected instructions from tool results

Flags:
  --trace   Print raw JSON-RPC messages (tools/list, tools/call, responses)
"""
import asyncio
import json
import re
import sys

import anyio

import ollama
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()
MODEL  = next((a for a in sys.argv[1:] if not a.startswith("--")), "qwen3.5:2b")
TRACE  = "--trace" in sys.argv

DB_SCHEMA = (
    "Tables:\n"
    "  sessions(id, title, speaker, track, day, start_time, duration_min, room)\n"
    "  models(name, params_b, size_gb, tool_call_pass_rate, avg_latency_ms, license)\n"
    "  deployments(id, org, model, use_case, transport, is_local)"
)

HARDENED_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": (
                "Get current temperature and conditions for a single city. "
                "city must be a simple city name only, "
                "e.g. 'Bengaluru', 'Mumbai', 'Delhi', 'Berlin'. "
                "Returns temp in Celsius and conditions. "
                "Does NOT return forecasts. Does NOT accept country names or descriptions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name only, e.g. 'Bengaluru', 'Mumbai', 'Delhi'",
                    },
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_database",
            "description": (
                "Run a read-only SQL SELECT query against the local conference database. "
                f"{DB_SCHEMA}. "
                "SELECT queries only — does NOT INSERT, UPDATE, or DELETE. "
                "Example: \"SELECT title, speaker FROM sessions WHERE track = 'building-with-mcp'\" "
                "Example: \"SELECT name, tool_call_pass_rate FROM models ORDER BY tool_call_pass_rate DESC\" "
                "Example: \"SELECT org, use_case FROM deployments WHERE is_local = 1\""
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql_query": {
                        "type": "string",
                        "description": "A valid SQL SELECT statement using only the tables listed above.",
                        "pattern": r"^\s*[Ss][Ee][Ll][Ee][Cc][Tt]",
                    },
                },
                "required": ["sql_query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_notes",
            "description": (
                "Search through local markdown notes files for a keyword or phrase. "
                "Returns matching excerpts. query should be a word or short phrase, "
                "e.g. 'MCP transport', 'tool calling', 'schema validation'. "
                "Does NOT search the web. Does NOT summarize — only returns raw excerpts."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Keyword or phrase, e.g. 'MCP transport', 'tool calling'",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Max notes to return. Default 3, max 5.",
                        "default": 3,
                        "minimum": 1,
                        "maximum": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
]

SUCCESS_PROMPTS = [
    "Which conference sessions are longer than 45 minutes?",
    "Do I have any notes about MCP transport?",
    "Show me sessions on the building-with-mcp track and the weather in Bengaluru at the same time",
]

# ── Pattern 5: Sanitize tool output ──────────────────────────────────────────

INJECTION_PATTERNS = [
    r"(?i)ignore (all |previous |prior )?instructions",
    r"(?i)system (override|prompt|message)",
    r"(?i)you are now",
    r"(?i)maintenance mode",
    r"(?i)important.*override",
]


def sanitize_tool_output(text: str) -> tuple[str, list[str]]:
    """Remove lines matching injection patterns. Returns (clean_text, removed_lines)."""
    lines   = text.split("\n")
    clean   = []
    removed = []
    for line in lines:
        if any(re.search(p, line) for p in INJECTION_PATTERNS):
            removed.append(line)
        else:
            clean.append(line)
    return "\n".join(clean), removed


# ── JSON-RPC tracer ───────────────────────────────────────────────────────────

def _trace_msg(direction: str, color: str, msg) -> None:
    try:
        if hasattr(msg, "model_dump"):
            data = msg.model_dump(mode="json", exclude_none=True)
        elif hasattr(msg, "__dict__"):
            data = vars(msg)
        else:
            data = str(msg)
        console.print(f"[{color}]{direction}[/{color}]")
        console.print(Syntax(
            json.dumps(data, indent=2, default=str)[:800],
            "json", theme="monokai", word_wrap=True,
        ))
    except Exception:
        pass


class TracingStream:
    """Wraps an MCP transport stream to pretty-print SessionMessage objects."""
    def __init__(self, stream, direction: str, color: str):
        self._stream    = stream
        self._direction = direction
        self._color     = color

    async def receive(self):
        msg = await self._stream.receive()
        if TRACE:
            _trace_msg(self._direction, self._color, msg)
        return msg

    async def send(self, msg):
        if TRACE:
            _trace_msg(self._direction, self._color, msg)
        await self._stream.send(msg)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            msg = await self._stream.receive()
        except (StopAsyncIteration, anyio.EndOfStream):
            raise StopAsyncIteration
        if TRACE:
            _trace_msg(self._direction, self._color, msg)
        return msg

    # __anext__ is the async-iteration path; receive() is the direct-call path.
    # Both log — that's intentional: the SDK uses one or the other, not both.

    async def __aenter__(self):
        if hasattr(self._stream, "__aenter__"):
            await self._stream.__aenter__()
        return self

    async def __aexit__(self, *args):
        if hasattr(self._stream, "__aexit__"):
            await self._stream.__aexit__(*args)

    def __getattr__(self, name):
        return getattr(self._stream, name)


# ── Main client logic ─────────────────────────────────────────────────────────

async def run_with_mcp(session: ClientSession, prompt: str):
    console.print(f"\n[bold green]PROMPT:[/bold green] {prompt}")
    console.rule(style="green")

    messages = [{"role": "user", "content": prompt}]
    response = ollama.chat(model=MODEL, messages=messages, tools=HARDENED_TOOLS)
    msg = response.message

    if not msg.tool_calls:
        console.print("[yellow]⚠ No tool call — model answered directly[/yellow]")
        console.print(msg.content or "")
        return

    results = []
    for tc in msg.tool_calls:
        tool_name = tc.function.name
        args      = tc.function.arguments or {}

        console.print(f"[cyan]→ Tool:[/cyan] [bold]{tool_name}[/bold]  args: {args}")

        try:
            result = await session.call_tool(tool_name, args)
            raw    = result.content[0].text
            clean, removed = sanitize_tool_output(raw)

            if removed:
                console.print(Panel(
                    "\n".join(f"[strike]{l}[/strike]" for l in removed),
                    title="[red bold]✗ INJECTION ATTEMPT STRIPPED (Pattern 5: sanitize output)[/red bold]",
                    border_style="red",
                ))

            results.append(clean)
            console.print(f"[green]✓ Result:[/green] {clean[:300]}")
        except Exception as e:
            console.print(f"[red]✗ MCP error:[/red] {e}")

    if results:
        messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ],
        })
        for i, tc in enumerate(msg.tool_calls):
            messages.append({"role": "tool", "content": results[i] if i < len(results) else ""})

        final = ollama.chat(model=MODEL, messages=messages)
        console.print(Panel(final.message.content, title="[green]FINAL ANSWER[/green]", border_style="green"))


async def main():
    mode_line = "Precise descriptions · schema constraints · output sanitization"
    if TRACE:
        mode_line += " · [yellow]JSON-RPC trace ON[/yellow]"

    console.print(Panel(
        f"[bold green]HARDENED CLIENT[/bold green]\n"
        f"Model: [cyan]{MODEL}[/cyan]\n"
        f"{mode_line}",
        border_style="green",
    ))

    server_params = StdioServerParameters(command="python3", args=["server.py"])

    async with stdio_client(server_params) as (read, write):
        # Wrap streams for tracing if --trace
        if TRACE:
            read  = TracingStream(read,  "← SERVER", "green")
            write = TracingStream(write, "→ CLIENT", "cyan")

        async with ClientSession(read, write) as session:
            await session.initialize()
            for prompt in SUCCESS_PROMPTS:
                await run_with_mcp(session, prompt)
                await asyncio.sleep(0.5)


if __name__ == "__main__":
    asyncio.run(main())
