# Iris — screen time, seen through your own eye 👁

Iris is a desktop screen-time tracker built around one idea: **your screen time
enters through your eye and lands in your brain — so that's exactly how the
report shows it.**

It has three parts:

1. **The tracker** — an Electron background app that samples your focused
   application every 5 seconds, detects idle time, and stores everything
   locally (nothing ever leaves your machine).
2. **The widget** — a small, frameless, always-on-top card that floats on your
   desktop: today's total, the app you're using right now, a
   tracking pause/resume toggle, and a live countdown to your next
   **20-20-20 eye break** (every 20 minutes, look ~20 feet away for 20 seconds —
   Iris notifies you and flashes the widget).
3. **The 3D report** — a scroll-driven WebGL journey. Scrolling is the
   timeline of the animation:
   - You start face-to-face with an **eye in starry space** — icy blue iris,
     pupil shaped like a **sand-clock**.
   - Scrolling dives past the pupil and swings down the **optic nerve**, a
     glowing tube with signal pulses racing along it. Each **synapse bubble**
     branching off the nerve is one application, sized and labelled with the
     time it took from you.
   - The nerve plugs into a vivid **particle brain**, which "thinks out"
     suggestion cards: eye-strain warnings, productivity ratio, idle screen
     burn, late-night usage, marathon-session alerts — plus a 7-day history.

## Run it

```bash
cd screen-time-tracker
npm install          # installs Electron (three.js is vendored, no build step)
npm start
```

The widget appears top-right; a tray icon gives you pause/resume, eye-care
toggle, the report, and quit. Closing windows keeps Iris tracking in the tray.

### Preview just the 3D report (no Electron needed)

```bash
npm run report:demo
# → http://localhost:5173  (uses demo data in a normal browser)
```

## Platform notes (active-window detection)

| OS | Mechanism | Needs |
|----|-----------|-------|
| Windows | PowerShell + user32 `GetForegroundWindow` | nothing extra |
| macOS | AppleScript (System Events) | grant Accessibility/Automation permission on first prompt |
| Linux (X11) | `xdotool` + `xprop` | `sudo apt install xdotool x11-utils` |
| Linux (Wayland) | not exposed by the compositor | time is still tracked as "unknown" |

Idle detection uses Electron's `powerMonitor` everywhere (no input for
90 s ⇒ counted as idle, not app time).

## Start Iris with your laptop

- **Windows**: `Win+R` → `shell:startup` → drop a shortcut to `npm start`
  (or the packaged exe) in that folder.
- **macOS**: System Settings → General → Login Items → add Iris.
- **Linux**: add an entry to `~/.config/autostart/iris.desktop`.

## Where the data lives

One JSON file per day in Electron's `userData/data/` directory
(`usage-YYYY-MM-DD.json`): per-app totals, per-hour buckets, focus sessions,
idle seconds. Delete a file and that day is forgotten.

## Project layout

```
src/main/main.js         app lifecycle, tray, windows, eye-break scheduler, IPC
src/main/tracker.js      cross-platform focused-app polling + idle detection
src/main/store.js        daily JSON persistence, session stitching, history
src/main/report-data.js  report schema + the suggestion engine
src/preload.js           the safe bridge (contextIsolation on)
src/widget/…             the floating desktop widget
src/report/…             the 3D scroll journey (three.js vendored in vendor/)
scripts/serve-report.js  static server for browser preview with demo data
```
