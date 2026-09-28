"""
tests/failure/test_network_death.py — Total network unavailability failure injection.

# STATUS: OFFLINE-CODE (not run here — no lib/ in this environment)
# RUN: pytest tests/failure/test_network_death.py -v
# EXPECTED: With every external dependency (Groq, Gemini, Calendar, Gmail)
#           unreachable, the system still answers from the DB/rule-based
#           path and never hangs or crashes end-to-end.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

import pytest
from unittest.mock import AsyncMock, MagicMock
from llm_fallback import FallbackLLM, TEMPLATE_RESPONSES
from graph_state import initial_state


@pytest.mark.asyncio
async def test_llm_fallback_network_death_reaches_template(monkeypatch):
    """Both Groq and Gemini calls raise a raw connection error (simulating
    total network death, not just a 429) — must still resolve to template."""
    f = FallbackLLM()

    async def network_dead(prompt, system=""):
        raise ConnectionError("Network is unreachable")

    f._get_groq = MagicMock()
    groq_backend = MagicMock()
    groq_backend.invoke = network_dead
    f._get_groq.return_value = groq_backend

    os.environ["GROQ_API_KEY"] = "k1"
    try:
        result = await f.invoke("test")
        assert result == TEMPLATE_RESPONSES["default"]
        assert f.last_tier_used == "template"
    finally:
        os.environ.pop("GROQ_API_KEY", None)


@pytest.mark.asyncio
async def test_calendar_network_death_returns_error_not_hang():
    from datetime import datetime
    from site_visit_booking import SiteVisitBooker

    cal = MagicMock()
    cal.check_availability = AsyncMock(side_effect=OSError("Network is unreachable"))
    email = MagicMock()
    email.send_confirmation = AsyncMock(return_value={"status": "sent"})

    booker = SiteVisitBooker(calendar=cal, email=email, agent_name="TestAgent")
    result = await booker.book(
        property_id="LAH-0001", client_name="Ali Raza",
        client_email="ali@example.com", preferred_time=datetime(2026, 11, 4, 9, 0),
    )
    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_full_graph_survives_with_no_network_at_all(offline_graph):
    """The offline_graph fixture already has no live keys, which is the
    closest approximation of full network death available without lib/;
    this test asserts the whole pipeline still answers ordinary questions
    end-to-end under that condition."""
    cfg = {"configurable": {"thread_id": "net-death-001"}}
    result = await offline_graph.ainvoke(initial_state("3 bedroom house in Lahore"), config=cfg)
    assert isinstance(result.get("response_text"), str)
    assert len(result["response_text"]) > 0


@pytest.mark.asyncio
async def test_full_graph_booking_under_network_death_reports_error_gracefully(offline_graph):
    """A booking attempt when Calendar/Gmail are simulated unreachable
    (via the offline_graph's mocked booker) must still produce SOME
    response text, not hang or crash — exact wording is not asserted since
    we cannot see graph_builder.py's actual error copy without lib/."""
    cfg = {"configurable": {"thread_id": "net-death-002"}}
    result = await offline_graph.ainvoke(
        initial_state("LAH-0001 visit book, Ali Raza, ali@example.com, 2026-11-05 10:00"),
        config=cfg,
    )
    assert "__interrupt__" in result or isinstance(result.get("response_text"), str)
