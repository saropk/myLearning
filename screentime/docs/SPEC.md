# Project Spec — Screen Time Tracker with 3D Scroll-Driven Report

## 1. Overview

A personal screen-time tracking application for laptop use, with two halves:

1. **A background tracker + desktop widget** — silently logs application usage, exposes a
   lightweight always-available toggle/widget on the desktop or menu bar.
2. **A 3D scroll-driven report website** — the review surface, where usage data is presented
   as a cinematic, scroll-scrubbed WebGL journey themed around *time and eyes*.

The purpose is not just measurement. The application should actively help manage screen time
and reduce eye strain — it is a wellbeing tool first, a dashboard second.

---

## 2. Goals

- Track time spent per application, accurately and passively.
- Distinguish productive time from idle/wasted time.
- Surface actionable suggestions, not just numbers.
- Protect the eyes: encourage breaks, discourage marathon sessions.
- Make reviewing usage something worth doing — hence the 3D report.

---

## 3. Component A — Tracker Daemon

### Responsibilities
- Poll the OS for the currently focused window/application at a fixed interval.
- Detect idle time (no keyboard/mouse input beyond a threshold) and log it separately
  from active use, so "8 hours with the laptop open" is not confused with "8 hours of use."
- Persist sessions to a local database. All data stays on the machine.
- Categorise applications (e.g. Work / Communication / Browsing / Entertainment),
  with user-editable category mappings.

### Data model (sketch)
- sessions — app name, window title, category, start timestamp, end timestamp, active vs idle
- daily_rollup — precomputed per-day totals per app and per category
- breaks — when a break was prompted, and whether it was taken
- categories — user-editable app → category mapping

### Platform: macOS

- **Focused app:** NSWorkspace.shared.frontmostApplication — app name and bundle ID.
  No special permissions required.
- **Idle detection:** CGEventSource.secondsSinceLastEventType(.hidSystemState, .anyInputEventType).
  Also requires no permissions.
- **Window titles:** require Accessibility permission. Since titles are optional and off by
  default (see below), the tracker can ship without ever triggering a permissions prompt.
  Only request Accessibility if the user explicitly enables title capture.
- **Polling interval:** ~1–5s. Simpler and more robust than event hooks; the cost is negligible.
- Window titles can be sensitive; storing them is optional and off by default.

---

## 4. Component B — Desktop Widget / Toggle

