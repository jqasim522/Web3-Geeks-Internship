"""
offline_crew_llm.py

Reproducibility shim for the CrewAI assignment, in the same spirit as
`offline_gemini_llm.py` from the LangGraph assignment. `build_llm()`
returns:

  - a real `crewai.LLM(model="gemini/gemini-3.5-flash")` if `GEMINI_API_KEY`
    is set, or
  - an `OfflineCrewLLM` -- a scripted `crewai.llms.base_llm.BaseLLM`
    subclass -- otherwise.

Unlike the LangGraph shim (which only stood in for `.invoke(prompt)`),
CrewAI's agent loop is a real multi-turn ReAct conversation: the LLM must
emit ``Thought / Action / Action Input`` to call a tool, read the
``Observation`` CrewAI appends, and eventually emit ``Thought / Final
Answer``. `OfflineCrewLLM.call()` implements that protocol for real, so
every agent still actually calls its tool, and the hierarchical manager
still actually delegates via CrewAI's own `Delegate work to coworker`
tool -- only the text generation is scripted. Set `GEMINI_API_KEY` and
re-run for live Gemini reasoning; no other code needs to change.
"""

import json
import os
import re
from typing import Any

from crewai.llms.base_llm import BaseLLM

# ---------------------------------------------------------------------------
# Role / task identification helpers
# ---------------------------------------------------------------------------

RESEARCHER_ROLE = "Senior Market Researcher"
WRITER_ROLE = "Content Strategist"
EDITOR_ROLE = "Fact-Checker & Editor"
MANAGER_ROLE = "Crew Manager"

ROLE_MARKERS = {
    RESEARCHER_ROLE: "researcher",
    WRITER_ROLE: "writer",
    EDITOR_ROLE: "editor",
    MANAGER_ROLE: "manager",
}

TASK_MARKERS = {
    "Research the top 3 CRM competitors": "research",
    "Using the research report above": "write",
    "Fact-check every pricing and feature claim": "edit",
}

COWORKER_FOR_TASK = {
    "research": RESEARCHER_ROLE,
    "write": WRITER_ROLE,
    "edit": EDITOR_ROLE,
}


def _identify_role(system_text: str) -> str | None:
    for marker, role in ROLE_MARKERS.items():
        if marker in system_text:
            return role
    return None


def _identify_task(user_text: str) -> str | None:
    for marker, task in TASK_MARKERS.items():
        if marker in user_text:
            return task
    return None


def _find_current_task_message(messages: list[dict[str, Any]]) -> str:
    """The message containing 'Current Task:' holds the task description,
    expected_output, and (if set) the injected context block."""
    for m in messages:
        if "Current Task:" in m.get("content", ""):
            return m["content"]
    return messages[-1].get("content", "") if messages else ""


def _extract_observation(messages: list[dict[str, Any]]) -> str:
    """Pull the text after the LAST 'Observation:' marker anywhere in the
    conversation (excluding the system message, whose fixed instructions
    template contains the literal string 'Observation:' as a format hint,
    not a real tool result)."""
    combined = "\n".join(
        m.get("content", "") for m in messages if m.get("role") != "system"
    )
    idx = combined.rfind("Observation:")
    if idx == -1:
        return combined.strip()
    return combined[idx + len("Observation:") :].strip()


def _has_real_observation(messages: list[dict[str, Any]]) -> bool:
    """True once a tool has actually returned a result.

    Checked across every non-system message rather than just the last one:
    CrewAI sometimes appends a trailing nudge message ("Analyze the tool
    result...") after the observation, which would otherwise hide it from a
    last-message-only check. The system message is excluded because its
    fixed ReAct instructions literally contain the string 'Observation:' as
    a format hint, not a real tool result.
    """
    return any(
        "Observation:" in m.get("content", "")
        for m in messages
        if m.get("role") != "system"
    )


