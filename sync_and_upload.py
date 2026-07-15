#!/usr/bin/env python3
"""
Sync from Google Sheets and upload a filtered batch to a remote SQLite DB.

Combines two operations into one process:
1. Download rows from a Google Spreadsheet into the local SQLite DB.
2. Upload a filtered subset (by count and/or age) to a remote SQLite DB
   by piping SQL ``INSERT`` statements over SSH to the remote ``sqlite3`` CLI.

Batch-limiting options
----------------------
* ``--max-records N``   — upload only the last *N* records.
* ``--max-age N``       — upload only records newer than *N* hours.
  If both are given, records must satisfy **both** conditions.

Usage
-----
::

    # Upload the last 50 records (no time filter)
    python sync_and_upload.py --max-records 50

    # Upload records from the last 24 hours (no count limit)
    python sync_and_upload.py --max-age 24

    # Both filters combined
    python sync_and_upload.py --max-records 50 --max-age 24

    # Upsert mode (update existing rows on remote)
    python sync_and_upload.py --max-records 100 --upsert

    # Full control
    python sync_and_upload.py \\
        --sheet Sheet1 --upsert \\
        --max-records 100 --max-age 48 \\
        --host myserver.com --port 2222 --username deploy \\
        --remote-db /home/deploy/data/leetcode_stats.db \\
        --key ~/.ssh/deploy_key
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from scheduler import DailyStats, engine, init_db
from sync_google_sheets import sync_from_sheets
from upload_to_remote import (
    load_config as load_remote_config,
    upload_records_via_sql_pipe,
)

# ── Configuration ────────────────────────────────────────────────────

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(PROJECT_DIR, "config.json")


def load_config() -> dict:
    """Load and return the full ``config.json`` as a dict."""
    if not os.path.exists(CONFIG_FILE):
        raise FileNotFoundError(f"{CONFIG_FILE} not found.")
    with open(CONFIG_FILE) as f:
        return json.load(f)


# ── Batch query ──────────────────────────────────────────────────────


def query_batch(
    max_records: int | None = None,
    max_age_hours: int | None = None,
) -> list[dict]:
    """Query the local DB for records matching the batch criteria.

    Parameters
    ----------
    max_records : int | None
        Maximum number of records to return (newest first).
        ``None`` means no limit.
    max_age_hours : int | None
        Only return records newer than this many hours.
        ``None`` means no time filter.

    Returns
    -------
    list[dict]
        Records as dicts with keys matching ``DailyStats`` columns,
        ordered by ``response_ts DESC``.
    """
    init_db()

    query = (
        Session(engine)
        .query(DailyStats)
        .order_by(DailyStats.response_ts.desc())
    )

    if max_age_hours is not None and max_age_hours > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        query = query.filter(DailyStats.response_ts >= cutoff)

    if max_records is not None and max_records > 0:
        query = query.limit(max_records)

    rows = query.all()

    # Convert ORM objects to plain dicts
    return [
        {
            "nickname": row.nickname,
            "response_ts": row.response_ts,
            "rating": row.rating,
            "easy": row.easy,
            "medium": row.medium,
            "hard": row.hard,
            "total": row.total,
        }
        for row in rows
    ]


# ── Combined process ─────────────────────────────────────────────────


def sync_and_upload(
    sheet_name: str = "Sheet1",
    upsert: bool = False,
    max_records: int | None = None,
    max_age_hours: int | None = None,
    host: str | None = None,
    port: int | None = None,
    username: str | None = None,
    remote_db_path: str | None = None,
    key_filename: str | None = None,
    verbose: bool = True,
) -> int:
    """Download from Google Sheets, then upload filtered records to remote.

    This is the main entry point that combines both operations.

    Parameters
    ----------
    sheet_name : str
        Worksheet name in the Google Spreadsheet (default ``"Sheet1"``).
    upsert : bool
        If ``True``, update existing rows on both local and remote DBs
        when a matching ``response_ts`` is found.
    max_records : int | None
        Maximum number of records to upload (newest first).
        ``None`` = no limit.
    max_age_hours : int | None
        Only upload records newer than this many hours.
        ``None`` = no time filter.
    host : str | None
        Remote hostname or IP. Falls back to ``config.json``.
    port : int | None
        SSH port. Falls back to ``config.json`` (default 22).
    username : str | None
        SSH username. Falls back to ``config.json``.
    remote_db_path : str | None
        Absolute path to SQLite DB on the remote server.
        Falls back to ``config.json`` → ``remote.remote_db_path``.
    key_filename : str | None
        SSH private key path. Falls back to ``config.json``.
    verbose : bool
        Print progress to stderr.

    Returns
    -------
    int
        Number of records uploaded to the remote server.
        Returns ``0`` if no records matched the batch criteria.

    Raises
    ------
    FileNotFoundError
        If ``config.json`` is missing.
    KeyError
        If required remote config fields are missing.
    """
    # ── Step 1: Sync from Google Sheets ────────────────────────────
    if verbose:
        print("Step 1: Syncing from Google Sheets …", file=sys.stderr)

    try:
        synced = sync_from_sheets(sheet_name=sheet_name, upsert=upsert)
    except Exception as exc:
        print(f"Google Sheets sync failed: {exc}", file=sys.stderr)
        raise

    if verbose:
        print(f"  Synced {synced} row(s) from Google Sheets.", file=sys.stderr)

    # ── Step 2: Query local DB for batch ───────────────────────────
    if verbose:
        filters = []
        if max_records:
            filters.append(f"max_records={max_records}")
        if max_age_hours:
            filters.append(f"max_age_hours={max_age_hours}")
        filter_desc = ", ".join(filters) if filters else "no filter (all records)"
        print(f"Step 2: Querying local DB ({filter_desc}) …", file=sys.stderr)

    records = query_batch(
        max_records=max_records,
        max_age_hours=max_age_hours,
    )

    if not records:
        print(
            "No records match the batch criteria. Nothing to upload.",
            file=sys.stderr,
        )
        return 0

    if verbose:
        print(f"  Found {len(records)} record(s) to upload.", file=sys.stderr)

    # ── Step 3: Resolve remote config ──────────────────────────────
    config = load_config()
    remote_cfg = config.get("remote", {})

    host = host or remote_cfg.get("host")
    port = port if port is not None else remote_cfg.get("port", 22)
    username = username or remote_cfg.get("username")
    remote_db_path = remote_db_path or remote_cfg.get("remote_db_path")
    key_filename = key_filename or remote_cfg.get("key_filename")

    # Validate required fields
    missing = []
    if not host:
        missing.append("host")
    if not username:
        missing.append("username")
    if not remote_db_path:
        missing.append("remote_db_path (set remote.remote_db_path in config.json)")

    if missing:
        raise KeyError(
            f"Missing required remote config fields: {', '.join(missing)}. "
            f"Set them in config.json or pass as arguments."
        )

    # ── Step 4: Upload via SQL-pipe ────────────────────────────────
    if verbose:
        print(
            f"Step 3: Uploading {len(records)} record(s) to "
            f"{username}@{host}:{remote_db_path} …",
            file=sys.stderr,
        )

    success = upload_records_via_sql_pipe(
        records=records,
        remote_db_path=remote_db_path,
        host=host,
        username=username,
        port=port,
        key_filename=key_filename,
        table_name="daily_stats",
        upsert=upsert,
        verbose=verbose,
    )

    if not success:
        raise RuntimeError("SQL-pipe upload failed — check remote server and SSH config.")

    if verbose:
        print(
            f"Done. Uploaded {len(records)} record(s) to remote DB.",
            file=sys.stderr,
        )

    return len(records)


# ── CLI entry point ──────────────────────────────────────────────────


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Sync from Google Sheets and upload a filtered batch "
            "to a remote SQLite DB via SSH."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s --max-records 50\n"
            "  %(prog)s --max-age 24\n"
            "  %(prog)s --max-records 100 --max-age 48 --upsert\n"
        ),
    )

    # ── Google Sheets options ──────────────────────────────────────
    parser.add_argument(
        "--sheet",
        default="Sheet1",
        help="Worksheet name in Google Spreadsheet (default: Sheet1)",
    )
    parser.add_argument(
        "--upsert",
        action="store_true",
        help="Update existing rows on both local and remote DBs",
    )

    # ── Batch filter options ───────────────────────────────────────
    parser.add_argument(
        "--max-records",
        type=int,
        default=None,
        help="Maximum number of records to upload (newest first)",
    )
    parser.add_argument(
        "--max-age",
        dest="max_age_hours",
        type=int,
        default=None,
        help="Only upload records newer than N hours",
    )

    # ── Remote connection options ──────────────────────────────────
    parser.add_argument("--host", help="Remote hostname or IP (overrides config)")
    parser.add_argument("--port", type=int, default=None, help="SSH port (default: 22)")
    parser.add_argument("--username", help="SSH username (overrides config)")
    parser.add_argument(
        "--remote-db",
        dest="remote_db_path",
        help="Remote SQLite DB path (overrides config)",
    )
    parser.add_argument(
        "--key",
        dest="key_filename",
        help="SSH private key file path (overrides config)",
    )

    # ── General options ────────────────────────────────────────────
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )

    args = parser.parse_args()

    try:
        count = sync_and_upload(
            sheet_name=args.sheet,
            upsert=args.upsert,
            max_records=args.max_records,
            max_age_hours=args.max_age_hours,
            host=args.host,
            port=args.port,
            username=args.username,
            remote_db_path=args.remote_db_path,
            key_filename=args.key_filename,
            verbose=not args.quiet,
        )
        print(f"Uploaded {count} record(s).")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
