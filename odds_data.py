"""
Odds ingestion via The Odds API.
Sign up at https://the-odds-api.com for a free key (500 credits/month).
"""

import os
import requests
from datetime import datetime, timezone
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

ODDS_API_KEY = os.getenv("ODDS_API_KEY")
BASE_URL = "https://api.the-odds-api.com/v4"


def get_mlb_odds(
    markets: str = "h2h,spreads,totals",
    regions: str = "us",
    odds_format: str = "american"
) -> List[Dict]:
    """
    Pull current MLB odds from multiple books.
    Returns list of events with bookmaker odds.
    """
    if not ODDS_API_KEY:
        raise ValueError("ODDS_API_KEY not set. Add it to your .env file.")

    params = {
        "apiKey": ODDS_API_KEY,
        "regions": regions,
        "markets": markets,
        "oddsFormat": odds_format,
    }

    resp = requests.get(f"{BASE_URL}/sports/baseball_mlb/odds", params=params, timeout=30)
    resp.raise_for_status()

    # Remaining credits are in headers
    remaining = resp.headers.get("x-requests-remaining")
    used = resp.headers.get("x-requests-used")
    print(f"Odds API credits — used: {used}, remaining: {remaining}")

    return resp.json()


def snapshot_odds_for_db(odds_data: List[Dict]) -> List[Dict]:
    """
    Flatten odds into rows ready for OddsSnapshot table.
    Each row = one bookmaker + market + outcome at this exact moment.
    """
    rows = []
    now = datetime.now(timezone.utc)

    for event in odds_data:
        game_id = event.get("id")  # The Odds API event id (string)
        home = event.get("home_team")
        away = event.get("away_team")
        commence = event.get("commence_time")

        for book in event.get("bookmakers", []):
            book_name = book.get("title") or book.get("key")
            for market in book.get("markets", []):
                market_key = market.get("key")  # h2h, spreads, totals
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