"""
lib/site_visit_booking.py — Day 4, Task 5

# STATUS: CODE-COMPLETE | UNTESTED — requires live OAuth + network
# RUN ON USER MACHINE (after credentials.json + token.json exist):
#   python -c "
#   import asyncio
#   from lib.site_visit_booking import SiteVisitBooker
#   from datetime import datetime, timedelta
#   async def m():
#       b = SiteVisitBooker()
#       t = datetime.now() + timedelta(days=1)
#       print(await b.book('LAH-0001', 'Ali Raza', 'ali@example.com', t))
#   asyncio.run(m())
#   "
# EXPECTED OUTPUT: a dict like
#   {"status": "booked", "event_id": "<real google id>", "email_sent": True,
#    "confirmation_text_urdu_lish": "..."}
#   ONLY if the calendar slot was free and the calendar+email calls succeeded.
#   If the property doesn't exist or the slot is busy, status is
#   "unavailable" or "error" — never "booked" — and event_id/email_sent
#   reflect what actually happened.

This is the single function Day 3's voice pipeline calls to turn a spoken
booking request into a real calendar event + email. It does not talk to
Google APIs directly — that's CalendarClient / EmailClient's job — it only
sequences: property lookup (Day 2 data) -> availability check -> event
creation -> email -> a structured result the agent can speak from.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from lib import rag_lib
from lib.calendar_client import CalendarClient
from lib.email_client import EmailClient

logger = logging.getLogger("day4.site_visit_booking")

VISIT_DURATION = timedelta(hours=1)


class SiteVisitBooker:
    def __init__(
        self,
        calendar: Optional[CalendarClient] = None,
        email: Optional[EmailClient] = None,
        agent_name: str = "Hajra",
    ) -> None:
        self.calendar = calendar or CalendarClient()
        self.email = email or EmailClient()
        self.agent_name = agent_name

    async def book(
        self,
        property_id: str,
        client_name: str,
        client_email: str,
        preferred_time: datetime,
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "status": "error",
            "event_id": None,
            "email_sent": False,
            "confirmation_text_urdu_lish": "",
        }

        # Step 1 — verify the property exists (Day 2 SQLite data, read-only).
        try:
            prop = rag_lib.get_property(property_id)
        except Exception as e:
            logger.exception("site_visit_booking: property lookup crashed")
            result["status"] = "error"
            result["error"] = f"property_lookup_failed: {e}"
            result["confirmation_text_urdu_lish"] = (
                "Sir, mujhe afsos hai, filhal system mein thodi dikkat aa rahi hai. "
                "Main aap ko hamare team member se callback karwata hoon."
            )
            return result

        if not prop:
            logger.info("site_visit_booking: property not found id=%s", property_id)
            result["status"] = "unavailable"
            result["confirmation_text_urdu_lish"] = (
                f"Sir, mujhe {property_id} ki listing nahi mil rahi filhal. "
                f"Kya aap property ID dobara confirm kar sakte hain?"
            )
            return result

        start = preferred_time
        end = preferred_time + VISIT_DURATION

        # Step 2 — check calendar availability.
        try:
            free = await self.calendar.check_availability(start, end)
        except Exception as e:
            logger.exception("site_visit_booking: availability check failed")
            result["status"] = "error"
            result["error"] = f"availability_check_failed: {e}"
            result["confirmation_text_urdu_lish"] = (
                "Sir, mujhe afsos hai, filhal calendar check karne mein masla aa raha hai. "
                "Main aap ko hamare team member se callback karwata hoon."
            )
            return result

        if not free:
            logger.info("site_visit_booking: slot busy %s-%s", start, end)
            result["status"] = "unavailable"
            result["confirmation_text_urdu_lish"] = (
                f"Sir, yeh waqt ({start.strftime('%d %b, %I:%M %p')}) already book hai. "
                f"Koi aur waqt suggest kar sakte hain?"
            )
            return result

        # Step 3 — create the event.
        area = prop.get("area") or ""
        city = prop.get("city") or ""
        summary = f"Site Visit: {property_id} ({area}, {city}) — {client_name}"
        description = (
            f"Client: {client_name} <{client_email}>\n"
            f"Property: {property_id} — {prop.get('property_type')} in {area}, {city}\n"
            f"Price: {prop.get('price_formatted')}\n"
            f"Source: {prop.get('source_url')}\n"
            f"Booked via RealEstate Hub voice agent."
        )
        try:
            event = await self.calendar.create_event(
                summary=summary,
                start=start,
                end=end,
                description=description,
                attendee_email=client_email,
            )
        except Exception as e:
            logger.exception("site_visit_booking: create_event failed")
            result["status"] = "error"
            result["error"] = f"create_event_failed: {e}"
            result["confirmation_text_urdu_lish"] = (
                "Sir, mujhe afsos hai, booking confirm karne mein masla aa raha hai. "
                "Main aap ko hamare team member se callback karwata hoon."
            )
            return result

        result["status"] = "booked"
        result["event_id"] = event.get("id")

        # Step 4 — send confirmation email. A failed email does NOT undo the
        # booking (the calendar event is the source of truth) — it's reported
        # honestly in email_sent so the caller/agent knows to follow up.
        visit_time_str = start.strftime("%A, %d %b %Y, %I:%M %p")
        try:
            email_result = await self.email.send_confirmation(
                to=client_email,
                property_id=property_id,
                visit_time=visit_time_str,
                agent_name=self.agent_name,
            )
            result["email_sent"] = email_result.get("status") == "sent"
            result["email_status"] = email_result.get("status")
        except Exception as e:
            logger.exception("site_visit_booking: send_confirmation crashed")
            result["email_sent"] = False
            result["email_status"] = "error"
            result["email_error"] = f"{type(e).__name__}: {e}"

        price = prop.get("price_formatted") or ""
        beds = prop.get("bedrooms")
        beds_txt = f"{beds}-bedroom " if beds not in (None, "") else ""
        result["confirmation_text_urdu_lish"] = (
            f"Ji {client_name} sahib, aap ki site visit confirm ho gayi hai — "
            f"{property_id}, {beds_txt}{prop.get('property_type')} in {area}, {city}, "
            f"{price} — {visit_time_str} ko. "
            + (
                "Confirmation email bhi bhej di gayi hai."
                if result["email_sent"]
                else "Calendar par book ho gaya hai, email thodi der mein follow up karenge."
            )
        )
        logger.info(
            "site_visit_booking.book -> status=booked event_id=%s email_sent=%s",
            result["event_id"], result["email_sent"],
        )
        return result
