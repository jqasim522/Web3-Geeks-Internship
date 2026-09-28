"""
lib/calendar_client.py — Day 4, Task 3

# STATUS: CODE-COMPLETE | UNTESTED — requires live OAuth + network
# RUN ON USER MACHINE:
#   python -c "
#   import asyncio
#   from lib.calendar_client import CalendarClient
#   from datetime import datetime, timedelta, timezone
#   async def m():
#       c = CalendarClient()
#       start = datetime.now(timezone.utc) + timedelta(days=1)
#       print(await c.check_availability(start, start + timedelta(hours=1)))
#   asyncio.run(m())
#   "
# EXPECTED OUTPUT: True or False (no exception) once you have a real
#   credentials.json + token.json from lib/google_auth.py.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from lib.google_auth import GoogleAuth

logger = logging.getLogger("day4.calendar_client")

_RETRYABLE_STATUS = {429, 503}
_LOCAL_TZ = "Asia/Karachi"


def _is_retryable(exc: BaseException) -> bool:
    status = getattr(getattr(exc, "resp", None), "status", None)
    return status in _RETRYABLE_STATUS


def _retryable_google_call():
    """Shared retry policy: exponential backoff on 429/503."""
    return retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=5, max=60),
        reraise=True,
    )


class CalendarClient:
    """Thin async wrapper around the Calendar v3 API.

    Every public method wraps a synchronous googleapiclient call in
    asyncio.to_thread() so it never blocks the voice pipeline's event loop.
    """

    def __init__(self, auth: Optional[GoogleAuth] = None, calendar_id: str = "primary") -> None:
        self._auth = auth or GoogleAuth()
        self.calendar_id = calendar_id
        self._service = None
        self._lock = asyncio.Lock()

    async def _get_service(self):
        async with self._lock:
            if self._service is None:
                self._service = await asyncio.to_thread(self._build_service)
            return self._service

    def _build_service(self):
        from googleapiclient.discovery import build
        creds = self._auth.get_credentials()
        return build("calendar", "v3", credentials=creds, cache_discovery=False)

    # ---------- HELPERS ----------

    @staticmethod
    def _ensure_aware(dt: datetime) -> datetime:
        """Google Calendar requires timezone-aware datetimes.
        A naive datetime from the user (e.g. parsed from '2026-10-25 15:00')
        MUST be interpreted as LOCAL time, not UTC — otherwise 3 PM gets
        stored as 3 PM UTC and displays as 8 PM in Pakistan.
        If already aware, leave as-is."""
        if dt.tzinfo is None:
            try:
                from zoneinfo import ZoneInfo
                local = ZoneInfo(_LOCAL_TZ)
            except Exception:
                # Fallback: fixed +05:00 for Pakistan (no DST since 2009)
                from datetime import timedelta
                local = timezone(timedelta(hours=5))
            logger.debug("datetime_was_naive -> attaching %s: %s", _LOCAL_TZ, dt)
            return dt.replace(tzinfo=local)
        return dt

    @classmethod
    def _rfc3339(cls, dt: datetime) -> str:
        """RFC3339 with explicit timezone offset (Google's required format)."""
        dt = cls._ensure_aware(dt)
        return dt.isoformat()

    # ---------- PUBLIC API ----------

    async def check_availability(self, start: datetime, end: datetime) -> bool:
        """True if the [start, end) slot is free on the primary calendar."""
        start = self._ensure_aware(start)
        end = self._ensure_aware(end)
        logger.info("calendar_client.check_availability %s -> %s", start, end)
        service = await self._get_service()

        @_retryable_google_call()
        def _call():
            body = {
                "timeMin": self._rfc3339(start),
                "timeMax": self._rfc3339(end),
                "timeZone": _LOCAL_TZ,
                "items": [{"id": self.calendar_id}],
            }
            logger.debug("freebusy_request_body %s", body)
            try:
                return service.freebusy().query(body=body).execute()
            except Exception as e:
                # Log the actual body Google rejected for easier debugging
                logger.error("freebusy_request_failed body=%s err=%s", body, e)
                raise

        result = await asyncio.to_thread(_call)
        await asyncio.sleep(1.0)
        busy = result.get("calendars", {}).get(self.calendar_id, {}).get("busy", [])
        logger.info("freebusy_result busy_count=%d", len(busy))
        return len(busy) == 0

    async def create_event(
        self,
        summary: str,
        start: datetime,
        end: datetime,
        description: str = "",
        attendee_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Creates an event on the primary calendar; sends an invite if attendee_email."""
        start = self._ensure_aware(start)
        end = self._ensure_aware(end)
        logger.info("calendar_client.create_event %r %s -> %s", summary, start, end)
        service = await self._get_service()

        event_body: Dict[str, Any] = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": self._rfc3339(start), "timeZone": _LOCAL_TZ},
            "end": {"dateTime": self._rfc3339(end), "timeZone": _LOCAL_TZ},
        }
        if attendee_email:
            event_body["attendees"] = [{"email": attendee_email}]

        @_retryable_google_call()
        def _call():
            logger.debug("create_event_request_body %s", event_body)
            return (
                service.events()
                .insert(
                    calendarId=self.calendar_id,
                    body=event_body,
                    sendUpdates="all" if attendee_email else "none",
                )
                .execute()
            )

        event = await asyncio.to_thread(_call)
        await asyncio.sleep(1.0)
        logger.info("calendar_client.create_event -> id=%s", event.get("id"))
        return event

    async def list_upcoming(self, days: int = 7) -> List[Dict[str, Any]]:
        """Lists upcoming events on the primary calendar for the next `days` days."""
        logger.info("calendar_client.list_upcoming days=%d", days)
        service = await self._get_service()

        # Fix: use timezone.utc instead of deprecated datetime.utcnow()
        now = datetime.now(timezone.utc)
        time_min = now.isoformat()
        time_max = (now + timedelta(days=days)).isoformat()

        @_retryable_google_call()
        def _call():
            return (
                service.events()
                .list(
                    calendarId=self.calendar_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )

        result = await asyncio.to_thread(_call)
        await asyncio.sleep(1.0)
        return result.get("items", [])

    async def cancel_event(self, event_id: str) -> None:
        """Deletes an event by ID from the primary calendar."""
        logger.info("calendar_client.cancel_event id=%s", event_id)
        service = await self._get_service()

        @_retryable_google_call()
        def _call():
            service.events().delete(
                calendarId=self.calendar_id, eventId=event_id
            ).execute()

        await asyncio.to_thread(_call)
        await asyncio.sleep(1.0)
        logger.info("calendar_client.cancel_event -> deleted %s", event_id)

    async def update_event(
        self,
        event_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        attendee_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Patches an existing event. Any arg left None is not changed.

        Google Calendar requires start+end together when changing times, so if
        only one is given we raise rather than sending a malformed patch.
        """
        if (start is None) != (end is None):
            raise ValueError("update_event: pass both start and end, or neither")

        logger.info("calendar_client.update_event id=%s start=%s end=%s",
                    event_id, start, end)
        service = await self._get_service()

        patch: Dict[str, Any] = {}
        if start is not None and end is not None:
            start = self._ensure_aware(start)
            end = self._ensure_aware(end)
            patch["start"] = {"dateTime": self._rfc3339(start), "timeZone": _LOCAL_TZ}
            patch["end"] = {"dateTime": self._rfc3339(end), "timeZone": _LOCAL_TZ}
        if summary is not None:
            patch["summary"] = summary
        if description is not None:
            patch["description"] = description
        if attendee_email is not None:
            patch["attendees"] = [{"email": attendee_email}]

        if not patch:
            raise ValueError("update_event: nothing to update")

        @_retryable_google_call()
        def _call():
            logger.debug("update_event_patch %s", patch)
            return (
                service.events()
                .patch(
                    calendarId=self.calendar_id,
                    eventId=event_id,
                    body=patch,
                    sendUpdates="all" if attendee_email else "none",
                )
                .execute()
            )

        event = await asyncio.to_thread(_call)
        await asyncio.sleep(1.0)
        logger.info("calendar_client.update_event -> id=%s", event.get("id"))
        return event