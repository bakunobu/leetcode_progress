# LeetCode Progress

A FastAPI application that tracks daily LeetCode statistics and displays your coding progress over the last calendar week and the last 30 days.

## Overview

This project stores daily LeetCode stats (rating, and numbers of easy/medium/hard problems solved) in an SQLite database, then exposes them through a small web dashboard built with FastAPI.

## Features

- **Main dashboard** (`/`) — an HTML page showing your nickname, weekly and 30-day summary cards, and detailed daily tables
- **Weekly progress API** (`/progress/week`) — JSON stats for the current calendar week (Monday–Sunday)
- **30-day progress API** (`/progress/30days`) — JSON stats for the trailing 30 days
- **Dark-themed, responsive UI** with difficulty color coding (easy = green, medium = yellow, hard = red)

## Project Structure

```
.
├── main.py                 # FastAPI application
├── insert_daily_stats.py   # Helper script to populate the daily_stats table
├── templates/
│   └── index.html          # Main dashboard template
├── data/
│   └── leetcode_stats.db   # SQLite database
├── venv/                   # Python virtual environment (gitignored)
├── .env                    # Environment variables (gitignored)
└── .gitignore
```

## Database Schema

The `daily_stats` table stores one row per day:

| Column         | Type     | Description                          |
|----------------|----------|--------------------------------------|
| `id`           | INTEGER  | Primary key                          |
| `nickname`     | VARCHAR  | LeetCode username                    |
| `response_ts`  | DATETIME | Timestamp of the record              |
| `rating`       | INTEGER  | LeetCode rating on that day          |
| `easy`         | INTEGER  | Easy problems solved                 |
| `medium`       | INTEGER  | Medium problems solved               |
| `hard`         | INTEGER  | Hard problems solved                 |
| `total`        | INTEGER  | Total problems solved                |

## Installation

```bash
# 1. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt  # fastapi, uvicorn, jinja2
```

## Usage

### Populate the database

Use the helper script to load pipe-delimited data into the `daily_stats` table:

```bash
python insert_daily_stats.py
```

The script accepts rows in the format:
`id|nickname|response_ts|rating|easy|medium|hard|total`

It uses `INSERT OR REPLACE`, so re-running it is safe (existing rows are overwritten by primary key).

### Run the server

```bash
uvicorn main:api --host 0.0.0.0 --port 8000
```

Then open the dashboard at `http://localhost:8000`.

## API Endpoints

| Method | Path                  | Description                                  |
|--------|-----------------------|----------------------------------------------|
| GET    | `/`                   | HTML dashboard with weekly + 30-day stats    |
| GET    | `/progress/week`      | JSON stats for the current calendar week     |
| GET    | `/progress/30days`    | JSON stats for the trailing 30 days          |

### Example response (`/progress/week`)

```json
{
  "period": "last_calendar_week",
  "start": "2026-08-17T00:00:00+00:00",
  "end": "2026-08-23T23:59:59.999999+00:00",
  "days_with_data": 5,
  "stats": [
    {
      "id": 52,
      "nickname": "bakunobu",
      "response_ts": "2026-08-23 00:00:05.384657",
      "rating": 61292,
      "easy": 1,
      "medium": 1,
      "hard": 0,
      "total": 2
    }
  ]
}