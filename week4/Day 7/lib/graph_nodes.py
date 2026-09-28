"""
lib/graph_nodes.py — Day 5, Task 2

# STATUS: CODE-COMPLETE | TESTED-OFFLINE for classify_intent_node (rule-based path),
#   greeting_node, refusal_node, retrieval_node, price_node, booking_node (slot-filling,
#   against the REAL data/realestate.db - no mocking) and error_node - see
#   _self_test_offline() at the bottom, which is actually run against real rag_lib +
#   the real DB, no network. confirm_booking_node's interrupt() call and
#   response_render_node's tts_urdu_lish import can only be exercised inside a real
#   compiled graph / a real Day 3 checkout, so those two are TESTED-OFFLINE only via
#   lib/graph_builder.py's own self-test (interrupt) and left UNTESTED-LIVE for the
#   tts_urdu_lish import specifically (that module was never included in any handoff
#   package this project was built from - see the note in _prepare_for_tts below).
#   classify_intent_node's LLM-fallback branch (ambiguous input) is UNTESTED-LIVE
#   (needs a real Groq/Gemini key) but its offline fallback (both providers absent ->
#   "search") IS exercised below.
# RUN ON USER MACHINE: python -m lib.graph_nodes
# EXPECTED OUTPUT: "lib/graph_nodes.py self-test: all assertions passed"

Every node is `async def node(state: AgentState, deps: GraphDeps) -> Dict[str, Any]`
- a partial-state update dict, per LangGraph convention. lib/graph_builder.py binds
`deps` via functools.partial when registering each node (verified pattern - see
that file's own docstring). Every node's body is wrapped by `_guarded()`, which
logs entry/exit + latency_ms and converts any exception into
`{"error": "<node>: <ExceptionType>: <message>"}` instead of raising, so the graph
can always continue to response_render_node / error_node.
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

VALID_INTENTS = ("search", "price", "book", "greet", "refuse")


# =====================================================================================
# Dependencies (bound into each node via functools.partial in graph_builder.py)
# =====================================================================================
@dataclass
class GraphDeps:
    tool_registry: Dict[str, Callable[..., Awaitable[Any]]]
    fallback_llm: FallbackLLM = field(default_factory=FallbackLLM)


# =====================================================================================
# Shared guard: entry/exit logging + latency + exception -> state["error"]
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
        # NOT a node failure - this is LangGraph's own control-flow signal for
        # interrupt() (used by confirm_booking_node). It MUST propagate to the
        # graph executor unchanged, or the whole HITL pause/resume mechanism
        # breaks (confirmed: an earlier version of this function caught it as a
        # generic exception and silently converted every confirmation into an
        # error - see docs/day5_graph_architecture.md's "bugs found" section).
        latency_ms = round((time.monotonic() - t0) * 1000, 1)
        logger.info("node_exit node=%s latency_ms=%s ok=paused(interrupt)", name, latency_ms)
        raise
    except Exception as e:
        latency_ms = round((time.monotonic() - t0) * 1000, 1)
        logger.exception("node_error node=%s", name)
        logger.info("node_exit node=%s latency_ms=%s ok=False", name, latency_ms)
        return {"error": f"{name}: {type(e).__name__}: {e}"}


# =====================================================================================
# a) classify_intent_node
# =====================================================================================
# NOTE ON HONESTY: the Day 5 prompt says "uses Day 2's classify_intent()". No function
# by that name exists in the rag_lib.py this project was actually given - the real
# building blocks are rag_lib.in_scope(), rag_lib.parse_question() and
# rag_lib.route_retrieval(). The rule-based classifier below is built from those (new
# code, not a Day 2 deliverable) rather than calling a function that doesn't exist.
_GREET_RE = re.compile(r"\b(assalam|salam|hello+|hi|hey|good morning|good evening|good afternoon)\b", re.I)
_BYE_RE = re.compile(r"\b(bye|goodbye|khuda ?hafiz|allah ?hafiz|shukriya|thank you|thanks)\b", re.I)
_BOOK_RE = re.compile(r"\b(book|booking|schedule|appointment|site visit|visit\s*(book|karna|karain|karini))\b", re.I)
_PRICE_WORDS_RE = re.compile(r"\b(price|priced|cost|kitne? ka|kitni|how much)\b", re.I)


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
    if _BOOK_RE.search(text):
        return "book"
    # Search refinements: "us se sasti", "cheaper", "aur options", "kaunse schools"
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
    if parsed.get("attribute") == "price_pkr" or parsed.get("aggregate") in ("avg", "median", "min", "max") or _PRICE_WORDS_RE.search(text):
        return "price"
    return "search"

async def classify_intent_node(state: Dict[str, Any], deps: GraphDeps) -> Dict[str, Any]:
    async def body() -> Dict[str, Any]:
        text = state["user_input"] or ""

        # --- Guardrail 1: fake / bulk / spam booking requests ----------------
        _FAKE_RE = re.compile(
            r"\b(fake|dummy|spam|prank|bakwas|jhoot|jhooti|"
            r"\d{2,}\s*(?:appointments?|bookings?|visits?)|"
            r"(?:appointments?|bookings?|visits?)\s*\d{2,}|"
            r"book\s+all|book\s+every|mass\s*book)\b",
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

        # --- Rule-based classification ---------------------------------------
        intent = _rule_based_intent(text)

        # Continuation heuristic: booking mid slot-fill
        if state.get("booking_details") is not None:
            if intent is None:
                return {"intent": "book"}
            if intent in ("book", "greet"):
                return {"intent": intent}
            return {"intent": intent, "booking_details": None}

        if intent is not None:
            return {"intent": intent}

        # --- Ambiguous → fallback LLM ----------------------------------------
        history = "\n".join(
            f"{getattr(m, 'type', 'user')}: {getattr(m, 'content', '')}"
            for m in state.get("messages", [])[-6:]
        )
        prompt = (
            f"Conversation so far:\n{history}\n\nLatest user message: {text!r}\n\n"
            "Classify the latest message into EXACTLY one label: search, price, book, greet, refuse. "
            "Reply with ONLY that single word, nothing else."
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
# b) greeting_node — no LLM call
# =====================================================================================
# Phrases reused verbatim from the Day 1 persona deliverable (docs/urdu_lish_persona.md,
# "Phrase Bank -> Greeting") and the Day 1 system prompt's escalation tone, not invented.
_GREETING_LINE = "Assalam-o-Alaikum sir! RealEstate Hub se baat ho rahi hai. Main aap ki kis tarah madad kar sakta hoon?"
_GOODBYE_LINE = "Allah Hafiz sir, RealEstate Hub se baat karne ka shukriya. Zaroorat par dobara call kar lijiega."


async def greeting_node(state: Dict[str, Any], deps: GraphDeps) -> Dict[str, Any]:
    async def body() -> Dict[str, Any]:
        text = state["user_input"]
        if _BYE_RE.search(text) and not _GREET_RE.search(text):
            return {"response_text": _GOODBYE_LINE}
        return {"response_text": _GREETING_LINE}

    return await _guarded("greeting_node", body)


# =====================================================================================
# c) refusal_node — no LLM call
# =====================================================================================
# Reused verbatim from docs/system_prompt.md's "SCOPE" redirect line.
_REFUSAL_LINE = "Ji is baare mein main directly madad nahi kar sakta, lekin property ke baare mein kuch pooochna ho to zaroor bataiye."


async def refusal_node(state: Dict[str, Any], deps: GraphDeps) -> Dict[str, Any]:
    async def body() -> Dict[str, Any]:
        # If a guardrail in classify_intent_node already wrote a specific refusal,
        # keep it — do not overwrite with the generic line.
        if state.get("response_text"):
            return {}
        return {"response_text": _REFUSAL_LINE}

    return await _guarded("refusal_node", body)


# =====================================================================================
# d) retrieval_node — Day 2's answer_question (auto-routed sql/vector/hybrid)
# =====================================================================================
# Add this right before `async def retrieval_node`
_REFINE_ONLY_RE = re.compile(
    r"^\s*(us\s+se\s+sast[iy]|sast[iy]|sasta|cheap(?:er)?|"
    r"aur\s+(?:options?|choices?)|koi\s+aur|dusra|doosra|"
    r"alternatives?|more\s+options?|kam\s+price|"
    r"batao|batayein|dikha\s*do)\b",
    re.I,
)


def _merge_refinement(state: Dict[str, Any], text: str) -> str:
    """If the current message is a refinement-only follow-up, prepend the last
    user query so the retriever has city/beds context."""
    if not _REFINE_ONLY_RE.search(text):
        return text
    messages = state.get("messages") or []
    # messages[-1] is the current turn (added by ConversationRunner); look further back
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
# f) booking_node — slot-filling only. Never calls SiteVisitBooker itself; only
#    confirm_booking_node does, and only after the human confirms (see that node and
#    docs/day5_graph_architecture.md's "Design decision" note on why).
# =====================================================================================
_NAME_RE = re.compile(r"(?:my name is|(?:mera\s+)?naam(?:\s+hai)?)\s*[:,]?\s*([A-Za-z][A-Za-z .]{1,40})", re.I)
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

    # --- 1. property_id from state or regex
    ids_this_turn = state.get("property_ids") or []
    m_id = r.ID_RE.search(text)
    if ids_this_turn:
        slots["property_id"] = ids_this_turn[0]
    elif m_id:
        slots["property_id"] = m_id.group(0).upper()

    # --- 2. email
    m_email = bt._EMAIL_RE.search(text)
    if m_email:
        slots["client_email"] = m_email.group(0).rstrip(".,;:!?").lower()

    # --- 3. name via explicit pattern ("my name is X")
    m_name = _NAME_RE.search(text)
    if m_name:
        candidate = m_name.group(1).strip()
        # reject property-code-looking fragments
        if not re.fullmatch(r"[A-Z]{2,4}", candidate):
            slots["client_name"] = candidate

    # --- 4. comma-separated fallback: "LAH-0001, Ali Raza, ali@x.com, 2026-10-05 10:00"
    if not slots.get("client_name") and "," in text:
        for part in (p.strip() for p in text.split(",")):
            if not part or len(part) > 50:
                continue
            if re.match(r"^[A-Z]{2,4}-\d{3,5}\b", part):        # property ID
                continue
            if "@" in part:                                      # email
                continue
            if re.search(r"\d{4}-\d{2}-\d{2}", part) or re.search(r"\d{1,2}:\d{2}", part):
                continue
            if re.match(r"^(visit|book|site|schedule|property|price|"
                        r"lahore|karachi|islamabad|rawalpindi)\b", part, re.I):
                continue
            if re.match(r"^[A-Za-z][A-Za-z.'\- ]+$", part):
                slots["client_name"] = part.title()
                break

    # --- 5. preferred_time
    m_dt = _DATETIME_RE.search(text)
    if m_dt:
        slots["preferred_time"] = f"{m_dt.group(1)} {m_dt.group(2)}"

    # --- 6. BARE-ANSWER FALLBACK (the critical fix)
    #     Fires independently for each empty slot, regardless of how many are missing.
    raw = (text or "").strip()

    # 6a. bare name — single or multi-word, letters + space/dot/apostrophe/hyphen only
    if not slots.get("client_name") and raw and 1 <= len(raw) < 60:
        bad_word = re.search(
            r"\b(book|visit|schedule|dekhna|chahta|chahiye|karna|kar\s*do|"
            r"reset|cancel|haan|yes|no|nahi|theek|ok|okay)\b",
            raw, re.I)
        has_email = "@" in raw
        has_date  = bool(re.search(r"\d{4}-\d{2}-\d{2}", raw))
        has_id    = bool(re.search(r"\b[A-Za-z]{2,4}[-\s]?\d{3,5}\b", raw))
        only_letters_spaces = bool(re.fullmatch(r"[A-Za-z][A-Za-z.'\- ]*", raw))
        looks_like_code = bool(re.fullmatch(r"[A-Z]{2,4}", raw))
        # also reject "L A H" (letter-space-letter-space pattern) as name
        looks_spaced_code = bool(re.fullmatch(r"(?:[A-Z]\s+){2,}[A-Z]", raw))
        if (not bad_word and not has_email and not has_date
                and not has_id and only_letters_spaces
                and not looks_like_code and not looks_spaced_code):
            name = raw
            if name.islower() or name.isupper():
                name = name.title()
            slots["client_name"] = name

    # 6b. bare email
    if not slots.get("client_email") and raw and "@" in raw and " " not in raw:
        slots["client_email"] = raw.rstrip(".,;:!?").lower()

    # --- 7. validate property_id against DB
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
                "response_text": _MISSING_PROMPTS.get(missing[0], "Thodi aur detail chahiye booking ke liye."),
            }
        return {"booking_details": slots, "confirmation_needed": True}

    return await _guarded("booking_node", body)


# =====================================================================================
# g) confirm_booking_node — HITL via langgraph.types.interrupt().
# =====================================================================================
# IMPORTANT (verified against langgraph 1.2.12, no network - see docs/day5_graph_
# architecture.md "HITL re-execution semantics" section for the actual test that
# proved this): on every resume, LangGraph RE-RUNS this node function from the top.
# Previously-resolved interrupt() calls return their cached resume value instantly;
# only the next *unresolved* interrupt() call actually pauses. This means everything
# in this function must be safe to re-execute - in particular, SiteVisitBooker.book()
# is only ever called AFTER every interrupt() in this function has resolved, so it
# runs exactly once no matter how many re-prompts happened above it.
_AFFIRM_RE = re.compile(r"\b(yes|haan|ji\s*haan|theek|confirm|ok(?:ay)?|bilkul)\b", re.I)
_NEGATE_RE = re.compile(r"\b(no|nahi|cancel|mat karo)\b", re.I)


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
                "summary": "Maazrat, samajh nahi aaya. Haan ya nahi mein jawab dein: " + summary,
                "booking_details": details,
            })
        if _NEGATE_RE.search(str(ans)):
            return {
                "confirmation_needed": False,
                "booking_details": None,
                "tool_result": None,
                "response_text": "Ji theek hai, booking cancel kar di. Kuch aur chahiye?",
            }
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
        return {"tool_result": result, "confirmation_needed": False, "booking_details": None}

    return await _guarded("confirm_booking_node", body)


# =====================================================================================
# h) response_render_node — renders whatever the previous node produced into UrduLish
# =====================================================================================
def _prepare_for_tts(text: str) -> str:
    """Day 3's lib/tts_urdu_lish.py::prepare_for_tts (respells prices/IDs for TTS) is
    referenced by lib/voice_pipeline.py but was never included in any handoff package
    this project was built from - so its exact behaviour beyond "exists, takes a str,
    returns a str" is unverified here. Imported defensively: used if present, plain
    text returned unchanged (with a logged warning) if not, so this node never crashes
    the graph over a missing Day 3 file."""
    try:
        from lib import tts_urdu_lish as ul

        return ul.prepare_for_tts(text)
    except Exception as e:
        logger.warning("response_render_node: tts_urdu_lish.prepare_for_tts unavailable (%s: %s); using raw text",
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
# i) error_node — dedicated terminal for a node that already failed upstream
# =====================================================================================
async def error_node(state: Dict[str, Any], deps: GraphDeps) -> Dict[str, Any]:
    async def body() -> Dict[str, Any]:
        logger.error("error_node handling error=%s", state.get("error"))
        return {
            "response_text": (
                "Sir, mujhe afsos hai, filhal system mein thodi dikkat aa rahi hai. "
                "Main aap ko hamare team member se callback karwata hoon."
            )
        }

    return await _guarded("error_node", body)


# =====================================================================================
# Offline self-test — real rag_lib + real data/realestate.db, no network, no LLM keys
# =====================================================================================
def _self_test_offline() -> None:
    import asyncio
    import os

    from lib.tool_registry import build_tool_registry

    for key in ("GROQ_API_KEY", "GEMINI_API_KEY"):
        os.environ.pop(key, None)

    async def main() -> None:
        # NOTE: this builds the TfidfIndex the same way lib.voice_pipeline.Day2Retriever
        # does internally (r.TfidfIndex(r.load_documents())), rather than importing
        # Day2Retriever itself, because voice_pipeline.py unconditionally imports Day 3's
        # lib/tts_urdu_lish.py at module level, and that file was never included in any
        # handoff package this project was built from - so it isn't importable in this
        # sandbox. On the user's real machine, where tts_urdu_lish.py exists, importing
        # Day2Retriever directly works fine and is what lib/graph_builder.py does.
        index_holder = {"index": r.TfidfIndex(r.load_documents())}
        registry = build_tool_registry(index_holder)
        deps = GraphDeps(tool_registry=registry)

        # classify_intent_node: rule-based paths (no LLM needed)
        r1 = await classify_intent_node({"user_input": "Assalam-o-Alaikum", "messages": []}, deps)
        assert r1["intent"] == "greet", r1
        r2 = await classify_intent_node({"user_input": "Lahore mein 3 bed flat chahiye DHA mein", "messages": []}, deps)
        assert r2["intent"] == "search", r2
        r3 = await classify_intent_node({"user_input": "LAH-0001 ki price kya hai?", "messages": []}, deps)
        assert r3["intent"] == "price", r3
        r4 = await classify_intent_node({"user_input": "Main site visit book karna chahta hoon", "messages": []}, deps)
        assert r4["intent"] == "book", r4
        r5 = await classify_intent_node({"user_input": "What's the weather like in Karachi today and tomorrow", "messages": []}, deps)
        assert r5["intent"] == "refuse", r5
        # ambiguous short fragment with no live LLM key -> falls through to template ("search")
        r6 = await classify_intent_node({"user_input": "aur?", "messages": []}, deps)
        assert r6["intent"] == "search", r6

        # greeting / refusal — pure templates
        g = await greeting_node({"user_input": "salam"}, deps)
        assert g["response_text"] == _GREETING_LINE
        f = await refusal_node({"user_input": "tell me a joke"}, deps)
        assert f["response_text"] == _REFUSAL_LINE

        # retrieval / price against the REAL db
        ret = await retrieval_node({"user_input": "3 bedroom houses in Lahore"}, deps)
        assert ret["retrieved_docs"], ret
        pr = await price_node({"user_input": "LAH-0001 ki price kya hai?"}, deps)
        assert pr["retrieved_docs"][0]["payload"]["kind"] in ("value", "not_found", "not_recorded"), pr

        # booking_node slot-filling: missing everything at first
        b1 = await booking_node({"user_input": "Main visit book karna chahta hoon", "property_ids": [], "booking_details": None}, deps)
        assert b1["confirmation_needed"] is False and "property" in b1["response_text"].lower() or "Property" in b1["response_text"]
        # then fill in a real property id
        b2 = await booking_node({"user_input": "LAH-0001", "property_ids": [], "booking_details": b1["booking_details"]}, deps)
        assert b2["booking_details"].get("property_id") == "LAH-0001", b2
        # then name + email + time in one message
        b3 = await booking_node({
            "user_input": "my name is Ali Raza, email ali@example.com, 2026-09-30 15:00",
            "property_ids": [], "booking_details": b2["booking_details"],
        }, deps)
        assert b3["confirmation_needed"] is True, b3
        assert b3["booking_details"]["client_email"] == "ali@example.com"

        # response_render_node fallback paths (tts_urdu_lish absent in this sandbox -> raw text kept)
        rr = await response_render_node({"response_text": "Test line", "error": None, "tool_result": None, "retrieved_docs": []}, deps)
        assert rr["response_text"] == "Test line", rr

        # error_node
        er = await error_node({"error": "boom"}, deps)
        assert "afsos" in er["response_text"]

    asyncio.run(main())
    print("lib/graph_nodes.py self-test: all assertions passed")


if __name__ == "__main__":
    _self_test_offline()
