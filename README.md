# amrit-docs-mcp

A Model Context Protocol (MCP) server that indexes AMRIT repository documentation and serves
plain-English search to any MCP-compatible AI agent (Claude Code, Cursor, Copilot, Gemini Code
Assist).

Built as proof-of-work for the **C4GT DMP 2026 — AMRIT Agentic AI Coding Framework** application
([issue #131](https://github.com/PSMRI/AMRIT/issues/131)).

## Why

AMRIT spans 10+ repositories across Angular, Java/Spring Boot, and Kotlin. Every new contributor
and every AI agent session starts cold: re-reading docs, re-pasting context, re-discovering how
the helpline frontends connect to the Spring Boot APIs that the FLW app also calls.

`amrit-docs` is the smallest useful piece of the proposed framework — a single MCP server that
makes AMRIT's documentation directly addressable to AI agents, so the cold-start cost goes away.

## What it does

- Fetches READMEs from every public repository in a GitHub organisation (default: `PSMRI`).
- Splits each README into overlapping chunks and generates local embeddings using
  `sentence-transformers/all-MiniLM-L6-v2` — runs on CPU in seconds, no API key required.
- Stores chunks + embeddings in a local SQLite database. No external vector DB.
- Exposes a single MCP tool — `search_amrit_docs(query, k)` — over the stdio transport.

## Quick start

### 1. Install

```bash
git clone https://github.com/zsklav/amrit-docs-mcp.git
cd amrit-docs-mcp
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

### 2. Index the AMRIT org

```bash
# Anonymous (rate-limited)
python -m amrit_docs_mcp.ingest

# Or with a token (recommended)
GITHUB_TOKEN=ghp_xxx python -m amrit_docs_mcp.ingest --org PSMRI --max-repos 15
```

You should see something like:

```
[ingest] listing repos for org=PSMRI
[ingest] 15 repos found
[ingest] Helpline104-UI: 12 chunks
[ingest] Helpline1097-UI: 9 chunks
...
[ingest] indexed 142 chunks across 15 repos
```

### 3. Wire it into Claude Code

Add an entry to your Claude Code MCP config (`~/.config/claude/claude_desktop_config.json` or
the project-local `.mcp.json`):

```json
{
  "mcpServers": {
    "amrit-docs": {
      "command": "amrit-docs-mcp"
    }
  }
}
```

Restart Claude Code. Ask:

> "How does the 1097 helpline UI connect to its backend?"

Claude Code calls `search_amrit_docs`, which returns ranked excerpts from the indexed READMEs
along with their repo URLs. Claude then answers using the retrieved context.

### 4. Try it directly

```bash
python -c "
from amrit_docs_mcp.embed import embed
from amrit_docs_mcp.store import search
q = embed(['how does the 1097 helpline route calls'])[0]
for score, chunk in search(q, k=3):
    print(f'{score:.3f}  {chunk.repo}  {chunk.url}')
"
```

## Architecture

```
AI Agent (Claude Code / Cursor / Copilot / Gemini)
        │  MCP (stdio)
        ▼
amrit-docs MCP server  (FastMCP)
        │
        ├─► sentence-transformers (all-MiniLM-L6-v2)  →  query embedding
        ├─► SQLite + NumPy cosine similarity          →  top-k retrieval
        └─► returns chunks with repo, URL, snippet

Ingestion path (run once or on a schedule):
GitHub REST API  →  README chunks  →  embeddings  →  SQLite
```

## Project layout

```
src/amrit_docs_mcp/
├── __init__.py
├── server.py     # MCP server (entry point)
├── ingest.py     # GitHub README → chunks → embeddings → SQLite
├── embed.py      # sentence-transformers wrapper
└── store.py      # SQLite-backed embedding store + cosine search
```

## Why these design choices

- **SQLite + NumPy instead of a vector DB.** For ~150 chunks of README text, a real vector DB
  is overkill. Cosine similarity over a NumPy array fits in memory and runs in milliseconds.
  Migration to FAISS or Chroma is a one-file change in `store.py` if scale grows.
- **`all-MiniLM-L6-v2` for embeddings.** Tiny (~80 MB), CPU-friendly, free, and good enough
  for short technical text. Swappable via `embed.py` if a stronger model is needed later.
- **stdio transport instead of HTTP.** Matches MCP's most-supported transport across all four
  target agents and avoids running a network service for what is fundamentally a local lookup.

## Roadmap

This POC is intentionally small. The full framework proposal extends it with:

- **`amrit-jira`** MCP server — read-first ticket and sprint access; gated write actions.
- **`amrit-code`** MCP server — cross-repo code search and API-endpoint discovery via tree-sitter.
- **Coding standards** distributable to Claude Code, Cursor, Copilot, and Gemini in their
  native config formats from a single Markdown source.
- **Skills** like `generate-jira-ticket-from-confluence`, `review-amrit-pr`, and `onboard-repo`.
- **`amrit init`** Node CLI that drops the right config into any AMRIT repo.

See the full proposal in the C4GT DMP 2026 application.

## License

MIT — see [LICENSE](LICENSE).
