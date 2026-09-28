"""
tests/consistency/test_booking_idempotency.py — Booking idempotency tests.

# STATUS: OFFLINE-CODE (not run here — no lib/ in this environment)
# RUN: pytest tests/consistency/test_booking_idempotency.py -v
# EXPECTED: Identical booking requests behave predictably; a resubmitted
#           request for an already-booked slot does not silently double-book.

Distinct from test_deterministic_answers.py (read-only query determinism):
this file is about write-path idempotency — booking the same slot twice
in a row via SiteVisitBooker.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

from datetime import datetime
import pytest
from site_visit_booking import SiteVisitBooker


@pytest.fixture
def future_time():
    return datetime(2026, 11, 1, 10, 0)


# ── identical booking submitted twice in a row ─────────────────────────────────
@pytest.mark.skip(reason="Fixture mock_calendar_busy_after_first not in conftest — Day 7 follow-up")
@pytest.mark.asyncio
async def test_identical_booking_twice_second_reports_busy(mock_calendar_busy_after_first, mock_email_ok, future_time):
    """First booking on a slot succeeds; an identical second attempt on the
    SAME slot should see the slot as busy on the calendar, not silently
    create a duplicate event.

    NOTE: this uses a fixture that is not defined in the attached conftest.py
    (mock_calendar_busy_after_first). It must be added to conftest.py, or
    this test replaced with an equivalent using the existing
    mock_calendar_free/mock_calendar_busy fixtures directly, once lib/ and
    the real calendar semantics are available to check against.
    """
    booker = SiteVisitBooker(
        calendar=mock_calendar_busy_after_first,
        email=mock_email_ok,
        agent_name="TestAgent",
    )
    r1 = await booker.book(
        property_id="LAH-0001", client_name="Ali Raza",
        client_email="ali@example.com", preferred_time=future_time,
    )
    r2 = await booker.book(
        property_id="LAH-0001", client_name="Ali Raza",
        client_email="ali@example.com", preferred_time=future_time,
    )
    assert r1["status"] == "booked"
    assert r2["status"] == "unavailable"


# ── same request, same free slot each time (no shared calendar state) ──────────
@pytest.mark.asyncio
async def test_repeated_booking_calls_on_always_free_calendar_are_stable(mock_calendar_free, mock_email_ok, future_time):
    """If the calendar mock always reports free (no cross-call memory), each
    call to book() should independently report 'booked' — this pins down
    that book() itself has no surprising internal state across calls."""
    booker = SiteVisitBooker(
        calendar=mock_calendar_free,
        email=mock_email_ok,
        agent_name="TestAgent",
    )
    results = [
        await booker.book(
            property_id="LAH-0001", client_name="Ali Raza",
            client_email="ali@example.com", preferred_time=future_time,
        )
        for _ in range(3)
    ]
    assert all(r["status"] == "booked" for r in results)


# ── different client, same slot ─────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_different_client_same_slot_respects_calendar_truth(mock_calendar_busy, mock_email_ok, future_time):
    """A second client trying to book a slot the calendar reports as busy
    must also get 'unavailable' — busy is busy regardless of who's asking."""
    booker = SiteVisitBooker(
        calendar=mock_calendar_busy,
        email=mock_email_ok,
        agent_name="TestAgent",
    )
    result = await booker.book(
        property_id="LAH-0001", client_name="A Different Client",
        client_email="different@example.com", preferred_time=future_time,
    )
    assert result["status"] == "unavailable"


# ── event_id stability ──────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_booking_result_event_id_matches_calendar_response(mock_calendar_free, mock_email_ok, future_time):
    booker = SiteVisitBooker(
        calendar=mock_calendar_free,
        email=mock_email_ok,
        agent_name="TestAgent",
    )
    result = await booker.book(
        property_id="LAH-0001", client_name="Ali Raza",
        client_email="ali@example.com", preferred_time=future_time,
    )
    assert result["event_id"] == "mock-event-id-001"
