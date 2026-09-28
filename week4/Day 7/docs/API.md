# API Documentation

STATUS: CODE-COMPLETE — documents the *intended* interface based on the
Day 1-6 file dependencies (`lib/graph_builder.py`, `graph_nodes.py`,
`conversation_runner.py`). No FastAPI wrapper or HTTP layer was present in
the environment that wrote this document, so the endpoint section below is
a specification to implement against, not a confirmed existing API.
Section 2 (internal Python API) reflects the actual function signatures
implied by the Day 5-6 test files and is more trustworthy than section 1.

## 1. HTTP endpoints (ASSUMPTION FLAGGED — spec, not confirmed)

If `lib/server.py` (or similarly named) wraps the LangGraph agent in
FastAPI, these are the endpoints that spec implies. If no such wrapper
exists yet, this is what Day 7+ should build to make the deploy stack in
this handover (`deploy/Dockerfile`'s `uvicorn lib.server:app`) meaningful.

### `POST /chat`

Send one user turn to the agent.

**Request:**
```json
{
  "message": "Lahore mein 3 bed chahiye",
  "thread_id": "user-session-abc123"
}
```

- `message` (string, required) — the user's utterance, Roman Urdu / Urdu
  script / English.
- `thread_id` (string, required) — a stable ID for this conversation,
  matching the `thread_id` used by LangGraph's checkpointing
  (`{"configurable": {"thread_id": ...}}`, per the Day 5/6 test suite).
  The caller (voice pipeline or a chat UI) is responsible for generating
  and persisting this per user session.

**Response (normal turn):**
```json
{
  "response_text": "Ji, Lahore mein 3 bedroom ke 37 listings hain...",
  "intent": "search",
  "interrupt": false
}
```

**Response (mid-booking, awaiting confirmation):**
```json
{
  "response_text": null,
  "interrupt": true,
  "interrupt_prompt": "Confirm karein: LAH-0001, 2026-09-30 15:00?"
}
```
Matches the `"__interrupt__" in result` / `Command(resume=...)` pattern
used throughout the Day 6 test suite.

**Errors:**

| Status | Meaning |
|---|---|
| `400` | Malformed request (missing `message` or `thread_id`) |
| `422` | `message` failed validation (e.g. empty string) |
| `500` | Unhandled server error — see `docs/TROUBLESHOOTING.md` |
| `503` | Dependencies not ready — see `docs/healthcheck.md`'s `/ready` |

### `GET /health`, `GET /ready`

See `docs/healthcheck.md` for full detail.

### Auth

ASSUMPTION FLAGGED: no authentication scheme was evidenced anywhere in the
attached Day 1-6 material. This spec assumes none exists yet. Before
exposing `/chat` on the public internet (per `deploy/nginx.conf`), add at
minimum an API key header (`X-API-Key`) checked against a value in
`deploy/.env`, since the current `nginx.conf` only rate-limits, it does not
authenticate.

### Rate limits

Enforced at the `deploy/nginx.conf` layer, not the application: 10
requests/second per client IP, burst 20 (see that file). The application
itself has no additional rate limiting confirmed.

## 2. Internal Python API (higher confidence — matches the Day 5/6 test suite)

These are the actual call patterns the Day 6 tests exercise directly
against `lib/`, so they're a more reliable description of the real
interface than section 1 above.

### `graph_builder.build_graph(deps) -> CompiledGraph`

```python
from graph_builder import build_default_deps, build_graph

deps = build_default_deps()          # wires real Calendar/Gmail/LLM
graph = build_graph(deps=deps)
```

### `graph.ainvoke(state, config) -> dict`

```python
from graph_state import initial_state

cfg = {"configurable": {"thread_id": "some-thread-id"}}
result = await graph.ainvoke(initial_state("3 bedroom house in Lahore"), config=cfg)
# result["response_text"], result["intent"], result.get("error")
```

### Resuming after a booking-confirmation interrupt

```python
from langgraph.types import Command

if "__interrupt__" in result:
    confirmed = await graph.ainvoke(Command(resume="ji haan"), config=cfg)
```

### `booking_tool.validate_args(args: dict) -> dict`

Raises `ToolCallError` on invalid booking arguments (missing field, bad
property ID format, malformed date). See
`tests/unit/test_booking_tool.py` and `tests/fuzz/test_fuzz_booking_args.py`
in the Day 6 suite for the exact validation rules exercised.

### `llm_fallback.FallbackLLM.invoke(prompt, system="", template_key="default") -> str`

Tries Groq, then Gemini, then a fixed template response, in that order.
`f.last_tier_used` reports which tier actually answered (`"groq"`,
`"gemini"`, or `"template"`).

### Error codes (internal)

| Error | Raised by | Meaning |
|---|---|---|
| `ToolCallError` | `booking_tool.validate_args` | Booking arguments failed validation |
| `RateLimitError` | `llm_fallback` | An LLM tier returned a 429/quota-exhausted response (caught internally — the fallback chain should absorb this, it should not surface to the caller) |

### Rate limits (internal)

`llm_fallback._MinIntervalLimiter` enforces a minimum interval between
calls to a given LLM tier client-side, independent of the provider's own
rate limits — see `tests/ratelimit/` in the Day 6 suite for the exact
backoff behavior tested.
