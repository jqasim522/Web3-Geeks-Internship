"""
afl_tools.py

Structured retrieval tools for the AFL chat agent. All of these are exact
pandas lookups against the Day 1/2 parquet tables -- deliberately NOT semantic
(vector) retrieval, because sports stats have one correct answer and a fuzzy
nearest-neighbor match could return a plausible-sounding but wrong number.
See the notebook / guardrail report for the full structured-vs-semantic
retrieval justification.

Every tool returns a single, self-contained natural-language string containing
the exact figures involved. The agent's final answer is expected to echo those
figures rather than reformulate them, which is what the notebook's grounding
check verifies.
"""

from difflib import get_close_matches
from typing import Optional

import pandas as pd
from langchain_core.tools import tool

MATCHES = pd.read_parquet("matches.parquet")
PLAYER_FEATURES = pd.read_parquet("player_features.parquet")

TEAMS = sorted(set(MATCHES["home_team"]) | set(MATCHES["away_team"]))
SEASON_MIN, SEASON_MAX = int(MATCHES["season"].min()), int(MATCHES["season"].max())
STAT_COLS = {"disposals": "Disposals", "goals": "Goals", "marks": "Marks",
             "tackles": "Tackles", "fantasy_points": "fantasy_points"}


def _normalize_round(round_) -> str:
    s = str(round_).strip().upper()
    return s if s.startswith("R") else f"R{s}"


def _team_error(team: str) -> str:
    return f"Unknown team: '{team}'. Valid teams: {', '.join(TEAMS)}"


@tool
def get_team_record(team: str, season: int) -> str:
    """Get a team's win/loss record for a given AFL season.

    Args:
        team: The AFL team name (e.g., "Collingwood"). Must be one of the 18
            teams in the 2012-2018 dataset.
        season: The season year (e.g., 2018). Data covers 2012-2018.
    """
    if team not in TEAMS:
        return _team_error(team)
    home = MATCHES[(MATCHES.home_team == team) & (MATCHES.season == season)]
    away = MATCHES[(MATCHES.away_team == team) & (MATCHES.season == season)]
    if home.empty and away.empty:
        return f"No matches found for {team} in {season}. Data covers seasons {SEASON_MIN}-{SEASON_MAX}."
    wins = int((home.home_win == 1).sum() + (away.home_win == 0).sum())
    played = len(home) + len(away)
    losses = played - wins
    return f"{team} in {season}: {wins}-{losses} (W-L) from {played} matches, {wins/played:.1%} win rate."


@tool
def get_round_result(team: str, season: int, round_: str) -> str:
    """Get a team's result (opponent, score, win/loss) for a specific round in a season.

    Args:
        team: The AFL team name.
        season: The season year.
        round_: The round, e.g. "R5", "5", or a finals code like "EF"/"GF".
    """
    if team not in TEAMS:
        return _team_error(team)
    r_norm = _normalize_round(round_)
    home = MATCHES[(MATCHES.home_team == team) & (MATCHES.season == season) & (MATCHES["round"] == r_norm)]
    away = MATCHES[(MATCHES.away_team == team) & (MATCHES.season == season) & (MATCHES["round"] == r_norm)]
    if home.empty and away.empty:
        return f"No match found for {team} in {season} {r_norm}."
    if not home.empty:
        row = home.iloc[0]
        result = "won" if row.home_win == 1 else "lost"
        return f"{team} {result} vs {row.away_team} in {season} {r_norm}: {row.home_score:.0f}-{row.away_score:.0f} (home)."
    row = away.iloc[0]
    result = "won" if row.home_win == 0 else "lost"
    return f"{team} {result} vs {row.home_team} in {season} {r_norm}: {row.away_score:.0f}-{row.home_score:.0f} (away)."


@tool
def get_player_season_stats(player_name: str, season: int) -> str:
    """Get a player's season averages/totals (disposals, goals, fantasy points).

    Args:
        player_name: Full player name in "Lastname, Firstname" form (e.g.,
            "Bontempelli, Marcus"), matching the dataset's naming convention.
        season: The season year.
    """
    d = PLAYER_FEATURES[(PLAYER_FEATURES.Player.str.lower() == player_name.lower()) & (PLAYER_FEATURES.season == season)]
    if d.empty:
        candidates = PLAYER_FEATURES["Player"].unique().tolist()
        close = get_close_matches(player_name, candidates, n=3, cutoff=0.6)
        hint = f" Did you mean: {', '.join(close)}?" if close else ""
        return f"No stats found for '{player_name}' in {season}.{hint}"
    games = len(d)
    return (f"{d.Player.iloc[0]} in {season}: {games} games, "
            f"{d.Disposals.mean():.1f} disposals/game ({int(d.Disposals.sum())} total), "
            f"{int(d.Goals.sum())} goals, {d.fantasy_points.mean():.1f} fantasy pts/game avg.")