def _extract_context_block(current_task_text: str) -> str:
    """Pull the injected upstream-task output, if this task has `context=[...]`."""
    marker = "This is the context you're working with:\n"
    idx = current_task_text.find(marker)
    if idx == -1:
        return ""
    rest = current_task_text[idx + len(marker) :]
    end_markers = ["\n\nBegin!", "\n\nThought:"]
    end = len(rest)
    for em in end_markers:
        pos = rest.find(em)
        if pos != -1:
            end = min(end, pos)
    return rest[:end].strip()


# ---------------------------------------------------------------------------
# Scripted content for the research task, in its two variants
# ---------------------------------------------------------------------------

_RESEARCH_UNSTRUCTURED = (
    "So I looked into HubSpot, Salesforce, and Zoho. HubSpot is pretty easy to "
    "get started with and has a free tier, pricing kicks in around $20/seat "
    "and it's got a big marketplace of integrations, good for smaller teams "
    "scaling up. Salesforce is the enterprise one, very customizable, pricier "
    "(roughly $25 up to $500/user/month depending on tier), lots of add-ons "
    "via AppExchange. Zoho is the budget option, around $14 to $52/user/month, "
    "bundled with the rest of the Zoho suite and has an AI assistant called "
    "Zia. Overall HubSpot = easy/all-in-one, Salesforce = enterprise/"
    "customizable, Zoho = cheap/good value."
)

_RESEARCH_STRUCTURED = (
    "Competitor Name: HubSpot\n"
    "Pricing: Starter CRM Suite from $20/seat/month; core CRM tier is free "
    "with limited features.\n"
    "Key Features:\n"
    "- All-in-one marketing, sales, and service hubs on one data model\n"
    "- Large ecosystem of native integrations and a public app marketplace\n"
    "- Strong free tier used as a lead-in funnel for paid seats\n"
    "Market Position: Easy-to-adopt, all-in-one platform for scaling SMBs "
    "that don't want to stitch together point tools.\n\n"
    "Competitor Name: Salesforce\n"
    "Pricing: Sales Cloud starts around $25/user/month (Starter) up to "
    "$500/user/month (Unlimited+); heavy customization is usually billed "
    "separately through implementation partners.\n"
    "Key Features:\n"
    "- Deep customization via Apex/Flow and a huge partner ecosystem\n"
    "- AppExchange marketplace with thousands of add-ons\n"
    "- Enterprise-grade permissioning, reporting, and forecasting\n"
    "Market Position: The enterprise standard -- the safe, highly "
    "configurable choice for large, complex sales orgs.\n\n"
    "Competitor Name: Zoho CRM\n"
    "Pricing: Plans from about $14/user/month (Standard) to $52/user/month "
    "(Ultimate), notably cheaper than HubSpot or Salesforce at comparable "
    "tiers.\n"
    "Key Features:\n"
    "- Bundled into the wider Zoho One suite of 40+ business apps\n"
    "- Built-in AI assistant (Zia) for lead scoring and forecasting\n"
    "- Generous customization for the price point\n"
    "Market Position: The value pick -- most of the features of the bigger "
    "platforms at a fraction of the per-seat cost."
)

_BLOG_POST_FROM_UNSTRUCTURED = (
    "Headline: Finding the Right CRM for Your Growing Team\n\n"
    "Introduction: Choosing a CRM means weighing ease of use against power "
    "and price, and the three big names -- HubSpot, Salesforce, and Zoho -- "
    "each pull in a different direction.\n\n"
    "HubSpot is the easy, all-in-one option, good for teams that want to get "
    "moving fast without a lot of setup.\n\n"
    "Salesforce is the powerful, enterprise-grade option for teams that need "
    "deep customization, though that power comes at a price.\n\n"
    "Zoho is the budget-friendly option if cost is the main driver.\n\n"
    "Call to action: Not sure which fits? Talk to our team for a tailored "
    "recommendation."
)

