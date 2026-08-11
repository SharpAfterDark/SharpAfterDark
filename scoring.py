"""
SharpAfterDark v1.2 scoring
Tight moneyline + player props (best price vs consensus)
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
    if edge is None or model_prob is None:
        return 0.0
    confidence = 0.5 + abs(model_prob - 0.5)
    return round(edge * 100 * confidence * 1.1, 2)


# ──────────────────────────────────────────────
# MONEYLINE
# ──────────────────────────────────────────────

def score_moneyline_event(event: Dict, sport: str, min_edge: float = 0.008) -> List[Dict]:
    """
