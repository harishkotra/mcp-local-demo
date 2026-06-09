# Running MCP Fully Local

Private, offline-capable agents with Ollama and open models.

Demo from **MCP Dev Summit Bengaluru 2026** — shows the difference between naive and hardened MCP tool design using the same model, same hardware, no cloud.

---

## What this demonstrates

- A full MCP server with 3 real tools running over STDIO
- A **naive client** that fails predictably (table hallucination, city format drift)
- A **hardened client** that works reliably — same model, same server
- A **model comparison** script showing pass rate and latency across models

The core point: **model inference stays local. The bottleneck is tool description quality, not model size.**

---

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com) running locally
- At least one of these models pulled:

```bash
ollama pull qwen3.5:2b      # recommended — 2.7 GB, fast, reliable
ollama pull gemma4:e2b      # for model swap demo — 7.2 GB
```

Install Python dependencies:

```bash
pip install mcp ollama rich
```

---

## Project structure

```
server.py            MCP server — 3 tools, SQLite DB auto-created on first run
client_naive.py      Naive client — vague descriptions, no schema constraints
client_hardened.py   Hardened client — examples, constrained schema, single responsibility
compare_models.py    Benchmark script — runs 5 prompts across 2 models, prints pass/fail table
run_demo.sh          Convenience runner
notes/               Local markdown files used by the search_notes tool
```

---

## The 3 tools

| Tool | What it does | Data location |
|------|-------------|---------------|
| `get_weather(city)` | Live weather via [wttr.in](https://wttr.in) | External (intentional — see below) |
| `query_database(sql_query)` | SELECT queries on a local SQLite DB | Local only |
| `search_notes(query)` | Search markdown files in `notes/` | Local only |

> **On the weather tool:** model inference is local. `get_weather` makes an outbound call to wttr.in — this is intentional and demonstrates the hybrid pattern: local reasoning, your choice of tool data source. Set `OFFLINE_MODE=1` to disable the outbound call and use fallback data instead.

The SQLite database (`demo.db`) is auto-created at server startup with conference session data, model benchmarks, and deployment examples.

---

## Run the demo

### Naive client — watch it fail

```bash
./run_demo.sh naive
# or with a specific model:
./run_demo.sh naive qwen3.5:2b
```

What fails and why:

1. **Table hallucination** — `"Query the database"` gives the model no schema. It sends `SELECT * FROM talks` — but the table is `sessions`. Training data guessed wrong.
2. **City format drift** — `"What's the weather in India's capital city?"` → model sends `"New Delhi,India"`. No format example in the description.

### Hardened client — same model, different result

```bash
./run_demo.sh hardened
# or swap the model:
./run_demo.sh hardened gemma4:e2b
```

Same 3 prompts. All succeed. What changed: descriptions include the DB schema, examples, and negative space (`"Does NOT INSERT/UPDATE/DELETE"`).

### Side-by-side (requires tmux)

```bash
./run_demo.sh side-by-side
```

Opens both clients in a split terminal.

### Model comparison table

```bash
./run_demo.sh compare
# or directly:
python3 compare_models.py
```

Runs 5 tool-call prompts against `qwen3.5:2b` and `gemma4:e2b` with hardened descriptions. Prints pass/fail and average latency per model.

---

## The 3 hardening patterns

### 1. Describe with examples

```python
# BAD
"description": "Query the database"

# GOOD
"description": (
    "Run a read-only SQL SELECT query against the local conference database. "
    "Tables: sessions(id, title, speaker, track, duration_min, room), "
    "        models(name, params_b, size_gb, tool_call_pass_rate), "
    "        deployments(id, org, model, use_case, transport, is_local). "
    "SELECT only. e.g. SELECT title FROM sessions WHERE track = 'local-ai'"
)
```

### 2. Constrain the schema

```python
# BAD
"sql_query": {"type": "string"}

# GOOD
"sql_query": {
    "type": "string",
    "pattern": r"^\s*[Ss][Ee][Ll][Ee][Cc][Tt]",   # SELECT-only, enforced at schema level
    "description": "Must start with SELECT. Use only the tables listed above.",
}
```

Use `pattern` for format, `enum` for known values, `minimum`/`maximum` for integers.

### 3. Single responsibility

```python
# BAD
search_and_summarize(query, format, max_results, include_metadata)

# GOOD
search_notes(query)       # returns raw excerpts
summarize_text(text)      # separate tool, called after
```

Rule: if the tool name contains "and" — split it.

---

## Testing with `thinking=False`

Both clients disable extended thinking (`think=False` in `ollama.chat`). Production agents skip extended reasoning for speed and cost. With thinking ON, smart models can reason around vague descriptions. With thinking OFF, only hardened descriptions work reliably.

**Test with thinking off before shipping. If it passes, you have a real contract.**

---

## Offline mode

```bash
OFFLINE_MODE=1 ./run_demo.sh hardened
```

Disables the wttr.in call. Uses local fallback weather data for Bengaluru, Mumbai, Delhi, Chennai.

---

## Model recommendations

| Model | Size | Tool call reliability | Notes |
|-------|------|-----------------------|-------|
| `qwen3.5:2b` | 2.7 GB | High | Best starting point |
| `gemma4:e2b` | 7.2 GB | High | Slower, good for comparison |
| `qwen3:8b` | 5 GB | High | Step up if needed |
| `llama3.1:8b` | 4.9 GB | Medium | Function-calling variant preferred |

General rule: **a structured-output fine-tune beats a general chat model 4× its size** for tool calling. Pick the right fine-tune before scaling up.

---

## Official MCP servers worth knowing

From [github.com/modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers):

- `sqlite` — local DB query, fully local
- `filesystem` — read/write local files, fully local  
- `git` — repo history, diff, blame, fully local
- `fetch` — web content retrieval
- `brave-search` — web search (API key required)
- `postgres` — local or remote database

---

## Transport

This demo uses **STDIO** — the server runs as a subprocess, communicating over stdin/stdout. No port binding, lowest latency, single client.

For multi-client or browser-compatible setups, switch to **HTTP+SSE**. The tool hardening patterns apply identically to both transports.

---

## Tech stack

- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) v1.27.2+
- [Ollama Python client](https://github.com/ollama/ollama-python)
- [Rich](https://github.com/Textualize/rich) for terminal output
- SQLite via Python stdlib `sqlite3` — no external DB needed
- [wttr.in](https://wttr.in) for live weather (no API key)
