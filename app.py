def show_run_pipeline():
    st.markdown("#### Run Pipeline")
    st.caption("Pull all 5 sports → snapshot odds → score → store with timestamp")

    target_date = st.date_input("Date", value=date.today(), label_visibility="collapsed")

    if st.button("▶ Run Full Pipeline", type="primary", use_container_width=True):

        # 1. MLB Schedule (still useful for pitchers)
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
                    from scoring import score_moneyline_event
                    from odds_data import get_all_sports_odds

                    all_odds = get_all_sports_odds()
                    total_events = sum(len(v) for v in all_odds.values())
                    st.write(f"**{total_events}** events across 5 sports")

                    all_preds = []
                    for sport, events in all_odds.items():
                        for event in events:
                            preds = score_moneyline_event(event, sport)
                            all_preds.extend(preds)
                        st.write(f"{sport}: {len(events)} games → scored")

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