_BLOG_POST_FROM_STRUCTURED = (
    "Headline: HubSpot vs. Salesforce vs. Zoho: Picking the Right CRM in 2026\n\n"
    "Introduction: The right CRM depends less on brand recognition and more "
    "on your price point and how much customization you actually need -- "
    "here's how the three leading platforms compare on the numbers.\n\n"
    "HubSpot starts free and scales to about $20/seat/month, backed by a "
    "large integration marketplace, making it the pick for teams that want "
    "an all-in-one platform without a steep setup curve.\n\n"
    "Salesforce ranges from roughly $25 to $500/user/month and is the most "
    "configurable of the three via Apex/Flow and the AppExchange "
    "marketplace, which is why larger, more complex sales orgs treat it as "
    "the enterprise standard.\n\n"
    "Zoho CRM undercuts both on price, from about $14 to $52/user/month, "
    "bundling in the wider Zoho One suite and an AI assistant (Zia) for "
    "lead scoring, making it the strongest choice on a budget.\n\n"
    "Call to action: Compare your own team's size and budget against these "
    "numbers, then book a walkthrough to see which platform fits best."
)


def _has_flagged_superlative(text: str) -> bool:
    lowered = text.lower()
    return any(
        p in lowered
        for p in ["best-in-class", "the best", "guaranteed", "#1", "unbeatable"]
    )


# ---------------------------------------------------------------------------
# The offline stub itself
# ---------------------------------------------------------------------------


