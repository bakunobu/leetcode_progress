# LeetCode Progress

Track your LeetCode activity automatically — fetches your daily accepted submissions (broken down by Easy / Medium / Hard) and global ranking, then persists them to a local SQLite database for historical tracking.

## How It Works

1. **[`utils.py`](utils.py)** — Queries LeetCode's GraphQL API for the configured user's global ranking and accepted submissions (AC) in the last 24 hours.
2. **[`scheduler.py`](scheduler.py)** — An [APScheduler](https://apscheduler.readthedocs.io/) blocking scheduler that runs once a day at **14:00 UTC+1**, calls `parse()` from `utils.py`, and stores the snapshot in a local SQLite database via SQLAlchemy.
3. **[`run_daily.py`](run_daily.py)** — A one-shot alternative for cron or manual ad-hoc runs. Fetches stats and persists them immediately, then exits.

## Setup

1. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

2. **Configure your LeetCode username:**

   Edit [`config.json`](config.json) and set your LeetCode user ID:

   ```json
   {"user_id": "your-leetcode-username"}
   ```

   If the file is missing or empty, it defaults to `bakunobu`.

## Usage

### Option A — Persistent scheduler

```bash
python scheduler.py
```

The script stays running and triggers every day at 14:00 UTC+1. Stats are appended to `data/leetcode_stats.db`.

### Option B — One-shot (cron / manual)

```bash
python run_daily.py
```

Fetches stats once and exits. Add a cron job to run this daily if you prefer not to keep the scheduler running.

Crontab example
```bash
crontab - e
```
Add string:
0 13 * * * cd ~/leetcode_progress && ~/leetcode_progress/venv/bin/python run_daily.py >> /var/log/leetcode-stats.log 2>&1

## Database

Snapshots are stored in [`data/leetcode_stats.db`](data/leetcode_stats.db) (SQLite). Each row contains:

| Column       | Description                           |
|--------------|---------------------------------------|
| `nickname`   | LeetCode username                     |
| `response_ts`| UTC timestamp of the fetch            |
| `rating`     | Global ranking at time of fetch       |
| `easy`       | Accepted submissions (Easy) — last 24h|
| `medium`     | Accepted submissions (Medium) — last 24h|
| `hard`       | Accepted submissions (Hard) — last 24h|
| `total`      | Sum of easy + medium + hard           |

## License

[MIT](LICENSE)