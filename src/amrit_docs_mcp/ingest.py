"""Fetch READMEs from PSMRI repos via the GitHub API and index them locally.

Usage:  python -m amrit_docs_mcp.ingest
        python -m amrit_docs_mcp.ingest --org PSMRI --max-repos 15
"""
from __future__ import annotations

import argparse
import base64
import os
import sys
import time

import requests

from .embed import embed
from .store import Chunk, write_chunks

GITHUB_API = "https://api.github.com"


def _gh_headers() -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def list_repos(org: str, max_repos: int) -> list[dict]:
    repos: list[dict] = []
    page = 1
    while len(repos) < max_repos:
        r = requests.get(
            f"{GITHUB_API}/orgs/{org}/repos",
            headers=_gh_headers(),
            params={"per_page": 100, "page": page, "type": "public"},
            timeout=30,
        )
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        repos.extend(batch)
        page += 1
    return repos[:max_repos]


def fetch_readme(org: str, repo: str) -> tuple[str, str] | None:
    r = requests.get(
        f"{GITHUB_API}/repos/{org}/{repo}/readme",
        headers=_gh_headers(),
        timeout=30,
    )
    if r.status_code == 404:
        return None
    r.raise_for_status()
    payload = r.json()
    content = base64.b64decode(payload["content"]).decode("utf-8", errors="replace")
    return payload.get("html_url", ""), content


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 200) -> list[str]:
    text = text.strip()
    if not text:
        return []
    chunks = []
    i = 0
    while i < len(text):
        chunks.append(text[i : i + chunk_size])
        i += chunk_size - overlap
    return chunks


def main() -> int:
    parser = argparse.ArgumentParser(description="Index PSMRI repo READMEs into a local vector store.")
    parser.add_argument("--org", default="PSMRI")
    parser.add_argument("--max-repos", type=int, default=15)
    args = parser.parse_args()

    print(f"[ingest] listing repos for org={args.org}", file=sys.stderr)
    repos = list_repos(args.org, args.max_repos)
    print(f"[ingest] {len(repos)} repos found", file=sys.stderr)

    chunks: list[Chunk] = []
    for repo in repos:
        name = repo["name"]
        try:
            result = fetch_readme(args.org, name)
        except requests.HTTPError as e:
            print(f"[ingest] {name}: HTTP error {e}", file=sys.stderr)
            continue
        if not result:
            print(f"[ingest] {name}: no README", file=sys.stderr)
            continue
        url, body = result
        for piece in chunk_text(body):
            chunks.append(Chunk(repo=name, path="README.md", title=name, text=piece, url=url))
        print(f"[ingest] {name}: {len(chunk_text(body))} chunks", file=sys.stderr)
        time.sleep(0.2)  # be polite to the GitHub API

    if not chunks:
        print("[ingest] nothing to index — aborting", file=sys.stderr)
        return 1

    print(f"[ingest] embedding {len(chunks)} chunks", file=sys.stderr)
    embeddings = embed([c.text for c in chunks])
    write_chunks(chunks, embeddings)
    print(f"[ingest] indexed {len(chunks)} chunks across {len(repos)} repos", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
