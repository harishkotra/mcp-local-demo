"""
Local MCP Server — MCP Dev Summit Bengaluru 2026
Tools: get_weather (wttr.in), query_database (SQLite local), search_notes (local files)
Transport: STDIO  |  Official MCP Python SDK v1.27.2
"""
import json
import sqlite3
import urllib.parse
import urllib.request
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

NOTES_DIR = Path(__file__).parent / "notes"
DB_PATH   = Path(__file__).parent / "demo.db"


# ─── SQLite seed ──────────────────────────────────────────────────────────────

def seed_database():
    if DB_PATH.exists():
        return
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.executescript("""
    CREATE TABLE sessions (
        id          INTEGER PRIMARY KEY,
        title       TEXT,
        speaker     TEXT,
        track       TEXT,
        duration_min INTEGER,
        room        TEXT
    );
    CREATE TABLE models (
        name                TEXT PRIMARY KEY,
        params_b            REAL,
        size_gb             REAL,
        tool_call_pass_rate REAL,
        avg_latency_ms      INTEGER,
        license             TEXT
    );
    CREATE TABLE deployments (
        id        INTEGER PRIMARY KEY,
        org       TEXT,
        model     TEXT,
        use_case  TEXT,
        transport TEXT,
        is_local  INTEGER
    );
    """)

    cur.executemany("INSERT INTO sessions VALUES (?,?,?,?,?,?)", [
        (1,  "Running MCP Fully Local",                    "Harish Kotra",    "local-ai",   25, "Hall A"),
        (2,  "MCP Security Patterns in Production",        "Priya Nair",      "security",   40, "Hall B"),
        (3,  "Agentic Pipelines with Open Models",         "Arjun Mehta",     "agents",     30, "Hall A"),
        (4,  "Tool Design for 7B Models",                  "Sara Lin",        "local-ai",   50, "Hall C"),
        (5,  "MCP + RAG: Enterprise Patterns",             "Vikram Rao",      "enterprise", 45, "Hall B"),
        (6,  "Debugging MCP in Production",                "Ananya Sharma",   "devtools",   35, "Hall C"),
        (7,  "Capability Negotiation Deep Dive",           "James Park",      "protocol",   60, "Hall A"),
        (8,  "From STDIO to HTTP+SSE: Migration Guide",    "Meera Pillai",    "protocol",   30, "Hall B"),
        (9,  "Local LLM Benchmarks for Tool Calling",      "Rohan Desai",     "local-ai",   45, "Hall C"),
        (10, "MCP in Air-Gapped Environments",             "Divya Kumar",     "enterprise", 55, "Hall A"),
    ])

    cur.executemany("INSERT INTO models VALUES (?,?,?,?,?,?)", [
        ("qwen3.5:2b",      2.5,  2.7,  1.00, 1200, "Apache-2.0"),
        ("gemma4:e2b",      9.0,  7.2,  1.00, 4800, "Gemma ToS"),
        ("qwen3:8b",        8.0,  5.0,  0.90, 2200, "Apache-2.0"),
        ("llama3.1:8b",     8.0,  4.9,  0.70, 2100, "Meta Llama 3"),
        ("phi4-mini",       3.8,  2.5,  0.00, 250,  "MIT"),
        ("gemma3:4b",       4.0,  3.1,  0.65, 1800, "Gemma ToS"),
        ("mistral:7b",      7.0,  4.1,  0.72, 2000, "Apache-2.0"),
    ])

    cur.executemany("INSERT INTO deployments VALUES (?,?,?,?,?,?)", [
        (1, "HealthCorp India",   "qwen3:8b",    "patient record query",      "stdio",     1),
        (2, "LegalTech Pune",     "llama3.1:8b", "contract analysis",          "http+sse",  1),
        (3, "FinServ Mumbai",     "qwen3.5:2b",  "transaction classification", "stdio",     1),
        (4, "EdTech Bengaluru",   "gemma3:4b",   "student Q&A",               "http+sse",  1),
        (5, "RetailCo Delhi",     "mistral:7b",  "inventory queries",          "stdio",     1),
        (6, "SaaS Startup",       "claude-3-5",  "customer support",           "http+sse",  0),
    ])

    con.commit()
    con.close()


