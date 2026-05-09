"""MCP server entry point for amrit-docs.

Exposes a `search_amrit_docs` tool that any MCP-compatible AI agent
(Cursor, Copilot, Claude Code, Gemini Code Assist) can call to retrieve
relevant chunks from indexed AMRIT repository documentation.

Run via stdio transport:
    python -m amrit_docs_mcp.server

Or as a console script after `pip install -e .`:
    amrit-docs-mcp
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .embed import embed
from .store import search

mcp = FastMCP("amrit-docs")


@mcp.tool()
def search_amrit_docs(query: str, k: int = 5) -> str:
    """Semantic search across indexed AMRIT repository documentation.

    Use this tool to answer questions about AMRIT's architecture, conventions,
    or how its 10+ repositories connect. Returns the top-k most relevant
    documentation chunks with their source repository and URL.

    Args:
        query: Plain-English question or topic to search for.
        k: Number of chunks to return (default 5, max 10).

    Returns:
        Formatted string with ranked results, each showing the score,
        source repository, URL, and a snippet of the matched text.
    """
    k = max(1, min(int(k), 10))
    query_emb = embed([query])[0]
    results = search(query_emb, k=k)

    if not results:
        return (
            "No indexed documents yet. "
            "Run `python -m amrit_docs_mcp.ingest --org PSMRI` first to index the AMRIT repos."
        )

    lines = [f"Top {len(results)} matches for: {query!r}", ""]
    for i, (score, chunk) in enumerate(results, start=1):
        lines.append(f"--- #{i}  score={score:.3f}  repo={chunk.repo} ---")
        lines.append(f"URL: {chunk.url}")
        snippet = chunk.text.strip().replace("\n", " ")
        if len(snippet) > 600:
            snippet = snippet[:600] + "…"
        lines.append(snippet)
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    """Run the MCP server over stdio. Used as the package's console-script entry point."""
    mcp.run()


if __name__ == "__main__":
    main()
