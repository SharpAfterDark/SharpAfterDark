"""
SharpAfterDark v1.1 scoring — multi-sport moneyline edge model
"""

from datetime import datetime, timezone
from typing import List, Dict


def american_to_implied(odds: float) -> float:
    if odds is None:
        return None
    if odds > 0:
        return 100 / (odds + 100)
    else:
        return abs(odds) / (abs(odds) + 100)


def remove_vig(prob_a: float, prob_b: float) -> tuple:
    total = prob_a + prob_b
    if total == 0:
        return 0.5, 0.5
    return prob_a / total, prob_b / total


def calculate_edge(model_prob: float, market_prob: float) -> float:
    if model_prob is None or market_prob is None:
        return None
    return model_prob - market_prob


def sad_score(edge: float, model_prob: float) -> float:
    if edge is None or model_prob is None:
        return 0.0
    return round(edge * 100 * (0.5 + abs(model_prob - 0.5)), 2)


def score_moneyline_event(event: Dict, sport: str) -> List[Dict]:
    """
    Score one event. Returns list of positive-edge prediction dicts.
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

    # v1 model: fair market + small home advantage
    HOME_ADVANTAGE = 0.02
    model_home = min(0.95, max(0.05, home_fair + HOME_ADVANTAGE))
    model_away = 1.0 - model_home

    edge_home = calculate_edge(model_home, home_imp)
    edge_away = calculate_edge(model_away, away_imp)

    now = datetime.now(timezone.utc)

    if edge_home and edge_home > 0.01:
        predictions.append({
            "sport": sport,
            "prediction_time": now,
            "market": "moneyline",
            "selection": home,
            "model_prob": round(model_home, 4),
            "market_implied_prob": round(home_imp, 4),
            "edge": round(edge_home, 4),
            "sad_score": sad_score(edge_home, model_home),
            "odds_at_prediction": best_home_odds,
            "bookmaker": best_home_book,
            "model_version": "v1.1-multi",
            "notes": f"vs {away}"
        })

    if edge_away and edge_away > 0.01:
        predictions.append({
            "sport": sport,
            "prediction_time": now,
            "market": "moneyline",
            "selection": away,
            "model_prob": round(model_away, 4),
            "market_implied_prob": round(away_imp, 4),
            "edge": round(edge_away, 4),
            "sad_score": sad_score(edge_away, model_away),
            "odds_at_prediction": best_away_odds,
            "bookmaker": best_away_book,
            "model_version": "v1.1-multi",
            "notes": f"vs {home}"
        })

    return predictions