class OfflineCrewLLM(BaseLLM):
    """Deterministic, rule-based scripted 'LLM' used only when no
    GEMINI_API_KEY is available. Speaks CrewAI's real ReAct protocol so the
    agents, tools, task hand-offs, and hierarchical delegation all execute
    for real; only text generation is scripted.

    NOTE: deliberately does NOT define `supports_function_calling`, so
    CrewAI's `check_native_tool_support` sees no such attribute and falls
    back to the text-based ReAct loop (`_invoke_loop_react`) rather than
    attempting native/OpenAI-style function calling, which this stub does
    not implement.
    """

    def __init__(self, **data: Any) -> None:
        data.setdefault("model", "gemini-3.5-flash-lite")
        super().__init__(**data)

    def call(
        self,
        messages,
        tools=None,
        callbacks=None,
        available_functions=None,
        from_task=None,
        from_agent=None,
        response_model=None,
    ) -> str:
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        system_text = next(
            (m["content"] for m in messages if m.get("role") == "system"), ""
        )
        current_task_text = _find_current_task_message(messages)
        has_observation = _has_real_observation(messages)
        observation_text = _extract_observation(messages) if has_observation else ""

        role = _identify_role(system_text)
        task = _identify_task(current_task_text)

        response = self._dispatch(
            role=role,
            task=task,
            current_task_text=current_task_text,
            has_observation=has_observation,
            observation_text=observation_text,
        )

        # Rough, clearly-labeled offline token estimate (chars / 4) purely so
        # crew.usage_metrics has something non-zero to report in this mode.
        prompt_chars = sum(len(m.get("content", "")) for m in messages)
        self._track_token_usage_internal(
            {
                "prompt_tokens": max(1, prompt_chars // 4),
                "completion_tokens": max(1, len(response) // 4),
            }
        )
        return response

    # -- dispatch -----------------------------------------------------------

    def _dispatch(
        self,
        role: str | None,
        task: str | None,
        current_task_text: str,
        has_observation: bool,
        observation_text: str,
    ) -> str:
        if role == "manager":
            return self._manager_turn(task, current_task_text, has_observation, observation_text)
        if role == "researcher" and task == "research":
            return self._researcher_turn(current_task_text, has_observation, observation_text)
        if role == "writer" and task == "write":
            return self._writer_turn(current_task_text, has_observation, observation_text)
        if role == "editor" and task == "edit":
            return self._editor_turn(current_task_text, has_observation, observation_text)

        # Fallback: no script matched (shouldn't happen for this assignment's
        # fixed set of agents/tasks) -- answer plainly rather than crash.
        return "Thought: I have enough information.\nFinal Answer: (offline stub: no script matched this prompt)"

    # -- manager (hierarchical process) -------------------------------------

    def _manager_turn(
        self, task: str | None, current_task_text: str, has_observation: bool, observation_text: str
    ) -> str:
        if has_observation:
            return f"Thought: The coworker has completed the task.\nFinal Answer: {observation_text}"

        coworker = COWORKER_FOR_TASK.get(task, RESEARCHER_ROLE)
        context = _extract_context_block(current_task_text) or "No prior context."
        action_input = json.dumps(
            {
                "task": current_task_text.split("Current Task:")[-1]
                .split("\n\nThis is the expected criteria")[0]
                .strip(),
                "context": context,
                "coworker": coworker,
            }
        )
        return (
            f"Thought: This task belongs to the {coworker}. I will delegate it.\n"
            f"Action: Delegate work to coworker\n"
            f"Action Input: {action_input}"
        )

    # -- researcher -----------------------------------------------------------

    def _researcher_turn(
        self, current_task_text: str, has_observation: bool, observation_text: str
    ) -> str:
        if not has_observation:
            return (
                "Thought: I need the competitor data before I can report on it.\n"
                "Action: Competitor Intel Lookup\n"
                'Action Input: {"query": "all"}'
            )
        strict = "exactly these labels" in current_task_text
        content = _RESEARCH_STRUCTURED if strict else _RESEARCH_UNSTRUCTURED
        return f"Thought: I now have the competitor data.\nFinal Answer: {content}"

    # -- writer -----------------------------------------------------------

    def _writer_turn(
        self, current_task_text: str, has_observation: bool, observation_text: str
    ) -> str:
        if not has_observation:
            return (
                "Thought: I should check the brand voice guidelines before writing.\n"
                "Action: Read a file's content\n"
                'Action Input: {"file_path": "brand_voice_guidelines.md"}'
            )
        research_context = _extract_context_block(current_task_text)
        structured = "Competitor Name:" in research_context
        content = _BLOG_POST_FROM_STRUCTURED if structured else _BLOG_POST_FROM_UNSTRUCTURED
        return f"Thought: I have the guidelines and the research. Drafting now.\nFinal Answer: {content}"

    # -- editor -----------------------------------------------------------

    def _editor_turn(
        self, current_task_text: str, has_observation: bool, observation_text: str
    ) -> str:
        draft_context = _extract_context_block(current_task_text)
        if not has_observation:
            action_input = json.dumps({"text": draft_context})
            return (
                "Thought: I should run the readability and claim checker on the draft first.\n"
                "Action: Readability & Claim Check\n"
                f"Action Input: {action_input}"
            )
        # observation_text contains the tool's word count / flagged-phrase report.
        flagged_any = "Flagged unverifiable superlatives:" in observation_text
        notes = [
            "Fact-Check Notes:",
            "- Pricing and feature figures cross-checked against the research report; all consistent.",
        ]
        if flagged_any:
            flag_line = next(
                (l for l in observation_text.splitlines() if l.startswith("Flagged")), ""
            )
            notes.append(f"- Readability tool flagged phrasing to soften: {flag_line}")
        else:
            notes.append("- Readability tool found no unverifiable superlatives; no wording changes needed.")
        final_text = "\n".join(notes) + "\n\n" + draft_context
        return f"Thought: Fact-check and polish complete.\nFinal Answer: {final_text}"



def build_llm(model_name: str = "gemini-3.5-flash-lite"):
    """
    Returns a real crewai.LLM (Gemini via LiteLLM) if GEMINI_API_KEY is set
    in the environment, otherwise an OfflineCrewLLM implementing the same
    BaseLLM interface CrewAI agents expect.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        from crewai import LLM

        return LLM(model=f"gemini/{model_name}", api_key=api_key)

    return OfflineCrewLLM(model=f"{model_name} (offline stub)")