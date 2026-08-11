"""
Database setup and helpers for SharpAfterDark Machine.
Uses SQLite for v1 (easy local + phone access via hosted app).
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timezone
import os

Base = declarative_base()

# Default to local SQLite. Change DATABASE_URL for Postgres later.
# Use /tmp in restricted environments; otherwise use project data/ folder.
_default_db = "/tmp/sad_machine.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{_default_db}")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, index=True)
    game_pk = Column(Integer, unique=True, index=True)          # MLB gamePk
    game_date = Column(String, index=True)                      # YYYY-MM-DD
    commence_time = Column(DateTime)
    home_team = Column(String)
    away_team = Column(String)
    home_team_id = Column(Integer)
    away_team_id = Column(Integer)
    probable_home_pitcher = Column(String, nullable=True)
    probable_away_pitcher = Column(String, nullable=True)
    status = Column(String, default="Scheduled")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class OddsSnapshot(Base):
    __tablename__ = "odds_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    game_pk = Column(Integer, index=True)
    snapshot_time = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    bookmaker = Column(String)
    market = Column(String)          # h2h, spreads, totals
    outcome = Column(String)         # team name or Over/Under
    price = Column(Float)            # American odds
    point = Column(Float, nullable=True)  # for spreads/totals
    raw_json = Column(JSON, nullable=True)


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    game_pk = Column(Integer, index=True)
    prediction_time = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    market = Column(String)                  # moneyline, run_line, total
    selection = Column(String)               # e.g. "NYY", "Over 8.5"
    model_prob = Column(Float)
    market_implied_prob = Column(Float)
    edge = Column(Float)                     # model_prob - market_implied
    sad_score = Column(Float)                # final ranking score
    odds_at_prediction = Column(Float)       # American odds when pick was made
    bookmaker = Column(String, nullable=True)
    features_used = Column(JSON, nullable=True)
    model_version = Column(String, default="v1.0")
    notes = Column(Text, nullable=True)


class Result(Base):
    __tablename__ = "results"

    id = Column(Integer, primary_key=True, index=True)
    prediction_id = Column(Integer, index=True)
    game_pk = Column(Integer, index=True)
    result = Column(String)                  # win / loss / push
    actual_score_home = Column(Integer, nullable=True)
    actual_score_away = Column(Integer, nullable=True)
    settled_at = Column(DateTime, nullable=True)
    closing_odds = Column(Float, nullable=True)
    clv = Column(Float, nullable=True)       # Closing Line Value


def init_db():
    """Create all tables."""
    os.makedirs("data", exist_ok=True)
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()