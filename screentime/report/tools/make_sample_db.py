#!/usr/bin/env python3
"""Generates a sample screentime.sqlite3 matching the tracker's schema,
so the report can be developed and tested without running the daemon.

Usage: python3 make_sample_db.py [out.sqlite3] [--days N]
"""

import datetime as dt
import random
import sqlite3
import sys

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bundle_id TEXT NOT NULL,
    app_name TEXT NOT NULL,
    window_title TEXT,
    category TEXT NOT NULL,
    start_ts INTEGER NOT NULL,
    end_ts INTEGER NOT NULL,
    is_idle INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_sessions_start ON sessions(start_ts);
CREATE TABLE IF NOT EXISTS daily_rollup (
    day TEXT NOT NULL,
    bundle_id TEXT NOT NULL,
    app_name TEXT NOT NULL,
    category TEXT NOT NULL,
    active_seconds INTEGER NOT NULL DEFAULT 0,
    idle_seconds INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, bundle_id)
);
CREATE TABLE IF NOT EXISTS breaks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompted_ts INTEGER NOT NULL,
    taken INTEGER,
    snoozed INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS categories (
    bundle_id TEXT PRIMARY KEY,
    app_name TEXT,
    category TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""

APPS = [
    ("com.microsoft.VSCode", "Code", "Work", 0.30),
    ("com.google.Chrome", "Chrome", "Browsing", 0.25),
    ("com.tinyspeck.slackmacgap", "Slack", "Communication", 0.12),
    ("com.apple.Terminal", "Terminal", "Work", 0.10),
    ("com.spotify.client", "Spotify", "Entertainment", 0.08),
    ("com.apple.Safari", "Safari", "Browsing", 0.07),
    ("us.zoom.xos", "zoom.us", "Communication", 0.05),
    ("com.apple.Notes", "Notes", "Work", 0.03),
]


def generate_day(db: sqlite3.Connection, day: dt.date, rng: random.Random):
    day_start = dt.datetime.combine(day, dt.time()).astimezone()

    # Working blocks: morning, afternoon, evening tail into late night.
    blocks = [
        (9.0, 12.5),
        (13.5, 18.0),
        (21.0, 24.5),  # crosses midnight → exercises day-splitting
    ]
    for block_start, block_end in blocks:
        t = day_start + dt.timedelta(hours=block_start)
        block_stop = day_start + dt.timedelta(hours=block_end)
        while t < block_stop:
            bundle, name, cat, weight = rng.choices(
                APPS, weights=[a[3] for a in APPS]
            )[0]
            # Occasional marathon in the top app; else 3–35 min sessions.
            if bundle == "com.microsoft.VSCode" and rng.random() < 0.08:
                dur = rng.randint(95, 150) * 60
            else:
                dur = rng.randint(3, 35) * 60
            end = min(t + dt.timedelta(seconds=dur), block_stop)
            db.execute(
                """INSERT INTO sessions
                   (bundle_id, app_name, category, start_ts, end_ts, is_idle)
                   VALUES (?, ?, ?, ?, ?, 0)""",
                (bundle, name, cat, int(t.timestamp()), int(end.timestamp())),
            )
            t = end
            # Sometimes wander off and leave the lid open.
            if rng.random() < 0.18:
                idle_end = min(
                    t + dt.timedelta(seconds=rng.randint(4, 40) * 60), block_stop
                )
                if idle_end > t:
                    db.execute(
                        """INSERT INTO sessions
                           (bundle_id, app_name, category, start_ts, end_ts, is_idle)
                           VALUES (?, ?, ?, ?, ?, 1)""",
                        (bundle, name, cat,
                         int(t.timestamp()), int(idle_end.timestamp())),
                    )
                    t = idle_end

    # Break prompts every ~20 active minutes; taken a bit less than half.
    t = day_start + dt.timedelta(hours=9)
    while t < day_start + dt.timedelta(hours=18):
        taken = rng.choices([1, 0, None], weights=[4, 4, 2])[0]
        db.execute(
            "INSERT INTO breaks (prompted_ts, taken, snoozed) VALUES (?, ?, ?)",
            (int(t.timestamp()), taken, 1 if taken is None else 0),
        )
        t += dt.timedelta(minutes=rng.randint(20, 35))


def rebuild_rollup(db: sqlite3.Connection):
    db.execute("DELETE FROM daily_rollup")
    for bundle, name, cat, start_ts, end_ts, is_idle in db.execute(
        "SELECT bundle_id, app_name, category, start_ts, end_ts, is_idle "
        "FROM sessions ORDER BY start_ts"
    ).fetchall():
        cursor = dt.datetime.fromtimestamp(start_ts).astimezone()
        end = dt.datetime.fromtimestamp(end_ts).astimezone()
        while cursor < end:
            next_midnight = dt.datetime.combine(
                cursor.date() + dt.timedelta(days=1), dt.time()
            ).astimezone()
            slice_end = min(next_midnight, end)
            seconds = int((slice_end - cursor).total_seconds())
            day = cursor.date().isoformat()
            db.execute(
                """INSERT INTO daily_rollup
                   (day, bundle_id, app_name, category, active_seconds, idle_seconds)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(day, bundle_id) DO UPDATE SET
                     active_seconds = active_seconds + excluded.active_seconds,
                     idle_seconds = idle_seconds + excluded.idle_seconds""",
                (day, bundle, name, cat,
                 0 if is_idle else seconds, seconds if is_idle else 0),
            )
            cursor = slice_end


def main():
    out = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") \
        else "sample.sqlite3"
    days = 3
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])

    rng = random.Random(20)
    db = sqlite3.connect(out)
    db.executescript(SCHEMA)
    db.execute("DELETE FROM sessions")
    db.execute("DELETE FROM breaks")

    today = dt.date.today()
    for offset in range(days, 0, -1):
        generate_day(db, today - dt.timedelta(days=offset - 1), rng)
    rebuild_rollup(db)
    db.commit()

    n_sessions = db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    day_list = [r[0] for r in db.execute(
        "SELECT DISTINCT day FROM daily_rollup ORDER BY day")]
    print(f"wrote {out}: {n_sessions} sessions across days {day_list}")


if __name__ == "__main__":
    main()
