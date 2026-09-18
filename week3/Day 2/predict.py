"""
predict.py

Callable prediction functions for the AFL match-winner and top-player models
trained in `AFL_Prediction_Models.ipynb` (Week 3, Day 2). This is the exact
interface the Day 4 chat-agent tools will wrap, so every function here returns
plain dicts/lists (no DataFrames, no model objects) and raises a clear
`ValueError` on bad input rather than letting a model call fail obscurely.

Expected directory layout (paths are resolved relative to this file, not the
caller's working directory, so this module works regardless of where it's
imported from):

    project/
      predict.py
      models/
        match_winner_logreg.pkl
        top_player_gbm.pkl
      data/
        team_snapshots.parquet
        player_features.parquet
        matches.parquet

No hardcoded absolute paths or secrets -- everything is loaded from these
relative, versioned artifacts.
"""

from __future__ import annotations

import functools
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "models"
DATA_DIR = BASE_DIR / "data"

MATCH_WINNER_MODEL_PATH = MODELS_DIR / "match_winner_logreg.pkl"
TOP_PLAYER_MODEL_PATH = MODELS_DIR / "top_player_gbm.pkl"

MATCH_WINNER_NUMERIC_FEATURES = [
    "home_last_5_avg_score", "away_last_5_avg_score", "home_days_rest", "away_days_rest",
    "home_win_streak_entering", "away_win_streak_entering", "home_last_5_avg_player_output",
    "away_last_5_avg_player_output", "home_ladder_position", "away_ladder_position",
    "home_h2h_win_rate", "away_h2h_win_rate",
]
MATCH_WINNER_CATEGORICAL_FEATURES = ["home_team", "away_team", "venue"]

TOP_PLAYER_NUMERIC_FEATURES = [
    "prev_game_fantasy_points", "last_3_avg_fantasy_points", "season_avg_fantasy_points_to_date",
    "career_games_played", "team_last_5_avg_score", "team_days_rest", "team_win_streak_entering",
    "team_ladder_position", "team_h2h_win_rate", "is_home",
]
TOP_PLAYER_CATEGORICAL_FEATURES = ["primary_position"]

SUPPORTED_STAT_TYPES = {"fantasy_points"}  # the only target the Day 2 model was trained on


# ---------------------------------------------------------------------------
# Lazy-loaded artifacts (loaded once per process, on first call)
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=1)
def _load_match_winner_model():
    if not MATCH_WINNER_MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Match-winner model not found at {MATCH_WINNER_MODEL_PATH}. "
            "Run the Day 2 notebook first to train and save it."
        )
    return joblib.load(MATCH_WINNER_MODEL_PATH)


@functools.lru_cache(maxsize=1)
def _load_top_player_model():
    if not TOP_PLAYER_MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Top-player model not found at {TOP_PLAYER_MODEL_PATH}. "
            "Run the Day 2 notebook first to train and save it."
        )
    return joblib.load(TOP_PLAYER_MODEL_PATH)


@functools.lru_cache(maxsize=1)
def _load_team_snapshots() -> pd.DataFrame:
    path = DATA_DIR / "team_snapshots.parquet"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run the Day 2 notebook first to build it.")
    df = pd.read_parquet(path)
    df["match_date"] = pd.to_datetime(df["match_date"])
    return df


@functools.lru_cache(maxsize=1)
def _load_player_features() -> pd.DataFrame:
    path = DATA_DIR / "player_features.parquet"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run the Day 2 notebook first to build it.")
    return pd.read_parquet(path)


@functools.lru_cache(maxsize=1)
def _valid_teams() -> set:
    return set(_load_team_snapshots()["team"].unique())


@functools.lru_cache(maxsize=1)
def _valid_match_ids() -> set:
    path = DATA_DIR / "matches.parquet"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run the Day 2 notebook first to build it.")
    return set(pd.read_parquet(path)["match_id"].unique())


