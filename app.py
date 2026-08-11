"""
SharpAfterDark Machine v1 — MLB
Mobile-first Streamlit app designed for iPhone (Add to Home Screen).
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime, timezone
import os
from pathlib import Path

from utils.db import init_db, SessionLocal, Game, Prediction, OddsSnapshot
from utils.mlb_data import get_todays_schedule
from utils.odds_data import get_mlb_odds, snapshot_odds_for_db

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
        "About": "SharpAfterDark Machine v1 — MLB engine"
    }
)

init_db()

# ──────────────────────────────────────────────
# Dark mobile CSS
# ──────────────────────────────────────────────
st.markdown("""
<style>
    /* Hide Streamlit chrome for cleaner app feel */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Dark background */
    .stApp {
        background-color: #0a0a0a;
        color: #e5e5e5;
    }
    
    /* Tighter mobile padding */
    .block-container {
        padding-top: 0.8rem !important;
        padding-bottom: 5rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        max-width: 480px;
    }
    
    /* Typography */
    h1 { font-size: 1.45rem !important; font-weight: 700 !important; margin-bottom: 0.2rem !important; color: #f5f5f5 !important; }
    h2, h3 { font-size: 1.15rem !important; color: #e5e5e5 !important; }
    p, label, .stMarkdown { color: #d4d4d4 !important; }
    
    /* Full-width buttons with good touch targets */
    .stButton > button {
        width: 100%;
        min-height: 48px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 1rem;
        border: none;
    }
    
    /* Primary button */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #7c3aed, #4f46e5);
        color: white;
    }
    
    /* Cards / info boxes */
    .stAlert {
        border-radius: 12px;
        border: 1px solid #262626;
    }
    
    /* Dataframes */
    .stDataFrame {
        border-radius: 10px;
        overflow: hidden;
    }
    
    /* Radio / navigation */
    div[role="radiogroup"] label {
        background: #171717;
        border-radius: 10px;
        padding: 10px 14px !important;
        margin-bottom: 6px;
        border: 1px solid #262626;
    }
    
    /* Bottom safe area for iPhone home indicator */
    .bottom-nav-spacer {
        height: 20px;
    }
</style>
""", unsafe_allow_html=True)


def main():
    # Top bar
    st.markdown("### 🌑 SharpAfterDark")
    st.caption("MLB Machine v1")

    # Bottom-style navigation using radio (works well on phone)
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

    # Stats row
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
        for i, p in enumerate(preds[:12], 1):
            edge_str = f"{p.edge:+.1%}" if p.edge is not None else "—"
            sad = f"{p.sad_score:.2f}" if p.sad_score is not None else "—"
            odds = p.odds_at_prediction if p.odds_at_prediction else "—"

            st.markdown(
                f"**{i}. {p.selection}**  \n"
                f"`{p.market}` · Edge **{edge_str}** · SAD **{sad}** · Odds **{odds}**"
            )
            st.divider()

    # Today’s games
    if games:
        st.markdown("#### Today’s Games")
        for g in games:
            pitchers = f"{g.probable_away_pitcher or 'TBD'} vs {g.probable_home_pitcher or 'TBD'}"
            st.markdown(
                f"**{g.away_team}** @ **{g.home_team}**  \n"
                f"_{pitchers}_ · {g.status or 'Scheduled'}"
            )
            st.divider()


def show_run_pipeline():
    st.markdown("#### Run Pipeline")
    st.caption("Pull schedule → snapshot odds → store with timestamp")

    target_date = st.date_input("Date", value=date.today(), label_visibility="collapsed")

    if st.button("▶ Run Full Pipeline", type="primary", use_container_width=True):
        # 1. Schedule
        with st.status("Pulling MLB schedule…", expanded=True) as status:
            try:
                games = get_todays_schedule(target_date.isoformat())
                st.write(f"Found **{len(games)}** games")

                db = SessionLocal()
                saved = 0
                for g in games:
                    existing = db.query(Game).filter(Game.game_pk == g["game_pk"]).first()
                    if not existing:
                        db.add(
                            Game(
                                game_pk=g["game_pk"],
                                game_date=g["game_date"],
                                home_team=g["home_team"],
                                away_team=g["away_team"],
                                home_team_id=g["home_team_id"],
                                away_team_id=g["away_team_id"],
                                probable_home_pitcher=g.get("probable_home_pitcher"),
                                probable_away_pitcher=g.get("probable_away_pitcher"),
                                status=g.get("status"),
                            )
                        )
                        saved += 1
                db.commit()
                db.close()
                st.write(f"Saved **{saved}** new games")
                status.update(label="Schedule done", state="complete")
            except Exception as e:
                status.update(label="Schedule failed", state="error")
                st.error(str(e))
                return

        # 2. Odds
        with st.status("Snapshotting odds…", expanded=True) as status:
            try:
                if not os.getenv("ODDS_API_KEY"):
                    st.warning("No ODDS_API_KEY set. Go to Settings and add your key.")
                    status.update(label="Odds skipped (no key)", state="error")
                else:
                    odds = get_mlb_odds()
                    rows = snapshot_odds_for_db(odds)
                    st.write(f"**{len(odds)}** events · **{len(rows)}** lines captured")
                    status.update(label="Odds snapshot complete", state="complete")
            except Exception as e:
                status.update(label="Odds failed", state="error")
                st.error(str(e))

        st.success("Pipeline finished. Probability model layer comes next.")

        # Quick preview
        if "games" in locals() and games:
            st.markdown("#### Games pulled")
            for g in games[:8]:
                st.markdown(f"• {g['away_team']} @ {g['home_team']}")


def show_predictions_log():
    st.markdown("#### Predictions Log")
    st.caption("Every pick is stored with the exact odds at the moment it was generated.")

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

    # Download
    df = pd.DataFrame(
        [
            {
                "time": p.prediction_time,
                "market": p.market,
                "selection": p.selection,
                "model_prob": p.model_prob,
                "edge": p.edge,
                "sad_score": p.sad_score,
                "odds": p.odds_at_prediction,
                "book": p.bookmaker,
            }
            for p in preds
        ]
    )
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
1. Open this URL in **Safari** (not Chrome)
2. Tap the **Share** button (square with arrow)
3. Scroll down and tap **Add to Home Screen**
4. Name it **SharpAfterDark** → Add

It will now open full-screen like a real app.
        """
    )

    st.divider()
    st.caption("SharpAfterDark Machine v1 · Engine first · No auto-posting")


if __name__ == "__main__":
    main()
