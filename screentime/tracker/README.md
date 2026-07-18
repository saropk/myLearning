# screentimed — tracker daemon

Step 1 of the build order: the background tracker + local SQLite database.
Everything else (2D report, menu bar widget, 3D report) reads what this writes.

macOS only. No permission prompts in the default configuration — frontmost-app
polling (`NSWorkspace`) and idle detection (`CGEventSource`) require none.
Window-title capture is **off by default**; enabling it (`--capture-titles`)
requires granting Accessibility permission.

## Build & run (on a Mac)

```sh
cd tracker
swift build -c release
.build/release/screentimed run
```

Leave it running; stop with Ctrl-C (the open session is closed cleanly).

## Everyday commands

```sh
screentimed status                 # today's summary in the terminal
screentimed status 2026-07-17     # a specific day
screentimed export > day.json      # the JSON the report site consumes
screentimed category list
screentimed category set com.google.Chrome Browsing
screentimed pause                  # privacy toggle; resume with `resume`
screentimed rollup                 # rebuild daily_rollup from raw sessions
```

## How tracking works

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
- **Pause** is stored in the database (`meta.paused`), so the future menu bar
  widget can toggle it by writing one row — no IPC needed.

## Database

`~/Library/Application Support/ScreenTime/screentime.sqlite3` (WAL mode, so
the report server can read while the daemon writes).

| table | contents |
|---|---|
| `sessions` | bundle id, app name, optional window title, category, start/end unix ts, is_idle |
| `daily_rollup` | per-day per-app active/idle second totals (sessions crossing midnight are split) |
| `breaks` | break prompts: when, taken/skipped, snoozed — written by the widget (step 3) |
| `categories` | bundle id → category; seeded with common apps on first run, then user-owned |
| `meta` | key/value: `paused`, etc. |

## Run at login

Edit `launchd/com.screentime.tracker.plist` to point at your built binary
(or copy it to `/usr/local/bin/screentimed`), then:

```sh
cp launchd/com.screentime.tracker.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.screentime.tracker.plist
```

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