@functools.lru_cache(maxsize=1)
def _date_range():
    snaps = _load_team_snapshots()
    return snaps["match_date"].min(), snaps["match_date"].max()


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def validate_team(team: str, valid_teams: set) -> None:
    """Raise ValueError with the full valid-team list if `team` isn't recognized."""
    if team not in valid_teams:
        raise ValueError(f"Unknown team: {team!r}. Valid teams: {sorted(valid_teams)}")


def validate_date(date: str, min_date: pd.Timestamp, max_date: pd.Timestamp) -> pd.Timestamp:
    """Parse `date` and raise ValueError if it falls outside the data's known range."""
    try:
        d = pd.to_datetime(date)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Could not parse date: {date!r}") from exc
    if not (min_date <= d <= max_date):
        raise ValueError(
            f"Date {date} is outside the range covered by the training data "
            f"({min_date.date()} to {max_date.date()})."
        )
    return d


def validate_match_id(match_id: str, valid_ids: set) -> None:
    """Raise ValueError if `match_id` isn't a known historical match."""
    if match_id not in valid_ids:
        raise ValueError(f"Unknown match_id: {match_id!r}. Call list_available_matches() to see valid IDs.")


def validate_stat_type(stat_type: str) -> None:
    """Raise ValueError for a stat_type the top-player model wasn't trained to predict."""
    if stat_type not in SUPPORTED_STAT_TYPES:
        raise ValueError(f"Unsupported stat_type: {stat_type!r}. Supported: {sorted(SUPPORTED_STAT_TYPES)}")


# ---------------------------------------------------------------------------
# Internal feature-lookup helpers
# ---------------------------------------------------------------------------

def _latest_team_snapshot(team: str, as_of_date: pd.Timestamp) -> pd.Series | None:
    """Most recent known rolling-feature snapshot for `team` strictly before `as_of_date`."""
    snaps = _load_team_snapshots()
    hist = snaps[(snaps["team"] == team) & (snaps["match_date"] < as_of_date)]
    if hist.empty:
        return None
    return hist.sort_values("match_date").iloc[-1]


def _h2h_win_rate(team: str, opponent: str, as_of_date: pd.Timestamp) -> float:
    """team's win rate vs opponent in all prior meetings before as_of_date (NaN if none)."""
    snaps = _load_team_snapshots()
    hist = snaps[
        (snaps["team"] == team) & (snaps["opponent"] == opponent) & (snaps["match_date"] < as_of_date)
    ]
    return float(hist["win"].mean()) if not hist.empty else np.nan


# ---------------------------------------------------------------------------
# Public prediction functions
# ---------------------------------------------------------------------------

