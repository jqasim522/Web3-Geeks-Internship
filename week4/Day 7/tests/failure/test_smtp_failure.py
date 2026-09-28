"""
tests/failure/test_smtp_failure.py — Email/SMTP failure injection.

# STATUS: OFFLINE-CODE (not run here — no lib/ in this environment)
# RUN: pytest tests/failure/test_smtp_failure.py -v
# EXPECTED: A failed confirmation email never cancels an already-successful
#           calendar booking; the failure is recorded but not fatal.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

from datetime import datetime
import pytest
from unittest.mock import AsyncMock, MagicMock
from site_visit_booking import SiteVisitBooker


@pytest.fixture
def future_time():
    return datetime(2026, 11, 3, 9, 0)


@pytest.mark.asyncio
async def test_smtp_connection_refused_does_not_cancel_booking(mock_calendar_free, mock_email_fail, future_time):
    booker = SiteVisitBooker(calendar=mock_calendar_free, email=mock_email_fail, agent_name="TestAgent")
    result = await booker.book(
        property_id="LAH-0001", client_name="Ali Raza",
        client_email="ali@example.com", preferred_time=future_time,
    )
    assert result["status"] == "booked"
    assert result["event_id"] is not None
    assert result["email_sent"] is False


@pytest.mark.asyncio
async def test_smtp_exception_raised_not_just_error_status(mock_calendar_free, future_time):
    """If the email client RAISES (rather than returning an error dict),
    the booker must still catch it and complete the booking."""
    email = MagicMock()
    email.send_confirmation = AsyncMock(side_effect=Exception("SMTPServerDisconnected"))

    booker = SiteVisitBooker(calendar=mock_calendar_free, email=email, agent_name="TestAgent")
    try:
        result = await booker.book(
            property_id="LAH-0001", client_name="Ali Raza",
            client_email="ali@example.com", preferred_time=future_time,
        )
    except Exception as e:
        pytest.fail(f"book() must catch email exceptions internally, not propagate: {e!r}")

    assert result["status"] == "booked"
    assert result["email_sent"] is False


@pytest.mark.asyncio
async def test_smtp_failure_confirmation_text_still_mentions_booking(mock_calendar_free, mock_email_fail, future_time):
    booker = SiteVisitBooker(calendar=mock_calendar_free, email=mock_email_fail, agent_name="TestAgent")
    result = await booker.book(
        property_id="LAH-0001", client_name="Ali Raza",
        client_email="ali@example.com", preferred_time=future_time,
    )
    text = result["confirmation_text_urdu_lish"].lower()
    assert "book" in text or "confirm" in text


@pytest.mark.asyncio
async def test_smtp_invalid_recipient_email_does_not_crash_booker(mock_calendar_free, future_time):
    """A malformed client_email reaching the booker (validation should
    normally catch this earlier) must not crash the email step."""
    email = MagicMock()
    email.send_confirmation = AsyncMock(side_effect=Exception("Invalid recipient"))

    booker = SiteVisitBooker(calendar=mock_calendar_free, email=email, agent_name="TestAgent")
    try:
        result = await booker.book(
            property_id="LAH-0001", client_name="Ali Raza",
            client_email="not-a-real-address", preferred_time=future_time,
        )
        assert result["status"] in ("booked", "error")
    except Exception as e:
        pytest.fail(f"book() must not crash on email send failure: {e!r}")