### Requirements
- Lives on the home screen / desktop / menu bar — always reachable, never in the way.
- At a glance: today's total, current session length, current app.
- A toggle: pause/resume tracking (for privacy, or when the laptop isn't really "in use").
- Eye-strain nudge: a gentle, non-modal prompt on the 20-20-20 rhythm
  (every 20 minutes, look 20 feet away for 20 seconds). Snoozable, never blocking.
- One click opens the full 3D report.

### Form factor: macOS menu bar (NSStatusItem)

The menu bar is the idiomatic home for this class of tool on macOS — always reachable, never
in the way, and where users already look for it.

The alternative, a true desktop widget via WidgetKit, is rejected: it's restricted to
periodic timeline updates (no live session counter), supports tap-to-open only (so it can't
host the pause/resume toggle), and would have to run *alongside* a menu bar item anyway.
Menu bar is strictly the better option here.

---

## 5. Component C — The 3D Report Website

The centrepiece. A single scrolling page where scroll position drives a continuous animation
from a defined start state to a defined end state. Scroll is the timeline scrubber — not a
trigger for discrete animations, but a scrub across one continuous sequence.

### Theme
**Time and eyes.** The visual language: cold, clinical, cosmic. Icy blues, deep starfield
blacks, anatomical precision rendered beautifully rather than medically.

### Scroll sequence

**Act I — The Eye (scroll 0%)**
- A single eyeball suspended in starry space.
- Icy blue iris, rendered with real depth — fibrous stromal detail, subsurface scattering
  through the cornea, a wet specular highlight.
- **The pupil is a clock.** Not a circle: an hourglass or clock-hand form, dark against the
  iris. This is the hook — the eye *is* the timepiece.
- Idle state: slow drift, subtle iris dilation, slow blink. It should feel alive before
  the user touches anything.
- As scroll begins: the camera pushes in, the eye rotates toward the viewer.

**Transition — Through the Pupil (scroll ~20–30%)**

The cut from eye to nerve is hidden inside the pupil. Sequence:

1. **Push in** — camera dollies toward the pupil. Depth of field tightens; iris detail blurs
   at the frame edges.
2. **Dilate** — the clock-pupil opens as the camera approaches, and the hands sweep faster
   the closer you get. Time expanding as you near it. This is the key beat of Act I.
3. **Through** — the pupil fills the frame. Near-black. The aperture rim blooms out as the
   camera passes through it. The pupil is real geometry, not a fade: you fly through a dark
   opening and out the other side.
4. **Emerge** — camera is now behind the globe. The nerve root is directly ahead. The
   darkness *resolves* into the nerve's dim interior light rather than fading out and back in.
5. **Warp** — a fast orbital sweep around the nerve's axis. An orbit, not a spin in place —
   parallax is what sells the dimensionality. Motion blur / slight lens distortion at peak
   speed; starfield streaks.
6. **Settle** — the orbit decelerates into a slow drift, landing on a broadside view of the
   nerve. Full silhouette, fascicles readable. This is the frame where Act II's report nodes
   begin branching.

**Constraints on the warp:**
- Scroll-driven *rotation* is where motion sickness lives — far worse than scroll-driven
  translation, because the user controls the speed and will scrub back and forth across it.
- **Keep it fast and short.** Compress the warp into roughly 10% of scroll distance. Long,
  slow orbits are the problem; brief ones are fine.
- **Consider making the warp non-scrubbable** — once triggered, it plays on its own timeline
  and scroll re-engages on the far side. This breaks the "scroll is the scrubber" purity, but
  most sites that pull this off cheat in exactly this way.
- **Gentler alternative:** hold the camera still and rotate the *nerve* into view instead.
  Reads as nearly the same shot, much kinder on the viewer, and far easier to control.
- The nerve scene must be **loaded during the push-in**, before the black. Loading at the
  black moment puts a hitch precisely where it can't be hidden.

**Act II — The Optic Nerve (scroll ~30–65%)**
- Coming out of the warp, the nerve is seen from outside — acute, realistic, elegant. Bundled
  fibres, not a smooth tube. Fascicles that separate and rejoin. Faint signal pulses
  travelling along it.
- The nerve **branches**, and each branch terminates in a report node — a bubble/pod carrying
  one slice of the usage data:
  - Time in each application
  - Category totals (Work / Browsing / Entertainment / Communication)
  - Longest unbroken session
  - Idle vs active split
  - Time-of-day distribution
- Nodes should be data-driven: more apps → more branches. The anatomy grows out of the actual
  numbers, rather than being decorative scenery with text pasted on.
- Nodes scale/illuminate in proportion to time spent — the eye should be able to read the
  worst offender before reading a single word.

**Act III — The Brain (scroll ~65–100%)**
- The nerve arrives at the brain. Vivid, dimensional, alive — not a grey lump. Translucent,
  with activity travelling across the surface.
- The brain delivers **suggestions**, surfacing from within the model:
  - Productivity observations
  - How to cut screen time without cutting output
  - Idle/wasted time called out honestly
  - Eye-strain patterns (marathon sessions, breaks skipped, late-night use)
- These must be genuinely useful and specific to the data. Generic wellness platitudes would
  undermine the whole thing.
- End state: a resolved summary. Something that feels like an arrival, not a scroll that
  simply ran out.

### Technical approach
- **Three.js / React Three Fiber** for the scene graph.
- **GSAP ScrollTrigger** to scrub the master timeline against scroll position.
- **Lenis** for smooth inertial scroll — without it, scrubbed animation feels stepped.
- **Postprocessing**: bloom for the glow, depth of field for the camera pushes.
- **Custom GLSL** for the iris, the nerve fibres, the particle starfield.
- **Camera on a spline path**, scroll-scrubbed — one continuous curve from outside-the-eye →
  through-pupil → orbit → down-the-nerve → brain. The warp segment may be lifted off the
  scrub onto its own timeline (see transition constraints above).
- **Scene handoff** hidden at the black frame inside the pupil: the eye scene unloads and the
  nerve scene takes over there, with preloading done during the push-in.
- Report data injected as JSON from the tracker's local database.

### Performance
This is heavy. It needs:
- A quality tier system (particle counts scaled to GPU capability).
- prefers-reduced-motion respected — a static/2D fallback report.
- A plain-numbers view available regardless. A wellbeing tool must not become the thing
  that's frying your eyes.

---

## 6. Aesthetic Reference

Dark cosmic WebGL, near-black backgrounds, blue→magenta gradient glow, particles forming
and dissolving structures, glassmorphic data cards floating over the 3D layer, geometric
sans typography (Inter / Satoshi / General Sans). Reference: textura.us and similar
particle-system landing pages.

### Addendum — Act II/III material direction (settled)

The optic nerve and brain are **realistic in form, idealized in material** — anatomically
accurate but never gory. "A medically accurate optic nerve and brain carved from backlit
porcelain, thinking in slow constellations of cold light."

- **Geometry:** true fascicle bundling, dural sheath, correct chiasm, anatomically faithful
  gyri/sulci. Realism carried by silhouette and proportion.
- **Material:** polished alabaster / bone china with subsurface scattering. Cool ivory-whites
  shading into icy blue in crevices; deep sulci fall toward starfield black. Satin specular,
  never wet — "wet" is where gore creeps back in. (The eye keeps its wet cornea; an eye must
  look wet to look alive.)
- **Life/intelligence:** internal light, not surface FX. Faint threads of cold light travel
  along internal fascicles, visible through the sheath like a candle through porcelain. In
  the brain: slow, sparse constellations that kindle, connect, fade — pacing sells elegance.
  Glow events can be data-driven (one kindling per session).
- **Lighting:** museum-piece lighting — one soft key, cool rim from behind, heavy falloff to
  black. No ambient fill, no clinical brightness.
- **Data nodes:** tether filaments use the same internal-light material as the nerve signals,
  so a branch reads as "a thought the brain is holding out to show you."
- **Ruled out:** visible vasculature, red/pink tissue tones, glistening wet surfaces on
  nerve/brain, exposed cross-sections.

---

## 7. Suggested Build Order

1. Tracker daemon + local database. Nothing works without real data.
2. Plain HTML/2D report. Prove the data and the insights are good.
3. Desktop widget + break nudges. This is where the actual wellbeing benefit lives.
4. 3D report — Act I (eye) only. Ship it. Prove the aesthetic is achievable.
5. Acts II and III.

The 3D layer is the reward, not the foundation. Built last, it can be dropped or scaled
back without losing the useful application underneath.

---

## 8. Architecture (locked)

**Target OS:** macOS only.

**Two halves, deliberately separate:**

| | Stack |
|---|---|
| Tracker daemon + menu bar widget | Swift / SwiftUI, NSStatusItem |
| Shared store | SQLite file on disk |
| Report web app | React + Vite + React Three Fiber |
| Report data access | Small local HTTP server reading the SQLite file |

The two halves have almost nothing in common — one is a background poller, the other is a
WebGL cinema. Forcing them into a single codebase buys little, and macOS's native APIs are
considerably less painful reached from Swift than through bindings.

**Rejected:**
- **Electron** — ~150MB and a permanent memory drag for an app whose whole purpose is to sit
  in the background all day. Wrong tool.
- **Tauri** — genuinely viable, and the right answer *if* a single distributable binary
  becomes a requirement. Rust core, web frontend, tray built in, ~10MB. The cost is writing
  the macOS API bindings via objc2 and paying the Rust tax on what is otherwise a very
  simple daemon.

---

## 9. Open Questions

- **Where does the report run?** Local server only, or hosted?
- **Suggestion engine?** Rule-based heuristics, or an LLM given the day's summary?
- **Category mapping?** Manual, or seeded from a default list?
- **Warp: camera orbit or rotate-the-nerve?** Needs to be felt, not decided on paper. Build
  the orbit first; fall back to rotating the nerve if it turns out to be nauseating.

### Working defaults (until overridden)

- Report runs from a local server only; data never leaves the machine.
- Suggestions are rule-based heuristics over the day's summary.
- Categories seeded from a default bundle-ID list, user-editable.
- Warp built as camera orbit first, rotate-the-nerve as fallback.
