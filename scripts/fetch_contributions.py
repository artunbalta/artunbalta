#!/usr/bin/env python3
"""Scrape a GitHub user's public contribution calendar (no token, no GraphQL).

Fetches the public HTML at:
    https://github.com/users/<username>/contributions

and writes ``data/contributions.json`` containing:
    - ``days``:  chronological list of {date, level (0-4), count (int)}
    - ``stats``: total, current_streak, longest_streak, best_day, months

The HTML layout (verified against live GitHub):
    - Day cells are ``<td class="ContributionCalendar-day">`` elements carrying
      ``data-date`` (YYYY-MM-DD), ``data-level`` (0..4) and an ``id``.
    - The numeric counts live in separate ``<tool-tip for="<cell id>">``
      elements whose text reads e.g. "10 contributions on July 12th." or
      "No contributions on July 13th." We join tips to cells by id.
GitHub tweaks this markup periodically, so the parser degrades gracefully
(falls back to level when a count is missing).
"""

import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ---- Config -----------------------------------------------------------------
GITHUB_USERNAME = os.environ.get("GITHUB_USERNAME", "artunbalta")

URL = f"https://github.com/users/{GITHUB_USERNAME}/contributions"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "contributions.json"


# ---- Fetch + parse ----------------------------------------------------------
def fetch_html(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(
            f"GitHub returned HTTP {resp.status_code} for {url}. "
            "The username may be wrong or GitHub is rate-limiting this IP."
        )
    return resp.text


def parse_days(html: str):
    """Return a chronological list of {date, level, count} dicts."""
    soup = BeautifulSoup(html, "html.parser")

    # Map each tool-tip's target cell id -> integer count.
    tip_count = {}
    for tip in soup.find_all("tool-tip"):
        target = tip.get("for")
        if not target:
            continue
        text = tip.get_text(strip=True)
        m = re.match(r"([\d,]+)\s+contribution", text)
        tip_count[target] = int(m.group(1).replace(",", "")) if m else 0

    cells = soup.select("td.ContributionCalendar-day[data-date]") or soup.select(
        "td[data-date]"
    )
    if not cells:
        raise RuntimeError(
            "No contribution day cells found. GitHub likely changed its HTML "
            "structure; update the selector in parse_days()."
        )

    days = []
    for td in cells:
        date = td.get("data-date")
        if not date:
            continue
        try:
            level = int(td.get("data-level", 0))
        except (TypeError, ValueError):
            level = 0
        cell_id = td.get("id")
        # Count from the tool-tip if we have it, else fall back to level so the
        # calendar still renders something sensible.
        if cell_id in tip_count:
            count = tip_count[cell_id]
        else:
            count = level  # coarse fallback
        days.append({"date": date, "level": level, "count": count})

    # De-dupe (defensive) and sort chronologically.
    seen = {}
    for d in days:
        seen[d["date"]] = d
    return [seen[k] for k in sorted(seen)]


def parse_header_total(html: str):
    """The '<N> contributions in the last year' figure, or None."""
    soup = BeautifulSoup(html, "html.parser")
    text = re.sub(r"\s+", " ", soup.get_text(" "))
    m = re.search(r"([\d,]+)\s+contributions?\s+in the last year", text)
    return int(m.group(1).replace(",", "")) if m else None


# ---- Derived stats ----------------------------------------------------------
def compute_stats(days, header_total):
    today = dt.date.today()
    # Only reason about days up to today for streaks.
    valid = [d for d in days if dt.date.fromisoformat(d["date"]) <= today]

    calendar_total = sum(d["count"] for d in days)
    total = header_total if header_total is not None else calendar_total

    # Best single day.
    best = max(days, key=lambda d: d["count"], default=None)
    best_day = (
        {"date": best["date"], "count": best["count"]}
        if best and best["count"] > 0
        else {"date": None, "count": 0}
    )

    # Longest streak: longest run of consecutive CALENDAR days with count > 0.
    # We verify calendar adjacency explicitly so that if the parser ever drops a
    # mid-range day (e.g. GitHub markup shifts), a gap breaks the run instead of
    # silently bridging two separate runs.
    longest = {"length": 0, "start": None, "end": None}
    run = 0
    run_start = None
    prev_date = None
    for d in valid:
        cur_date = dt.date.fromisoformat(d["date"])
        contiguous = prev_date is not None and cur_date == prev_date + dt.timedelta(days=1)
        if d["count"] > 0:
            if run > 0 and contiguous:
                run += 1
            else:
                run = 1
                run_start = d["date"]
            if run > longest["length"]:
                longest = {"length": run, "start": run_start, "end": d["date"]}
        else:
            run = 0
            run_start = None
        prev_date = cur_date

    # Current streak: run of consecutive calendar days ending at the most recent
    # day. Today counts as a grace day if it's still empty (the day isn't over).
    current = {"length": 0, "start": None, "end": None}
    i = len(valid) - 1
    if (
        valid
        and valid[i]["count"] == 0
        and dt.date.fromisoformat(valid[i]["date"]) == today
    ):
        i -= 1  # skip an empty "today"
    cur_end = None
    cur_start = None
    length = 0
    next_date = None  # date of the day one later in the streak
    while i >= 0 and valid[i]["count"] > 0:
        cur_date = dt.date.fromisoformat(valid[i]["date"])
        if next_date is not None and cur_date != next_date - dt.timedelta(days=1):
            break  # calendar gap -> the streak ended here
        if cur_end is None:
            cur_end = valid[i]["date"]
        cur_start = valid[i]["date"]
        length += 1
        next_date = cur_date
        i -= 1
    if length:
        current = {"length": length, "start": cur_start, "end": cur_end}

    # Per-month totals (YYYY-MM -> sum).
    months = {}
    for d in days:
        ym = d["date"][:7]
        months[ym] = months.get(ym, 0) + d["count"]

    return {
        "total": total,
        "calendar_total": calendar_total,
        "current_streak": current,
        "longest_streak": longest,
        "best_day": best_day,
        "months": months,
        "days_with_activity": sum(1 for d in days if d["count"] > 0),
    }


def main():
    print(f"Fetching contributions for @{GITHUB_USERNAME} ...")
    html = fetch_html(URL)
    days = parse_days(html)
    header_total = parse_header_total(html)
    stats = compute_stats(days, header_total)

    payload = {
        "username": GITHUB_USERNAME,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(
            timespec="seconds"
        ),
        "range": {"start": days[0]["date"], "end": days[-1]["date"]} if days else {},
        "total": stats["total"],
        "days": days,
        "stats": stats,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(
        f"Wrote {OUT.relative_to(ROOT)}  "
        f"({len(days)} days, {stats['total']} contributions, "
        f"best {stats['best_day']['count']} on {stats['best_day']['date']}, "
        f"current streak {stats['current_streak']['length']}, "
        f"longest {stats['longest_streak']['length']})"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # surface a clear error, non-zero exit
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
