"""
lib/tool_registry.py — Day 5, Task 4

# STATUS: CODE-COMPLETE | TESTED-OFFLINE (registry construction, extract_tool_call,
#   and invoke_tool's error-wrapping path are exercised in _self_test() below with
#   no network. Live tool execution — real query_properties against a real DB
#   connection, real SiteVisitBooker.book() — is UNTESTED-LIVE, same as Day 4.)
# RUN ON USER MACHINE: python -m lib.tool_registry
# EXPECTED OUTPUT: "lib/tool_registry.py self-test: all assertions passed"

Maps tool names to async-callable wrappers so graph_nodes.py and
conversation_runner.py can invoke a tool by name (e.g. from an LLM's JSON tool
call) without importing rag_lib/site_visit_booking directly everywhere.

rag_lib.query_properties / rag_lib.get_property are synchronous (plain sqlite3
calls) - wrapped here with asyncio.to_thread so every entry in TOOLS is
awaitable, matching SiteVisitBooker.book (already async). There is no
rag_lib.hybrid_search function (the Day 5 prompt names one, but it does not
exist in the Day 2 rag_lib.py this project was actually given — the closest
equivalent is rag_lib.answer_question, which internally routes to
sql/vector/hybrid retrieval via route_retrieval()). Registered under BOTH
"answer_question" (its real name) and "hybrid_search" (an alias, so code
written against the Day 5 prompt's expected name still resolves) to avoid
silently doing nothing for a name that was never real.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Callable, Dict, Optional

from lib import booking_tool as bt
from lib import rag_lib as r
from lib.site_visit_booking import SiteVisitBooker

logger = logging.getLogger("day5.tool_registry")

_TOOL_CALL_RE = re.compile(r"\{.*\"tool\"\s*:\s*\".+?\".*\}", re.DOTALL)


def _make_answer_question(index_holder: Dict[str, Any]) -> Callable[..., Any]:
    """answer_question needs a TfidfIndex, which is expensive to build - callers
    pass a mutable `index_holder` dict (e.g. {"index": Day2Retriever(...).index})
    built once at startup, not per-call."""

    async def _call(question: str, force_route: Optional[str] = None) -> Dict[str, Any]:
        index = index_holder.get("index")
        if index is None:
            raise RuntimeError("tool_registry: index_holder['index'] not set - "
                                "build a Day2Retriever/TfidfIndex at startup first")
        return await asyncio.to_thread(r.answer_question, question, index, None, 5, force_route)

    return _call


async def _get_property(property_id: str) -> Optional[Dict[str, Any]]:
    return await asyncio.to_thread(r.get_property, property_id)


async def _query_properties(**kwargs: Any) -> Any:
    return await asyncio.to_thread(r.query_properties, **kwargs)


def build_tool_registry(index_holder: Dict[str, Any], booker: Optional[SiteVisitBooker] = None) -> Dict[str, Callable[..., Any]]:
    """Returns {tool_name: async_callable}. `index_holder` is a mutable dict the
    caller fills with {"index": <TfidfIndex>} once retrieval is ready (see
    lib/graph_builder.py) - passed by reference so the registry always sees the
    current index even if it's built slightly after this function runs."""
    booker = booker or SiteVisitBooker()
    answer_question_call = _make_answer_question(index_holder)
    return {
        "search_properties": _query_properties,          # rag_lib.query_properties, sync SQL filters
        "get_property": _get_property,                    # rag_lib.get_property, single-ID lookup
        "answer_question": answer_question_call,           # rag_lib.answer_question (real name)
        "hybrid_search": answer_question_call,              # alias: the Day 5 prompt's name for the same thing
        "book_site_visit": booker.book,                     # lib.site_visit_booking.SiteVisitBooker.book
    }


def extract_tool_call(text: str) -> Optional[Dict[str, Any]]:
    """Parses an LLM message's content string for a {"tool": ..., "args": {...}}
    JSON object, generically (any tool name) - unlike booking_tool.extract_tool_call,
    which only recognizes book_site_visit specifically. Returns None if no such
    JSON object is present (ordinary free-text reply). Raises json.JSONDecodeError
    if something that looks like a tool call is malformed - callers should treat
    that the same as "no valid tool call", never as success."""
    if '"tool"' not in text:
        return None
    m = _TOOL_CALL_RE.search(text)
    if not m:
        return None
    obj = json.loads(m.group(0))  # let JSONDecodeError propagate - caller decides fallback behaviour
    if "tool" not in obj:
        return None
    return obj


async def invoke_tool(name: str, args: Dict[str, Any], registry: Dict[str, Callable[..., Any]]) -> Dict[str, Any]:
    """Calls registry[name](**args) and wraps the outcome uniformly:
    {"ok": True, "result": ...} or {"ok": False, "error": "<type>: <message>"}.
    Never raises - every failure (unknown tool name, bad args, the tool itself
    raising) becomes an {"ok": False, ...} dict so graph nodes can always set
    state["error"] cleanly instead of crashing the graph."""
    fn = registry.get(name)
    if fn is None:
        return {"ok": False, "error": f"unknown tool: {name!r} (known: {sorted(registry.keys())})"}
    try:
        result = await fn(**args)
        return {"ok": True, "result": result}
    except TypeError as e:
        return {"ok": False, "error": f"bad_args for {name!r}: {e}"}
    except Exception as e:
        logger.exception("tool_registry.invoke_tool: %s raised", name)
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _self_test() -> None:
    """Offline only - proves extract_tool_call/invoke_tool logic without touching
    the real DB or Google APIs."""
    import asyncio as _asyncio

    good = '{"tool": "get_property", "args": {"property_id": "LAH-0001"}}'
    call = extract_tool_call(good)
    assert call == {"tool": "get_property", "args": {"property_id": "LAH-0001"}}, call

    assert extract_tool_call("Ji bilkul sir, DHA Phase 6 available hai.") is None

    async def _boom(**kwargs):
        raise ValueError("simulated failure")

    registry = {"boom": _boom}
    r1 = _asyncio.run(invoke_tool("boom", {}, registry))
    assert r1 == {"ok": False, "error": "ValueError: simulated failure"}, r1

    r2 = _asyncio.run(invoke_tool("does_not_exist", {}, registry))
    assert r2["ok"] is False and "unknown tool" in r2["error"], r2

    print("lib/tool_registry.py self-test: all assertions passed")


if __name__ == "__main__":
    _self_test()
