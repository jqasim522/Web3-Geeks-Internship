"""
offline_afl_llm.py

Reproducibility shim for the Day 3 AFL chat-agent assignment, in the same spirit as
`offline_gemini_llm.py` (Day 3 LangGraph) and `offline_crew_llm.py` (Day 4 CrewAI):
`build_llm()` returns a real `ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")`
if `GEMINI_API_KEY` is set, and otherwise falls back to `OfflineAFLChatModel` -- a
scripted `langchain_core.language_models.chat_models.BaseChatModel` subclass.

Unlike the earlier `.invoke(prompt)`-style stubs, LangChain's tool-calling agent
loop is a real multi-turn protocol: the LLM must either return an `AIMessage` with
`tool_calls` (to invoke a registered `@tool`) or a plain `AIMessage` with no tool
calls (a final answer). `OfflineAFLChatModel._generate()` implements that protocol
for real -- `AgentExecutor`, tool dispatch, `ConversationBufferMemory`, and the
scope/grounding logic in the notebook all execute for real. Only the "reasoning"
(scope classification, entity extraction, tool selection, final-answer wording) is
rule-based pattern matching instead of a neural model -- and it is *intentionally*
conservative: it never states a number that didn't come from a ToolMessage. Set
`GEMINI_API_KEY` and re-run for live Gemini reasoning; no other code needs to change.
"""

import os
import re
from typing import Any, List, Optional, Sequence

import pandas as pd
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable

# ---------------------------------------------------------------------------
# Static knowledge the scope classifier and entity extractor need
# ---------------------------------------------------------------------------

TEAMS = [
    "Adelaide", "Brisbane Lions", "Carlton", "Collingwood", "Essendon", "Fremantle",
    "Geelong", "Gold Coast", "Greater Western Sydney", "Hawthorn", "Melbourne",
    "North Melbourne", "Port Adelaide", "Richmond", "St Kilda", "Sydney",
    "West Coast", "Western Bulldogs",
]
# longest names first so "Greater Western Sydney" matches before a shorter false-positive would
_TEAMS_BY_LEN = sorted(TEAMS, key=len, reverse=True)

OTHER_SPORT_KEYWORDS = [
    "nba", "nrl", "soccer", "fifa", "premier league", "world cup", "cricket", "ashes",
    "basketball", "tennis", "wimbledon", "rugby league", "rugby union", "golf", "pga",
    "boxing", "ufc", "mma", "formula 1", "f1 ", "nfl", "super bowl", "baseball", "mlb",
    "hockey", "nhl", "olympics",
]
NON_AFL_TRIVIA_KEYWORDS = [
    "prime minister", "president", "election", "weather", "recipe", "capital of",
    "movie", "actor", "actress", "song", "album", "stock price", "who are you",
    "what model are you", "joke", "poem",
]
INJECTION_PATTERNS = [
    r"\bpretend you'?re not\b", r"\bignore (your|previous|all) instructions\b",
    r"\bforget your rules\b", r"\bact as\b(?!.{0,20}afl)", r"\byou are now\b",
    r"\bdisregard\b.*\binstructions\b",
]
EDGE_KEYWORDS = ["best sport", "favourite team", "favorite team", "which sport is better", "is afl better than"]

AFL_HINT_KEYWORDS = [
    "afl", "footy", "football", "premiership", "grand final", "disposals", "goals",
    "guernsey", "brownlow", "ladder", "round", "match", "game", "team", "player",
]

STAT_COLS = {"disposals": "Disposals", "goals": "Goals", "marks": "Marks",
             "tackles": "Tackles", "fantasy_points": "fantasy_points"}

CANNED_RULES_ANSWERS = {
    r"how many players.*(field|team)": (
        "Each AFL team has 18 players on the field at once, plus 4 interchange players on the bench."
    ),
    r"what is a behind|what'?s a behind": (
        "A behind is worth 1 point, scored when the ball passes between one of the outer goalposts, "
        "or is touched before crossing the goal line between the main posts (worth 6 points)."
    ),
    r"when was the afl (founded|formed)|history of the afl": (
        "The competition was founded as the VFL (Victorian Football League) in 1897 and was renamed "
        "the AFL (Australian Football League) in 1990."
    ),
}


