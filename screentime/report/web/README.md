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

- **The full almond eye**: upper/lower lids with the fish-curve fissure
  and instanced lashes, floating in space (near-black shells dissolve
  into the starfield — no face). The globe (sclera + iris + cornea +
  pupil) drifts behind stationary lids; blinks are real lid geometry,
  and the lids part wider as the camera pushes in.
- **The iris & cornea**: custom-GLSL iris (radial stromal fibres, limbal
  ring, collarette, icy palette, animated shimmer), refractive cornea
  shell with the wet specular.
- **The clock pupil**: ring + hands as real geometry, ticking at idle;
  hands accelerate through the push-in and smear into spinning additive
  blur arcs at the through moment — the vortex.
- **Strain reddening**: the sclera shader grows bloodshot veins from the
  periphery toward the iris, driven by the eye-strain score
  (`src/strain.js`) computed from `/api/report` — marathons, skipped
  breaks, late-night use, heavy totals. `?strain=0.9` pins it for
  look-dev.
- **Push-in (scroll 0–30%)**: camera dollies from off-axis into the
  pupil; FOV tightens; pupil dilates; a black veil resolves at ~27–31% —
  the scene-handoff moment where Act II will take over.
- **Starfield**: two parallax point layers plus a streak layer — lines
  stretch radially as speed builds through the push-in (full hyperspace
  is reserved for the warp).
- **Quality tiers** (`src/quality.js`): star counts and DPR scaled to the
  GPU; bloom off on the low tier; `off` tier and `prefers-reduced-motion`
  render a static page linking to the plain-numbers report.
- **Look-dev**: `?p=0.22` pins the timeline, `?strain=0.9` pins the
  redness — inspect any beat without scrolling or real data.

## Still to come (steps 5a/5b)

- Transition: through-the-pupil geometry flight, warp orbit (with the
  rotate-the-nerve fallback), scene handoff + preloading.
- Act II: porcelain optic nerve, data-driven branch nodes from
  `/api/report`.
- Act III: the brain, suggestion cards from the `suggestions` array,
  the resolved ending.
