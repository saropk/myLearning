#!/usr/bin/env python3
"""Local report server for the screen-time tracker.

Reads the SQLite database written by screentimed and serves:

  /api/days            -> list of days that have data
  /api/report?day=...  -> the day report JSON (same contract as
                          `screentimed export`, plus "suggestions")
  /                    -> the static 2D report page

Stdlib only — no dependencies. Data never leaves the machine: the server
binds to 127.0.0.1.
"""

import argparse
import datetime as dt
import json
import os
import sqlite3
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

DEFAULT_DB = os.path.expanduser(
    "~/Library/Application Support/ScreenTime/screentime.sqlite3"
)


def day_bounds(day: str) -> tuple[int, int]:
    start = dt.datetime.strptime(day, "%Y-%m-%d").astimezone()
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + dt.timedelta(days=1)
    return int(start.timestamp()), int(end.timestamp())


def build_report(db: sqlite3.Connection, day: str) -> dict:
    day_start, day_end = day_bounds(day)

    apps = [
        {
            "bundleId": r[0],
            "appName": r[1],
            "category": r[2],
            "activeSeconds": r[3],
            "idleSeconds": r[4],
        }
        for r in db.execute(
            """SELECT bundle_id, app_name, category, active_seconds, idle_seconds
               FROM daily_rollup WHERE day = ? ORDER BY active_seconds DESC""",
            (day,),
        )
    ]

    categories: dict[str, dict] = {}
    for app in apps:
        c = categories.setdefault(
            app["category"],
            {"category": app["category"], "activeSeconds": 0, "idleSeconds": 0},
        )
        c["activeSeconds"] += app["activeSeconds"]
        c["idleSeconds"] += app["idleSeconds"]
    category_list = sorted(
        categories.values(), key=lambda c: -c["activeSeconds"]
    )

    totals = {
        "activeSeconds": sum(a["activeSeconds"] for a in apps),
        "idleSeconds": sum(a["idleSeconds"] for a in apps),
    }

    longest = db.execute(
        """SELECT bundle_id, app_name, start_ts, end_ts, (end_ts - start_ts) AS dur
           FROM sessions
           WHERE is_idle = 0 AND start_ts < ? AND end_ts > ?
           ORDER BY dur DESC LIMIT 1""",
        (day_end, day_start),
    ).fetchone()
    longest_session = (
        {
            "bundleId": longest[0],
            "appName": longest[1],
            "startTs": longest[2],
            "endTs": longest[3],
            "seconds": longest[4],
        }
        if longest
        else None
    )

    hourly = [{"hour": h, "activeSeconds": 0, "idleSeconds": 0} for h in range(24)]
    for start_ts, end_ts, is_idle in db.execute(
        "SELECT start_ts, end_ts, is_idle FROM sessions WHERE start_ts < ? AND end_ts > ?",
        (day_end, day_start),
    ):
        cursor = max(start_ts, day_start)
        end = min(end_ts, day_end)
        while cursor < end:
            hour = (cursor - day_start) // 3600
            if hour < 0 or hour > 23:
                break
            hour_end = day_start + (hour + 1) * 3600
            slice_s = min(hour_end, end) - cursor
            key = "idleSeconds" if is_idle else "activeSeconds"
            hourly[hour][key] += slice_s
            cursor = min(hour_end, end)

    row = db.execute(
        """SELECT COUNT(*),
                  COALESCE(SUM(CASE WHEN taken = 1 THEN 1 ELSE 0 END), 0),
                  COALESCE(SUM(CASE WHEN taken = 0 THEN 1 ELSE 0 END), 0),
                  COALESCE(SUM(snoozed), 0)
           FROM breaks WHERE prompted_ts >= ? AND prompted_ts < ?""",
        (day_start, day_end),
    ).fetchone()
    breaks = {
        "prompted": row[0],
        "taken": row[1],
        "skipped": row[2],
        "snoozed": row[3],
    }

    report = {
        "day": day,
        "generatedAt": dt.datetime.now(dt.timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "totals": totals,
        "apps": apps,
        "categories": category_list,
        "longestSession": longest_session,
        "hourly": hourly,
        "breaks": breaks,
    }
    report["suggestions"] = suggestions(report)
    return report


def _hm(seconds: int) -> str:
    h, m = seconds // 3600, (seconds % 3600) // 60
    return f"{h}h {m:02d}m" if h else f"{m}m"


def suggestions(report: dict) -> list[dict]:
    """Rule-based heuristics. Every rule speaks with the day's real numbers;
    rules that don't fire stay silent. No generic wellness platitudes."""
    out: list[dict] = []
    totals = report["totals"]
    active = totals["activeSeconds"]
    idle = totals["idleSeconds"]
    apps = report["apps"]
    breaks = report["breaks"]

    longest = report.get("longestSession")
    if longest and longest["seconds"] >= 90 * 60:
        start = dt.datetime.fromtimestamp(longest["startTs"]).strftime("%H:%M")
        out.append(
            {
                "id": "marathon-session",
                "kind": "eye-strain",
                "severity": "high",
                "message": (
                    f"Your longest unbroken stretch was {_hm(longest['seconds'])} "
                    f"in {longest['appName']}, starting at {start}. Past 90 minutes, "
                    f"focus quality drops before you notice it — a 5-minute break "
                    f"would have cost less than the fatigue did."
                ),
            }
        )

    if breaks["prompted"] > 0 and breaks["skipped"] + breaks["snoozed"] > breaks["taken"]:
        out.append(
            {
                "id": "breaks-skipped",
                "kind": "eye-strain",
                "severity": "medium",
                "message": (
                    f"You took {breaks['taken']} of {breaks['prompted']} break "
                    f"prompts and dismissed or snoozed the rest. The prompts only "
                    f"work if the answer is occasionally yes."
                ),
            }
        )

    late = sum(
        h["activeSeconds"]
        for h in report["hourly"]
        if h["hour"] >= 23 or h["hour"] < 5
    )
    if late >= 30 * 60:
        out.append(
            {
                "id": "late-night",
                "kind": "eye-strain",
                "severity": "medium",
                "message": (
                    f"{_hm(late)} of active use fell between 23:00 and 05:00. "
                    f"Late-night screen light is the hardest kind on your eyes "
                    f"and your sleep."
                ),
            }
        )

    open_time = active + idle
    if open_time > 0 and idle >= max(int(open_time * 0.25), 3600):
        out.append(
            {
                "id": "idle-share",
                "kind": "honesty",
                "severity": "low",
                "message": (
                    f"The laptop was open but unused for {_hm(idle)} — "
                    f"{idle * 100 // open_time}% of the time it was awake. "
                    f"That time was already yours; closing the lid just makes "
                    f"it official."
                ),
            }
        )

    if apps and active > 0:
        top = apps[0]
        share = top["activeSeconds"] * 100 // active
        if share >= 40 and top["activeSeconds"] >= 3600:
            out.append(
                {
                    "id": "top-app-dominance",
                    "kind": "productivity",
                    "severity": "medium",
                    "message": (
                        f"{top['appName']} took {share}% of your active day "
                        f"({_hm(top['activeSeconds'])}). If that matches your "
                        f"intent, fine — if not, it's the single biggest lever "
                        f"you have."
                    ),
                }
            )

    cat = {c["category"]: c["activeSeconds"] for c in report["categories"]}
    leisure = cat.get("Browsing", 0) + cat.get("Entertainment", 0)
    work = cat.get("Work", 0)
    if leisure > work and leisure >= 3600:
        out.append(
            {
                "id": "leisure-vs-work",
                "kind": "productivity",
                "severity": "low",
                "message": (
                    f"Browsing and entertainment ({_hm(leisure)}) outweighed "
                    f"work ({_hm(work)}) today. Worth one honest question: "
                    f"was that the plan?"
                ),
            }
        )

    if active >= 9 * 3600:
        out.append(
            {
                "id": "heavy-day",
                "kind": "eye-strain",
                "severity": "medium",
                "message": (
                    f"{_hm(active)} of active screen time is a heavy day. "
                    f"The 20-20-20 rhythm matters most on exactly this kind "
                    f"of day."
                ),
            }
        )

    return out


class Handler(SimpleHTTPRequestHandler):
    db_path = DEFAULT_DB

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def log_message(self, fmt, *args):  # quieter default logging
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/report":
            day = parse_qs(parsed.query).get("day", [today()])[0]
            self.send_json(lambda db: build_report(db, day))
        elif parsed.path == "/api/days":
            self.send_json(
                lambda db: [
                    r[0]
                    for r in db.execute(
                        "SELECT DISTINCT day FROM daily_rollup ORDER BY day DESC"
                    )
                ]
            )
        else:
            super().do_GET()

    def send_json(self, fn):
        try:
            uri = f"file:{self.db_path}?mode=ro"
            with sqlite3.connect(uri, uri=True) as db:
                payload = fn(db)
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:  # surface the reason to the page
            body = json.dumps({"error": str(e)}).encode()
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)


def today() -> str:
    return dt.date.today().isoformat()


def main():
    parser = argparse.ArgumentParser(description="Screen-time report server")
    parser.add_argument("--db", default=DEFAULT_DB, help="path to screentime.sqlite3")
    parser.add_argument("--port", type=int, default=5177)
    args = parser.parse_args()

    if not os.path.exists(args.db):
        sys.exit(
            f"error: database not found at {args.db}\n"
            f"Run the tracker first, or generate sample data with "
            f"report/tools/make_sample_db.py"
        )

    Handler.db_path = args.db
    server = HTTPServer(("127.0.0.1", args.port), Handler)
    print(f"report → http://127.0.0.1:{args.port}  (db: {args.db})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