# ---------------------------------------------------------------------------
# Scope classification
# ---------------------------------------------------------------------------

def classify_scope(text: str) -> str:
    """Returns one of: 'refuse_other_sport', 'refuse_trivia', 'refuse_injection',
    'refuse_edge', 'in_scope'. Order matters: injection/other-sport/trivia checks
    run before the AFL-hint check, so a message can't smuggle an off-topic
    question past the guardrail just by also mentioning an AFL team."""
    lowered = text.lower()

    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, lowered):
            return "refuse_injection"
    for kw in OTHER_SPORT_KEYWORDS:
        if kw in lowered:
            return "refuse_other_sport"
    for kw in EDGE_KEYWORDS:
        if kw in lowered:
            return "refuse_edge"
    for kw in NON_AFL_TRIVIA_KEYWORDS:
        if kw in lowered:
            return "refuse_trivia"
    return "in_scope"


REFUSAL_TEMPLATES = {
    "refuse_other_sport": (
        "I'm focused on AFL, so I can't help with that -- but if you want to compare "
        "two teams' records or check a player's stats, I'm your bot!"
    ),
    "refuse_trivia": (
        "I'd rather stick to footy -- got a team or player you're curious about?"
    ),
    "refuse_injection": (
        "That's outside my lane. But here's something in-scope: want to know the top "
        "disposal-getters from a recent round?"
    ),
    "refuse_edge": (
        "I don't do rankings outside AFL, but I can tell you plenty about how AFL teams "
        "stack up against each other -- want a head-to-head record?"
    ),
}


# ---------------------------------------------------------------------------
# Entity extraction (teams, season, round, player, stat)
# ---------------------------------------------------------------------------

def extract_teams(text: str) -> List[str]:
    """Returns teams mentioned in `text`, ordered by where they first appear
    (not by name length) -- so "Collingwood won vs Western Bulldogs" resolves
    to Collingwood first, matching which team the sentence is actually about."""
    lowered = text.lower()
    positions = []
    seen = set()
    for team in _TEAMS_BY_LEN:  # longest-first avoids partial-name false matches
        idx = lowered.find(team.lower())
        if idx != -1 and team not in seen:
            seen.add(team)
            positions.append((idx, team))
    positions.sort(key=lambda x: x[0])
    return [team for _, team in positions]


def extract_season(text: str) -> Optional[int]:
    m = re.search(r"\b(20\d{2})\b", text)
    return int(m.group(1)) if m else None


def extract_round(text: str) -> Optional[str]:
    m = re.search(r"\bround\s+(\d+)\b", text, re.IGNORECASE) or re.search(r"\bR(\d+)\b", text)
    if m:
        return f"R{m.group(1)}"
    return None


def extract_player(text: str, known_players: Sequence[str]) -> Optional[str]:
    lowered = text.lower()
    for player in known_players:
        last, first = [p.strip() for p in player.split(",", 1)] if "," in player else (player, "")
        if first and f"{first.lower()} {last.lower()}" in lowered:
            return player
        if last.lower() in lowered and len(last) > 3:  # avoid tiny-surname false positives
            return player
    return None


def extract_stat(text: str) -> str:
    lowered = text.lower()
    if "goal" in lowered:
        return "goals"
    if "tackle" in lowered:
        return "tackles"
    if "mark" in lowered:
        return "marks"
    if "fantasy" in lowered:
        return "fantasy_points"
    return "disposals"  # default, matches the assignment's example questions


# ---------------------------------------------------------------------------
# Conversational memory resolution: scan prior turns' text for the most
# recently mentioned team / season / round / player, for follow-up questions
# like "What about the round before that?" or "How does that compare?"
# ---------------------------------------------------------------------------

