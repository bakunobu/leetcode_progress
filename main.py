from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import sqlite3
from datetime import datetime, timedelta, timezone

DB_PATH = "data/leetcode_stats.db"

api = FastAPI()
templates = Jinja2Templates(directory="templates")


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_start_of_week(ref: datetime) -> datetime:
    """Return midnight Monday of the calendar week containing ref."""
    days_since_monday = ref.weekday()
    start = ref.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_since_monday)
    return start


def get_end_of_week(ref: datetime) -> datetime:
    """Return 23:59:59 Sunday of the calendar week containing ref."""
    start = get_start_of_week(ref)
    end = start + timedelta(days=7) - timedelta(microseconds=1)
    return end


def fetch_stats(start_dt: datetime, end_dt: datetime):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, nickname, response_ts, rating, easy, medium, hard, total
        FROM daily_stats
        WHERE response_ts >= ? AND response_ts <= ?
        ORDER BY response_ts ASC
        """,
        (start_dt.isoformat(), end_dt.isoformat()),
    )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def aggregate_stats(rows: list) -> dict:
    """Aggregate easy/medium/hard/total counts and latest rating."""
    easy = sum(r["easy"] for r in rows)
    medium = sum(r["medium"] for r in rows)
    hard = sum(r["hard"] for r in rows)
    total = sum(r["total"] for r in rows)
    current_rating = rows[-1]["rating"] if rows else 0
    return {
        "easy": easy,
        "medium": medium,
        "hard": hard,
        "total": total,
        "current_rating": current_rating,
        "days_with_data": len(rows),
    }


@api.get("/")
def index(request: Request):
    now = datetime.now(timezone.utc)

    # Week stats
    week_start = get_start_of_week(now)
    week_end = get_end_of_week(now)
    week_rows = fetch_stats(week_start, week_end)
    week_agg = aggregate_stats(week_rows)

    # 30-day stats
    month_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    month_start = month_end - timedelta(days=30)
    month_rows = fetch_stats(month_start, month_end)
    month_agg = aggregate_stats(month_rows)

    nickname = month_rows[0]["nickname"] if month_rows else "bakunobu"

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request,
            "nickname": nickname,
            "now": now.strftime("%Y-%m-%d %H:%M UTC"),
            "week": {
                **week_agg,
                "start": week_start.strftime("%Y-%m-%d"),
                "end": week_end.strftime("%Y-%m-%d"),
                "stats": week_rows,
            },
            "month": {
                **month_agg,
                "start": month_start.strftime("%Y-%m-%d"),
                "end": month_end.strftime("%Y-%m-%d"),
                "stats": month_rows,
            },
        },
    )


@api.get("/progress/week")
def progress_week():
    now = datetime.now(timezone.utc)
    start = get_start_of_week(now)
    end = get_end_of_week(now)
    rows = fetch_stats(start, end)

    return {
        "period": "last_calendar_week",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "days_with_data": len(rows),
        "stats": rows,
    }


@api.get("/progress/30days")
def progress_30days():
    now = datetime.now(timezone.utc)
    end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    start = end - timedelta(days=30)
    rows = fetch_stats(start, end)

    return {
        "period": "last_30_days",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "days_with_data": len(rows),
        "stats": rows,
    }