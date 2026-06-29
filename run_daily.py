#!/usr/bin/env python3
"""
One-shot LeetCode stats fetcher.

Fetches today's LeetCode stats via utils.parse() and persists them to the
SQLite database used by scheduler.py, then exits.

Intended for use with cron or manual ad-hoc runs.
"""

import os
import sys
from datetime import datetime, timezone

from scheduler import init_db, save_stats
from utils import parse


def main() -> int:
    """Fetch and save one daily snapshot."""
    init_db()

    nickname, response_ts_str, ranking, easy, medium, hard, total = parse()

    # The timestamp from parse() is an ISO string; convert to aware datetime.
    try:
        ts = datetime.fromisoformat(response_ts_str)
    except ValueError:
        ts = datetime.now(timezone.utc)

    save_stats(nickname, ts, ranking, easy, medium, hard, total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
