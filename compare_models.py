"""
Model comparison — runs 5 tool-call prompts against two models,
prints a pass/fail table. Live demo segment: model swap.

Usage: python3 compare_models.py
"""
import asyncio
import json
import time

import ollama
from rich.console import Console
from rich.table import Table

console = Console()

MODELS = ["qwen3.5:2b", "gemma4:e2b"]

DB_SCHEMA = (
    "Tables: sessions(id, title, speaker, track, day, start_time, duration_min, room), "
    "models(name, params_b, size_gb, tool_call_pass_rate, avg_latency_ms, license), "
    "deployments(id, org, model, use_case, transport, is_local)"
)

HARDENED_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": (
                "Get current temperature and conditions for a single city. "
                "city must be a city name only, e.g. 'Bengaluru', 'Mumbai', 'Delhi', 'Berlin'. "
                "Returns temp in Celsius and conditions. Does NOT accept country names."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name e.g. 'Bengaluru'"},
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
                f"Run a read-only SQL SELECT query against the local conference database. {DB_SCHEMA}. "
                "SELECT only — no INSERT/UPDATE/DELETE. "
                "Example: \"SELECT title, speaker FROM sessions WHERE track = 'local-ai'\""
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql_query": {
                        "type": "string",
                        "pattern": r"^\s*[Ss][Ee][Ll][Ee][Cc][Tt]",
                        "description": "A valid SQL SELECT statement using only the tables listed above.",
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
                "Search local markdown notes for a keyword or phrase. "
                "Returns matching excerpts. Does NOT search the web."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer", "default": 3, "minimum": 1, "maximum": 5},
                },
                "required": ["query"],
            },
        },
    },
]

# (prompt, expected_tool, expected_arg_key)
TEST_CASES = [
    ("What's the weather in Bengaluru?",                         "get_weather",    "city"),
    ("Which sessions are in the local-ai track?",                "query_database", "sql_query"),
    ("Search my notes for MCP transport",                        "search_notes",   "query"),
    ("Show me all models with tool_call_pass_rate above 0.8",    "query_database", "sql_query"),
    ("Find notes about tool calling and schemas",                "search_notes",   "query"),
]


def check_tool_call(response, expected_tool: str, expected_arg: str) -> tuple[bool, str]:
    msg = response.message
    if not msg.tool_calls:
        return False, "no tool call"
    tc = msg.tool_calls[0]
    if tc.function.name != expected_tool:
        return False, f"called '{tc.function.name}' (expected '{expected_tool}')"
    args = tc.function.arguments or {}
    if expected_arg not in args:
        return False, f"missing arg '{expected_arg}'"
    return True, "✓"


def run_test(model: str, prompt: str, expected_tool: str, expected_arg: str) -> tuple[bool, str, float]:
    try:
        t0 = time.time()
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            tools=HARDENED_TOOLS,
        )
        elapsed = time.time() - t0
        ok, reason = check_tool_call(response, expected_tool, expected_arg)
        return ok, reason, elapsed
    except Exception as e:
        return False, str(e)[:40], 0.0


def main():
    console.print("\n[bold]Local MCP Model Comparison[/bold] — hardened tool descriptions\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Prompt", style="dim", max_width=38)
    table.add_column("Tool", style="cyan")
    for m in MODELS:
        table.add_column(m, justify="center")

    results  = {m: [] for m in MODELS}
    timings  = {m: [] for m in MODELS}

    for prompt, expected_tool, expected_arg in TEST_CASES:
        row = [prompt[:38], expected_tool]
        for model in MODELS:
            console.print(f"  Testing [cyan]{model}[/cyan]: {prompt[:50]}...", end="")
            ok, reason, elapsed = run_test(model, prompt, expected_tool, expected_arg)
            results[model].append(ok)
            timings[model].append(elapsed)
            status = "PASS" if ok else "FAIL"
            cell = (
                f"[green]PASS[/green]\n[dim]{elapsed:.1f}s[/dim]"
                if ok else
                f"[red]FAIL[/red]\n[dim]{reason}[/dim]"
            )
            row.append(cell)
            console.print(f" {status} ({elapsed:.1f}s)")
        table.add_row(*row)

    console.print()
    console.print(table)

    console.print("\n[bold]Summary[/bold]")
    for model in MODELS:
        score   = sum(results[model])
        total   = len(TEST_CASES)
        avg_t   = sum(timings[model]) / len(timings[model]) if timings[model] else 0
        color   = "green" if score == total else "yellow" if score >= total // 2 else "red"
        console.print(f"  [{color}]{model}: {score}/{total}  avg {avg_t:.1f}s/call[/{color}]")


if __name__ == "__main__":
    main()
