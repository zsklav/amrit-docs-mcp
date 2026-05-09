"""SQLite-backed embedding store. No external vector DB — keeps the POC dependency-light."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import numpy as np

DEFAULT_DB_PATH = Path.home() / ".amrit-docs-mcp" / "index.sqlite"


@dataclass
class Chunk:
    repo: str
    path: str
    title: str
    text: str
    url: str


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chunks (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            repo      TEXT NOT NULL,
            path      TEXT NOT NULL,
            title     TEXT,
            text      TEXT NOT NULL,
            url       TEXT,
            embedding BLOB NOT NULL
        )
        """
    )
    return conn


def write_chunks(chunks: list[Chunk], embeddings: np.ndarray, db_path: Path = DEFAULT_DB_PATH) -> None:
    if len(chunks) != embeddings.shape[0]:
        raise ValueError("chunks and embeddings length mismatch")
    conn = _connect(db_path)
    with conn:
        conn.execute("DELETE FROM chunks")
        rows = [
            (c.repo, c.path, c.title, c.text, c.url, embeddings[i].astype(np.float32).tobytes())
            for i, c in enumerate(chunks)
        ]
        conn.executemany(
            "INSERT INTO chunks (repo, path, title, text, url, embedding) VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
    conn.close()


def search(query_emb: np.ndarray, k: int, db_path: Path = DEFAULT_DB_PATH) -> list[tuple[float, Chunk]]:
    conn = _connect(db_path)
    cur = conn.execute("SELECT repo, path, title, text, url, embedding FROM chunks")
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return []

    embs = np.stack([np.frombuffer(r[5], dtype=np.float32) for r in rows])
    q = query_emb.astype(np.float32)
    # Embeddings are already L2-normalized at write time, but normalize defensively.
    embs_n = embs / (np.linalg.norm(embs, axis=1, keepdims=True) + 1e-9)
    q_n = q / (np.linalg.norm(q) + 1e-9)
    scores = embs_n @ q_n
    top = np.argsort(-scores)[:k]

    return [
        (
            float(scores[i]),
            Chunk(repo=rows[i][0], path=rows[i][1], title=rows[i][2], text=rows[i][3], url=rows[i][4]),
        )
        for i in top
    ]
