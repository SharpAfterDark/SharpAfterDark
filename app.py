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
        edges = [p.edge for p in preds if p.edge is not None]
        avg_edge = f"{sum(edges)/len(edges):.1%}" if edges else "—"
        st.metric("Avg Edge", avg_edge)

    st.markdown("#### Ranked Board")

    if not preds:
        st.info("No predictions yet. Go to **⚡ Run** and pull today’s slate.")
    else:
        for i, p in enumerate(preds[:20], 1):
            edge_str = f"{p.edge:+.1%}" if p.edge is not None else "—"
            sad = f"{p.sad_score:.2f}" if p.sad_score is not None else "—"
            odds = p.odds_at_prediction if p.odds_at_prediction else "—"
            sport_tag = ""
            if p.notes and "|" in p.notes:
                sport_tag = p.notes.split("|")[0].strip()

            st.markdown(
                f"**{i}. {p.selection}**  \n"
                f"`{p.market}` · {sport_tag} · Edge **{edge_str}** · SAD **{sad}** · Odds **{odds}**"
            )
            st.divider()

    if games:
        st.markdown("#### Today’s MLB Games")
        for g in games:
            pitchers = f"{g.probable_away_pitcher or 'TBD'} vs {g.probable_home_pitcher or 'TBD'}"
            st.markdown(
                f"**{g.away_team}** @ **{g.home_team}**  \n"
                f"_{pitchers}_ · {g.status or 'Scheduled'}"
            )
            st.divider()


def show_run_pipeline():
    st.markdown("#### Run Pipeline")
    st.caption("Pull all 5 sports → snapshot odds → score → store with timestamp")

    target_date = st.date_input("Date", value=date.today(), label_visibility="collapsed")

    if st.button("▶ Run Full Pipeline", type="primary", use_container_width=True):

        # 1. MLB Schedule
        with st.status("Pulling MLB schedule…", expanded=True) as status:
            try:
                games = get_todays_schedule(target_date.isoformat())
                st.write(f"Found **{len(games)}** MLB games")

                db = SessionLocal()
                saved = 0
                for g in games:
                    existing = db.query(Game).filter(Game.game_pk == g["game_pk"]).first()
                    if not existing:
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
                st.write(f"Saved **{saved}** new MLB games")
                status.update(label="MLB schedule done", state="complete")
            except Exception as e:
                status.update(label="MLB schedule failed", state="error")
                st.error(str(e))

        # 2. All sports odds + scoring
        with st.status("Pulling all sports + scoring…", expanded=True) as status:
            try:
                if not os.getenv("ODDS_API_KEY"):
                    st.warning("No ODDS_API_KEY set. Go to Settings.")
                    status.update(label="Skipped – no key", state="error")
                else:
                    all_odds = get_all_sports_odds()
                    total_events = sum(len(v) for v in all_odds.values())
                    st.write(f"**{total_events}** events across 5 sports")

                    all_preds = []
                    for sport, events in all_odds.items():
                        for event in events:
                            preds = score_moneyline_event(event, sport)
                            all_preds.extend(preds)
                        st.write(f"{sport}: {len(events)} games")

                    db = SessionLocal()
                    saved = 0
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
                            notes=f"{p['sport']} | {p.get('notes', '')}",
                        ))
                        saved += 1
                    db.commit()
                    db.close()

                    st.write(f"**{saved}** positive-edge picks saved")
                    status.update(label="All sports scored", state="complete")
            except Exception as e:
                status.update(label="Odds/scoring failed", state="error")
                st.error(str(e))

        st.success("Multi-sport pipeline finished.")


def show_predictions_log():
    st.markdown("#### Predictions Log")
    st.caption("Every pick stored with the exact odds at generation time.")

    db = SessionLocal()
    try:
        preds = db.query(Prediction).order_by(Prediction.prediction_time.desc()).limit(50).all()
    finally:
        db.close()

    if not preds:
        st.info("No predictions logged yet.")
        return

    for p in preds:
        time_str = p.prediction_time.strftime("%m/%d %H:%M") if p.prediction_time else "—"
        edge = f"{p.edge:+.1%}" if p.edge is not None else "—"
        st.markdown(
            f"**{p.selection}**  \n"
            f"{time_str} · `{p.market}` · Edge {edge} · Odds {p.odds_at_prediction or '—'} · {p.bookmaker or ''}"
        )
        st.divider()

    df = pd.DataFrame([{
        "time": p.prediction_time,
        "market": p.market,
        "selection": p.selection,
        "model_prob": p.model_prob,
        "edge": p.edge,
        "sad_score": p.sad_score,
        "odds": p.odds_at_prediction,
        "book": p.bookmaker,
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

    st.markdown("**The Odds API Key**")
    current = os.getenv("ODDS_API_KEY", "")
    if current:
        st.success(f"Key loaded · ends with …{current[-4:]}")
    else:
        st.warning("No key set yet")

    new_key = st.text_input(
        "Paste key",
        type="password",
        placeholder="Get free key at the-odds-api.com",
        label_visibility="collapsed",
    )

    if st.button("Save Key", use_container_width=True) and new_key.strip():
        env_path = Path(".env")
        content = f"ODDS_API_KEY={new_key.strip()}\n"
        if env_path.exists():
            lines = env_path.read_text().splitlines()
            updated = False
            for i, line in enumerate(lines):
                if line.startswith("ODDS_API_KEY="):
                    lines[i] = f"ODDS_API_KEY={new_key.strip()}"
                    updated = True
                    break
            if not updated:
                lines.append(f"ODDS_API_KEY={new_key.strip()}")
            content = "\n".join(lines) + "\n"
        env_path.write_text(content)
        st.success("Saved. Restart / redeploy the app for it to take effect.")
        st.rerun()

    st.divider()
    st.markdown("#### How to put this on your iPhone")
    st.markdown(
        """
1. Open this URL in **Safari**
2. Tap the **Share** button
3. Tap **Add to Home Screen**
4. Name it **SharpAfterDark** → Add
        """
    )

    st.divider()
    st.caption("SharpAfterDark Machine v1.1 · Multi-Sport · Engine first")


if __name__ == "__main__":
    main()
