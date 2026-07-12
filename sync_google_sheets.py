#!/usr/bin/env python3
"""
Sync data from a Google Spreadsheet into the local SQLite database.

Expects a spreadsheet with columns matching the DailyStats model:
    nickname, response_ts, rating, easy, medium, hard, total

Usage
-----
    python sync_google_sheets.py                  # insert-only
    python sync_google_sheets.py --upsert          # update existing rows
    python sync_google_sheets.py --sheet Sheet2    # different worksheet
"""

import json
import os
import sys
from datetime import datetime, timezone

import gspread
from google.oauth2.service_account import Credentials
from sqlalchemy.orm import Session

from scheduler import DailyStats, engine, init_db

# ── Configuration ────────────────────────────────────────────────────

SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(PROJECT_DIR, "google_credentials.json")
CONFIG_FILE = os.path.join(PROJECT_DIR, "config.json")


def load_config() -> dict:
    """Load config.json and return it as a dict."""
    if not os.path.exists(CONFIG_FILE):
        raise FileNotFoundError(
            f"{CONFIG_FILE} not found. Create it with a 'spreadsheet_key' field."
        )
    with open(CONFIG_FILE) as f:
        return json.load(f)


def get_worksheet(sheet_name: str = "Sheet1"):
    """Authenticate with Google Sheets and return a Worksheet object.

    Parameters
    ----------
    sheet_name : str
        Name of the worksheet/tab in the spreadsheet (default ``"Sheet1"``).

    Returns
    -------
    gspread.Worksheet

    Raises
    ------
    FileNotFoundError
        If ``google_credentials.json`` is missing.
    KeyError
        If ``config.json`` lacks a ``spreadsheet_key`` field.
    """
    if not os.path.exists(CREDENTIALS_FILE):
        raise FileNotFoundError(
            f"Google credentials file not found at {CREDENTIALS_FILE}. "
            "Download a service-account JSON key from Google Cloud Console."
        )

    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPE)
    client = gspread.authorize(creds)

    config = load_config()
    spreadsheet_key = config.get("spreadsheet_key")
    if not spreadsheet_key:
        raise KeyError(
            "Missing 'spreadsheet_key' in config.json. "
            "Set it to your Google Spreadsheet ID or URL."
        )

    # Open by URL or by key
    if spreadsheet_key.startswith("http://") or spreadsheet_key.startswith("https://"):
        sh = client.open_by_url(spreadsheet_key)
    else:
        sh = client.open_by_key(spreadsheet_key)

    return sh.worksheet(sheet_name)


def fetch_all_rows(worksheet) -> list[dict]:
    """Get all records from the worksheet as a list of dicts.

    The first row of the sheet is used as header / dict keys.
    """
    return worksheet.get_all_records()


def parse_row(row: dict) -> dict:
    """Convert a spreadsheet row dict into a dict suitable for ``DailyStats``.

    Adjust the column-name mapping below to match your spreadsheet headers.

    Parameters
    ----------
    row : dict
        A single row from ``get_all_records()``.

    Returns
    -------
    dict
        Keys match ``DailyStats`` column names.
    """
    # Parse the timestamp — try ISO format first, then fall back
    ts_raw = str(row.get("response_ts", ""))
    try:
        response_ts = datetime.fromisoformat(ts_raw)
    except (ValueError, TypeError):
        # If the sheet stores dates in a different format, handle it here
        response_ts = datetime.now(timezone.utc)

    return {
        "nickname": str(row.get("nickname", "")),
        "response_ts": response_ts,
        "rating": int(row.get("rating", 0)),
        "easy": int(row.get("easy", 0)),
        "medium": int(row.get("medium", 0)),
        "hard": int(row.get("hard", 0)),
        "total": int(row.get("total", 0)),
    }


def row_exists(session: Session, response_ts: datetime) -> bool:
    """Check whether a row with the given timestamp already exists."""
    return (
        session.query(DailyStats)
        .filter(DailyStats.response_ts == response_ts)
        .first()
        is not None
    )


def sync_from_sheets(sheet_name: str = "Sheet1", upsert: bool = False) -> int:
    """Download all rows from Google Sheets and insert missing ones into the DB.

    Parameters
    ----------
    sheet_name : str
        Name of the worksheet/tab in the spreadsheet (default ``"Sheet1"``).
    upsert : bool
        If ``True``, update existing rows when a matching ``response_ts`` is found.
        If ``False`` (default), skip duplicates.

    Returns
    -------
    int
        Number of rows inserted (or updated if ``upsert=True``).
    """
    init_db()
    worksheet = get_worksheet(sheet_name)
    records = fetch_all_rows(worksheet)

    print(f"Found {len(records)} rows in worksheet '{sheet_name}'.", file=sys.stderr)

    affected = 0
    with Session(engine) as session:
        for record in records:
            parsed = parse_row(record)
            exists = row_exists(session, parsed["response_ts"])

            if exists and upsert:
                # ── Update existing row ──────────────────────────────
                row = (
                    session.query(DailyStats)
                    .filter(DailyStats.response_ts == parsed["response_ts"])
                    .first()
                )
                for key, value in parsed.items():
                    setattr(row, key, value)
                session.commit()
                affected += 1

            elif not exists:
                # ── Insert new row ───────────────────────────────────
                row = DailyStats(**parsed)
                session.add(row)
                session.commit()
                affected += 1

    action = "Updated" if upsert else "Inserted"
    print(f"{action} {affected} row(s) from Google Sheets.", file=sys.stderr)
    return affected


# ── CLI entry point ──────────────────────────────────────────────────

def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Sync data from a Google Spreadsheet into the local SQLite DB."
    )
    parser.add_argument(
        "--sheet",
        default="Sheet1",
        help="Worksheet name (default: Sheet1)",
    )
    parser.add_argument(
        "--upsert",
        action="store_true",
        help="Update existing rows if a matching timestamp is found",
    )
    args = parser.parse_args()

    try:
        sync_from_sheets(sheet_name=args.sheet, upsert=args.upsert)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
