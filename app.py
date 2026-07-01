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


# ── CLI entry point ────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    print(f"Starting LeetCode Progress Dashboard on http://127.0.0.1:{port}", file=sys.stderr)
    app.run(host="0.0.0.0", port=port, debug=debug)