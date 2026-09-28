"""
lib/booking_tool.py — Day 4, Task 10 (support module for the voice_pipeline.py patch)

# STATUS: CODE-COMPLETE | UNTESTED — requires live OAuth + network + a real
#   Groq call to confirm the model actually emits the JSON shape below.
#   The JSON parsing/validation here IS covered by ordinary unit testing
#   (no network needed) via _self_test() at the bottom.

Defines the ONE new tool the LLM gateway gains in Day 4: book_site_visit.
This module only does parsing/validation/execution — it does not touch
VoiceAgent itself. See lib/voice_pipeline_day4_patch.md for the minimal,
add-only integration into lib/voice_pipeline.py.

Tool contract (given to the LLM in the system prompt addendum below): when
the caller has given all five required details (see system_prompt.md's
"APPOINTMENT BOOKING POLICY" — name, phone, property, date, time), and only
then, the model may respond with ONLY this JSON object (nothing else in the
message):

    {"tool": "book_site_visit",
     "args": {"property_id": "LAH-0004", "client_name": "Ali Raza",
               "client_email": "ali@example.com",
               "preferred_time": "2026-09-30 15:00"}}

Any other reply is normal spoken UrduLish text and is handled exactly as
before this patch (unaffected — this module changes nothing about the
non-booking path).
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger("day4.booking_tool")

TOOL_NAME = "book_site_visit"

TOOL_SCHEMA: Dict[str, Any] = {
    "name": TOOL_NAME,
    "description": (
        "Book a property site visit: creates a Google Calendar event and "
        "sends the client a confirmation email. Only call this once the "
        "caller's full name, property of interest, preferred date and "
        "preferred time are all confirmed (per the appointment booking "
        "policy) and you have a valid client email address."
    ),
    "args": {
        "property_id": "string, e.g. LAH-0004 / KAR-0123 / ISL-0045 / RAW-0012",
        "client_name": "string, caller's full name",
        "client_email": "string, a valid email address",
        "preferred_time": "string, 'YYYY-MM-DD HH:MM' in 24h time",
    },
}

BOOKING_SYSTEM_ADDENDUM = (
    "\n\nYou also have ONE tool available: book_site_visit. Use it only once "
    "you have confirmed, in the conversation, all of: caller's full name, "
    "the property (by its ID, e.g. LAH-0004), a preferred date, and a "
    "preferred time, plus a client email address to send the confirmation "
    "to. When and ONLY when all of those are confirmed, reply with EXACTLY "
    "this JSON and nothing else (no extra words before or after it):\n"
    '{"tool": "book_site_visit", "args": {"property_id": "...", '
    '"client_name": "...", "client_email": "...", "preferred_time": '
    '"YYYY-MM-DD HH:MM"}}\n'
    "If any of those five details is still missing, do not emit this JSON — "
    "ask for the missing detail in natural UrduLish instead, as normal."
)

_TOOL_JSON_RE = re.compile(r"\{.*\"tool\"\s*:\s*\"book_site_visit\".*\}", re.DOTALL)
_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


class ToolCallError(ValueError):
    """Raised when text looks like a tool call but is malformed, or a
    well-formed call has invalid/missing arguments."""


def extract_tool_call(text: str) -> Optional[Dict[str, Any]]:
    """Returns the parsed {"tool": ..., "args": {...}} dict if `text`
    contains a book_site_visit tool call, else None (ordinary spoken text).
    Raises ToolCallError if it looks like a tool call but is malformed —
    callers should treat that as "fall back to template", never as success.
    """
    if '"tool"' not in text or TOOL_NAME not in text:
        return None
    m = _TOOL_JSON_RE.search(text)
    if not m:
        raise ToolCallError(f"text mentions {TOOL_NAME} but no parseable JSON object found")
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise ToolCallError(f"malformed tool-call JSON: {e}") from e
    if obj.get("tool") != TOOL_NAME:
        return None
    return obj


def validate_args(args: Dict[str, Any]) -> Dict[str, Any]:
    """Validates and coerces raw tool-call args. Raises ToolCallError on any
    problem — never silently fills in a guessed value."""
    required = ("property_id", "client_name", "client_email", "preferred_time")
    missing = [k for k in required if not args.get(k)]
    if missing:
        raise ToolCallError(f"missing required args: {missing}")

    property_id = str(args["property_id"]).strip().upper()
    if not re.match(r"^(LAH|KAR|ISL|RAW)-\d{4}$", property_id):
        raise ToolCallError(f"property_id {property_id!r} doesn't match the known ID format")

    client_email = str(args["client_email"]).strip()
    if not _EMAIL_RE.match(client_email):
        raise ToolCallError(f"client_email {client_email!r} doesn't look like a valid email")

    preferred_raw = str(args["preferred_time"]).strip()
    preferred_time = None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            preferred_time = datetime.strptime(preferred_raw, fmt)
            break
        except ValueError:
            continue
    if preferred_time is None:
        raise ToolCallError(
            f"preferred_time {preferred_raw!r} isn't parseable "
            f"(expected 'YYYY-MM-DD HH:MM')"
        )

    return {
        "property_id": property_id,
        "client_name": str(args["client_name"]).strip(),
        "client_email": client_email,
        "preferred_time": preferred_time,
    }


async def run_tool_call(call: Dict[str, Any], booker: Any) -> Dict[str, Any]:
    """Validates `call["args"]` and executes it via `booker.book(...)`
    (a SiteVisitBooker). Returns SiteVisitBooker's result dict unchanged.
    Raises ToolCallError before ever touching the booker if args are bad —
    the caller (voice_pipeline.py) is expected to fall back to a spoken
    clarification, exactly like the existing number/ID guard fallback."""
    args = validate_args(call.get("args", {}))
    logger.info("booking_tool.run_tool_call -> %s", {**args, "preferred_time": str(args["preferred_time"])})
    return await booker.book(**args)


def _self_test() -> None:
    """No network, no Google APIs — just proves the parsing/validation logic
    is correct. Run: python -m lib.booking_tool"""
    good = ('{"tool": "book_site_visit", "args": {"property_id": "lah-0004", '
            '"client_name": "Ali Raza", "client_email": "ali@example.com", '
            '"preferred_time": "2026-09-30 15:00"}}')
    call = extract_tool_call(good)
    assert call is not None
    args = validate_args(call["args"])
    assert args["property_id"] == "LAH-0004"
    assert args["preferred_time"] == datetime(2026, 9, 30, 15, 0)

    assert extract_tool_call("Ji bilkul sir, DHA Phase 6 available hai.") is None

    try:
        extract_tool_call('{"tool": "book_site_visit", "args": {')
        raise AssertionError("expected ToolCallError on malformed JSON")
    except ToolCallError:
        pass

    try:
        validate_args({"property_id": "LAH-4", "client_name": "A",
                        "client_email": "not-an-email", "preferred_time": "x"})
        raise AssertionError("expected ToolCallError on bad args")
    except ToolCallError:
        pass

    print("lib/booking_tool.py self-test: all assertions passed")


if __name__ == "__main__":
    _self_test()