@tool
def get_player_game_stats(player_name: str, season: int, round_: str) -> str:
    """Get a player's stat line for one specific game.

    Args:
        player_name: Full player name in "Lastname, Firstname" form.
        season: The season year.
        round_: The round, e.g. "R5" or "5".
    """
    r_norm = _normalize_round(round_)
    d = PLAYER_FEATURES[
        (PLAYER_FEATURES.Player.str.lower() == player_name.lower())
        & (PLAYER_FEATURES.season == season) & (PLAYER_FEATURES["round"] == r_norm)
    ]
    if d.empty:
        return f"No record found for '{player_name}' in {season} {r_norm}."
    row = d.iloc[0]
    return (f"{row.Player} in {season} {r_norm} ({row.team} vs {row.Opposition}): "
            f"{int(row.Disposals)} disposals, {int(row.Goals)} goals, {int(row.fantasy_points)} fantasy points.")


@tool
def get_head_to_head(team_a: str, team_b: str) -> str:
    """Get the historical head-to-head record between two AFL teams (2012-2018).

    Args:
        team_a: First team name.
        team_b: Second team name.
    """
    if team_a not in TEAMS or team_b not in TEAMS:
        bad = team_a if team_a not in TEAMS else team_b
        return _team_error(bad)
    a_home = MATCHES[(MATCHES.home_team == team_a) & (MATCHES.away_team == team_b)]
    a_away = MATCHES[(MATCHES.home_team == team_b) & (MATCHES.away_team == team_a)]
    total = len(a_home) + len(a_away)
    if total == 0:
        return f"No historical meetings found between {team_a} and {team_b} in the {SEASON_MIN}-{SEASON_MAX} data."
    a_wins = int((a_home.home_win == 1).sum() + (a_away.home_win == 0).sum())
    b_wins = total - a_wins
    return f"{team_a} vs {team_b} ({SEASON_MIN}-{SEASON_MAX}): {team_a} {a_wins}-{b_wins} {team_b} from {total} meetings."


@tool
def get_top_performer(season: int, round_: str, stat: str = "disposals", team: Optional[str] = None) -> str:
    """Get the top-performing player for a stat in a given round, optionally
    restricted to one team (omit `team` for the league-wide leader that round).

    Args:
        season: The season year.
        round_: The round, e.g. "R5" or "5".
        stat: One of "disposals", "goals", "marks", "tackles", "fantasy_points".
        team: Optional team name to restrict the search to.
    """
    stat = stat.lower()
    if stat not in STAT_COLS:
        return f"Unsupported stat '{stat}'. Supported: {', '.join(STAT_COLS)}"
    col = STAT_COLS[stat]
    r_norm = _normalize_round(round_)
    d = PLAYER_FEATURES[(PLAYER_FEATURES.season == season) & (PLAYER_FEATURES["round"] == r_norm)]
    if team:
        if team not in TEAMS:
            return _team_error(team)
        d = d[d.team == team]
    if d.empty:
        scope = f"{team} in " if team else ""
        return f"No player data found for {scope}{season} {r_norm}. Data covers seasons {SEASON_MIN}-{SEASON_MAX}."
    top = d.loc[d[col].idxmax()]
    scope = f" ({team})" if team else " (league-wide)"
    return f"Top {stat} in {season} {r_norm}{scope}: {top.Player} with {top[col]:.0f} {stat} (playing for {top.team})."


@tool
def get_next_match(team: str, season: int, after_round: str) -> str:
    """Get a team's next scheduled match after a given round in a season.

    Args:
        team: The AFL team name.
        season: The season year.
        after_round: The round to look after, e.g. "R4" or "4".
    """
    if team not in TEAMS:
        return _team_error(team)
    after_norm = _normalize_round(after_round)
    if not after_norm[1:].isdigit():
        return f"'{after_round}' isn't a home-and-away round number, so I can't find what's strictly 'next' after it."
    after_num = int(after_norm[1:])
    szn = MATCHES[((MATCHES.home_team == team) | (MATCHES.away_team == team)) & (MATCHES.season == season)].copy()
    szn = szn[szn["round"].str.match(r"^R\d+$", na=False)]
    szn["round_num"] = szn["round"].str[1:].astype(int)
    nxt = szn[szn.round_num > after_num].sort_values("round_num")
    if nxt.empty:
        return f"No further matches found for {team} in {season} after {after_norm}."
    row = nxt.iloc[0]
    opponent = row.away_team if row.home_team == team else row.home_team
    venue = "home" if row.home_team == team else "away"
    return f"{team}'s next match after {after_norm} in {season} is {row['round']} vs {opponent} ({venue})."


ALL_TOOLS = [
    get_team_record, get_round_result, get_player_season_stats, get_player_game_stats,
    get_head_to_head, get_top_performer, get_next_match,
]