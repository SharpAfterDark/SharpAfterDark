"""
SharpAfterDark Machine v1.3
Single-sport Run → Moneyline + Player Props with SAD scores
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime, timezone
import os
from pathlib import Path

from db import init_db, SessionLocal, Game, Prediction
from mlb_data import get_todays_schedule
from odds_data import get_odds_for_sport, get_props_for_sport, SPORTS
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
    st.caption("v1.3 · Sport → Moneyline + Props")

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
            index=1
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

    if sport_filter != "All":
        preds = [p for p in preds if p.notes and p.notes.startswith(sport_filter)]

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
        st.info(f"No {market_filter.lower()} for **{sport_filter}**. Go to Run.")
    else:
        for i, p in enumerate(preds[:40], 1):
            edge_str = f"{p.edge:+.1%}" if p.edge is not None else "—"
            sad = f"{p.sad_score:.2f}" if p.sad_score is not None else "—"
            odds = p.odds_at_prediction if p.odds_at_prediction else "—"
            sport_tag = p.notes.split("|")[0].strip() if p.notes and "|" in p.notes else ""

            st.markdown(
                f"**{i}. {p.selection}**  \n"
                f"`{p.market}` · {sport_tag} · Edge **{edge_str}** · SAD **{sad}** · Odds **{odds}**"
            )
            st.divider()


def show_run_pipeline():
    st.markdown("#### Run Pipeline")
    st.caption("Pick a sport → pull today’s games → score moneylines + player props")

    if st.button("🗑 Clear today's predictions", use_container_width=True):
        db = SessionLocal()
        today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)
        deleted = db.query(Prediction).filter(Prediction.prediction_time >= today_start).delete()
        db.commit()
        db.close()
        st.success(f"Cleared {deleted} predictions")
        st.rerun()

    sport = st.selectbox(
        "Sport",
        ["MLB", "NBA", "NFL", "NHL", "WNBA"],
        index=0
    )
    target_date = st.date_input("Date", value=date.today(), label_visibility="collapsed")
    include_props = st.checkbox("Also pull player props", value=True)

    if st.button("▶ Run for this sport", type="primary", use_container_width=True):
        sport_key = SPORTS.get(sport)
        if not sport_key:
            st.error("Unknown sport")
            return

        # 1. MLB schedule
        if sport == "MLB":
            with st.status("Pulling MLB schedule…", expanded=True) as status:
                try:
                    games = get_todays_schedule(target_date.isoformat())
                    st.write(f"**{len(games)}** games")
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
                    status.update(label="Schedule done", state="complete")
                except Exception as e:
                    status.update(label="Schedule failed", state="error")
                    st.error(str(e))

        # 2. Moneyline
        with st.status(f"Moneyline – {sport}…", expanded=True) as status:
            try:
                if not os.getenv("ODDS_API_KEY"):
                    st.warning("No ODDS_API_KEY set")
                    status.update(label="Skipped", state="error")
                else:
                    events = get_odds_for_sport(sport_key, markets="h2h")
                    st.write(f"**{len(events)}** events with odds")

                    all_preds = []
                    for event in events:
                        all_preds.extend(
                            score_moneyline_event(event, sport, min_edge=0.005)
                        )

                    seen = set()
                    db = SessionLocal()
                    saved = 0
                    for p in all_preds:
                        key = (p["selection"], p["market"], p.get("odds_at_prediction"))
                        if key in seen:
                            continue
                        seen.add(key)
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
                        saved += 1
                    db.commit()
                    db.close()

                    st.write(f"**{saved}** moneyline picks scored")
                    status.update(label="Moneyline done", state="complete")
            except Exception as e:
                status.update(label="Moneyline failed", state="error")
                st.error(str(e))

        # 3. Player props (with diagnostic)
        if include_props:
            with st.status(f"Player props – {sport}…", expanded=True) as status:
                try:
                    prop_events = get_props_for_sport(sport, max_events=6)
                    st.write(f"Props API returned **{len(prop_events)}** games")

                    if not prop_events:
                        st.warning("No events returned from props endpoint.")
                        status.update(label="No events", state="error")
                    else:
                        total_markets = 0
                        total_outcomes = 0
                        sample_keys = set()

                        for ev_data in prop_events:
                            for book in ev_data.get("bookmakers", []):
                                for market in book.get("markets", []):
                                    total_markets += 1
                                    sample_keys.add(market.get("key") or "unknown")
                                    total_outcomes += len(market.get("outcomes", []))

                        st.write(f"Markets found: **{total_markets}**")
                        st.write(f"Outcomes found: **{total_outcomes}**")
                        st.write(f"Market keys: {', '.join(sorted(sample_keys)) or 'none'}")

                        prop_preds = []
                        for ev_data in prop_events:
                            event_name = ev_data.get("_event_name", "")
                            for book in ev_data.get("bookmakers", []):
                                for market in book.get("markets", []):
                                    prop_preds.extend(
                                        score_player_prop_market(
                                            market, sport, event_name, min_edge=0.005
                                        )
                                    )

                        seen = set()
                        db = SessionLocal()
                        saved = 0
                        for p in prop_preds:
                            key = (p["selection"], p["market"], p.get("odds_at_prediction"))
                            if key in seen:
                                continue
                            seen.add(key)
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
                            saved += 1
                        db.commit()
                        db.close()

                        st.write(f"**{saved}** prop picks scored")
                        status.update(label="Props done", state="complete")
                except Exception as e:
                    status.update(label="Props failed", state="error")
                    st.error(str(e))

        st.success(f"{sport} pipeline finished. Check the Board.")


def show_predictions_log():
    st.markdown("#### Predictions Log")
    db = SessionLocal()
    try:
        preds = db.query(Prediction).order_by(Prediction.prediction_time.desc()).limit(100).all()
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
    st.download_button(
        "Download CSV",
        df.to_csv(index=False),
        file_name=f"sad_log_{date.today()}.csv",
        mime="text/csv",
        use_container_width=True,
    )


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
**iPhone**
1. Open in Safari  
2. Share → Add to Home Screen  
3. Name it SharpAfterDark
    """)
    st.caption("v1.3 · One sport at a time")


if __name__ == "__main__":
    main()
