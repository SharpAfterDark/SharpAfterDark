"""
Odds ingestion via The Odds API — multi-sport version.
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


def get_odds_for_sport(sport_key: str, markets: str = "h2h", regions: str = "us") -> list:
    """Pull odds for one sport key from The Odds API."""
    if not ODDS_API_KEY:
        raise ValueError("ODDS_API_KEY not set. Add it in Settings or Streamlit secrets.")

    params = {
        "apiKey": ODDS_API_KEY,
        "regions": regions,
        "markets": markets,
        "oddsFormat": "american",
    }

    resp = requests.get(
        f"{BASE_URL}/sports/{sport_key}/odds",
        params=params,
        timeout=30
    )
    resp.raise_for_status()

    remaining = resp.headers.get("x-requests-remaining")
    used = resp.headers.get("x-requests-used")
    print(f"Odds API — used: {used}, remaining: {remaining}")

    return resp.json()


def get_all_sports_odds() -> dict:
    """
    Pull odds for all five major sports.
    Returns { "MLB": [...], "NBA": [...], ... }
    """
    results = {}
    for name, key in SPORTS.items():
        try:
            events = get_odds_for_sport(key)
            results[name] = events
            print(f"{name}: {len(events)} events")
        except Exception as e:
            print(f"Failed to pull {name}: {e}")
            results[name] = []
    return results


def get_mlb_odds(markets: str = "h2h,spreads,totals", regions: str = "us") -> list:
    """Kept for backward compatibility with older MLB
