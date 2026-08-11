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
    return get_odds_for_sport("baseball_mlb", markets=markets, regions=regions)


def snapshot_odds_for_db(odds_data: List[Dict]) -> List[Dict]:
    rows = []
    now = datetime.now(timezone.utc)

    for event in odds_data:
        game_id = event.get("id")
        home = event.get("home_team")
        away = event.get("away_team")
        commence = event.get("commence_time")

        for book in event.get("bookmakers", []):
            book_name = book.get("title") or book.get("key")
            for market in book.get("markets", []):
                market_key = market.get("key")
                for outcome in market.get("outcomes", []):
                    rows.append({
                        "external_event_id": game_id,
                        "home_team": home,
                        "away_team": away,
                        "commence_time": commence,
                        "snapshot_time": now,
                        "bookmaker": book_name,
                        "market": market_key,
                        "outcome": outcome.get("name"),
                        "price": outcome.get("price"),
                        "point": outcome.get("point"),
                    })
    return rows