def predict_match_winner(team_a: str, team_b: str, date: str) -> dict:
    """
    Predict the winner of a match between `team_a` (treated as the home team)
    and `team_b` (away team) on `date`.

    Rebuilds the same rolling/contextual features the model was trained on
    (last-5 form, ladder position, win streak, rest days, head-to-head) from
    each team's most recent known state strictly before `date` -- no venue is
    supplied by this interface, so venue is treated as unknown (the model
    falls back on team- and form-based signal only).

    Args:
        team_a: Home team name (must match a team in the training data).
        team_b: Away team name.
        date: ISO date string (e.g. "2018-09-08"), must fall within the
            range covered by the training data.

    Returns:
        {
            "winner": "Team A" | "Team B" | "Draw",
            "probability": float,   # model's probability for the predicted winner
            "confidence": "low" | "medium" | "high",
        }

    Raises:
        ValueError: unknown team name, unparseable/out-of-range date, or no
            historical data available yet for one of the teams at that date.
    """
    valid_teams = _valid_teams()
    validate_team(team_a, valid_teams)
    validate_team(team_b, valid_teams)
    min_date, max_date = _date_range()
    as_of = validate_date(date, min_date, max_date)

    snap_a = _latest_team_snapshot(team_a, as_of)
    snap_b = _latest_team_snapshot(team_b, as_of)
    if snap_a is None or snap_b is None:
        missing = team_a if snap_a is None else team_b
        raise ValueError(f"No historical data available for {missing!r} before {date}.")

    row = pd.DataFrame([{
        "home_last_5_avg_score": snap_a["last_5_avg_score"],
        "away_last_5_avg_score": snap_b["last_5_avg_score"],
        "home_days_rest": (as_of - snap_a["match_date"]).days,
        "away_days_rest": (as_of - snap_b["match_date"]).days,
        "home_win_streak_entering": snap_a["win_streak_entering"],
        "away_win_streak_entering": snap_b["win_streak_entering"],
        "home_last_5_avg_player_output": snap_a["last_5_avg_player_output"],
        "away_last_5_avg_player_output": snap_b["last_5_avg_player_output"],
        "home_ladder_position": snap_a["ladder_position"],
        "away_ladder_position": snap_b["ladder_position"],
        "home_h2h_win_rate": _h2h_win_rate(team_a, team_b, as_of),
        "away_h2h_win_rate": _h2h_win_rate(team_b, team_a, as_of),
        "home_team": team_a,
        "away_team": team_b,
        "venue": "__unknown__",  # unseen category -> OneHotEncoder(handle_unknown="ignore") zeroes it out
    }])

    model = _load_match_winner_model()
    proba_home = float(
        model.predict_proba(row[MATCH_WINNER_NUMERIC_FEATURES + MATCH_WINNER_CATEGORICAL_FEATURES])[0, 1]
    )

    if abs(proba_home - 0.5) < 0.02:
        winner, probability = "Draw", 0.5
    elif proba_home >= 0.5:
        winner, probability = team_a, proba_home
    else:
        winner, probability = team_b, 1 - proba_home

    margin = abs(proba_home - 0.5)
    confidence = "low" if margin < 0.05 else "medium" if margin < 0.15 else "high"

    return {"winner": winner, "probability": round(probability, 3), "confidence": confidence}


def predict_top_player(match_id: str, stat_type: str = "fantasy_points", k: int = 5) -> list:
    """
    Predict the top-k performing players for a given historical match.

    Args:
        match_id: A known match_id from the Day 1 `matches` table (see
            `list_available_matches()`).
        stat_type: Which stat to rank on. Only "fantasy_points" is supported
            by the trained model (the Day 1/2 composite score).
        k: How many players to return, ranked highest-predicted-value first.

    Returns:
        [
            {"rank": 1, "player": "Name", "predicted_value": float},
            {"rank": 2, "player": "Name", "predicted_value": float},
            ...
        ]

    Raises:
        ValueError: unknown match_id, unsupported stat_type, or no player
            rows found for that match.
    """
    validate_match_id(match_id, _valid_match_ids())
    validate_stat_type(stat_type)

    player_features = _load_player_features()
    grp = player_features[player_features["match_id"] == match_id].copy()
    if grp.empty:
        raise ValueError(f"No player data found for match_id: {match_id!r}")

    model = _load_top_player_model()
    X = grp[TOP_PLAYER_NUMERIC_FEATURES + TOP_PLAYER_CATEGORICAL_FEATURES]
    grp["predicted_value"] = model.predict(X)

    ranked = grp.sort_values("predicted_value", ascending=False).head(k)
    return [
        {"rank": i + 1, "player": row.Player, "predicted_value": round(float(row.predicted_value), 1)}
        for i, row in enumerate(ranked.itertuples())
    ]


def list_available_teams() -> list:
    """Convenience helper: all team names the models recognize."""
    return sorted(_valid_teams())


def list_available_matches() -> list:
    """Convenience helper: all match_ids the top-player model can be called on."""
    return sorted(_valid_match_ids())


if __name__ == "__main__":
    # Small smoke test when run directly: `python predict.py`
    print(predict_match_winner("Richmond", "Hawthorn", "2018-09-08"))
    sample_match = next(iter(_valid_match_ids()))
    print(predict_top_player(sample_match))
