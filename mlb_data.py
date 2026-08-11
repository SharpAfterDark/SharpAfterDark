"""
MLB schedule + basic game data from the official (free) MLB Stats API.
"""

import requests
from datetime import datetime, date
from typing import List, Dict, Optional


BASE_URL = "https://statsapi.mlb.com/api/v1"


def get_todays_schedule(target_date: Optional[str] = None) -> List[Dict]:
    """
    Pull today's (or specified date) MLB schedule.
    Returns list of game dicts with gamePk, teams, probable pitchers, etc.
    """
    if target_date is None:
        target_date = date.today().isoformat()

    params = {
        "sportId": 1,
        "date": target_date,
        "hydrate": "probablePitcher,team,venue"
    }

    resp = requests.get(f"{BASE_URL}/schedule", params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    games = []
    for d in data.get("dates", []):
        for g in d.get("games", []):
            game = {
                "game_pk": g.get("gamePk"),
                "game_date": d.get("date"),
                "status": g.get("status", {}).get("detailedState"),
                "home_team": g.get("teams", {}).get("home", {}).get("team", {}).get("name"),
                "away_team": g.get("teams", {}).get("away", {}).get("team", {}).get("name"),
                "home_team_id": g.get("teams", {}).get("home", {}).get("team", {}).get("id"),
                "away_team_id": g.get("teams", {}).get("away", {}).get("team", {}).get("id"),
                "home_score": g.get("teams", {}).get("home", {}).get("score"),
                "away_score": g.get("teams", {}).get("away", {}).get("score"),
                "probable_home_pitcher": None,
                "probable_away_pitcher": None,
                "venue": g.get("venue", {}).get("name"),
                "game_time": g.get("gameDate"),
            }

            # Probable pitchers
            home_pp = g.get("teams", {}).get("home", {}).get("probablePitcher")
            away_pp = g.get("teams", {}).get("away", {}).get("probablePitcher")
            if home_pp:
                game["probable_home_pitcher"] = home_pp.get("fullName")
            if away_pp:
                game["probable_away_pitcher"] = away_pp.get("fullName")

            games.append(game)

    return games


def get_game_boxscore(game_pk: int) -> Dict:
    """Fetch full boxscore for a finished or in-progress game."""
    resp = requests.get(f"{BASE_URL}/game/{game_pk}/boxscore", timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_standings() -> Dict:
    """Current standings."""
    resp = requests.get(f"{BASE_URL}/standings", params={"leagueId": "103,104"}, timeout=30)
    resp.raise_for_status()
    return resp.json()