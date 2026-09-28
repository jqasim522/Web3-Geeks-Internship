"""
tests/failure/test_calendar_503.py — Google Calendar service-unavailable failure injection.

# STATUS: OFFLINE-CODE (not run here — no lib/ in this environment)
# RUN: pytest tests/failure/test_calendar_503.py -v
# EXPECTED: A Calendar 503 is caught by SiteVisitBooker and surfaced as a
#           graceful "error" status with an apologetic message — never a
#           raw exception bubbling to the user.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

from datetime import datetime
import pytest
from unittest.mock import AsyncMock, MagicMock
from site_visit_booking import SiteVisitBooker


@pytest.fixture
def future_time():
    return datetime(2026, 11, 2, 14, 0)


@pytest.mark.asyncio
async def test_calendar_503_on_availability_check_returns_error_status(mock_calendar_error, mock_email_ok, future_time):
    booker = SiteVisitBooker(calendar=mock_calendar_error, email=mock_email_ok, agent_name="TestAgent")
    result = await booker.book(
        property_id="LAH-0001", client_name="Ali Raza",
        client_email="ali@example.com", preferred_time=future_time,
    )
    assert result["status"] == "error"
    assert result["event_id"] is None
    assert result["email_sent"] is False


@pytest.mark.asyncio
async def test_calendar_503_message_does_not_expose_stack_trace(mock_calendar_error, mock_email_ok, future_time):
    booker = SiteVisitBooker(calendar=mock_calendar_error, email=mock_email_ok, agent_name="TestAgent")
    result = await booker.book(
        property_id="LAH-0001", client_name="Ali Raza",
        client_email="ali@example.com", preferred_time=future_time,
    )
    text = result.get("confirmation_text_urdu_lish", "")
    assert "Traceback" not in text
    assert "Exception" not in text


@pytest.mark.asyncio
async def test_calendar_503_on_create_event_after_available_check(mock_email_ok, future_time):
    """Availability check succeeds, but create_event itself then 503s —
    still must resolve to 'error', not a half-booked state."""
    cal = MagicMock()
    cal.check_availability = AsyncMock(return_value=True)
    cal.create_event = AsyncMock(side_effect=Exception("Calendar 503 Service Unavailable"))

    booker = SiteVisitBooker(calendar=cal, email=mock_email_ok, agent_name="TestAgent")
    result = await booker.book(
        property_id="LAH-0001", client_name="Ali Raza",
        client_email="ali@example.com", preferred_time=future_time,
    )
    assert result["status"] == "error"
    assert result["event_id"] is None
    # Email must not have been sent for a booking that never actually completed
    assert result["email_sent"] is False


@pytest.mark.asyncio
async def test_calendar_503_does_not_retry_indefinitely(mock_calendar_error, mock_email_ok, future_time):
    """A single book() call must return promptly on 503 rather than
    silently retrying forever — verified indirectly by asserting the
    mock's check_availability was awaited a small, bounded number of times."""
    booker = SiteVisitBooker(calendar=mock_calendar_error, email=mock_email_ok, agent_name="TestAgent")
    await booker.book(
        property_id="LAH-0001", client_name="Ali Raza",
        client_email="ali@example.com", preferred_time=future_time,
    )
    assert mock_calendar_error.check_availability.await_count <= 3