def resolve_context(current_text: str, history_texts: List[str], known_players: Sequence[str]) -> dict:
    ctx = {
        "teams": extract_teams(current_text),
        "season": extract_season(current_text),
        "round": extract_round(current_text),
        "player": extract_player(current_text, known_players),
    }
    lowered = current_text.lower()
    needs_prior_team = not ctx["teams"] and any(w in lowered for w in ["they", "their", "them"])
    # "round before that" / "previous round" mean decrement the last-mentioned round;
    # "that game" alone just means reuse the last-mentioned round unchanged.
    needs_round_decrement = ("round before that" in lowered or "previous round" in lowered)
    needs_prior_round = needs_round_decrement or "that game" in lowered
    needs_prior_player = ctx["player"] is None and any(w in lowered for w in ["his ", "he ", "that player"])

    round_from_history = None
    for past in reversed(history_texts):
        if not ctx["teams"]:
            t = extract_teams(past)
            if t:
                ctx["teams"] = t
        if ctx["season"] is None:
            s = extract_season(past)
            if s:
                ctx["season"] = s
        if needs_prior_player and ctx["player"] is None:
            p = extract_player(past, known_players)
            if p:
                ctx["player"] = p
        if round_from_history is None:
            r = extract_round(past)
            if r:
                round_from_history = r
        if ctx["teams"] and ctx["season"] and round_from_history and (ctx["player"] or not needs_prior_player):
            break

    if needs_round_decrement and round_from_history:
        # "the round before that" / "previous round" -- decrement the last-mentioned round
        n = int(round_from_history[1:])
        ctx["round"] = f"R{max(n - 1, 1)}"
    elif ctx["round"] is None:
        ctx["round"] = round_from_history

    return ctx


# ---------------------------------------------------------------------------
# The offline stub itself
# ---------------------------------------------------------------------------

