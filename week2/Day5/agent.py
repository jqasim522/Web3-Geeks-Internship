"""
agent.py — Content Research & Blog Draft Agent (LangGraph workflow)

Architecture
-----------
  research_node  →  draft_node  →  [INTERRUPT before publish_node]
                         ↓ (on LLM error)
                      error_node

Framework choice: LangGraph
  - Control-heavy, deterministic state machine (research → draft → human gate → publish)
  - Native interrupt/checkpoint support for HITL without polling
  - Conditional branching on error states
  - MemorySaver persists state between the two API calls per session
  - CrewAI would add role-routing overhead not needed for this linear pipeline

LLM: Gemini 3.5 Flash lite via langchain-google-genai
External tool: Wikipedia API (langchain-community)
Local DB: SQLite via tools.py
"""
import os
import logging
import time
from typing import Optional, List

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict

from tools import safe_wikipedia, db_log, db_save_content, init_db

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── LLM factory ───────────────────────────────────────────────────────────
def _llm() -> ChatGoogleGenerativeAI:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY environment variable is not set. "
            "Copy .env.example → .env and add your key."
        )
    return ChatGoogleGenerativeAI(
        model="gemini-3.5-flash-lite",
        google_api_key=api_key,
        temperature=0.3,
        max_tokens=2048,
    )


# ── State schema ──────────────────────────────────────────────────────────
class AgentState(TypedDict):
    query:            str
    thread_id:        str
    research:         str
    draft:            str
    # researching | drafting | awaiting_approval | approved | rejected | error
    status:           str
    error:            Optional[str]
    tokens_used:      int
    tools_called:     List[str]
    approved:         Optional[bool]   # set by human via /agent/approve
    rejection_reason: Optional[str]


# ── Node: research ────────────────────────────────────────────────────────
def research_node(state: AgentState) -> dict:
    """
    Fetch Wikipedia summary for the query.
    Falls back gracefully when Wikipedia is unavailable.
    Logs tool call name, args, and result length.
    """
    logger.info(f"[research] thread={state['thread_id']} | query={state['query'][:60]!r}")
    db_log(state["thread_id"], "research_start", state["query"][:120])

    research_text = safe_wikipedia(state["query"])

    if research_text.startswith("__TOOL_ERROR__"):
        logger.warning("[research] Wikipedia unavailable — using LLM knowledge fallback")
        research_text = (
            f"[Wikipedia unavailable. Responding from model knowledge for topic: {state['query']}]"
        )

    db_log(state["thread_id"], "research_done", f"chars={len(research_text)}")
    logger.info(f"[research] Done | {len(research_text)} chars")

    return {
        "research":     research_text,
        "status":       "drafting",
        "tools_called": state.get("tools_called", []) + ["wikipedia"],
    }


# ── Node: draft ───────────────────────────────────────────────────────────
def draft_node(state: AgentState) -> dict:
    """
    Generate a structured blog post from research using Gemini 3.5 Flash lite.
    Handles model refusal and general LLM errors gracefully.
    Logs token usage and latency.
    """
    logger.info(f"[draft] thread={state['thread_id']}")
    db_log(state["thread_id"], "draft_start")
    t0 = time.time()

    system_prompt = (
        "You are a professional content writer producing factual blog posts. "
        "Structure: ## Title, one-paragraph introduction, three sections with ### headers, "
        "and a Conclusion section. Stay under 600 words. "
        "Ground every claim in the provided research — never invent statistics. "
        "If the research is insufficient, say so clearly rather than fabricating details."
    )
    user_prompt = (
        f"Topic: {state['query']}\n\n"
        f"Research material:\n{state['research'][:2500]}\n\n"
        "Write the complete blog post now."
    )

    try:
        llm = _llm()
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])
        draft = response.content

        # Extract token usage (Gemini returns usage_metadata)
        usage = getattr(response, "usage_metadata", None) or {}
        total_tokens = usage.get("total_tokens", 0)
        elapsed_ms = int((time.time() - t0) * 1000)

        logger.info(
            f"[draft] Done | {len(draft)} chars | {total_tokens} tokens | {elapsed_ms}ms"
        )
        db_log(
            state["thread_id"], "draft_done",
            f"chars={len(draft)} tokens={total_tokens} ms={elapsed_ms}",
        )

        return {
            "draft":       draft,
            "status":      "awaiting_approval",
            "tokens_used": state.get("tokens_used", 0) + total_tokens,
        }

    except Exception as exc:
        # Covers both model refusals and network errors
        logger.error(f"[draft] LLM error: {exc}")
        db_log(state["thread_id"], "draft_error", str(exc))
        return {"status": "error", "error": str(exc)}


# ── Node: publish ─────────────────────────────────────────────────────────
def publish_node(state: AgentState) -> dict:
    """
    HITL gate: save to SQLite if approved, log rejection otherwise.
    This is the consequential action that requires human sign-off.
    """
    if state.get("approved") is True:
        db_save_content(state["thread_id"], state["query"], state["draft"])
        db_log(state["thread_id"], "published")
        logger.info(f"[publish] Content published | thread={state['thread_id']}")
        return {"status": "approved"}
    else:
        reason = state.get("rejection_reason", "no reason given")
        db_log(state["thread_id"], "rejected", reason)
        logger.info(f"[publish] Rejected | thread={state['thread_id']} | reason={reason}")
        return {"status": "rejected"}


# ── Node: error ───────────────────────────────────────────────────────────
def error_node(state: AgentState) -> dict:
    """Terminal node for unrecoverable errors — logs and passes state through."""
    logger.error(f"[error] thread={state['thread_id']} | {state.get('error')}")
    db_log(state["thread_id"], "terminal_error", state.get("error", ""))
    return {}   # no state changes; graph ends


# ── Routing ───────────────────────────────────────────────────────────────
def _after_draft(state: AgentState) -> str:
    return "error" if state["status"] == "error" else "publish"


# ── Build graph ───────────────────────────────────────────────────────────
_memory = MemorySaver()


def _after_draft(state: AgentState) -> str:
    # ✅ Return NODE names, not state keys
    return "error_node" if state["status"] == "error" else "publish_node"


def build_graph() -> StateGraph:
    init_db()

    builder = StateGraph(AgentState)

    # ✅ Node names — "research", "draft", "publish", "error" ke saath "_node" suffix
    builder.add_node("research_node", research_node)
    builder.add_node("draft_node",    draft_node)
    builder.add_node("publish_node",  publish_node)
    builder.add_node("error_node",    error_node)

    builder.set_entry_point("research_node")
    builder.add_edge("research_node", "draft_node")

    # ✅ Conditional routing — mapping keys bhi node names se match karein
    builder.add_conditional_edges(
        "draft_node",
        _after_draft,
        {"publish_node": "publish_node", "error_node": "error_node"},
    )

    builder.add_edge("publish_node", END)
    builder.add_edge("error_node",   END)

    # ✅ interrupt_before ab "publish_node" ko point karta hai
    return builder.compile(
        checkpointer=_memory,
        interrupt_before=["publish_node"],
    )


graph = build_graph()
