"""
tests/conftest.py — Shared pytest fixtures for Day 6 test suite.

# STATUS: OFFLINE-PASS
# RUN: pytest tests/ --collect-only
# EXPECTED: All fixtures resolve without errors

Key fixtures:
  - db_conn          : real SQLite connection to data/realestate.db
  - scripted_llm     : deterministic mock LLM (no network)
  - mock_calendar    : mock CalendarClient (no Google API)
  - mock_email       : mock EmailClient (no SMTP)
  - mock_booker      : mock SiteVisitBooker (no live calls)
  - graph_deps_offline : GraphDeps wired with mocked registry
  - real_index       : real TfidfIndex built from brochures (may be empty dir)
"""
from __future__ import annotations

import asyncio
import os
import sqlite3
import sys
from datetime import datetime
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── path setup ───────────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "lib"))
sys.path.insert(0, PROJECT_ROOT)

DB_PATH = os.path.join(PROJECT_ROOT, "data", "realestate.db")


# ── database ─────────────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def db_conn():
    """Real read-only connection to data/realestate.db."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def db_path():
    return DB_PATH


# ── ScriptedLLM — deterministic mock, no network ─────────────────────────────
class ScriptedLLM:
    """Returns pre-programmed responses in order. Raises on underflow.
    Usage: ScriptedLLM(["search", "price", "book"]) -> successive calls
    return those strings in order, then raise StopIteration."""

    def __init__(self, responses: list[str]) -> None:
        self._q = list(responses)
        self.calls: list[str] = []
        self.last_tier_used = "scripted"

    async def invoke(self, prompt: str, system: str = "", template_key: str = "default") -> str:
        self.calls.append(prompt)
        if not self._q:
            raise StopIteration("ScriptedLLM queue exhausted")
        return self._q.pop(0)


@pytest.fixture
def scripted_llm():
    return ScriptedLLM


# ── Mock Google Calendar ──────────────────────────────────────────────────────
@pytest.fixture
def mock_calendar_free():
    """CalendarClient that always reports the slot as free."""
    cal = MagicMock()
    cal.check_availability = AsyncMock(return_value=True)
    cal.create_event = AsyncMock(return_value={"id": "mock-event-id-001", "status": "confirmed"})
    cal.list_upcoming = AsyncMock(return_value=[])
    cal.cancel_event = AsyncMock(return_value=None)
    return cal


@pytest.fixture
def mock_calendar_busy():
    """CalendarClient that always reports the slot as busy."""
    cal = MagicMock()
    cal.check_availability = AsyncMock(return_value=False)
    cal.create_event = AsyncMock(return_value={"id": "mock-event-id-002"})
    return cal


@pytest.fixture
def mock_calendar_error():
    """CalendarClient that always raises an exception."""
    cal = MagicMock()
    cal.check_availability = AsyncMock(side_effect=Exception("Calendar 503 Service Unavailable"))
    cal.create_event = AsyncMock(side_effect=Exception("Calendar 503 Service Unavailable"))
    return cal


# ── Mock Email ────────────────────────────────────────────────────────────────
@pytest.fixture
def mock_email_ok():
    email = MagicMock()
    email.send_confirmation = AsyncMock(
        return_value={"status": "sent", "to": "client@example.com", "subject": "Site Visit Confirmed"}
    )
    return email


@pytest.fixture
def mock_email_fail():
    email = MagicMock()
    email.send_confirmation = AsyncMock(
        return_value={"status": "error", "to": "client@example.com", "error": "SMTPException: Connection refused"}
    )
    return email


# ── Mock SiteVisitBooker ──────────────────────────────────────────────────────
@pytest.fixture
def mock_booker_success():
    booker = MagicMock()
    booker.book = AsyncMock(return_value={
        "status": "booked",
        "event_id": "mock-event-xyz",
        "email_sent": True,
        "confirmation_text_urdu_lish": (
            "Ji Ali Raza sahib, aap ki site visit confirm ho gayi hai — "
            "LAH-0001, House in DHA Phase 6, Lahore — 2026-09-30 15:00 ko."
        ),
    })
    return booker


@pytest.fixture
def mock_booker_busy():
    booker = MagicMock()
    booker.book = AsyncMock(return_value={
        "status": "unavailable",
        "event_id": None,
        "email_sent": False,
        "confirmation_text_urdu_lish": "Sir, yeh waqt already book hai.",
    })
    return booker


@pytest.fixture
def mock_booker_error():
    booker = MagicMock()
    booker.book = AsyncMock(return_value={
        "status": "error",
        "event_id": None,
        "email_sent": False,
        "confirmation_text_urdu_lish": "Sir, mujhe afsos hai, booking confirm karne mein masla aa raha hai.",
        "error": "availability_check_failed: timeout",
    })
    return booker


# ── Real tool registry (offline, real DB) ────────────────────────────────────
@pytest.fixture(scope="session")
def real_tool_registry(mock_booker_session):
    """Tool registry using real rag_lib + DB, but mocked booker."""
    import rag_lib as r
    from tool_registry import build_tool_registry
    index_holder = {"index": r.TfidfIndex(r.load_documents())}
    return build_tool_registry(index_holder, booker=mock_booker_session)


@pytest.fixture(scope="session")
def mock_booker_session():
    """Session-scoped mock booker for the tool registry fixture."""
    booker = MagicMock()
    booker.book = AsyncMock(return_value={
        "status": "booked",
        "event_id": "sess-mock-event",
        "email_sent": True,
        "confirmation_text_urdu_lish": "Ji, site visit confirm ho gayi hai.",
    })
    return booker


# ── GraphDeps (offline) ───────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def graph_deps_offline(real_tool_registry):
    """GraphDeps wired with real rag_lib registry + scripted LLM."""
    from graph_nodes import GraphDeps
    from llm_fallback import FallbackLLM

    # ensure no live keys leak in
    for k in ("GROQ_API_KEY", "GEMINI_API_KEY"):
        os.environ.pop(k, None)

    deps = GraphDeps(
        tool_registry=real_tool_registry,
        fallback_llm=FallbackLLM(),  # will fall to template tier — no keys
    )
    return deps


# ── Built graph (offline) ─────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def offline_graph(mock_booker_session):
    """Full compiled graph, real DB, no live LLM/Calendar/Email."""
    for k in ("GROQ_API_KEY", "GEMINI_API_KEY"):
        os.environ.pop(k, None)

    from graph_builder import build_default_deps, build_graph
    deps = build_default_deps(booker=mock_booker_session)
    return build_graph(deps=deps)


# ── Booking args helpers ──────────────────────────────────────────────────────
@pytest.fixture
def valid_booking_args():
    return {
        "property_id": "lah-0001",
        "client_name": "Ali Raza",
        "client_email": "ali@example.com",
        "preferred_time": "2026-09-30 15:00",
    }


@pytest.fixture
def valid_booking_call(valid_booking_args):
    import json
    return json.dumps({"tool": "book_site_visit", "args": valid_booking_args})


# ── Helpers ───────────────────────────────────────────────────────────────────
@pytest.fixture
def known_property_id(db_conn):
    """Returns a real property ID from the DB."""
    row = db_conn.execute("SELECT property_id FROM properties LIMIT 1").fetchone()
    return row[0]


@pytest.fixture
def lahore_property_id(db_conn):
    row = db_conn.execute(
        "SELECT property_id FROM properties WHERE city='Lahore' LIMIT 1"
    ).fetchone()
    return row[0]