class OfflineAFLChatModel(BaseChatModel):
    """Deterministic, rule-based scripted chat model used only when no
    GEMINI_API_KEY is available. Speaks LangChain's real tool-calling protocol
    (AIMessage.tool_calls -> ToolMessage -> final AIMessage), so AgentExecutor,
    tool dispatch, and ConversationBufferMemory all execute for real.

    Grounding guarantee: the final-answer branch (`_final_answer`) only ever
    echoes/lightly rewords the most recent ToolMessage's content -- it never
    injects a number that didn't come from a tool result. This is deliberately
    stricter than a real LLM, which can hallucinate; it's the offline stand-in
    for the notebook's separate grounding-check code, not a replacement for it.
    """

    player_features_path: str = "data/player_features.parquet"

    @property
    def _llm_type(self) -> str:
        return "offline-afl-chat-model"

    def bind_tools(self, tools: Sequence, **kwargs: Any) -> Runnable:
        return self.bind(tools=tools)

    def _known_players(self) -> List[str]:
        if not hasattr(self, "_players_cache"):
            df = pd.read_parquet(self.player_features_path)
            object.__setattr__(self, "_players_cache", sorted(df["Player"].unique()))
        return self._players_cache

    # -- main entry point -----------------------------------------------------

    def _generate(self, messages: List[BaseMessage], stop=None, run_manager=None, **kwargs: Any) -> ChatResult:
        tools = kwargs.get("tools", [])
        tools_by_name = {t.name: t for t in tools}

        if messages and isinstance(messages[-1], ToolMessage):
            ai_msg = self._final_answer(messages)
        else:
            current_human = next(m for m in reversed(messages) if isinstance(m, HumanMessage))
            # History includes both prior HumanMessages (what the user asked) and prior
            # AIMessages (the bot's final answers) -- entities like "which player led
            # disposals" are often only stated in the bot's own previous answer, not
            # repeated in the user's follow-up question.
            history_texts = [
                m.content for m in messages
                if isinstance(m, (HumanMessage, AIMessage)) and m is not current_human and m.content
            ]
            ai_msg = self._first_turn(current_human.content, history_texts, tools_by_name)

        return ChatResult(generations=[ChatGeneration(message=ai_msg)])

    # -- turn 1: scope check + tool selection ----------------------------------

    def _first_turn(self, text: str, history_texts: List[str], tools_by_name: dict) -> AIMessage:
        scope = classify_scope(text)
        if scope != "in_scope":
            return AIMessage(content=REFUSAL_TEMPLATES[scope])

        for pattern, answer in CANNED_RULES_ANSWERS.items():
            if re.search(pattern, text, re.IGNORECASE):
                return AIMessage(content=answer)

        players = self._known_players()
        ctx = resolve_context(text, history_texts, players)
        lowered = text.lower()

        tool_name, args = self._select_tool(text, lowered, ctx)
        if tool_name is None or tool_name not in tools_by_name:
            return AIMessage(content=(
                "I can help with AFL team records, player stats, head-to-head history, "
                "round results, top performers, or upcoming fixtures -- could you name a "
                "specific team, player, season, or round?"
            ))
        return AIMessage(content="", tool_calls=[{"name": tool_name, "args": args, "id": "call_1"}])

    def _select_tool(self, text: str, lowered: str, ctx: dict):
        default_season = ctx["season"] or 2018  # most recent season in this dataset, used as "current" when unstated

        if ("head to head" in lowered or "head-to-head" in lowered or " vs " in lowered
                or "history against" in lowered) and len(ctx["teams"]) >= 2:
            return "get_head_to_head", {"team_a": ctx["teams"][0], "team_b": ctx["teams"][1]}

        if "next match" in lowered or "play next" in lowered or "who do they play" in lowered:
            if ctx["teams"]:
                return "get_next_match", {"team": ctx["teams"][0], "season": default_season, "after_round": ctx["round"] or "R1"}

        if ("top disposal" in lowered or "most disposals" in lowered or "leading disposal" in lowered
                or ("top" in lowered and "disposal" in lowered)):
            args = {"season": default_season, "round_": ctx["round"] or "R1", "stat": "disposals"}
            if ctx["teams"]:
                args["team"] = ctx["teams"][0]
            return "get_top_performer", args
        if "goal-kicker" in lowered or "goalkicker" in lowered or ("top" in lowered and "goal" in lowered):
            args = {"season": default_season, "round_": ctx["round"] or "R1", "stat": "goals"}
            if ctx["teams"]:
                args["team"] = ctx["teams"][0]
            return "get_top_performer", args

        if "season average" in lowered or ("compare" in lowered and ctx["player"]):
            if ctx["player"]:
                return "get_player_season_stats", {"player_name": ctx["player"], "season": default_season}

        if ctx["player"] and (extract_stat(text) != "disposals" or "disposal" in lowered
                               or "goal" in lowered or "stats" in lowered or "how many" in lowered):
            if ctx["round"] and ("last round" in lowered or "this round" in lowered or extract_round(text)):
                return "get_player_game_stats", {"player_name": ctx["player"], "season": default_season, "round_": ctx["round"]}
            return "get_player_season_stats", {"player_name": ctx["player"], "season": default_season}

        if ctx["teams"]:
            if ctx["round"]:
                return "get_round_result", {"team": ctx["teams"][0], "season": default_season, "round_": ctx["round"]}
            return "get_team_record", {"team": ctx["teams"][0], "season": default_season}

        return None, {}

    # -- turn 2: synthesize a final answer strictly from the tool result ------

    def _final_answer(self, messages: List[BaseMessage]) -> AIMessage:
        tool_msg = messages[-1]
        return AIMessage(content=str(tool_msg.content))


def build_llm(model_name: str = "gemini-3.5-flash-lite"):
    """
    Returns a real ChatGoogleGenerativeAI if GEMINI_API_KEY is set in the
    environment, otherwise an OfflineAFLChatModel implementing the same
    BaseChatModel interface the LangChain agent expects.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key, temperature=0)

    return OfflineAFLChatModel()