"""
NAIVE client — vague tool descriptions, loose schemas, thinking DISABLED.

Production agents skip extended thinking for speed/cost.
Without thinking, small models fail on vague descriptions.
Good tool descriptions work even WITHOUT extended thinking.

Failure modes triggered:
  1. Table hallucination   — model sends wrong table name (talks vs sessions)
  2. City format failure   — model sends "New Delhi" instead of "Delhi"
  3. Tool-selection collapse — compound prompt, model picks one tool or collapses
"""
import asyncio
import json
import re
import sys

import ollama
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()
MODEL = sys.argv[1] if len(sys.argv) > 1 else "qwen3.5:2b"

VALID_TABLES = {"sessions", "models", "deployments"}

# NAIVE tool definitions — vague, no schema info, no required fields
NAIVE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Gets weather",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                },
                # no "required"
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_database",
            "description": "Query the database",   # no schema, no table names, no examples
            "parameters": {
                "type": "object",
                "properties": {
                    "sql_query": {},               # no type — anything goes
                },
                # no "required"
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_notes",
            "description": "Search",
            "parameters": {
                "type": "object",
                "properties": {
                    "query":       {"type": "string"},
                    "max_results": {"type": "number"},
                },
            },
        },
    },
]

FAILURE_PROMPTS = [
    # Trigger: model hallucinates table name ("talks", "events", "talks_db")
    # because naive desc gives zero schema info
    "Which conference sessions are longer than 45 minutes?",

    # Trigger: indirect city reference → model sends "New Delhi" or "India's capital"
    # Naive desc has no format guidance; hardened says "e.g. 'Bengaluru'"
    "What's the weather in India's capital city and do I have any notes about it?",

    # Trigger: compound — model picks one tool, drops the other, or collapses
    "Show me sessions about local AI and the weather in Bengaluru at the same time",
]

# Strict rules a hardened server would enforce
STRICT_RULES = {
    "query_database": {
        # SQL must start with SELECT and reference a real table
        "sql_query": lambda v: (
            isinstance(v, str)
            and v.strip().upper().startswith("SELECT")
            and any(t in v.lower() for t in VALID_TABLES)
        ),
    },
    "get_weather": {
        "city": lambda v: (
            isinstance(v, str)
            and "'" not in v
            and "," not in v
            and "capital" not in v.lower()
            and len(v.strip().split()) <= 2
        ),
    },
    "search_notes": {
        "query": lambda v: isinstance(v, str) and len(v.strip()) > 0 and "_" not in v,
    },
}

REQUIRED_ARGS = {
    "query_database": ["sql_query"],
    "get_weather":    ["city"],
    "search_notes":   ["query"],
}


def validate_args(tool_name: str, args: dict) -> list[str]:
    errors = []

    for field in REQUIRED_ARGS.get(tool_name, []):
        if field not in args or args[field] is None:
            errors.append(f"missing required field '{field}'")

    for field, rule in STRICT_RULES.get(tool_name, {}).items():
        if field not in args:
            continue
        val = args[field]
        if not rule(val):
            if tool_name == "query_database":
                used_tables = [w for w in val.lower().split() if w.isalpha() and w not in
                               ("select", "from", "where", "and", "or", "order", "by", "limit",
                                "join", "on", "as", "group", "having", "distinct", "count",
                                "sum", "avg", "max", "min", "int", "text", "null")]
                bad = [t for t in used_tables if t not in VALID_TABLES]
                errors.append(
                    f"SQL references unknown table(s): {bad}.\n"
                    f"    Valid tables: {sorted(VALID_TABLES)}.\n"
                    f"    Naive desc gave no schema → model guessed from training data.\n"
                    f"    Hardened desc lists all tables and columns → model sends correct SQL."
                )
            elif field == "city":
                errors.append(
                    f"'{field}' = {val!r} is not a simple city name.\n"
                    f"    Naive desc said nothing about format.\n"
                    f"    Hardened desc says \"e.g. 'Bengaluru'\" → model sends exact name."
                )
            else:
                errors.append(f"'{field}' = {val!r} failed validation")

    return errors


async def run_with_mcp(session: ClientSession, prompt: str):
    console.print(f"\n[bold yellow]PROMPT:[/bold yellow] {prompt}")
    console.rule(style="yellow")

    response = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        tools=NAIVE_TOOLS,
        think=False,
    )

    msg = response.message
    raw = {k: v for k, v in msg.model_dump().items() if k not in ("thinking", "images")}
    console.print(Panel(
        Syntax(json.dumps(raw, indent=2, default=str), "json", theme="monokai"),
        title="[red]RAW MODEL RESPONSE (thinking=OFF)[/red]",
        border_style="red",
    ))

    if not msg.tool_calls:
        console.print("[red]✗ No tool call — model answered directly or gave up[/red]")
        if msg.content:
            console.print(f"[dim]{msg.content[:200]}[/dim]")
        return

    for tc in msg.tool_calls:
        tool_name = tc.function.name
        args      = tc.function.arguments or {}

        console.print(f"[cyan]→ Tool:[/cyan] [bold]{tool_name}[/bold]  args: {args}")

        errors = validate_args(tool_name, args)
        if errors:
            for err in errors:
                console.print(f"[red bold]✗ SCHEMA VALIDATION FAILED:[/red bold] {err}")
            console.print("[red]  → A strict MCP server would reject this call.[/red]")
            return

        try:
            result = await session.call_tool(tool_name, args)
            console.print(f"[green]✓ MCP result:[/green] {result.content[0].text[:300]}")
        except Exception as e:
            console.print(f"[red]✗ MCP call failed:[/red] {e}")


async def main():
    console.print(Panel(
        f"[bold red]NAIVE CLIENT[/bold red]\n"
        f"Model: [cyan]{MODEL}[/cyan]  thinking=[red]OFF[/red]\n"
        f"Vague descriptions · no schema · no required fields",
        border_style="red",
    ))

    server_params = StdioServerParameters(command="python3", args=["server.py"])

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            for prompt in FAILURE_PROMPTS:
                await run_with_mcp(session, prompt)
                await asyncio.sleep(0.5)


if __name__ == "__main__":
    asyncio.run(main())
