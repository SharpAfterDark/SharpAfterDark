"""
Odds ingestion via The Odds API — multi-sport + player props
"""

import os
import requests
from datetime import datetime, timezone
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

ODDS_API_KEY = os.getenv("ODDS_API_KEY")
BASE_URL = "https://api.the-odds-api.com/v4"

SPORTS = {
    "MLB": "baseball_mlb",
    "NBA": "basketball_nba",
    "NFL": "americanfootball_nfl",
    "NHL": "icehockey_nhl",
    "WNBA": "basketball_wnba",
}

# Featured prop markets we care about (keeps API usage reasonable)
PROP_MARKETS = {
    "MLB": "pitcher_strikeouts,batter_hits,batter_total_bases,batter_home_runs,batter_rbis",
    "NBA": "player_points,player_rebounds,player_assists,player_threes",
    "NFL": "player_pass_yds,player_rush_yds,player_receptions,player_pass_tds",
    "NHL": "player_points,player_shots_on_goal,player_goals,player_assists",
    "WNBA": "player_points,player_rebounds,player_assists,player_threes",
}


def get_odds_for_sport(sport_key: str, markets: str = "h2h", regions: str = "us") -> list:
    if not ODDS_API_KEY:
        raise ValueError("ODDS_API_KEY not set")

    params = {
        "apiKey": ODDS_API_KEY,
        "regions": regions,
        "markets": markets,
        "oddsFormat": "american",
    }
    resp = requests.get(f"{BASE_URL}/sports/{sport_key}/odds", params=params, timeout=30)
    resp.raise_for_status()
    print(f"Odds API remaining: {resp.headers.get('x-requests-remaining')}")
    return resp.json()


def get_all_sports_odds() -> dict:
    results = {}
    for name, key in SPORTS.items():
        try:
            events = get_odds_for_sport(key, markets="h2h")
            results[name] = events
            print(f"{name}: {len(events)} moneyline events")
        except Exception as e:
            print(f"Failed {name}: {e}")
            results[name] = []
    return results


def get_events_list(sport_key: str) -> list:
    """Lightweight list of upcoming events (no odds)."""
    if not ODDS_API_KEY:
        raise ValueError("ODDS_API_KEY not set")
    params = {"apiKey": ODDS_API_KEY}
    resp = requests.get(f"{BASE_URL}/sports/{sport_key}/events", params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def get_event_props(sport_key: str, event_id: str, markets: str) -> dict:
    """
    Player props require the event-odds endpoint (one game at a time).
    """
    if not ODDS_API_KEY:
        raise ValueError("ODDS_API_KEY not set")

    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "us",
        "markets": markets,
        "oddsFormat": "american",
    }
    url = f"{BASE_URL}/sports/{sport_key}/events/{event_id}/odds"
    resp = requests.get(url, params=params, timeout=25)
    resp.raise_for_status()
    print(f"Props remaining: {resp.headers.get('x-requests-remaining')}")
    return resp.json()


def get_props_for_sport(sport_name: str, max_events: int = 4) -> list:
    """
    Pull player props for the next few events in one sport.
    max_events keeps free-tier usage under control.
    """
    sport_key = SPORTS.get(sport_name)
    markets = PROP_MARKETS.get(sport_name)
    if not sport_key or not markets:
        return []

    try:
        events = get_events_list(sport_key)
    except Exception as e:
        print(f"Events list failed for {sport_name}: {e}")
        return []

    # Sort by commence time and take the next few
    events = sorted(events, key=lambda x: x.get("commence_time", ""))[:max_events]
    results = []

    for ev in events:
        event_id = ev.get("id")
        home = ev.get("home_team", "")
        away = ev.get("away_team", "")
        event_name = f"{away} @ {home}"
        try:
            data = get_event_props(sport_key, event_id, markets)
            data["_event_name"] = event_name
            data["_sport"] = sport_name
            results.append(data)
        except Exception as e:
            print(f"Props failed for {event_name}: {e}")
            continue

    return results


def get_mlb_odds(markets: str = "h2h", regions: str = "us") -> list:
    return get_odds_for_sport("baseball_mlb", markets=markets, regions=regions)
