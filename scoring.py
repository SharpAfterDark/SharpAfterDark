"""
SharpAfterDark v1.2 scoring
Tight moneyline + player props (Over/Under)
"""

from datetime import datetime, timezone
from typing import List, Dict, Optional


def american_to_implied(odds: float) -> Optional[float]:
    if odds is None:
        return None
    if odds > 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)


def remove_vig(prob_a: float, prob_b: float) -> tuple:
    total = prob_a + prob_b
    if total <= 0:
        return 0.5, 0.5
    return prob_a / total, prob_b / total


def calculate_edge(model_prob: float, market_prob: float) -> Optional[float]:
    if model_prob is None or market_prob is None:
        return None
    return model_prob - market_prob


def sad_score(edge: float, model_prob: float) -> float:
    """Higher is better. Rewards larger edges and more decisive probabilities."""
    if edge is None or model_prob is None:
        return 0.0
    confidence = 0.5 + abs(model_prob - 0.5)
    return round(edge * 100 * confidence * 1.15, 2)


# ──────────────────────────────────────────────
# MONEYLINE
# ──────────────────────────────────────────────

def score_moneyline_event(event: Dict, sport: str, min_edge: float = 0.02) -> List[Dict]:
    """
    Score one moneyline event.
    Only returns sides with edge >= min_edge (default 2%).
    """
    predictions = []
    home = event.get("home_team")
    away = event.get("away_team")

    best_home_odds = None
    best_away_odds = None
    best_home_book = None
    best_away_book = None

    for book in event.get("bookmakers", []):
        book_name = book.get("title") or book.get("key")
        for market in book.get("markets", []):
            if market.get("key") != "h2h":
                continue
            for outcome in market.get("outcomes", []):
                name = outcome.get("name")
                price = outcome.get("price")
                if price is None:
                    continue
                if name == home:
                    if best_home_odds is None or price > best_home_odds:
                        best_home_odds = price
                        best_home_book = book_name
                elif name == away:
                    if best_away_odds is None or price > best_away_odds:
                        best_away_odds = price
                        best_away_book = book_name

    if best_home_odds is None or best_away_odds is None:
        return []

    home_imp = american_to_implied(best_home_odds)
    away_imp = american_to_implied(best_away_odds)
    home_fair, away_fair = remove_vig(home_imp, away_imp)

    # Tight v1.2 model: fair market + small home advantage
    HOME_ADV = 0.015
    model_home = min(0.92, max(0.08, home_fair + HOME_ADV))
    model_away = 1.0 - model_home

    edge_home = calculate_edge(model_home, home_imp)
    edge_away = calculate_edge(model_away, away_imp)
    now = datetime.now(timezone.utc)

    if edge_home and edge_home >= min_edge:
        predictions.append({
            "sport": sport,
            "market_type": "moneyline",
            "prediction_time": now,
            "market": "moneyline",
            "selection": home,
            "model_prob": round(model_home, 4),
            "market_implied_prob": round(home_imp, 4),
            "edge": round(edge_home, 4),
            "sad_score": sad_score(edge_home, model_home),
            "odds_at_prediction": best_home_odds,
            "bookmaker": best_home_book,
            "model_version": "v1.2-tight",
            "notes": f"{sport} | vs {away}"
        })

    if edge_away and edge_away >= min_edge:
        predictions.append({
            "sport": sport,
            "market_type": "moneyline",
            "prediction_time": now,
            "market": "moneyline",
            "selection": away,
            "model_prob": round(model_away, 4),
            "market_implied_prob": round(away_imp, 4),
            "edge": round(edge_away, 4),
            "sad_score": sad_score(edge_away, model_away),
            "odds_at_prediction": best_away_odds,
            "bookmaker": best_away_book,
            "model_version": "v1.2-tight",
            "notes": f"{sport} | vs {home}"
        })

    return predictions


# ──────────────────────────────────────────────
# PLAYER PROPS (Over/Under)
# ──────────────────────────────────────────────

def score_player_prop_market(market: Dict, sport: str, event_name: str, min_edge: float = 0.025) -> List[Dict]:
    """
    Score one player prop market (Over/Under).
    market key example: player_points, pitcher_strikeouts, etc.
    """
    predictions = []
    market_key = market.get("key", "prop")
    outcomes = market.get("outcomes", [])

    # Group by player + point line
    lines = {}
    for o in outcomes:
        name = o.get("name")          # "Over" or "Under"
        description = o.get("description")  # player name
        point = o.get("point")
        price = o.get("price")
        if not description or point is None or price is None:
            continue
        key = (description, point)
        if key not in lines:
            lines[key] = {}
        lines[key][name] = price

    now = datetime.now(timezone.utc)

    for (player, point), prices in lines.items():
        over_odds = prices.get("Over")
        under_odds = prices.get("Under")
        if over_odds is None or under_odds is None:
            continue

        over_imp = american_to_implied(over_odds)
        under_imp = american_to_implied(under_odds)
        over_fair, under_fair = remove_vig(over_imp, under_imp)

        # Simple model: use fair probability (no strong prior yet)
        # Slight lean toward Under on high totals is common but we stay neutral for v1.2
        model_over = over_fair
        model_under = under_fair

        edge_over = calculate_edge(model_over, over_imp)
        edge_under = calculate_edge(model_under, under_imp)

        prop_label = market_key.replace("player_", "").replace("batter_", "").replace("pitcher_", "").replace("_", " ").title()

        if edge_over and edge_over >= min_edge:
            predictions.append({
                "sport": sport,
                "market_type": "props",
                "prediction_time": now,
                "market": market_key,
                "selection": f"{player} Over {point} {prop_label}",
                "model_prob": round(model_over, 4),
                "market_implied_prob": round(over_imp, 4),
                "edge": round(edge_over, 4),
                "sad_score": sad_score(edge_over, model_over),
                "odds_at_prediction": over_odds,
                "bookmaker": None,
                "model_version": "v1.2-props",
                "notes": f"{sport} | {event_name} | {market_key}"
            })

        if edge_under and edge_under >= min_edge:
            predictions.append({
                "sport": sport,
                "market_type": "props",
                "prediction_time": now,
                "market": market_key,
                "selection": f"{player} Under {point} {prop_label}",
                "model_prob": round(model_under, 4),
                "market_implied_prob": round(under_imp, 4),
                "edge": round(edge_under, 4),
                "sad_score": sad_score(edge_under, model_under),
                "odds_at_prediction": under_odds,
                "bookmaker": None,
                "model_version": "v1.2-props",
                "notes": f"{sport} | {event_name} | {market_key}"
            })

    return predictions
