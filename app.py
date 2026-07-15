#!/usr/bin/env python3
"""
Web dashboard for LeetCode Progress.

Provides a simple Flask-based UI to:
- View latest stats and history
- Generate the progress plot via ``plot_progress()``
- Trigger a fresh data fetch from LeetCode
"""

import os
import sys
from datetime import datetime, timezone

from flask import Flask, redirect, render_template, request, url_for

from plot_progress import (
    get_latest_stats,
    get_summary_stats,
    load_data,
    plot_progress,
)
from scheduler import init_db, save_stats
from utils import parse

app = Flask(__name__)

# Ensure database is initialised
init_db()


# ── Routes ──────────────────────────────────────────────────────────


@app.route("/")
def index():
    """Dashboard home — show latest stats and history table."""
    latest = get_latest_stats()
    summary = get_summary_stats()
    df = load_data()

    # Convert DataFrame to a list of dicts for the template
    history = []
    if not df.empty:
        df_sorted = df.sort_values("dt", ascending=False)
        history = df_sorted.head(50).to_dict("records")
        # Convert Timestamps to strings
        for row in history:
            row["dt"] = str(row["dt"])

    return render_template(
        "index.html",
        latest=latest,
        summary=summary,
        history=history,
    )


@app.route("/plot")
def plot():
    """Generate and display the progress plot."""
    df = load_data()
    if df.empty:
        return render_template("plot.html", plot_url=None, error="No data available. Fetch stats first.")

    try:
        plot_url = plot_progress(df)
        return render_template("plot.html", plot_url=plot_url, error=None)
    except Exception as exc:
        return render_template("plot.html", plot_url=None, error=str(exc))


@app.route("/refresh")
def refresh():
    """Fetch fresh stats from LeetCode and save them."""
    try:
        nickname, response_ts_str, ranking, easy, medium, hard, total = parse()
        ts = datetime.fromisoformat(response_ts_str)
        save_stats(nickname, ts, ranking, easy, medium, hard, total)
        return redirect(url_for("index"))
    except Exception as exc:
        return render_template(
            "index.html",
            latest={},
            summary=get_summary_stats(),
            history=[],
            error=f"Failed to fetch stats: {exc}",
        )


@app.route("/sync-sheets")
def sync_sheets():
    """Download data from Google Sheets and update the local DB."""
    try:
        from sync_google_sheets import sync_from_sheets

        count = sync_from_sheets()
        return redirect(url_for("index"))
    except Exception as exc:
        return render_template(
            "index.html",
            latest={},
            summary=get_summary_stats(),
            history=[],
            error=f"Google Sheets sync failed: {exc}",
        )


@app.route("/upload-remote")
def upload_remote():
    """Upload the local SQLite DB to the remote server via SCP."""
    try:
        from upload_to_remote import upload_to_remote

        success = upload_to_remote()
        if not success:
            raise RuntimeError("Upload returned False — check config and remote server.")
        return redirect(url_for("index"))
    except Exception as exc:
        return render_template(
            "index.html",
            latest={},
            summary=get_summary_stats(),
            history=[],
            error=f"Remote upload failed: {exc}",
        )


@app.route("/sync-and-upload")
def sync_and_upload():
    """Sync from Google Sheets, then upload filtered records to remote.

    Accepts optional query parameters for batch limiting:
    * ``max_records`` — only upload the last N records.
    * ``max_age_hours`` — only upload records newer than N hours.
    * ``upsert`` — set to ``1`` to update existing rows.

    If no batch parameters are given, defaults from ``config.json``
    (``remote.batch``) are used.
    """
    try:
        from sync_and_upload import sync_and_upload as combined_process

        # Read query parameters (optional)
        max_records = request.args.get("max_records", type=int, default=None)
        max_age_hours = request.args.get("max_age_hours", type=int, default=None)
        upsert = request.args.get("upsert", type=str, default="") == "1"

        count = combined_process(
            max_records=max_records,
            max_age_hours=max_age_hours,
            upsert=upsert,
        )
        return redirect(url_for("index"))
    except Exception as exc:
        return render_template(
            "index.html",
            latest={},
            summary=get_summary_stats(),
            history=[],
            error=f"Sync + upload failed: {exc}",
        )


# ── CLI entry point ────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    print(f"Starting LeetCode Progress Dashboard on http://127.0.0.1:{port}", file=sys.stderr)
    app.run(host="0.0.0.0", port=port, debug=debug)