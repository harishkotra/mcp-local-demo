"""
HARDENED client — precise descriptions, constrained schemas, examples.
Same model, same server, radically different results.

Patterns applied:
  1. DESCRIBE WITH EXAMPLES  — table schemas, city names, query formats
  2. CONSTRAIN THE SCHEMA    — SELECT-only pattern, city word limit
  3. SINGLE RESPONSIBILITY   — each tool does exactly one thing
  4. NEGATIVE SPACE          — "Does NOT INSERT/UPDATE/DELETE"
"""
import asyncio
import json
import sys

import ollama
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from rich.console import Console
from rich.panel import Panel

console = Console()
MODEL = sys.argv[1] if len(sys.argv) > 1 else "qwen3.5:2b"

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
                "Example: \"SELECT title, speaker FROM sessions WHERE track = 'local-ai'\" "
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
    "Show me sessions about local AI and the weather in Bengaluru at the same time",
]


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
            text = result.content[0].text
            results.append(text)
            console.print(f"[green]✓ Result:[/green] {text[:300]}")
        except Exception as e:
            console.print(f"[red]✗ MCP error:[/red] {e}")

    # Let model synthesize final answer from tool results
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
    console.print(Panel(
        f"[bold green]HARDENED CLIENT[/bold green]\n"
        f"Model: [cyan]{MODEL}[/cyan]\n"
        f"Precise descriptions · schema constraints · examples · negative space",
        border_style="green",
    ))

    server_params = StdioServerParameters(command="python3", args=["server.py"])

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            for prompt in SUCCESS_PROMPTS:
                await run_with_mcp(session, prompt)
                await asyncio.sleep(0.5)


if __name__ == "__main__":
    asyncio.run(main())
