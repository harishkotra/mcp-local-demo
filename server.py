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
        id           INTEGER PRIMARY KEY,
        title        TEXT,
        speaker      TEXT,
        track        TEXT,
        day          TEXT,
        start_time   TEXT,
        duration_min INTEGER,
        room         TEXT
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

    # Real sessions from MCP Dev Summit Bengaluru 2026
    # Tracks: keynote | building-with-mcp | security | agents | protocol | enterprise | ecosystem | workshop
    cur.executemany("INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?)", [
        # ── Tuesday June 9 — Keynotes ─────────────────────────────────────────
        ( 1, "Welcome & Opening Remarks",
              "Angie Jones",
              "keynote", "Tuesday", "09:30", 10, "Convention Hall"),
        ( 2, "Keynote: Director of Developer Experience, AWS",
              "David Nalley",
              "keynote", "Tuesday", "09:40", 10, "Convention Hall"),
        ( 3, "The Missing Middle: Shared Infrastructure MCP Needs",
              "Hrittik Roy",
              "keynote", "Tuesday", "09:55", 10, "Convention Hall"),
        ( 4, "From UX to MX: Designing Software for Machines",
              "Sam Partee",
              "keynote", "Tuesday", "10:05", 10, "Convention Hall"),
        ( 5, "Building Trustworthy Agentic AI on India's Digital Public Infrastructure",
              "Jagadish Babu, Neha Jagadeesh & Arjun Venkatraman",
              "keynote", "Tuesday", "10:15", 15, "Convention Hall"),

        # ── Tuesday June 9 — Sessions ─────────────────────────────────────────
        ( 6, "Improving Reliability in MCP Applications Through Tool Design",
              "Yashasvi Misra",
              "building-with-mcp", "Tuesday", "11:00", 25, "Convention Hall"),
        ( 7, "MCP in Production: OAuth, Session Isolation, and Audit Trails",
              "Rajan Sharma",
              "security", "Tuesday", "11:00", 25, "Scarlet 2&3"),
        ( 8, "Workshop: From One Agent To a Fleet: Distributed Multi-Agent Workflows",
              "Mansi Rathod & Yashraj Singh",
              "workshop", "Tuesday", "11:00", 60, "Scarlet 1"),
        ( 9, "Intelligence Placement Patterns for MCP-Connected Agent Systems",
              "Giri Venkatesan",
              "building-with-mcp", "Tuesday", "11:30", 25, "Convention Hall"),
        (10, "From Alert To Revert: One MCP, 500+ Tools for Production Triage",
              "Avinash Kumar Lodhi",
              "enterprise", "Tuesday", "11:30", 25, "Scarlet 2&3"),
        (11, "Context-Aware MCP Servers for Small Language Models",
              "Vivek Mankar, Anto Ajay Raj John & Nethra Khandige",
              "building-with-mcp", "Tuesday", "12:00", 25, "Scarlet 2&3"),
        (12, "OWASP MCP Top 10: A Practical Security Guide for MCP Builders",
              "Sankalp Paranjpe & Dheeraj Choudhary",
              "security", "Tuesday", "12:00", 25, "Convention Hall"),
        (13, "Designing a Control Plane for Agentic Systems Using MCP",
              "Malepati Bala Siva Sai Akhil",
              "agents", "Tuesday", "13:55", 25, "Scarlet 2&3"),
        (14, "From SSE To Streamable HTTP: What Actually Changed in MCP's Transport Layer",
              "Animesh Pathak",
              "protocol", "Tuesday", "13:55", 25, "Convention Hall"),
        (15, "Workshop: Bridging OpenClaw and MCP for Autonomous Cross-Cloud Operations",
              "Paras Mamgain, Anmol Krishan Sachdeva & Indumathy Thiagarajan",
              "workshop", "Tuesday", "13:55", 60, "Scarlet 1"),
        (16, "Voice-First MCP: Real-Time Tool Calling Through a Spoken Interface",
              "Samyuktha Mohan Alagiri",
              "building-with-mcp", "Tuesday", "14:25", 25, "Convention Hall"),
        (17, "Putting MCP on a Diet: A Proxy for Tool Scoping and Context Compression",
              "Prathamesh Saraf",
              "building-with-mcp", "Tuesday", "14:55", 25, "Convention Hall"),
        (18, "InstaMCP: Instant MCP-ification of Enterprise APIs",
              "Rupal Sharma & Ujjal Sharma",
              "enterprise", "Tuesday", "14:55", 25, "Scarlet 2&3"),
        (19, "Cloud-engineer-mcp: Gateway Pattern for Multi-Cloud MCP Orchestration",
              "Aniruddha Biyani",
              "agents", "Tuesday", "15:25", 25, "Scarlet 2&3"),
        (20, "MCP Schema Evolution: Versioning Tool Contracts Without Breaking Agents",
              "Yogesh Sardana",
              "protocol", "Tuesday", "15:25", 25, "Convention Hall"),
        (21, "MCP Resources Are Already a Knowledge Graph",
              "Kesigan Anbalagan",
              "building-with-mcp", "Tuesday", "16:20", 25, "Convention Hall"),
        (22, "MCPeek Into Your Server's Secrets",
              "Akash Sathish",
              "security", "Tuesday", "16:20", 25, "Scarlet 2&3"),
        (23, "Workshop: Enabling MCP at Enterprise Scale: Authentication and Governance",
              "Shannon Williams & Chris Urwin",
              "workshop", "Tuesday", "16:20", 60, "Scarlet 1"),
        (24, "MCP Servers on Kubernetes: Deployment Patterns, Scaling, and What Breaks",
              "Kunal Das",
              "ecosystem", "Tuesday", "16:50", 25, "Scarlet 2&3"),
        (25, "When MCP Meets Reality: Performance, Latency, and Hidden Cost",
              "Partha Sarthy",
              "enterprise", "Tuesday", "16:50", 25, "Convention Hall"),
        (26, "MCP + Kubernetes: Building a Self-Healing AI Platform",
              "Raghu Reddy & Esakki Raj",
              "agents", "Tuesday", "17:20", 25, "Scarlet 2&3"),
        (27, "Who Let the Agent In? Securing MCP Servers in Production",
              "Prachi Jamdade",
              "security", "Tuesday", "17:20", 25, "Convention Hall"),

        # ── Wednesday June 10 — Keynotes ──────────────────────────────────────
        (28, "Keynote: Welcome Back",
              "Angie Jones",
              "keynote", "Wednesday", "10:00", 5,  "Convention Hall"),
        (29, "Architecting Internet-Scale Agent Skills with Managed MCP",
              "Prashanth Subrahmanyam",
              "keynote", "Wednesday", "10:00", 10, "Convention Hall"),
        (30, "Extending Goose: Building an AI Teammate for Open Source",
              "Abhijay Jain",
              "keynote", "Wednesday", "10:15", 10, "Convention Hall"),
        (31, "From Shadow IT To Scale: The MCP Adoption Journey",
              "Shannon Williams",
              "keynote", "Wednesday", "10:25", 10, "Convention Hall"),

        # ── Wednesday June 10 — Sessions ──────────────────────────────────────
        (32, "From Intent To Production: MCP Gateway Patterns for Regulated Banking",
              "Hariskumar Panakkal",
              "building-with-mcp", "Wednesday", "11:00", 25, "Convention Hall"),
        (33, "Beyond Tools and Resources: A Deep Dive into MCP Sampling",
              "Kevin Vaz",
              "protocol", "Wednesday", "11:00", 25, "Scarlet 2&3"),
        (34, "Allowed To Is Not Enough: Access Control That Understands Agent Intent",
              "Tejas Ladhani & Chandrashekar Haleupparahalli",
              "security", "Wednesday", "11:00", 25, "Scarlet 1"),
        (35, "Beyond Tool Calls: Unlocking Interactive Token-Smart Agents with MCP Apps",
              "Suraj B",
              "building-with-mcp", "Wednesday", "11:30", 25, "Convention Hall"),
        (36, "Building Interactive Tools With MCP Elicitation",
              "Ashwin Hariharan",
              "building-with-mcp", "Wednesday", "11:30", 25, "Scarlet 2&3"),
        (37, "SEO for Agents: Designing MCP Endpoints That Let Agents Evaluate Each Other",
              "Manav Agarwal",
              "security", "Wednesday", "11:30", 25, "Scarlet 1"),
        (38, "Running MCP Fully Local: Private Offline-Capable Agents with Ollama",
              "Harish Kotra",
              "building-with-mcp", "Wednesday", "12:00", 25, "Convention Hall"),
        (39, "From MCP Discovery To Execution: Governed Marketplace and Gateway",
              "Rahul Ganesh Partheeban",
              "ecosystem", "Wednesday", "12:00", 25, "Scarlet 1"),
        (40, "Ambient Identity: Just-in-Time Authorization Patterns for MCP",
              "Ayesha Dissanayaka",
              "security", "Wednesday", "12:00", 25, "Scarlet 2&3"),
        (41, "Agents Don't Fail, Environments Do: Lessons From Production MCP Deployments",
              "Divya Vijay",
              "agents", "Wednesday", "13:55", 25, "Scarlet 1"),
        (42, "One MCP Server, Five Languages, Zero Containers",
              "Bharath Nallapeta",
              "building-with-mcp", "Wednesday", "13:55", 25, "Convention Hall"),
        (43, "Why Your Database MCP Should Never Talk To Your Database",
              "Gowtham Raj Elangovan",
              "security", "Wednesday", "13:55", 25, "Scarlet 2&3"),
        (44, "Skills Are Not MCP Servers: When To Use Which",
              "Animesh Pathak & Jyoti Bisht",
              "building-with-mcp", "Wednesday", "14:25", 25, "Convention Hall"),
        (45, "The Stdio Deadlock Nobody Warned Us About",
              "Yuvraj Pradhan & Archana Kumari",
              "protocol", "Wednesday", "14:25", 25, "Scarlet 1"),
        (46, "Auditing MCP Tool Calls at the Kernel Level with eBPF",
              "Harini Anand",
              "security", "Wednesday", "14:25", 25, "Scarlet 2&3"),
        (47, "You Built an MCP Server — Now What? Prototype to Production",
              "Jatin Mehrotra & Varsha Das",
              "enterprise", "Wednesday", "14:55", 25, "Scarlet 2&3"),
        (48, "The Invincible MCP Server: Crash-Proof AI Tools With Durable Execution",
              "Shubham Londhe",
              "building-with-mcp", "Wednesday", "14:55", 25, "Convention Hall"),
        (49, "Agentic DX: Bringing Your Internal Developer Platform Into the IDE",
              "Adnan Vahora & Rinkal Mav",
              "enterprise", "Wednesday", "14:55", 25, "Scarlet 1"),
        (50, "Why Agents Make Different Decisions With the Same Tools",
              "Jyoti Bisht, Animesh Pathak & Aditya Oberai",
              "agents", "Wednesday", "15:25", 25, "Scarlet 1"),
        (51, "Building Rich AI-Native UI for Agentic Interactions Using MCP Apps",
              "Ashita Prasad",
              "building-with-mcp", "Wednesday", "15:25", 25, "Convention Hall"),
        (52, "When Agents Get SSH Keys: Securing Distributed AI Fleet with MCP",
              "Mradul Dubey",
              "security", "Wednesday", "15:25", 25, "Scarlet 2&3"),
        (53, "The MCP Has No Clothes: What Most Benchmarks Miss",
              "Arnav Balyan",
              "building-with-mcp", "Wednesday", "16:20", 25, "Convention Hall"),
        (54, "Multilingual MCP: Making Tool Calling Work for the Next Billion Users",
              "Samyuktha Mohan Alagiri",
              "ecosystem", "Wednesday", "16:20", 25, "Scarlet 1"),
        (55, "Where MCP Ends and A2A Begins",
              "Arushi Garg & MV Shiva",
              "protocol", "Wednesday", "16:20", 25, "Scarlet 2&3"),
        (56, "Managing Token Usage in MCP Servers Using Code Mode",
              "Bhumika Satpathy",
              "building-with-mcp", "Wednesday", "16:50", 25, "Scarlet 2&3"),
        (57, "MCP Anti-Patterns: Mistakes Made While Building Agentic Systems",
              "Abhishek Pandit & Satyam Soni",
              "enterprise", "Wednesday", "16:50", 25, "Convention Hall"),
        (58, "Extending MCP: Writing Custom Protocol Extensions Without Breaking Compatibility",
              "Saurabh Mishra",
              "protocol", "Wednesday", "16:50", 25, "Scarlet 1"),
        (59, "Why We Built a CLI Instead of an MCP Server for Jupyter Notebooks",
              "Piyush Jain",
              "agents", "Wednesday", "17:20", 25, "Scarlet 1"),
        (60, "Why Our AI Agent Couldn't Scale Without MCP — and How We Built It",
              "Para Hitesh & Mohit Jichkar",
              "building-with-mcp", "Wednesday", "17:20", 25, "Scarlet 2&3"),
    ])

    cur.executemany("INSERT INTO models VALUES (?,?,?,?,?,?)", [
        ("qwen3.5:2b",  2.5,  2.7,  1.00, 1200, "Apache-2.0"),
        ("gemma4:e2b",  9.0,  7.2,  1.00, 4800, "Gemma ToS"),
        ("qwen3:8b",    8.0,  5.0,  0.90, 2200, "Apache-2.0"),
        ("llama3.1:8b", 8.0,  4.9,  0.70, 2100, "Meta Llama 3"),
        ("phi4-mini",   3.8,  2.5,  0.00,  250, "MIT"),
        ("gemma3:4b",   4.0,  3.1,  0.65, 1800, "Gemma ToS"),
        ("mistral:7b",  7.0,  4.1,  0.72, 2000, "Apache-2.0"),
    ])

    cur.executemany("INSERT INTO deployments VALUES (?,?,?,?,?,?)", [
        (1, "HealthCorp India",  "qwen3:8b",    "patient record query",      "stdio",    1),
        (2, "LegalTech Pune",    "llama3.1:8b", "contract analysis",         "http+sse", 1),
        (3, "FinServ Mumbai",    "qwen3.5:2b",  "transaction classification", "stdio",    1),
        (4, "EdTech Bengaluru",  "gemma3:4b",   "student Q&A",               "http+sse", 1),
        (5, "RetailCo Delhi",    "mistral:7b",  "inventory queries",         "stdio",    1),
        (6, "SaaS Startup",      "claude-3-5",  "customer support",          "http+sse", 0),
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
                    "sql_query": {
                        "type": "string",
                        "description": (
                            "A valid SQL SELECT statement. "
                            "Tables: "
                            "sessions(id, title, speaker, track, day, start_time, duration_min, room), "
                            "models(name, params_b, size_gb, tool_call_pass_rate, avg_latency_ms, license), "
                            "deployments(id, org, model, use_case, transport, is_local). "
                            "SELECT only."
                        ),
                    },
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
