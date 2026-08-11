"""
SharpAfterDark Machine v1.2
Tight multi-sport moneyline + player props
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime, timezone
import os
from pathlib import Path

from db import init_db, SessionLocal, Game, Prediction
from mlb_data import get_todays_schedule
from odds_data import get_all_sports_odds, get_props_for_sport
from scoring import score_moneyline_event, score_player_prop_market

st.set_page_config(
    page_title="SharpAfterDark",
    page_icon="🌑",
    layout="centered",
    initial_sidebar_state="collapsed",
)

init_db()

st.markdown("""
<style>
    #MainMenu, footer, header {visibility: hidden;}
    .stApp { background-color: #0a0a0a; color: #e5e5e5; }
    .block-container {
        padding-top: 0.8rem !important;
        padding-bottom: 5rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        max-width: 480px;
    }
    h1, h2, h3 { color: #f5f5f5 !important; }
    p, label, .stMarkdown { color: #d4d4d4 !important; }
    .stButton > button {
        width: 100%; min-height: 48px; border-radius: 12px;
        font-weight: 600; border: none;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #7c3aed, #4f46e5); color: white;
    }
</style>
""", unsafe_allow_html=True)


def main():
    st.markdown("### 🌑 SharpAfterDark")
    st.caption("v1.2 · Tight + Props")

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


def show_dashboard():
    today = date.today().isoformat()
    st.markdown(f"**{today}**")

    col_a, col_b = st.columns(2)
    with col_a:
        sport_filter = st.selectbox(
            "Sport",
            ["All", "MLB", "NBA", "NFL", "NHL", "WNBA"],
            index=0
        )
    with col_b:
        market_filter = st.selectbox(
            "Market",
            ["Moneyline", "Player Props"],
            index=0
        )

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

    # Sport filter
    if sport_filter != "All":
        preds = [p for p in preds if p.notes and p.notes.startswith(sport_filter)]

    # Market filter
    if market_filter == "Moneyline":
        preds = [p for p in preds if p.market == "moneyline"]
    else:
        preds = [p for p in preds if p.market and p.market != "moneyline"]

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Games", len(games) if sport_filter in ["All", "MLB"] else "—")
    with c2:
        st.metric("Picks", len(preds))
    with c3:
        edges = [p.edge for p in preds if p.edge is not None]
        avg = f"{sum(edges)/len(edges):.1%}" if edges else "—"
        st.metric("Avg Edge", avg)

    st.markdown("#### Ranked Board")

    if not preds:
        st.info(f"No {market_filter.lower()} picks for **{sport_filter}**. Run the pipeline.")
    else:
        for i, p in enumerate(preds[:30], 1):
            edge_str = f"{p.edge:+.1%}" if p.edge is not None else "—"
            sad = f"{p.sad_score:.2f}" if p.sad_score is not None else "—"
            odds = p.odds_at_prediction if p.odds_at_prediction else "—"
            sport_tag = p.notes.split("|")[0].strip() if p.notes and "|" in p.notes else ""

            st.markdown(
                f"**{i}. {p.selection}**  \n"
                f"`{p.market}` · {sport_tag} · Edge **{edge_str}** · SAD **{sad}** · Odds **{odds}**"
            )
            st.divider()

    if sport_filter in ["All", "MLB"] and games and market_filter == "Moneyline":
        st.markdown("#### Today’s MLB Games")
        for g in games:
            pitchers = f"{g.probable_away_pitcher or 'TBD'} vs {g.probable_home_pitcher or 'TBD'}"
            st.markdown(f"**{g.away_team}** @ **{g.home_team}**  \n_{pitchers}_")
            st.divider()


def show_run_pipeline():
    st.markdown("#### Run Pipeline")
    st.caption("Moneyline (all sports) + optional player props for one sport")

    # Clear button
    if st.button("🗑 Clear today's predictions", use_container)