# ─── Weather ───────────────────────────────────────────────────────────────────

# Offline fallback if OFFLINE_MODE=1 or wttr.in unreachable
OFFLINE_WEATHER = {
    "bengaluru": {"temp_c": 24, "conditions": "pleasant, light breeze", "humidity": 60},
    "mumbai":    {"temp_c": 32, "conditions": "humid, partly cloudy",   "humidity": 85},
    "delhi":     {"temp_c": 38, "conditions": "hot, hazy",              "humidity": 40},
    "chennai":   {"temp_c": 34, "conditions": "hot and humid",          "humidity": 80},
}

import os

def fetch_weather(city: str) -> dict:
    if os.getenv("OFFLINE_MODE"):
        data = OFFLINE_WEATHER.get(city.lower())
        if data:
            return {"city": city, "source": "offline", **data}
        raise ValueError(f"No offline data for '{city}'")

    url = f"https://wttr.in/{urllib.parse.quote(city)}?format=j1"
    req = urllib.request.Request(url, headers={"User-Agent": "mcp-local-demo/1.0"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read())

    current = data["current_condition"][0]
    area    = data["nearest_area"][0]
    return {
        "city":         area["areaName"][0]["value"],
        "country":      area["country"][0]["value"],
        "temp_c":       int(current["temp_C"]),
        "feels_like_c": int(current["FeelsLikeC"]),
        "conditions":   current["weatherDesc"][0]["value"],
        "humidity":     int(current["humidity"]),
        "wind_kmph":    int(current["windspeedKmph"]),
        "source":       "wttr.in",
    }


# ─── Server ────────────────────────────────────────────────────────────────────

seed_database()
app = Server("local-mcp-demo")

VALID_TABLES = {"sessions", "models", "deployments"}


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_weather",
            description="Get current weather for a city.",
            inputSchema={
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        ),
        Tool(
            name="query_database",
            description="Run a SQL query against the local conference database.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sql_query": {"type": "string"},
                },
                "required": ["sql_query"],
            },
        ),
        Tool(
            name="search_notes",
            description="Search local notes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query":       {"type": "string"},
                    "max_results": {"type": "integer"},
                },
                "required": ["query"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "get_weather":
        city = arguments.get("city", "").strip()
        if not city:
            return [TextContent(type="text", text="Error: city is required.")]
        try:
            result = json.dumps(fetch_weather(city))
        except Exception as e:
            result = f"Error: {e}"
        return [TextContent(type="text", text=result)]

    if name == "query_database":
        sql = arguments.get("sql_query", "").strip()
        if not sql.upper().startswith("SELECT"):
            return [TextContent(type="text", text="Error: only SELECT queries allowed.")]
        try:
            con = sqlite3.connect(DB_PATH)
            con.row_factory = sqlite3.Row
            cur = con.execute(sql)
            rows = [dict(r) for r in cur.fetchall()]
            con.close()
            result = json.dumps(rows, indent=2) if rows else "No rows returned."
        except sqlite3.OperationalError as e:
            result = f"SQL error: {e}"
        return [TextContent(type="text", text=result)]

    if name == "search_notes":
        query = arguments.get("query", "").lower()
        max_results = int(arguments.get("max_results", 3))
        hits = []
        if NOTES_DIR.exists():
            for f in NOTES_DIR.glob("*.md"):
                text = f.read_text()
                if query in text.lower():
                    hits.append({"file": f.name, "excerpt": text[:300]})
                if len(hits) >= max_results:
                    break
        if not hits:
            return [TextContent(type="text", text=f"No notes found matching '{query}'.")]
        return [TextContent(type="text", text=json.dumps(hits, indent=2))]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
