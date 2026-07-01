#!/usr/bin/env python3
"""
Plotting module for LeetCode progress.

Wraps the ``plot_progress`` function from the original notebook, loading data
from the SQLite database created by ``scheduler.py``.
"""

import os
from datetime import datetime

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.lines import Line2D

from scheduler import DailyStats, engine

# Ensure the images directory exists
IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "img")
os.makedirs(IMG_DIR, exist_ok=True)


def load_data() -> pd.DataFrame:
    """Load daily stats from the SQLite DB into a DataFrame.

    Returns
    -------
    pd.DataFrame
        Columns: ``dt`` (date), ``user_rank`` (global ranking), ``num_problems`` (total problems solved).
    """
    query = (
        DailyStats.__table__.select()
        .order_by(DailyStats.response_ts)
    )
    df = pd.read_sql(query, engine)
    if df.empty:
        return df

    # Rename columns to match what plot_progress expects
    df = df.rename(
        columns={
            "response_ts": "dt",
            "rating": "user_rank",
            "total": "num_problems",
        }
    )
    df["dt"] = pd.to_datetime(df["dt"])
    return df


def plot_progress(
    df: pd.DataFrame,
    filename: str = "leetcode_progress.png",
) -> str:
    """Generate the LeetCode progress plot and save it.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain columns ``dt``, ``user_rank``, ``num_problems``.
    filename : str
        Output filename (saved under ``static/img/``).

    Returns
    -------
    str
        The relative URL path to the saved image (for embedding in HTML).
    """
    if df.empty:
        raise ValueError("No data to plot. Run a data fetch first.")

    df = df.sort_values("dt")

    df["rate_lag"] = df["user_rank"].shift(1)
    df["problem_lag"] = df["num_problems"].cumsum()
    df["rate_diff"] = df["rate_lag"] - df["user_rank"]
    df["rate_diff2"] = df["rate_diff"].cumsum()

    problems_solved = df["num_problems"].sum()
    pos_gained = int(df.iloc[0]["user_rank"] - df.iloc[-1]["user_rank"])

    savepath = os.path.join(IMG_DIR, filename)

    # ── FIGURE & LAYOUT SETUP ──
    plt.style.use("seaborn-v0_8")
    sns.set_palette("deep")

    fig = plt.figure(figsize=(12, 10))
    gs = fig.add_gridspec(2, 2)

    # ── TOP PLOT ──
    ax1 = fig.add_subplot(gs[0, :])
    sns.lineplot(
        x="dt", y="rate_diff2", data=df,
        ax=ax1, color="#007acc", linewidth=2.5, label="Rating",
    )
    ax1.set_ylabel("Positions Overtaken", fontsize=12, color="#007acc", weight="bold")
    ax1.tick_params(axis="y", labelcolor="#007acc", length=6, width=1.2)
    ax1.set_xlabel("Date", fontsize=12, weight="bold")

    date_form = mdates.DateFormatter("%d %b")
    ax1.xaxis.set_major_formatter(date_form)
    for label in ax1.get_xticklabels():
        label.set_rotation(30)

    ax2 = ax1.twinx()
    sns.lineplot(
        x="dt", y="problem_lag", data=df,
        ax=ax2, color="#d62728", linewidth=2.5, label="Problems Solved",
    )
    ax2.set_ylabel(
        "Problems Solved", fontsize=12, color="#d62728", weight="bold",
    )
    ax2.tick_params(axis="y", labelcolor="#d62728", length=6, width=1.2)

    ax1.set_title(
        "My LeetCode Progress",
        fontsize=16, weight="bold", color="darkslategray", pad=20,
    )

    leg1 = ax1.get_legend()
    if leg1 is not None:
        leg1.remove()
    leg2 = ax2.get_legend()
    if leg2 is not None:
        leg2.remove()

    legend_elements = [
        Line2D([0], [0], color="#007acc", lw=2.5, label="Positions Taken"),
        Line2D([0], [0], color="#d62728", lw=2.5, label="Problems Solved"),
    ]
    legend = ax1.legend(
        handles=legend_elements,
        loc="upper left",
        ncol=2,
        fontsize=11,
        frameon=True,
        fancybox=True,
        shadow=False,
        facecolor="white",
        edgecolor="gray",
    )
    legend.set_zorder(20)
    legend.get_frame().set_linewidth(1.2)

    ax1.grid(True, which="major", axis="x", linestyle="--", alpha=0.5)
    ax1.grid(True, which="major", axis="y", linestyle="-", alpha=0.3)
    ax1.set_axisbelow(True)

    # ── BOTTOM LEFT ──
    ax3 = fig.add_subplot(gs[1, 0])
    arrow_style = dict(
        arrowstyle="simple, tail_width=2.5, head_width=5, head_length=2.5",
        fc="#d62728",
        ec="#d62728",
        linewidth=0,
    )
    ax3.annotate(
        text=f"+{problems_solved} PROBLEMS SOLVED",
        xy=(0.5, 0.6),
        xytext=(0.5, 0.2),
        xycoords="axes fraction",
        textcoords="axes fraction",
        fontsize=24,
        fontweight="bold",
        ha="center",
        va="center",
        arrowprops=arrow_style,
    )
    ax3.set_xticks([])
    ax3.set_yticks([])
    for spine in ax3.spines.values():
        spine.set_visible(False)

    # ── BOTTOM RIGHT ──
    ax4 = fig.add_subplot(gs[1, 1])
    arrow_style = dict(
        arrowstyle="simple, tail_width=2.5, head_width=5, head_length=2.5",
        fc="#007acc",
        ec="#007acc",
        linewidth=0,
    )
    ax4.annotate(
        text=f"+{pos_gained} POS GAINED",
        xy=(0.5, 0.6),
        xytext=(0.5, 0.2),
        xycoords="axes fraction",
        textcoords="axes fraction",
        fontsize=24,
        fontweight="bold",
        ha="center",
        va="center",
        arrowprops=arrow_style,
    )
    ax4.set_xticks([])
    ax4.set_yticks([])
    for spine in ax4.spines.values():
        spine.set_visible(False)

    plt.tight_layout()
    plt.subplots_adjust(top=0.92, hspace=0.4)
    plt.savefig(savepath, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return f"static/img/{filename}"


def get_latest_stats() -> dict:
    """Return the most recent daily stats row as a dict."""
    df = load_data()
    if df.empty:
        return {}
    latest = df.iloc[-1].to_dict()
    latest["dt"] = str(latest["dt"])
    return latest


def get_summary_stats() -> dict:
    """Return aggregate statistics from all data."""
    df = load_data()
    if df.empty:
        return {"total_problems": 0, "days_tracked": 0, "rank_change": 0}

    total = int(df["num_problems"].sum())
    days = len(df)
    rank_change = int(df.iloc[0]["user_rank"] - df.iloc[-1]["user_rank"])
    best_rank = int(df["user_rank"].min())
    current_rank = int(df.iloc[-1]["user_rank"])

    return {
        "total_problems": total,
        "days_tracked": days,
        "rank_change": rank_change,
        "best_rank": best_rank,
        "current_rank": current_rank,
    }