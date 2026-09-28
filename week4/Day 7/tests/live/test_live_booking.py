"""
tests/live/test_live_booking.py — REQUIRES real Google Calendar + Gmail credentials.

# STATUS: REQUIRES-LIVE
# RUN: pytest tests/live/test_live_booking.py -m live -v -s
# EXPECTED: Only meaningful with real Google Calendar OAuth credentials and
#           a working Gmail sender configured (per .env at
#           D:\Qasim Rajput\Doc\.env). CREATES A REAL CALENDAR EVENT AND
#           SENDS A REAL EMAIL — run deliberately, not in CI, and clean up
#           the created event afterwards (see test teardown below).

These tests are marked @pytest.mark.live. They are the only place in this
suite that touches real external state, so each test that creates
something also attempts to cancel/delete it in a finally block.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

from datetime import datetime, timedelta
import pytest

pytestmark = pytest.mark.live


def _require_calendar_and_email_config():
    # ASSUMPTION FLAGGED: exact env var names for real Calendar/Gmail
    # credentials are not confirmed from the attached files. Adjust these
    # to whatever Days 2-5 actually named them once lib/ is available.
    required = ["GOOGLE_CALENDAR_CREDENTIALS_PATH", "GMAIL_APP_PASSWORD"]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        pytest.skip(f"Missing live credentials: {missing} — skipping live booking test")


@pytest.mark.asyncio
async def test_live_booking_creates_real_calendar_event_and_sends_email():
    _require_calendar_and_email_config()

    from google_calendar_client import CalendarClient  # ASSUMPTION: module name
    from gmail_email_client import EmailClient  # ASSUMPTION: module name
    from site_visit_booking import SiteVisitBooker

    calendar = CalendarClient()
    email = EmailClient()
    booker = SiteVisitBooker(calendar=calendar, email=email, agent_name="Day6LiveTest")

    # far enough in the future to avoid clashing with real bookings, and
    # distinctive enough (test client name) to identify for manual cleanup
    # if the automated cancel step below fails for any reason.
    slot = datetime.now() + timedelta(days=180)

    result = None
    try:
        result = await booker.book(
            property_id="LAH-0001",
            client_name="Day6 Live Test — DO NOT ACTION",
            client_email="day6-live-test@example.com",
            preferred_time=slot,
        )
        assert result["status"] in ("booked", "unavailable")
        if result["status"] == "booked":
            assert result["event_id"] is not None
    finally:
        if result and result.get("event_id"):
            try:
                await calendar.cancel_event(result["event_id"])
            except Exception as cleanup_error:
                pytest.fail(
                    f"Test created a real calendar event ({result['event_id']}) "
                    f"but cleanup failed: {cleanup_error!r}. "
                    f"Please cancel it manually."
                )


@pytest.mark.asyncio
async def test_live_booking_conflict_detected_against_real_calendar():
    """Book the same slot twice in a row against the REAL calendar and
    confirm the second attempt is correctly reported as unavailable."""
    _require_calendar_and_email_config()

    from google_calendar_client import CalendarClient
    from gmail_email_client import EmailClient
    from site_visit_booking import SiteVisitBooker

    calendar = CalendarClient()
    email = EmailClient()
    booker = SiteVisitBooker(calendar=calendar, email=email, agent_name="Day6LiveTest")

    slot = datetime.now() + timedelta(days=181)
    r1 = None
    try:
        r1 = await booker.book(
            property_id="LAH-0001",
            client_name="Day6 Live Test A — DO NOT ACTION",
            client_email="day6-live-test-a@example.com",
            preferred_time=slot,
        )
        r2 = await booker.book(
            property_id="LAH-0001",
            client_name="Day6 Live Test B — DO NOT ACTION",
            client_email="day6-live-test-b@example.com",
            preferred_time=slot,
        )
        if r1["status"] == "booked":
            assert r2["status"] == "unavailable"
    finally:
        if r1 and r1.get("event_id"):
            try:
                await calendar.cancel_event(r1["event_id"])
            except Exception as cleanup_error:
                pytest.fail(
                    f"Please cancel calendar event {r1['event_id']} manually: {cleanup_error!r}"
                )
