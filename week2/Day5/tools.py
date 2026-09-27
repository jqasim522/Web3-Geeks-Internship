"""
tools.py — External data sources and DB helpers.

External tool: Wikipedia API (via langchain-community)
Local DB:      SQLite (agent_data.db) — stores published content + event logs
"""
import os
import sqlite3
import logging
import time
from datetime import datetime

from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DB_PATH", "agent_data.db")

# ── Wikipedia Tool ─────────────────────────────────────────────────────────
_wiki_wrapper = WikipediaAPIWrapper(top_k_results=3, doc_content_chars_max=3000)
wikipedia_tool = WikipediaQueryRun(api_wrapper=_wiki_wrapper)


def safe_wikipedia(query: str) -> str:
    """
    Call Wikipedia safely with a 10-second timeout guard.
    Returns '__TOOL_ERROR__: <msg>' on any failure so callers can branch.
    """
    try:
        t0 = time.time()
        result = wikipedia_tool.run(query)
        elapsed = round(time.time() - t0, 2)
        logger.info(f"[Wikipedia] {len(result)} chars in {elapsed}s | query={query[:60]!r}")
        return result
    except Exception as exc:
        logger.error(f"[Wikipedia] Tool error: {exc}")
        return f"__TOOL_ERROR__: {exc}"


# ── SQLite helpers ─────────────────────────────────────────────────────────
def init_db() -> None:
    """Create tables if they don't already exist."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS published_content (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id    TEXT NOT NULL,
                query        TEXT NOT NULL,
                draft        TEXT NOT NULL,
                published_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS agent_logs (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id  TEXT NOT NULL,
                event      TEXT NOT NULL,
                details    TEXT DEFAULT '',
                created_at TEXT NOT NULL
            );
        """)
    logger.info(f"[DB] Initialized → {DB_PATH}")


def db_log(thread_id: str, event: str, details: str = "") -> None:
    """Append a structured event row to agent_logs (non-blocking on error)."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO agent_logs (thread_id, event, details, created_at) VALUES (?,?,?,?)",
                (thread_id, event, details, datetime.utcnow().isoformat()),
            )
    except Exception as exc:
        logger.warning(f"[DB] log failed (non-fatal): {exc}")


def db_save_content(thread_id: str, query: str, draft: str) -> None:
    """Persist an approved draft to published_content (the 'publish' action)."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO published_content (thread_id, query, draft, published_at) VALUES (?,?,?,?)",
                (thread_id, query, draft, datetime.utcnow().isoformat()),
            )
        logger.info(f"[DB] Content saved | thread={thread_id}")
    except Exception as exc:
        logger.error(f"[DB] save_content failed: {exc}")
        raise
