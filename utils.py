import re
import json
import os
import datetime as dt
import doctest
import requests
from bs4 import BeautifulSoup

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
GRAPHQL_URL = "https://leetcode.com/graphql"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def load_config():
    """Load user_id from config.json."""
    if not os.path.exists(CONFIG_FILE):
        config = {"user_id": "bakunobu"}
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)
        return config["user_id"]

    with open(CONFIG_FILE) as f:
        config = json.load(f)
    return config.get("user_id", "bakunobu")


def parse(url: str = "https://leetcode.com/u") -> tuple:
    """
    Fetch a LeetCode user's contest rating and AC submissions (last 24 h)
    broken down by difficulty.

    Builds the full profile URL from *url* and the nickname stored in
    ``config.json``, then queries LeetCode's GraphQL API for the user's
    contest rating and recent accepted submissions (with difficulty).

    Parameters
    ----------
    url : str, optional
        Base LeetCode profile URL (default ``"https://leetcode.com/u"``).

    Returns
    -------
    tuple
        A seven-element tuple ``(nickname, response_ts, rating,
        easy, medium, hard, total)``:
        - *nickname* – the LeetCode user id (from config.json).
        - *response_ts* – current UTC date/time in ISO‑8601 format.
        - *rating* – user's contest rating (integer; 0 if unranked).
        - *easy, medium, hard* – number of AC submissions by difficulty
          in the last 24 h (0 if none).
        - *total* – sum of easy + medium + hard.

    Raises
    ------
    ValueError
        If any GraphQL response is missing expected data.
    requests.RequestException
        If a network request fails.
    """
    import time

    nickname = load_config()
    now = time.time()
    cutoff = now - 86400  # 24 hours ago (Unix timestamp)

    profile_url = url.rstrip("/") + "/" + nickname + "/"

    headers = {
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
        "Referer": profile_url,
    }

    # ── step 1: fetch contest rating ────────────────────────────────
    rating_query = """
    query userContestRanking($username: String!) {
        userContestRanking(username: $username) {
            rating
        }
    }
    """
    rating_payload = {
        "query": rating_query,
        "variables": {"username": nickname},
    }
    rating_resp = requests.post(GRAPHQL_URL, json=rating_payload,
                                headers=headers, timeout=15)
    rating_resp.raise_for_status()
    rating_data = rating_resp.json()
    ranking = rating_data.get("data", {}).get("userContestRanking")
    rating = int(ranking["rating"]) if ranking else 0

    # ── step 2: fetch recent AC submissions ─────────────────────────
    recent_query = """
    query recentAcSubmissions($username: String!, $limit: Int!) {
        recentAcSubmissionList(username: $username, limit: $limit) {
            titleSlug
            timestamp
        }
    }
    """
    recent_payload = {
        "query": recent_query,
        "variables": {"username": nickname, "limit": 100},
    }
    recent_resp = requests.post(GRAPHQL_URL, json=recent_payload,
                                headers=headers, timeout=15)
    recent_resp.raise_for_status()
    recent_data = recent_resp.json()
    submissions = (
        recent_data.get("data", {}).get("recentAcSubmissionList")
    )
    if submissions is None:
        raise ValueError(
            f"Could not retrieve submissions for '{nickname}'. "
            f"Response: {json.dumps(recent_data)}"
        )

    # ── step 3: keep only submissions from the last 24 h ──────────
    recent = [s for s in submissions if int(s["timestamp"]) >= cutoff]

    # ── step 4: query difficulty for each unique problem ───────────
    unique_slugs = list({s["titleSlug"] for s in recent})
    diff_map = {}

    if unique_slugs:
        alias_parts = [
            f'q{i}: question(titleSlug: "{slug}") {{ difficulty }}'
            for i, slug in enumerate(unique_slugs)
        ]
        diff_query = "query { " + " ".join(alias_parts) + " }"
        diff_resp = requests.post(GRAPHQL_URL, json={"query": diff_query},
                                  headers=headers, timeout=15)
        diff_resp.raise_for_status()
        diff_data = diff_resp.json().get("data", {})
        for i, slug in enumerate(unique_slugs):
            diff_map[slug] = diff_data.get(f"q{i}", {}).get("difficulty", "Unknown")

    # ── step 5: count by type ──────────────────────────────────────
    easy = medium = hard = 0
    for s in recent:
        d = diff_map.get(s["titleSlug"], "Unknown")
        if d == "Easy":
            easy += 1
        elif d == "Medium":
            medium += 1
        elif d == "Hard":
            hard += 1

    total = easy + medium + hard
    response_ts = dt.datetime.now(dt.timezone.utc).isoformat()
    return (nickname, response_ts, rating, easy, medium, hard, total)


def hand_input() -> str:
    """
    Function gets user input in format (L) or (L YYYY-mm-dd) 
    where L is question difficulty (E, M, H) and YYYY-mm-dd is the date (optional).

    Returns:
        str: The input in format 'L' or 'L YYYY-mm-dd' if date is valid and not in the future.

    Raises:
        ValueError: If date format is incorrect or date is in the future.
    """
    while True:
        rec = input('Enter task difficulty (E, M, H) and date (YYYY-mm-dd, optionally): ').upper().strip()
        
        parts = rec.split()
        difficulty = parts[0]
        
        if difficulty not in 'EHM':
            print('Wrong input. Try again.')
            continue
            
        if len(parts) == 1:
            return rec, None
        
        if len(parts) == 2:
            date_str = parts[1]
            try:
                # Convert the input date string to a datetime object
                input_date = dt.datetime.strptime(date_str, '%Y-%m-%d').date()
                today = dt.date.today()
                
                if input_date <= today:
                    return rec.split(' ')
                else:
                    print("Can't add future date")
            except ValueError:
                print('Wrong input. Try again.')
        else:
            # Handles cases like "E 2023-10-05 extra" or "E M"
            print('Wrong input. Try again.')

def save_to_db(conn, db, table):
    difficulty, date_str = hand_input()
    query = f"""INSERT INTO {table} (difficulty, date) VALUES ({difficulty}, {date_str})"""
    conn.execute(query)
    conn.commit()
