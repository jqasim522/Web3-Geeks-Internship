"""
lib/graph_nodes.py — Day 5, Task 2 (Day 7 extension: cancel + reschedule)

Every node is `async def node(state: AgentState, deps: GraphDeps) -> Dict[str, Any]`
- a partial-state update dict, per LangGraph convention. lib/graph_builder.py binds
`deps` via functools.partial when registering each node. Every node's body is wrapped
by `_guarded()`, which logs entry/exit + latency_ms and converts any exception into
`{"error": "<node>: <ExceptionType>: <message>"}` instead of raising.

RUN ON USER MACHINE: python -m lib.graph_nodes
EXPECTED OUTPUT: "lib/graph_nodes.py self-test: all assertions passed"
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional

from langgraph.errors import GraphInterrupt
from langgraph.types import interrupt

from lib import booking_tool as bt
from lib import rag_lib as r
from lib.llm_fallback import FallbackLLM

logger = logging.getLogger("day5.graph_nodes")

VALID_INTENTS = ("search", "price", "book", "greet", "refuse", "cancel", "reschedule")


# =====================================================================================
# Dependencies (bound into each node via functools.partial in graph_builder.py)
# =====================================================================================
@dataclass
class GraphDeps:
    tool_registry: Dict[str, Callable[..., Awaitable[Any]]]
    fallback_llm: FallbackLLM = field(default_factory=FallbackLLM)
    booking_store: Optional[Any] = None       # lib.booking_store.BookingStore
    calendar_client: Optional[Any] = None     # lib.calendar_client.CalendarClient


# =====================================================================================
# Shared guard
# =====================================================================================
async def _guarded(name: str, body: Callable[[], Awaitable[Dict[str, Any]]]) -> Dict[str, Any]:
    t0 = time.monotonic()
    logger.info("node_enter node=%s", name)
    try:
        result = await body()
        latency_ms = round((time.monotonic() - t0) * 1000, 1)
        logger.info("node_exit node=%s latency_ms=%s ok=True", name, latency_ms)
        return result
    except GraphInterrupt:
        latency_ms = round((time.monotonic() - t0) * 1000, 1)
        logger.info("node_exit node=%s latency_ms=%s ok=paused(interrupt)", name, latency_ms)
        raise
    except Exception as e:
        latency_ms = round((time.monotonic() - t0) * 1000, 1)
        logger.exception("node_error node=%s", name)
        logger.info("node_exit node=%s latency_ms=%s ok=False", name, latency_ms)
        return {"error": f"{name}: {type(e).__name__}: {e}"}


# =====================================================================================
# Intent classifier regexes — SINGLE definitions, do not duplicate these lower in file
# =====================================================================================
_GREET_RE = re.compile(r"\b(assalam|salam|hello+|hi|hey|good morning|good evening|good afternoon)\b", re.I)
_BYE_RE = re.compile(r"\b(bye|goodbye|khuda ?hafiz|allah ?hafiz|shukriya|thank you|thanks)\b", re.I)
_BOOK_RE = re.compile(r"\b(book|booking|schedule|appointment|site visit|visit\s*(book|karna|karain|karini))\b", re.I)
_PRICE_WORDS_RE = re.compile(r"\b(price|priced|cost|kitne? ka|kitni|how much)\b", re.I)

# Cancel: permissive on purpose — reschedule is checked first in
# _rule_based_intent, so a bare "cancel" is safe to treat as cancel.
_CANCEL_RE = re.compile(
    r"\bcancel\b"
    r"|\bkan[ck]el\b"
    r"|\bmansookh\b"
    r"|\bradd\b",
    re.I,
)
_RESCHEDULE_RE = re.compile(
    r"\breschedul[ei]?\b"
    r"|\breskedule\b"
    r"|\bvisit\s+date\s+update\b"
    r"|\bdate\s+update\s+kar\b"
    r"|\b(move|change|tabdeel|badal)\b[\s\w]{0,40}\b"
    r"(book|booking|visit|appointment|time|date|schedule)\b"
    r"|\b(book|booking|visit|appointment|time|date|schedule)\b[\s\w]{0,40}\b"
    r"(move|change|tabdeel|badal)\b",
    re.I,
)
_SEARCH_REFINE_RE = re.compile(
    r"\b(sasti|sasta|sast[ae]|cheap(?:er)?|kam\s*(?:price|qeemat)|"
    r"affordable|budget|under|less\s+than|"
    r"aur\s+(?:options?|choices?)|koi\s+aur|dusra|doosra|"
    r"alternatives?|options?|choices?|"
    r"show\s+me|dikha\s*do|batao|batayein|"
    r"kaunse|kaun\s*se|kya\s+hai|kya\s+hain)\b",
    re.I,
)


def _rule_based_intent(text: str) -> Optional[str]:
    """Returns one of VALID_INTENTS, or None if genuinely ambiguous."""
    # Order matters. Reschedule / cancel BEFORE book, because "cancel booking"
    # contains "booking" which _BOOK_RE would otherwise swallow.
    if _RESCHEDULE_RE.search(text):
        return "reschedule"
    if _CANCEL_RE.search(text):
        return "cancel"
    if _BOOK_RE.search(text):
        return "book"
    # Price BEFORE search refine: "kya hai" is a search signal on its own,
    # but "price kya hai" is a price query — must not be shadowed.
    if _PRICE_WORDS_RE.search(text):
        return "price"
    if _SEARCH_REFINE_RE.search(text):
        return "search"
    in_scope = r.in_scope(text)
    if (_GREET_RE.search(text) or _BYE_RE.search(text)) and not in_scope:
        return "greet"
    if not in_scope:
        if len(text.split()) <= 3:
            return None
        return "refuse"
    parsed = r.parse_question(text)
    if (parsed.get("attribute") == "price_pkr"
            or parsed.get("aggregate") in ("avg", "median", "min", "max")):
        return "price"
    return "search"

async def classify_intent_node(state: Dict[str, Any], deps: GraphDeps) -> Dict[str, Any]:
    async def body() -> Dict[str, Any]:
        text = state["user_input"] or ""

        # --- Guardrail 1: fake / bulk / spam booking requests -----------------
        _FAKE_RE = re.compile(
            r"\b(fake|dummy|spam|prank|bakwas|jhoot|jhooti)\b"
            r"|(?<![A-Za-z0-9-])\d{2,}\s+(?:appointments?|bookings?|visits?)\b"
            r"|\b(?:appointments?|bookings?|visits?)\s+\d{2,}\b"
            r"|\b(?:book\s+all|book\s+every|mass\s*book)\b",
            re.I,
        )
        if _FAKE_RE.search(text):
            return {
                "intent": "refuse",
                "response_text": (
                    "Ji sir, main fake ya bulk bookings nahi kar sakta. "
                    "Agar kisi specific property ka real visit schedule karna ho "
                    "to bata dijiye — main woh zaroor arrange kar dunga."
                ),
            }

        # --- Guardrail 2: prompt-injection / reveal / meta / internal data ----
        _META_RE = re.compile(
            r"(ignore|forget|disregard|bypass|override)\s+"
            r"(your|all|previous|the|these|any)\s+"
            r"(instructions?|prompts?|rules?|guidelines?|directives?)"
            r"|(reveal|show|display|print|tell|share|give)\s+(me\s+)?"
            r"(your|the)\s+(prompt|instructions?|system|rules?|guidelines?)"
            r"|(which|what|kaunsa|konsa)\s+(llm|model|ai|gpt|engine|version)"
            r"|(internal|company|confidential|private|proprietary)\s+"
            r"(data|info(?:rmation)?|records?|details?|files?)"
            r"|(give|send|show|share)\s+(me\s+)?(the\s+)?"
            r"(internal|company|confidential|private)"
            r"|(summary|khulasa)\s+(of|kya\s+tha)\s+(our|hamari|humari)?\s*"
            r"(conversation|baat|chat)"
            r"|(what|kya)\s+(have|we|hum)\s+(discussed|baat\s*ki)"
            r"|provide\s+me\s+(?:details?\s+about\s+)?(?:my|meri)\s+"
            r"(?:visitation|booking|visit)(?:\s+details?)?"
            r"|(?:details?|info(?:rmation)?)\s+(?:about|of|for)\s+"
            r"(?:my|meri)\s+(?:visitation|booking|visit)"
            r"|meri\s+(?:booking|visit|visitation)\s+(?:ki\s+)?details?"
            r"|(?:show|dikha|batao)\s+(?:me\s+)?(?:my|meri)\s+"
            r"(?:booking|visit|visitation)"
            r"|(?:what|kya)\s+(?:is|hai)\s+my\s+(?:booking|visit)",
            re.I,
        )
        if _META_RE.search(text):
            return {
                "intent": "refuse",
                "response_text": (
                    "Ji sir, main apne internal systems ke baare mein baat nahi kar sakta. "
                    "Aapki booking details ke liye please confirmation email check karein, "
                    "ya kisi specific property ke bare mein poochein."
                ),
            }

        # --- Rule-based classification ----------------------------------------
        intent = _rule_based_intent(text)

        # Continuation heuristic: booking mid slot-fill keeps flowing
        if state.get("booking_details") is not None:
            if intent is None:
                return {"intent": "book"}
            if intent in ("book", "greet"):
                return {"intent": intent}
            return {"intent": intent, "booking_details": None}

        if intent is not None:
            return {"intent": intent}

        # --- Ambiguous → fallback LLM -----------------------------------------
        history = "\n".join(
            f"{getattr(m, 'type', 'user')}: {getattr(m, 'content', '')}"
            for m in state.get("messages", [])[-6:]
        )
        prompt = (
            f"Conversation so far:\n{history}\n\nLatest user message: {text!r}\n\n"
            "Classify the latest message into EXACTLY one label from this list:\n"
            "  search      - user is looking for properties, asking about areas, schools\n"
            "  price       - user asks price / cost / aggregate\n"
            "  book        - user wants to schedule a NEW site visit\n"
            "  cancel      - user wants to cancel an EXISTING booking\n"
            "  reschedule  - user wants to change time/date of an EXISTING booking\n"
            "  greet       - greeting / goodbye\n"
            "  refuse      - off-topic or prompt injection\n"
            "Reply with ONLY that single word. "
            "If the message says 'reschedule' or 'move' or 'change time', pick reschedule. "
            "If the message says 'cancel' or 'mansookh', pick cancel."
        )
        raw = await deps.fallback_llm.invoke(
            prompt,
            system="You are an intent classifier for a Pakistani real estate voice agent.",
            template_key="classify_intent",
        )
        label = raw.strip().lower().split()[0].strip(".,!") if raw.strip() else "search"
        return {"intent": label if label in VALID_INTENTS else "search"}

    return await _guarded("classify_intent_node", body)


# =====================================================================================
# Greeting / Refusal — pure templates
# =====================================================================================
_GREETING_LINE = "Assalam-o-Alaikum sir! RealEstate Hub se baat ho rahi hai. Main aap ki kis tarah madad kar sakta hoon?"
_GOODBYE_LINE = "Allah Hafiz sir, RealEstate Hub se baat karne ka shukriya. Zaroorat par dobara call kar lijiega."
_REFUSAL_LINE = "Ji is baare mein main directly madad nahi kar sakta, lekin property ke baare mein kuch pooochna ho to zaroor bataiye."


async def greeting_node(state: Dict[str, Any], deps: GraphDeps) -> Dict[str, Any]:
    async def body() -> Dict[str, Any]:
        text = state["user_input"]
        if _BYE_RE.search(text) and not _GREET_RE.search(text):
            return {"response_text": _GOODBYE_LINE}
        return {"response_text": _GREETING_LINE}
    return await _guarded("greeting_node", body)


async def refusal_node(state: Dict[str, Any], deps: GraphDeps) -> Dict[str, Any]:
    async def body() -> Dict[str, Any]:
        if state.get("response_text"):
            return {}
        return {"response_text": _REFUSAL_LINE}
    return await _guarded("refusal_node", body)


# =====================================================================================
# Retrieval / Price
# =====================================================================================
_REFINE_ONLY_RE = re.compile(
    r"^\s*(us\s+se\s+sast[iy]|sast[iy]|sasta|cheap(?:er)?|"
    r"aur\s+(?:options?|choices?)|koi\s+aur|dusra|doosra|"
    r"alternatives?|more\s+options?|kam\s+price|"
    r"batao|batayein|dikha\s*do)\b",
    re.I,
)


def _merge_refinement(state: Dict[str, Any], text: str) -> str:
    if not _REFINE_ONLY_RE.search(text):
        return text
    messages = state.get("messages") or []
    for m in reversed(messages[:-1] if len(messages) > 1 else []):
        role = getattr(m, "type", None) or getattr(m, "role", None)
        content = getattr(m, "content", "") or ""
        if role in ("human", "user") and content.strip():
            return f"{content.strip()} {text.strip()}"
    return text


async def retrieval_node(state: Dict[str, Any], deps: GraphDeps) -> Dict[str, Any]:
    async def body() -> Dict[str, Any]:
        query = _merge_refinement(state, state["user_input"])
        result = await deps.tool_registry["answer_question"](query)
        ids = [str(s) for s in result.get("sources", []) if r.ID_RE.fullmatch(str(s))]
        return {"retrieved_docs": [result], "property_ids": ids}
    return await _guarded("retrieval_node", body)


async def price_node(state: Dict[str, Any], deps: GraphDeps) -> Dict[str, Any]:
    async def body() -> Dict[str, Any]:
        query = _merge_refinement(state, state["user_input"])
        result = await deps.tool_registry["answer_question"](query, force_route="sql")
        ids = [str(s) for s in result.get("sources", []) if r.ID_RE.fullmatch(str(s))]
        return {"retrieved_docs": [result], "property_ids": ids}
    return await _guarded("price_node", body)


# =====================================================================================
# Booking slot extraction
# =====================================================================================
_NAME_RE = re.compile(
    r"(?:my name is|(?:mera\s+)?naam(?:\s+hai)?)\s*[:,]?\s*([A-Za-z][A-Za-z .]{1,40})",
    re.I,
)
_DATETIME_RE = re.compile(r"(\d{4}-\d{2}-\d{2})[ T](\d{1,2}:\d{2})")

_MISSING_PROMPTS = {
    "property_id": "Konsi property ke liye visit book karni hai? Property ID ya area bata dein.",
    "client_name": "Aap ka poora naam kya hai?",
    "client_email": "Confirmation email kis address par bhejun?",
    "preferred_time": "Kis din aur kis waqt visit karna chahenge? (e.g. 2026-09-30 15:00)",
}
_REQUIRED_BOOKING_FIELDS = ("property_id", "client_name", "client_email", "preferred_time")


async def _extract_booking_slots(state: Dict[str, Any], deps: GraphDeps) -> Dict[str, Any]:
    text = state["user_input"]
    slots: Dict[str, Any] = dict(state.get("booking_details") or {})

    ids_this_turn = state.get("property_ids") or []
    m_id = r.ID_RE.search(text)
    if ids_this_turn:
        slots["property_id"] = ids_this_turn[0]
    elif m_id:
        slots["property_id"] = m_id.group(0).upper()

    m_email = bt._EMAIL_RE.search(text)
    if m_email:
        slots["client_email"] = m_email.group(0).rstrip(".,;:!?").lower()

    m_name = _NAME_RE.search(text)
    if m_name:
        candidate = m_name.group(1).strip()
        if not re.fullmatch(r"[A-Z]{2,4}", candidate):
            slots["client_name"] = candidate

    if not slots.get("client_name") and "," in text:
        for part in (p.strip() for p in text.split(",")):
            if not part or len(part) > 50:
                continue
            if re.match(r"^[A-Z]{2,4}-\d{3,5}\b", part):
                continue
            if "@" in part:
                continue
            if re.search(r"\d{4}-\d{2}-\d{2}", part) or re.search(r"\d{1,2}:\d{2}", part):
                continue
            if re.match(r"^(visit|book|site|schedule|property|price|"
                        r"lahore|karachi|islamabad|rawalpindi)\b", part, re.I):
                continue
            if re.match(r"^[A-Za-z][A-Za-z.'\- ]+$", part):
                slots["client_name"] = part.title()
                break

    m_dt = _DATETIME_RE.search(text)
    if m_dt:
        slots["preferred_time"] = f"{m_dt.group(1)} {m_dt.group(2)}"

    raw = (text or "").strip()

    if not slots.get("client_name") and raw and 1 <= len(raw) < 60:
        bad_word = re.search(
            r"\b(book|visit|schedule|dekhna|chahta|chahiye|karna|kar\s*do|"
            r"reset|cancel|haan|yes|no|nahi|theek|ok|okay)\b", raw, re.I)
        has_email = "@" in raw
        has_date = bool(re.search(r"\d{4}-\d{2}-\d{2}", raw))
        has_id = bool(re.search(r"\b[A-Za-z]{2,4}[-\s]?\d{3,5}\b", raw))
        only_letters_spaces = bool(re.fullmatch(r"[A-Za-z][A-Za-z.'\- ]*", raw))
        looks_like_code = bool(re.fullmatch(r"[A-Z]{2,4}", raw))
        looks_spaced_code = bool(re.fullmatch(r"(?:[A-Z]\s+){2,}[A-Z]", raw))
        if (not bad_word and not has_email and not has_date
                and not has_id and only_letters_spaces
                and not looks_like_code and not looks_spaced_code):
            name = raw
            if name.islower() or name.isupper():
                name = name.title()
            slots["client_name"] = name

    if not slots.get("client_email") and raw and "@" in raw and " " not in raw:
        slots["client_email"] = raw.rstrip(".,;:!?").lower()

    if slots.get("property_id"):
        prop = await deps.tool_registry["get_property"](slots["property_id"])
        if not prop:
            slots.pop("property_id", None)

    return slots


async def booking_node(state: Dict[str, Any], deps: GraphDeps) -> Dict[str, Any]:
    async def body() -> Dict[str, Any]:
        slots = await _extract_booking_slots(state, deps)
        missing = [f for f in _REQUIRED_BOOKING_FIELDS if not slots.get(f)]
        if missing:
            return {
                "booking_details": slots,
                "confirmation_needed": False,
                "tool_result": None,
                "response_text": _MISSING_PROMPTS.get(missing[0], "Thodi aur detail chahiye."),
            }
        return {"booking_details": slots, "confirmation_needed": True}
    return await _guarded("booking_node", body)


# =====================================================================================
# HITL helpers
# =====================================================================================
_AFFIRM_RE = re.compile(r"\b(yes|haan|ji\s*haan|theek|confirm|ok(?:ay)?|bilkul)\b", re.I)
_NEGATE_RE = re.compile(r"\b(no|nahi|cancel|mat karo)\b", re.I)

from lib.site_visit_booking import VISIT_DURATION   # noqa: E402


# =====================================================================================
# Cancel node
# =====================================================================================
async def cancel_booking_node(state: Dict[str, Any], deps: GraphDeps) -> Dict[str, Any]:
    async def body() -> Dict[str, Any]:
        text = state["user_input"]
        property_id = None
        if state.get("property_ids"):
            property_id = state["property_ids"][0]
        else:
            m = r.ID_RE.search(text)
            if m:
                property_id = m.group(0).upper()

        if not property_id:
            return {"response_text":
                    "Konsi property ki booking cancel karni hai? Property ID batayein."}

        if getattr(deps, "booking_store", None) is None:
            return {"error": "cancel_booking_node: booking_store not configured"}

        booking = await deps.booking_store.find_active(property_id=property_id)
        if not booking:
            return {"response_text": f"Sir, {property_id} ki koi active booking nahi mili."}

        summary = (
            f"Confirm karain: {booking['property_id']} ki {booking['preferred_time']} "
            f"({booking['client_name']}) site visit cancel kar dun? (haan / nahi)"
        )
        ans = interrupt({"type": "confirm_cancel", "summary": summary, "booking": booking})
        while not (_AFFIRM_RE.search(str(ans)) or _NEGATE_RE.search(str(ans))):
            ans = interrupt({"type": "confirm_cancel",
                             "summary": "Haan ya nahi: " + summary, "booking": booking})

        if _NEGATE_RE.search(str(ans)):
            return {"tool_result": {"status": "declined"},
                    "response_text": "Ji theek hai, cancellation cancel kar di."}

        event_id = booking.get("event_id")
        if event_id:
            try:
                await deps.calendar_client.cancel_event(event_id)
            except Exception as e:
                logger.exception("cancel_booking_node: calendar failed")
                return {"error": f"cancel_booking_node: {type(e).__name__}: {e}"}

        try:
            await deps.booking_store.cancel(booking["booking_id"])
        except Exception:
            logger.exception("cancel_booking_node: store update failed")

        return {"tool_result": {
            "status": "cancelled",
            "booking_id": booking["booking_id"],
            "event_id": event_id,
            "confirmation_text_urdu_lish": (
                f"Ji {booking['client_name']} sahib, {booking['property_id']} ki "
                f"site visit ({booking['preferred_time']}) cancel kar di gayi hai. "
                + ("Calendar se bhi hata diya." if event_id else
                   "Store se hata diya.")
            ),
        }}
    return await _guarded("cancel_booking_node", body)


# =====================================================================================
# Reschedule node
# =====================================================================================
async def reschedule_booking_node(state: Dict[str, Any], deps: GraphDeps) -> Dict[str, Any]:
    async def body() -> Dict[str, Any]:
        text = state["user_input"]
        property_id = None
        if state.get("property_ids"):
            property_id = state["property_ids"][0]
        else:
            m = r.ID_RE.search(text)
            if m:
                property_id = m.group(0).upper()

        if not property_id:
            return {"response_text":
                    "Konsi property ki booking reschedule karni hai? Property ID batayein."}

        m_dt = _DATETIME_RE.search(text)
        if not m_dt:
            return {"response_text": "Naya din aur waqt? (e.g. 2026-10-15 16:00)"}

        new_time_str = f"{m_dt.group(1)} {m_dt.group(2)}"

        if getattr(deps, "booking_store", None) is None:
            return {"error": "reschedule_booking_node: booking_store not configured"}

        booking = await deps.booking_store.find_active(property_id=property_id)
        if not booking:
            return {"response_text": f"Sir, {property_id} ki koi active booking nahi mili."}

        summary = (
            f"Confirm karain: {booking['property_id']} ki site visit "
            f"{booking['preferred_time']} se {new_time_str} par reschedule kar dun? (haan / nahi)"
        )
        ans = interrupt({"type": "confirm_reschedule", "summary": summary,
                         "booking": booking, "new_time": new_time_str})
        while not (_AFFIRM_RE.search(str(ans)) or _NEGATE_RE.search(str(ans))):
            ans = interrupt({"type": "confirm_reschedule",
                             "summary": "Haan ya nahi: " + summary,
                             "booking": booking, "new_time": new_time_str})

        if _NEGATE_RE.search(str(ans)):
            return {"tool_result": {"status": "declined"},
                    "response_text": "Ji theek hai, reschedule nahi kiya."}

        try:
            new_dt = datetime.strptime(new_time_str, "%Y-%m-%d %H:%M")
        except ValueError as e:
            return {"error": f"reschedule_booking_node: bad time {new_time_str!r}: {e}"}

        new_end = new_dt + VISIT_DURATION
        event_id = booking.get("event_id")
        if not event_id:
            return {"response_text": "Sir, is booking ka calendar event record nahi mila."}

        try:
            await deps.calendar_client.update_event(
                event_id=event_id,
                start=new_dt,
                end=new_end,
                attendee_email=booking["client_email"],
            )
        except Exception as e:
            logger.exception("reschedule_booking_node: update failed")
            return {"error": f"reschedule_booking_node: {type(e).__name__}: {e}"}

        try:
            from lib.email_client import EmailClient
            visit_time_str = new_dt.strftime("%A, %d %b %Y, %I:%M %p")
            await EmailClient().send_confirmation(
                to=booking["client_email"],
                property_id=booking["property_id"],
                visit_time=visit_time_str,
                agent_name="Hajra",
            )
            logger.info("reschedule_booking_node: email sent to %s", booking["client_email"])
        except Exception:
            logger.exception("reschedule_booking_node: email failed (non-fatal)")

        try:
            await deps.booking_store.mark_rescheduled(
                booking["booking_id"], new_preferred_time=new_time_str)
        except Exception:
            logger.exception("reschedule_booking_node: store update failed")

        return {"tool_result": {
            "status": "rescheduled",
            "booking_id": booking["booking_id"],
            "new_time": new_time_str,
            "confirmation_text_urdu_lish": (
                f"Ji {booking['client_name']} sahib, {booking['property_id']} ki "
                f"site visit {booking['preferred_time']} se {new_time_str} par "
                "reschedule kar di gayi hai. Calendar update ho gaya."
            ),
        }}
    return await _guarded("reschedule_booking_node", body)


# =====================================================================================
# Confirm booking node
# =====================================================================================
async def confirm_booking_node(state: Dict[str, Any], deps: GraphDeps) -> Dict[str, Any]:
    async def body() -> Dict[str, Any]:
        details = state.get("booking_details") or {}
        summary = (
            f"Confirm karain: {details.get('property_id')} property ke liye, "
            f"{details.get('client_name')} ke naam se, {details.get('preferred_time')} ko visit book kar dun? "
            f"(haan / nahi)"
        )
        ans = interrupt({"type": "confirm_booking", "summary": summary, "booking_details": details})
        while not (_AFFIRM_RE.search(str(ans)) or _NEGATE_RE.search(str(ans))):
            ans = interrupt({
                "type": "confirm_booking",
                "summary": "Maazrat, samajh nahi aaya. Haan ya nahi: " + summary,
                "booking_details": details,
            })

        if _NEGATE_RE.search(str(ans)):
            return {"confirmation_needed": False, "booking_details": None,
                    "tool_result": None,
                    "response_text": "Ji theek hai, booking cancel kar di. Kuch aur chahiye?"}

        try:
            preferred_time = datetime.strptime(details["preferred_time"], "%Y-%m-%d %H:%M")
        except (KeyError, ValueError) as e:
            return {"error": f"confirm_booking_node: bad preferred_time {details.get('preferred_time')!r}: {e}"}

        result = await deps.tool_registry["book_site_visit"](
            property_id=details["property_id"],
            client_name=details["client_name"],
            client_email=details["client_email"],
            preferred_time=preferred_time,
        )

        if result.get("status") == "booked" and getattr(deps, "booking_store", None) is not None:
            try:
                bid = await deps.booking_store.save(
                    property_id=details["property_id"],
                    client_name=details["client_name"],
                    client_email=details["client_email"],
                    preferred_time=details["preferred_time"],
                    event_id=result.get("event_id"),
                )
                result["booking_id"] = bid
                logger.info("confirm_booking_node: stored booking_id=%s event_id=%s",
                            bid, result.get("event_id"))
            except Exception:
                logger.exception("confirm_booking_node: booking_store.save failed (non-fatal)")

        return {"tool_result": result, "confirmation_needed": False, "booking_details": None}
    return await _guarded("confirm_booking_node", body)


# =====================================================================================
# Response render
# =====================================================================================
def _prepare_for_tts(text: str) -> str:
    try:
        from lib import tts_urdu_lish as ul
        return ul.prepare_for_tts(text)
    except Exception as e:
        logger.warning("response_render_node: tts_urdu_lish unavailable (%s: %s)",
                       type(e).__name__, e)
        return text


async def response_render_node(state: Dict[str, Any], deps: GraphDeps) -> Dict[str, Any]:
    async def body() -> Dict[str, Any]:
        if state.get("error"):
            text = ("Sir, mujhe afsos hai, filhal system mein thodi dikkat aa rahi hai. "
                    "Main aap ko hamare team member se callback karwata hoon.")
        elif state.get("response_text"):
            text = state["response_text"]
        elif state.get("tool_result") is not None:
            tr = state["tool_result"]
            text = tr.get("confirmation_text_urdu_lish") or "Ji, aap ki request process ho gayi hai."
        elif state.get("retrieved_docs"):
            payload = state["retrieved_docs"][-1]
            text = payload.get("answer") or "Maazrat, mujhe iska jawab nahi mila."
        else:
            text = "Maazrat sir, mujhe samajh nahi aaya. Dobara bata sakte hain?"
        return {
            "response_text": text,
            "response_text_tts": _prepare_for_tts(text),
        }
    return await _guarded("response_render_node", body)


# =====================================================================================
# Error node
# =====================================================================================
async def error_node(state: Dict[str, Any], deps: GraphDeps) -> Dict[str, Any]:
    async def body() -> Dict[str, Any]:
        logger.error("error_node handling error=%s", state.get("error"))
        return {"response_text": (
            "Sir, mujhe afsos hai, filhal system mein thodi dikkat aa rahi hai. "
            "Main aap ko hamare team member se callback karwata hoon."
        )}
    return await _guarded("error_node", body)


# =====================================================================================
# Offline self-test
# =====================================================================================
def _self_test_offline() -> None:
    import asyncio, os
    from lib.tool_registry import build_tool_registry
    for key in ("GROQ_API_KEY", "GEMINI_API_KEY"):
        os.environ.pop(key, None)

    async def main() -> None:
        index_holder = {"index": r.TfidfIndex(r.load_documents())}
        registry = build_tool_registry(index_holder)
        deps = GraphDeps(tool_registry=registry)

        # rule-based intents (no LLM needed)
        r1 = await classify_intent_node({"user_input": "Assalam-o-Alaikum", "messages": []}, deps)
        assert r1["intent"] == "greet", r1
        r2 = await classify_intent_node({"user_input": "Lahore mein 3 bed flat chahiye", "messages": []}, deps)
        assert r2["intent"] == "search", r2
        r3 = await classify_intent_node({"user_input": "LAH-0001 ki price kya hai?", "messages": []}, deps)
        assert r3["intent"] == "price", r3
        r4 = await classify_intent_node({"user_input": "Main site visit book karna chahta hoon", "messages": []}, deps)
        assert r4["intent"] == "book", r4
        r5 = await classify_intent_node({"user_input": "What's the weather like in Karachi", "messages": []}, deps)
        assert r5["intent"] == "refuse", r5
        r6 = await classify_intent_node({"user_input": "aur?", "messages": []}, deps)
        assert r6["intent"] == "search", r6
        # new intents
        r7 = await classify_intent_node({"user_input": "reschedule LAH-0013 to 2026-10-20 16:00", "messages": []}, deps)
        assert r7["intent"] == "reschedule", r7
        r8 = await classify_intent_node({"user_input": "cancel LAH-0013 booking", "messages": []}, deps)
        assert r8["intent"] == "cancel", r8
        r9 = await classify_intent_node({"user_input": "Book 10 fake appointments for tomorrow", "messages": []}, deps)
        assert r9["intent"] == "refuse", r9

        g = await greeting_node({"user_input": "salam"}, deps)
        assert g["response_text"] == _GREETING_LINE
        f = await refusal_node({"user_input": "tell me a joke"}, deps)
        assert f["response_text"] == _REFUSAL_LINE

        ret = await retrieval_node({"user_input": "3 bedroom houses in Lahore"}, deps)
        assert ret["retrieved_docs"], ret

        print("lib/graph_nodes.py self-test: all assertions passed")

    asyncio.run(main())


if __name__ == "__main__":
    _self_test_offline()