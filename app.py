"""
SharpAfterDark Machine v1.1 — Multi-Sport
MLB + NBA + NFL + NHL + WNBA
Mobile-first for iPhone (Add to Home Screen)
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime, timezone
import os
from pathlib import Path

# Flattened imports (no utils/ folder)
from db import init_db, SessionLocal, Game, Prediction, OddsSnapshot
from mlb_data import get_todays_schedule
from odds_data import get_mlb_odds, get_all_sports_odds
from scoring import score_moneyline_event

# ──────────────────────────────────────────────
# Page config
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="SharpAfterDark",
    page_icon="🌑",
    layout="centered",
    initial_sidebar_state="collapsed",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": "SharpAfterDark Machine v1.1 — Multi-Sport"
    }
)

init_db()

# ──────────────────────────────────────────────
# Dark mobile CSS
# ──────────────────────────────────────────────
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    .stApp {
        background-color: #0a0a0a;
        color: #e5e5e5;
    }
    
    .block-container {
        padding-top: 0.8rem !important;
        padding-bottom: 5rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        max-width: 480px;
    }
    
    h1 { font-size: 1.45rem !important; font-weight: 700 !important; color: #f5f5f5 !important; }
    h2, h3 { font-size: 1.15rem !important; color: #e5e5e5 !important; }
    p, label, .stMarkdown { color: #d4d4d4 !important; }
    
    .stButton > button {
        width: 100%;
        min-height: 48px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 1rem;
        border: none;
    }
    
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #7c3aed, #4f46e5);
        color: white;
    }
    
    .stAlert {
        border-radius: 12px;
        border: 1px solid #262626;
    }
    
    div[role="radiogroup"] label {
        background: #171717;
        border-radius: 10px;
        padding: 10px 14px !important;
        margin-bottom: 6px;
        border: 1px solid #262626;
    }
    
    .bottom-nav-spacer {
        height: 20px;
    }
</style>
""", unsafe_allow_html=True)


def main():
    st.markdown("### 🌑 SharpAfterDark")
    st.caption("Multi-Sport Machine v1.1")

    page = st.radio(
        "nav",
        ["🏠 Board", "⚡ Run", "📋 Log", "⚙️ Settings"],
        horizontal=True,
        label_visibility="collapsed"
    )

    st.divider()

    if "Board" in page:
        show_dashboard()
    elif "Run" in page:
        show_run_pipeline()
    elif "Log" in page:
        show_predictions_log()
    else:
        show_settings()

    st.markdown('<div class="bottom-nav-spacer"></div>', unsafe_allow_html=True)


def show_dashboard():
    today = date.today().isoformat()
    st.markdown(f"**{today}**")

    db = SessionLocal()
    try:
        games = db.query(Game).filter(Game.game_date == today).all()
        preds = (
            db.query(Prediction)
            .filter(
                Prediction.prediction_time
                >= datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)
            )
            .order_by(Prediction.sad_score.desc())
            .all()
        )
    finally:
        db.close()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Games", len(games))
    with col2:
        st.metric("Picks", len(preds))
    with col3:
        edges = [p.edge for p in
