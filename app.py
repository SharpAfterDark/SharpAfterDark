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

    # Apply filters
    if sport_filter != "All":
        preds = [p for p in preds if p.notes and p.notes.startswith(sport_filter)]

    if market_filter == "Moneyline":
        preds = [p for p in preds if p.market == "moneyline"]
    else:
        preds = [p for p in preds if p.market != "moneyline"]

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

    target_date = st.date_input("Date", value=date.today(), label_visibility="collapsed")

    prop_sport = st.selectbox(
        "Also pull player props for:",
        ["None", "MLB", "NBA", "NFL", "NHL", "WNBA"],
        index=1
    )

    if st.button("▶ Run Full Pipeline", type="primary", use_container_width=True):

        # 1. MLB schedule
        with st.status("MLB schedule…", expanded=True) as status:
            try:
                games = get_todays_schedule(target_date.isoformat())
                st.write(f"**{len(games)}** MLB games")
                db = SessionLocal()
                saved = 0
                for g in games:
                    if not db.query(Game).filter(Game.game_pk == g["game_pk"]).first():
                        db.add(Game(
                            game_pk=g["game_pk"],
                            game_date=g["game_date"],
                            home_team=g["home_team"],
                            away_team=g["away_team"],
                            home_team_id=g["home_team_id"],
                            away_team_id=g["away_team_id"],
                            probable_home_pitcher=g.get("probable_home_pitcher"),
                            probable_away_pitcher=g.get("probable_away_pitcher"),
                            status=g.get("status"),
                        ))
                        saved += 1
                db.commit()
                db.close()
                status.update(label="MLB schedule done", state="complete")
            except Exception as e:
                status.update(label="Schedule failed", state="error")
                st.error(str(e))

        # 2. Moneyline – all sports
        with st.status("Moneyline – all sports…", expanded=True) as status:
            try:
                if not os.getenv("ODDS_API_KEY"):
                    st.warning("No ODDS_API_KEY")
                    status.update(label="Skipped", state="error")
                else:
                    all_odds = get_all_sports_odds()
                    all_preds = []
                    for sport, events in all_odds.items():
                        for event in events:
                            all_preds.extend(score_moneyline_event(event, sport, min_edge=0.02))
                        st.write(f"{sport}: {len(events)} games")

                    db = SessionLocal()
                    for p in all_preds:
                        db.add(Prediction(
                            prediction_time=p["prediction_time"],
                            market=p["market"],
                            selection=p["selection"],
                            model_prob=p["model_prob"],
                            market_implied_prob=p["market_implied_prob"],
                            edge=p["edge"],
                            sad_score=p["sad_score"],
                            odds_at_prediction=p["odds_at_prediction"],
                            bookmaker=p["bookmaker"],
                            model_version=p["model_version"],
                            notes=p["notes"],
                        ))
                    db.commit()
                    db.close()
                    st.write(f"**{len(all_preds)}** moneyline edges ≥ 2%")
                    status.update(label="Moneyline done", state="complete")
            except Exception as e:
                status.update(label="Moneyline failed", state="error")
                st.error(str(e))

        # 3. Player props (optional, limited events)
        if prop_sport != "None":
            with st.status(f"Player props – {prop_sport}…", expanded=True) as status:
                try:
                    prop_events = get_props_for_sport(prop_sport, max_events=4)
                    st.write(f"Pulled props for **{len(prop_events)}** games")

                    prop_preds = []
                    for ev_data in prop_events:
                        event_name = ev_data.get("_event_name", "")
                        sport = ev_data.get("_sport", prop_sport)
                        for book in ev_data.get("bookmakers", []):
                            for market in book.get("markets", []):
                                prop_preds.extend(
                                    score_player_prop_market(market, sport, event_name, min_edge=0.025)
                                )

                    db = SessionLocal()
                    for p in prop_preds:
                        db.add(Prediction(
                            prediction_time=p["prediction_time"],
                            market=p["market"],
                            selection=p["selection"],
                            model_prob=p["model_prob"],
                            market_implied_prob=p["market_implied_prob"],
                            edge=p["edge"],
                            sad_score=p["sad_score"],
                            odds_at_prediction=p["odds_at_prediction"],
                            bookmaker=p.get("bookmaker"),
                            model_version=p["model_version"],
                            notes=p["notes"],
                        ))
                    db.commit()
                    db.close()
                    st.write(f"**{len(prop_preds)}** prop edges ≥ 2.5%")
                    status.update(label="Props done", state="complete")
                except Exception as e:
                    status.update(label="Props failed", state="error")
                    st.error(str(e))

        st.success("Pipeline finished.")


def show_predictions_log():
    st.markdown("#### Predictions Log")
    db = SessionLocal()
    try:
        preds = db.query(Prediction).order_by(Prediction.prediction_time.desc()).limit(60).all()
    finally:
        db.close()

    if not preds:
        st.info("No predictions yet.")
        return

    for p in preds:
        time_str = p.prediction_time.strftime("%m/%d %H:%M") if p.prediction_time else "—"
        edge = f"{p.edge:+.1%}" if p.edge is not None else "—"
        st.markdown(
            f"**{p.selection}**  \n"
            f"{time_str} · `{p.market}` · Edge {edge} · Odds {p.odds_at_prediction or '—'}"
        )
        st.divider()

    df = pd.DataFrame([{
        "time": p.prediction_time,
        "market": p.market,
        "selection": p.selection,
        "edge": p.edge,
        "sad_score": p.sad_score,
        "odds": p.odds_at_prediction,
        "notes": p.notes,
    } for p in preds])
    st.download_button("Download CSV", df.to_csv(index=False),
                       file_name=f"sad_log_{date.today()}.csv",
                       mime="text/csv", use_container_width=True)


def show_settings():
    st.markdown("#### Settings")
    current = os.getenv("ODDS_API_KEY", "")
    if current:
        st.success(f"Key loaded · …{current[-4:]}")
    else:
        st.warning("No key set")

    new_key = st.text_input("Paste key", type="password", label_visibility="collapsed")
    if st.button("Save Key", use_container_width=True) and new_key.strip():
        Path(".env").write_text(f"ODDS_API_KEY={new_key.strip()}\n")
        st.success("Saved. Redeploy for it to take effect.")
        st.rerun()

    st.divider()
    st.markdown("""
**iPhone home screen**
1. Open in Safari  
2. Share → Add to Home Screen  
3. Name it SharpAfterDark
    """)
    st.caption("v1.2 · Engine first")


if __name__ == "__main__":
    main()
