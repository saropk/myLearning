# web — the 3D report (Act I: the eye)

Build step 4: the scroll-driven WebGL journey. This ships **Act I only** —
the eye in starfield space, the clock pupil, and the push-in — per the
spec's build order ("ship it; prove the aesthetic is achievable").

React + Vite + React Three Fiber, GSAP ScrollTrigger + Lenis for the
scroll scrub, custom GLSL for the iris and starfield.

## Run

```sh
npm install
npm run dev        # http://localhost:5173, proxies /api to :5177
```

Start the report server too (`python3 ../server/server.py`) — the "plain
numbers" link points at it, and Acts II–III will pull `/api/report`.

## What's implemented

- **The eye**: sclera with a polar-cap aperture, custom-GLSL iris
  (radial stromal fibres, limbal ring, collarette, icy palette, animated
  shimmer), refractive cornea shell with the wet specular, and the
  **clock pupil** — ring + hands as real geometry, ticking at idle.
- **Idle life**: slow drift, subtle pupil breathing, a screen-space blink
  every ~8 s. The drift calms as scrolling begins.
- **Push-in (scroll 0–30%)**: camera dollies from off-axis into the pupil;
  FOV tightens; the pupil dilates and the hands sweep faster the closer
  you get; a black veil resolves at ~27–31% — the scene-handoff moment
  where Act II will take over.
- **Starfield**: two parallax layers of GPU points, additive, twinkling.
- **Quality tiers** (`src/quality.js`): star counts and DPR scaled to the
  GPU; bloom off on the low tier; `off` tier and `prefers-reduced-motion`
  render a static page linking to the plain-numbers report.
- **Look-dev**: `?p=0.22` pins the timeline at any progress for
  inspection/screenshots without scrolling.

## Still to come (steps 5a/5b)

- Transition: through-the-pupil geometry flight, warp orbit (with the
  rotate-the-nerve fallback), scene handoff + preloading.
- Act II: porcelain optic nerve, data-driven branch nodes from
  `/api/report`.
- Act III: the brain, suggestion cards from the `suggestions` array,
  the resolved ending.
