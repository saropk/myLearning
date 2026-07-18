# mac — tracker daemon + menu bar widget

The native half of the project (build steps 1 and 3). One Swift package,
three targets:

| target | what |
|---|---|
| `ScreenTimeCore` | shared library: SQLite access, schema, rollups, report building, categories |
| `screentimed` | background tracker daemon (step 1) |
| `screentimebar` | menu bar widget + 20-20-20 break nudges (step 3) |

macOS only. **No permission prompts** in the default configuration —
frontmost-app polling (`NSWorkspace`), idle detection (`CGEventSource`), and
the widget need none. Window-title capture is off by default; enabling it
(`--capture-titles`) requires granting Accessibility permission.

## Build & run (on a Mac)

```sh
cd mac
swift build -c release
.build/release/screentimed run &        # the tracker
.build/release/screentimebar &          # the menu bar widget
```

Stop the daemon with Ctrl-C / SIGTERM (the open session closes cleanly);
quit the widget from its menu.

## The daemon: everyday commands

```sh
screentimed status                 # today's summary in the terminal
screentimed status 2026-07-17     # a specific day
screentimed export > day.json      # the JSON the report site consumes
screentimed category list
screentimed category set com.google.Chrome Browsing
screentimed pause                  # privacy toggle; resume with `resume`
screentimed rollup                 # rebuild daily_rollup from raw sessions
```

### How tracking works

- Polls the frontmost application every 2s (`--interval` to change).
- A **session** is an unbroken run of the same (app, active-vs-idle) state.
  The open session's end time is updated on every poll, so a crash or power
  loss costs at most one poll interval of data.
- **Idle**: no keyboard/mouse input for 120s (`--idle-threshold`). When the
  idle transition is detected, the preceding active session is backdated to
  the moment input actually stopped, so the threshold lag never counts as
  active use. Idle time is attributed to the app that was frontmost, flagged
  `is_idle = 1` — "laptop open" is never confused with "laptop in use."
- **Sleep/gaps**: a gap of more than 3 poll intervals closes the session at
  the last real sample rather than spanning the sleep.

## The widget

- Menu bar: eye glyph + today's active total (an `eye.slash` + "paused"
  when tracking is paused).
- Menu: today's active/idle totals, the current app and session length,
  pause/resume, "Take a Break Now", "Open Report…" (the local report
  server, `--report-url` to change), quit.
- **20-20-20 nudges**: after 20 minutes of continuous active use, a small
  non-activating floating panel appears top-right — look 20 feet away for
  20 seconds, with a countdown. "I looked away" / "Snooze 5 min" / "Skip";
  ignoring it dismisses after 60s. It never steals focus and is never
  modal. Idle time or pausing resets the rhythm (a real break already
  happened). Every prompt and its outcome is recorded to the `breaks`
  table, which feeds the report's honesty stats.
- The widget and daemon share nothing but the database: pause is a `meta`
  row, stats are read straight from `sessions`/`daily_rollup`. No IPC.

## Database

`~/Library/Application Support/ScreenTime/screentime.sqlite3` (WAL mode, so
the report server and widget can read while the daemon writes).

| table | contents |
|---|---|
| `sessions` | bundle id, app name, optional window title, category, start/end unix ts, is_idle |
| `daily_rollup` | per-day per-app active/idle second totals (sessions crossing midnight are split) |
| `breaks` | break prompts: when, taken (1) / skipped (0) / dismissed (NULL), snoozed |
| `categories` | bundle id → category; seeded with common apps on first run, then user-owned |
| `meta` | key/value: `paused`, etc. |

## Run at login

Edit `launchd/com.screentime.tracker.plist` to point at your built binary
(or copy it to `/usr/local/bin/screentimed`), then:

```sh
cp launchd/com.screentime.tracker.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.screentime.tracker.plist
```

The widget can be added as a normal Login Item (System Settings → General
→ Login Items) pointing at `screentimebar`.

## Report JSON contract

`screentimed export [day]` emits the shape the report site consumes:

```jsonc
{
  "day": "2026-07-18",
  "generatedAt": "2026-07-18T18:00:00Z",
  "totals": { "activeSeconds": 21600, "idleSeconds": 4800 },
  "apps": [        // sorted by activeSeconds desc — drives Act II node sizing
    { "bundleId": "com.google.Chrome", "appName": "Chrome",
      "category": "Browsing", "activeSeconds": 9000, "idleSeconds": 600 }
  ],
  "categories": [ { "category": "Work", "activeSeconds": 12000, "idleSeconds": 900 } ],
  "longestSession": { "bundleId": "…", "appName": "…",
                      "startTs": 0, "endTs": 0, "seconds": 13200 },
  "hourly": [ { "hour": 0, "activeSeconds": 0, "idleSeconds": 0 } /* ×24 */ ],
  "breaks": { "prompted": 12, "taken": 7, "skipped": 3, "snoozed": 2 }
}
```

The Python report server (`../report/server/server.py`) produces the same
shape directly from the database, plus a `suggestions` array.
