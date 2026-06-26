#!/usr/bin/env python3
"""
Daily LeetCode stats scheduler.

Runs once a day at 14:00 UTC+1 (13:00 UTC), calls the ``parse()``
function from ``utils.py``, and persists the result to a local SQLite
database via SQLAlchemy.
"""

import os
import sys
from datetime import datetime, timezone

from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session

# Ensure the 'data' directory exists next to this script
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "leetcode_stats.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, echo=False)


# ── ORM model ───────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


class DailyStats(Base):
    """One row per daily snapshot."""

    __tablename__ = "daily_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nickname = Column(String, nullable=False)
    response_ts = Column(DateTime(timezone=True), nullable=False)
    rating = Column(Integer, nullable=False, default=0)
    easy = Column(Integer, nullable=False, default=0)
    medium = Column(Integer, nullable=False, default=0)
    hard = Column(Integer, nullable=False, default=0)
    total = Column(Integer, nullable=False, default=0)


def init_db():
    """Create tables if they do not already exist."""
    Base.metadata.create_all(engine)


def save_stats(nickname, response_ts, rating, easy, medium, hard, total):
    """Insert a new DailyStats row and commit."""
    with Session(engine) as session:
        row = DailyStats(
            nickname=nickname,
            response_ts=response_ts,
            rating=rating,
            easy=easy,
            medium=medium,
            hard=hard,
            total=total,
        )
        session.add(row)
        session.commit()
        print(
            f"[{response_ts}] Saved: {nickname} "
            f"rating={rating} "
            f"e={easy} m={medium} h={hard} t={total}",
            file=sys.stderr,
        )


def job():
    """Fetch today's LeetCode stats and persist them."""
    from utils import parse

    nickname, response_ts_str, rating, easy, medium, hard, total = parse()

    # The timestamp from parse() is an ISO string; convert to aware datetime.
    try:
        ts = datetime.fromisoformat(response_ts_str)
    except ValueError:
        ts = datetime.now(timezone.utc)

    save_stats(nickname, ts, rating, easy, medium, hard, total)


def main():
    init_db()
    print(f"Database ready at {DB_PATH}", file=sys.stderr)

    scheduler = BlockingScheduler(timezone="Europe/Berlin")  # UTC+1 / UTC+2

    # Schedule daily at 14:00 local time (UTC+1 in winter, UTC+2 in summer)
    scheduler.add_job(job, "cron", hour=14, minute=0)

    print("Scheduler started. Waiting for 14:00 UTC+1 …", file=sys.stderr)

    # Run the job once immediately on startup (optional, for testing).
    job()

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("Scheduler stopped.", file=sys.stderr)


if __name__ == "__main__":
    main()
