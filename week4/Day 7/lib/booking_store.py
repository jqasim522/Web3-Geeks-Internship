# lib/booking_store.py
"""SQLite-backed store for site-visit bookings.

Why a separate DB from realestate.db:
- realestate.db is read-only listings data (575 rows)
- bookings are user-generated, mutable, small
- separating them means we can wipe/rebuild listings without touching bookings

Booking lifecycle:
    active  --[reschedule]-->  rescheduled  (event_id may change)
    active  --[cancel]----->  cancelled

    "rescheduled" is treated as active for lookup purposes — we always want
    the *current* booking for a property/client, not a historical record.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("day7.booking_store")

DEFAULT_DB = os.path.join("data", "bookings.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS bookings (
    booking_id      TEXT PRIMARY KEY,
    event_id        TEXT,
    property_id     TEXT NOT NULL,
    client_name     TEXT NOT NULL,
    client_email    TEXT NOT NULL,
    preferred_time  TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active',
    thread_id       TEXT,
    created_at      REAL NOT NULL,
    updated_at      REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bookings_property ON bookings(property_id);
CREATE INDEX IF NOT EXISTS idx_bookings_status   ON bookings(status);
CREATE INDEX IF NOT EXISTS idx_bookings_email    ON bookings(client_email);
"""

_ACTIVE_STATUSES = ("active", "rescheduled")


@contextmanager
def _connect(db_path: str):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ensure_schema(db_path: str) -> None:
    with _connect(db_path) as c:
        c.executescript(SCHEMA)


# -------------------------------------------------------------- sync primitives
def _save_sync(
    property_id: str,
    client_name: str,
    client_email: str,
    preferred_time: str,
    event_id: Optional[str],
    thread_id: Optional[str],
    db_path: str,
) -> str:
    _ensure_schema(db_path)
    booking_id = "BK-" + uuid.uuid4().hex[:8].upper()
    now = time.time()
    with _connect(db_path) as c:
        c.execute(
            """INSERT INTO bookings
               (booking_id, event_id, property_id, client_name, client_email,
                preferred_time, status, thread_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)""",
            (booking_id, event_id, property_id, client_name, client_email,
             preferred_time, thread_id, now, now),
        )
    logger.info("booking_store.save booking_id=%s property=%s event=%s",
                booking_id, property_id, event_id)
    return booking_id


def _find_sync(
    db_path: str,
    property_id: Optional[str] = None,
    client_email: Optional[str] = None,
    booking_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    include_inactive: bool = False,
) -> Optional[Dict[str, Any]]:
    _ensure_schema(db_path)
    clauses: list[str] = []
    args: list = []
    if not include_inactive:
        clauses.append("status IN ('active','rescheduled')")
    if property_id:
        clauses.append("property_id = ?")
        args.append(property_id)
    if client_email:
        clauses.append("client_email = ?")
        args.append(client_email)
    if booking_id:
        clauses.append("booking_id = ?")
        args.append(booking_id)
    if thread_id:
        clauses.append("thread_id = ?")
        args.append(thread_id)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect(db_path) as c:
        row = c.execute(
            f"SELECT * FROM bookings{where} ORDER BY created_at DESC LIMIT 1",
            args,
        ).fetchone()
    return dict(row) if row else None


def _update_sync(
    db_path: str,
    booking_id: str,
    status: Optional[str] = None,
    new_event_id: Optional[str] = None,
    new_preferred_time: Optional[str] = None,
) -> bool:
    _ensure_schema(db_path)
    fields = ["updated_at = ?"]
    args: list = [time.time()]
    if status is not None:
        fields.append("status = ?")
        args.append(status)
    if new_event_id is not None:
        fields.append("event_id = ?")
        args.append(new_event_id)
    if new_preferred_time is not None:
        fields.append("preferred_time = ?")
        args.append(new_preferred_time)
    args.append(booking_id)
    with _connect(db_path) as c:
        cur = c.execute(
            f"UPDATE bookings SET {', '.join(fields)} WHERE booking_id = ?", args
        )
        return cur.rowcount > 0


# -------------------------------------------------------------- async facade
class BookingStore:
    """Async wrapper. All DB work runs in the default thread executor."""

    def __init__(self, db_path: str = DEFAULT_DB):
        self.db_path = db_path

    async def save(
        self,
        property_id: str,
        client_name: str,
        client_email: str,
        preferred_time: str,
        event_id: Optional[str],
        thread_id: Optional[str] = None,
    ) -> str:
        return await asyncio.to_thread(
            _save_sync,
            property_id=property_id,
            client_name=client_name,
            client_email=client_email,
            preferred_time=preferred_time,
            event_id=event_id,
            thread_id=thread_id,
            db_path=self.db_path,
        )

    async def find_active(
        self,
        property_id: Optional[str] = None,
        client_email: Optional[str] = None,
        booking_id: Optional[str] = None,
        thread_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        return await asyncio.to_thread(
            _find_sync,
            db_path=self.db_path,
            property_id=property_id,
            client_email=client_email,
            booking_id=booking_id,
            thread_id=thread_id,
            include_inactive=False,
        )

    async def cancel(self, booking_id: str) -> bool:
        return await asyncio.to_thread(
            _update_sync, db_path=self.db_path, booking_id=booking_id,
            status="cancelled",
        )

    async def mark_rescheduled(
        self, booking_id: str,
        new_event_id: Optional[str] = None,
        new_preferred_time: Optional[str] = None,
    ) -> bool:
        return await asyncio.to_thread(
            _update_sync,
            db_path=self.db_path,
            booking_id=booking_id,
            status="rescheduled",
            new_event_id=new_event_id,
            new_preferred_time=new_preferred_time,
        )