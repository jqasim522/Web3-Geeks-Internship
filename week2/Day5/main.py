"""
main.py — FastAPI wrapper for the Content Research & Blog Draft Agent

Endpoints
---------
POST /agent          → run research + draft; pauses for human approval
POST /agent/approve  → resume graph; publish or reject the draft
GET  /health         → liveness probe

Run locally:
    uvicorn main:app --reload --port 8000
"""
import time
import uuid
import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator

from agent import graph, AgentState
from validation import validate_input

# ── Logging ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("api")

# ── App ───────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Content Research & Blog Draft Agent",
    version="1.0.0",
    description="LangGraph + Gemini 3.5 Flash lite agent that researches topics and drafts blog posts, "
                "with a human-in-the-loop approval step before publishing.",
)


# ── Schemas ───────────────────────────────────────────────────────────────
class AgentRequest(BaseModel):
    query:     str
    thread_id: str = ""

    @field_validator("query")
    @classmethod
    def query_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("query cannot be empty")
        return v


class ApprovalRequest(BaseModel):
    thread_id:        str
    approved:         bool
    rejection_reason: str = ""


class AgentResponse(BaseModel):
    status:           str
    output:           str
    tokens_used:      int
    latency_ms:       int
    tools_called:     list
    thread_id:        str
    requires_approval: bool = False


# ── POST /agent ───────────────────────────────────────────────────────────
@app.post("/agent", response_model=AgentResponse)
def run_agent(req: AgentRequest):
    """
    Step 1 of 2.
    Runs research → draft, then pauses for human approval.
    Returns the draft and requires_approval=True if successful.
    """
    t0 = time.time()
    thread_id = req.thread_id.strip() or str(uuid.uuid4())

    # ── Log input ──────────────────────────────────────────────────────
    logger.info(f"[/agent] RECV | thread={thread_id} | query={req.query[:80]!r}")

    # ── Validate ───────────────────────────────────────────────────────
    try:
        query = validate_input(req.query)
    except ValueError as exc:
        logger.warning(f"[/agent] Validation failed | {exc}")
        raise HTTPException(status_code=422, detail=str(exc))

    # ── Build initial state ────────────────────────────────────────────
    config: dict = {"configurable": {"thread_id": thread_id}}
    init_state: AgentState = {
        "query":            query,
        "thread_id":        thread_id,
        "research":         "",
        "draft":            "",
        "status":           "researching",
        "error":            None,
        "tokens_used":      0,
        "tools_called":     [],
        "approved":         None,
        "rejection_reason": None,
    }

    # ── Invoke graph (pauses at interrupt_before=["publish"]) ──────────
    try:
        result = graph.invoke(init_state, config=config)
    except Exception as exc:
        logger.error(f"[/agent] Graph error: {exc}")
        raise HTTPException(status_code=500, detail=f"Agent error: {exc}")

    lat = int((time.time() - t0) * 1000)
    status  = result.get("status", "unknown")
    output  = result.get("draft") or result.get("error") or ""
    tokens  = result.get("tokens_used", 0)
    tools   = result.get("tools_called", [])

    logger.info(
        f"[/agent] DONE | thread={thread_id} | status={status} | "
        f"lat={lat}ms | tokens={tokens} | tools={tools}"
    )

    if status == "error":
        raise HTTPException(status_code=500, detail=output)

    return AgentResponse(
        status=status, output=output, tokens_used=tokens,
        latency_ms=lat, tools_called=tools, thread_id=thread_id,
        requires_approval=(status == "awaiting_approval"),
    )


# ── POST /agent/approve ───────────────────────────────────────────────────
@app.post("/agent/approve", response_model=AgentResponse)
def approve_draft(req: ApprovalRequest):
    """
    Step 2 of 2 — HITL checkpoint.
    Inject the human decision, resume the graph, and publish (or reject) the draft.

    This is the consequential action gated by human oversight:
    the draft is only saved to the database when approved=True.
    """
    t0 = time.time()
    action = "APPROVE" if req.approved else "REJECT"
    logger.info(f"[/agent/approve] {action} | thread={req.thread_id} | reason={req.rejection_reason!r}")

    config: dict = {"configurable": {"thread_id": req.thread_id}}

    try:
        # Inject the human decision into the checkpoint
        graph.update_state(
            config,
            {"approved": req.approved, "rejection_reason": req.rejection_reason},
        )
        # Resume from where the graph was interrupted (before publish_node)
        result = graph.invoke(None, config=config)
    except Exception as exc:
        logger.error(f"[/agent/approve] Error: {exc}")
        raise HTTPException(status_code=500, detail=f"Approval error: {exc}")

    lat = int((time.time() - t0) * 1000)
    status = result.get("status", action.lower() + "d")
    tokens = result.get("tokens_used", 0)
    tools  = result.get("tools_called", [])

    logger.info(f"[/agent/approve] DONE | thread={req.thread_id} | status={status} | lat={lat}ms")

    return AgentResponse(
        status=status, output=result.get("draft", ""),
        tokens_used=tokens, latency_ms=lat,
        tools_called=tools, thread_id=req.thread_id,
        requires_approval=False,
    )


# ── GET /health ───────────────────────────────────────────────────────────
@app.get("/health")
def health():
    """Liveness probe."""
    return {"status": "ok", "version": "1.0.0"}
