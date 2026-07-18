# report — local server + 2D report

Step 2 of the build order: prove the data and the insights before any WebGL.
This directory will also host the 3D report (steps 4–5); the 2D page remains
permanently as the plain-numbers view the spec requires.

## Run

```sh
# with real data from the tracker (default DB path):
python3 server/server.py

# or against generated sample data (no Mac / no tracker needed):
python3 tools/make_sample_db.py sample.sqlite3 --days 3
python3 server/server.py --db sample.sqlite3
```

Then open http://127.0.0.1:5177 — optionally `/?day=YYYY-MM-DD`.

Stdlib only, no dependencies. Binds to 127.0.0.1; data never leaves the
machine. The DB is opened read-only per request, so the daemon can keep
writing (WAL) while you browse.

## Endpoints

| route | returns |
|---|---|
| `/api/days` | days that have data, newest first |
| `/api/report?day=YYYY-MM-DD` | day report JSON — same contract as `screentimed export`, plus `suggestions` |
| `/` | the 2D report page |

## Suggestions engine

Rule-based heuristics in `server.py` (`suggestions()`), per the spec's
"working defaults." Every rule speaks with the day's actual numbers and
stays silent when it doesn't apply — no generic wellness platitudes:

- `marathon-session` — longest unbroken active stretch ≥ 90 min
- `breaks-skipped` — more prompts dismissed/snoozed than taken
- `late-night` — ≥ 30 min active between 23:00 and 05:00
- `idle-share` — laptop open but unused ≥ 25% of awake time
- `top-app-dominance` — one app ≥ 40% of the active day
- `leisure-vs-work` — browsing + entertainment outweigh work
- `heavy-day` — ≥ 9 h active

The 3D report's Act III (brain) will consume this same `suggestions` array.
