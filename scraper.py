#!/usr/bin/env python3
"""
LeetCode daily stats scraper.
Fetches contest rating and problem counts from LeetCode's public GraphQL API
and appends the result to data.json.
"""

import json
import os
import sys
from datetime import date
from urllib.request import Request, urlopen
from urllib.error import URLError

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")
GRAPHQL_URL = "https://leetcode.com/graphql"


def load_config():
    """Load user_id from config.json. Create with defaults if missing."""
    if not os.path.exists(CONFIG_FILE):
        config = {"user_id": "bakunobu"}
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)
        return config["user_id"]

    with open(CONFIG_FILE) as f:
        config = json.load(f)
    return config.get("user_id", "bakunobu")


def load_existing_data():
    """Load existing records from data.json."""
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


TIMEOUT = 15  # seconds


def graphql_request(query, variables):
    """Send a GraphQL request and return the JSON response."""
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    req = Request(
        GRAPHQL_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    resp = urlopen(req, timeout=TIMEOUT)
    return json.loads(resp.read().decode("utf-8"))


def fetch_stats(username):
    """Fetch contest rating and solved counts for a LeetCode user."""
    rating_query = """
    query userContestRanking($username: String!) {
        userContestRanking(username: $username) {
            rating
        }
    }
    """

    solved_query = """
    query matchedUser($username: String!) {
        matchedUser(username: $username) {
            submitStats {
                acSubmissionNum {
                    difficulty
                    count
                }
            }
        }
    }
    """

    errors = []

    # Fetch rating
    try:
        rating_data = graphql_request(rating_query, {"username": username})
        ranking = rating_data.get("data", {}).get("userContestRanking")
        rating = int(ranking["rating"]) if ranking else 0
    except (URLError, KeyError, TypeError, ValueError) as e:
        errors.append(f"rating: {e}")
        rating = 0

    # Fetch solved counts
    try:
        solved_data = graphql_request(solved_query, {"username": username})
        ac_list = (
            solved_data.get("data", {})
            .get("matchedUser", {})
            .get("submitStats", {})
            .get("acSubmissionNum", [])
        )
        counts = {item["difficulty"]: item["count"] for item in ac_list}
        easy = counts.get("Easy", 0)
        medium = counts.get("Medium", 0)
        hard = counts.get("Hard", 0)
    except (URLError, KeyError, TypeError, ValueError) as e:
        errors.append(f"solved counts: {e}")
        easy = medium = hard = 0

    total = easy + medium + hard

    if errors:
        print(f"Warning: errors fetching data for '{username}': {'; '.join(errors)}",
              file=sys.stderr)

    return {
        "date": date.today().isoformat(),
        "rating": rating,
        "easy": easy,
        "medium": medium,
        "hard": hard,
        "total": total,
    }


def record_exists(records, today):
    """Check if a record for today already exists."""
    return any(r.get("date") == today for r in records)


def main():
    username = load_config()
    today = date.today().isoformat()

    records = load_existing_data()

    if record_exists(records, today):
        print(f"Record for {today} already exists. Skipping.")
        return

    stats = fetch_stats(username)
    records.append(stats)

    with open(DATA_FILE, "w") as f:
        json.dump(records, f, indent=2)

    print(f"Appended stats for {username} on {today}: "
          f"rating={stats['rating']}, "
          f"easy={stats['easy']}, medium={stats['medium']}, "
          f"hard={stats['hard']}, total={stats['total']}")


if __name__ == "__main__":
    main()