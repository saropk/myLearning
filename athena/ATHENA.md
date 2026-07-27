# ATHENA.md — Athena, spec v3

A fully local, always-listening voice assistant for macOS, in the spirit of JARVIS. Athena runs as a background daemon, wakes on spoken trigger phrases, answers questions, performs tasks on the local machine, and remembers past conversations. She is paired with a companion chat app (the "Aegis" UI) that talks to the same brain over a localhost API.

**Motto: "Athena always listens" — but nothing she hears ever leaves this machine except through one logged, user-tuned valve.**

This file (ATHENA.md) is the authoritative spec (v3: merges the v2 feature set with the hardening decisions — sandboxed execution contract, three-layer redaction, acoustic test protocol, daily-driver gate). When in doubt, the Security Invariants and the State Machine win over convenience.

---

## Core principles

1. **Local-first.** All audio processing, transcription, reasoning, memory, and task execution happen on-device. The system must be fully functional with the network cable pulled (at valve Level 0).
2. **One network chokepoint.** Exactly one module — `gateway/` — is permitted to make outbound network requests. Every other module must have zero networking code. No `requests`, `httpx`, `urllib`, or socket use anywhere outside `gateway/` (localhost calls to the daemon's own API and to Ollama on 127.0.0.1 are exempt — they never leave the machine).
3. **Tunable data valve.** Cloud intelligence (Anthropic API) is available, but only through the Gateway, governed by a valve level the user controls. The valve fails closed: any ambiguity routes to local processing.
4. **One consciousness, many faces.** The daemon owns all state. Voice pipeline and the Aegis chat UI are thin clients of the same localhost API. Killing the UI never affects Athena.
5. **Auditability over promises.** Every byte that leaves the machine is logged verbatim, locally, before it is sent.
6. **Capability pattern.** Every capability decomposes into a tool + a routing path + a permission posture. Growth is additive; no architectural change should ever be needed to add a skill.

---

## Hardware profile — 16 GB Apple Silicon (binding constraint)

RAM is the one real constraint. Budget table (numbers are the design targets from v2 — sanity-check against measured reality in phase 1 and correct this table, never silently exceed it):

| Component | Resident when | Target footprint |
|---|---|---|
| Daemon + FastAPI + wake word + VAD | always | ≤ 0.5 GB |
| whisper.cpp (`small.en`) | ACTIVE/SERIOUS only (lazy) | ~1 GB |
| Ollama 8B brain (q4) | ACTIVE/SERIOUS + 10 min grace | ~5 GB |
| Embedding model | on demand | ~0.5 GB |
| **Warm total (talking)** | | **~7 GB** |
| **DORMANT total** | | **≤ 0.6 GB** |

Discipline levers (rules, not suggestions):

- **Lazy whisper:** the STT model loads on wake and is released on return to DORMANT.
- **Ollama `keep_alive`:** the brain unloads after 10 minutes of DORMANT.
- **`brain.lite` escape hatch:** documented config flag swapping the 8B model for a ~3B one when the user needs headroom; degrades quality, never availability.
- **Convention:** any new resident component must be justified against this table before it is added.

**Measured reality:** recorded in `tests/phase1_ram.md`, and reported live by `/api/status`
(Aegis shows total-vs-budget and turns red when over). As of the phase 1 build the
always-resident Python slice measures ~0.06 GB against the 0.5 GB line it shares with the
wake word and VAD, so **no correction to the table is justified yet** — but the numbers
above remain unverified on 16 GB Apple Silicon until whisper and the 8B brain are actually
resident there. Re-measure and correct the table during phase 2.

Accepted trade-off: valve Level 0 SERIOUS mode on an 8B brain is competent but not sharp; the valve exists so cloud-grade reasoning is available when privacy permits.

---

## Repository layout

```
athena/
├── ATHENA.md                  # this file — the authoritative spec
├── CLAUDE.md                  # one line: points Claude Code to ATHENA.md
├── athena.toml                # user config (wake phrases, models, valve default, port, brain.lite)
├── pyproject.toml
├── design/
│   └── reference.png          # GROUND TRUTH for the Aegis emblem — see Aegis UI spec
├── athena/
│   ├── __main__.py            # entrypoint: python -m athena
│   ├── daemon.py              # FastAPI app, lifespan wiring, localhost binding
│   ├── state.py               # the state machine (single source of truth)
│   ├── brain.py               # routing: fast path → constrained tool intent → answer
│   ├── voice/
│   │   ├── wake.py            # wake word engine wrapper (custom "Athena" keyword)
│   │   ├── vad.py             # Silero VAD gate in front of whisper
│   │   ├── listen.py          # mic capture + transcription + name-addressing filter
│   │   └── speak.py           # TTS output, interruptible
│   ├── tools/
│   │   ├── registry.py        # tool schema registry exposed to the LLM
│   │   ├── music.py           # Tier 1 — AppleScript control of Music/Spotify
│   │   ├── calendar.py        # Tier 1 — EventKit via `shortcuts run` or pyobjc
│   │   ├── files.py           # Tier 1 — mdfind search, open, read (read-only)
│   │   ├── apps.py            # Tier 1 — open/quit applications
│   │   ├── safari.py          # Tier 1 — open URLs/tabs via AppleScript
│   │   ├── system.py          # Tier 1 — volume, brightness, sleep, Do Not Disturb
│   │   ├── mail.py            # Tier 1 — local Mail.app store, away-briefing
│   │   ├── code.py            # Tier 1.5 — sandboxed execution (padded room)
│   │   ├── draft.py           # Tier 1.5 — creation-only writing, never overwrites
│   │   └── fallback.py        # Tier 2 — System Events generic app control
│   ├── memory/
│   │   ├── store.py           # SQLite schema, write path
│   │   ├── recall.py          # tiered retrieval (hot → warm → cold PQ re-rank)
│   │   └── consolidate.py     # nightly "Athena dreams" job
│   ├── gateway/
│   │   ├── gateway.py         # THE ONLY MODULE WITH INTERNET ACCESS
│   │   ├── valve.py           # levels 0–3, classification, fail-closed logic
│   │   ├── redact.py          # three-layer Level 2 redaction pipeline
│   │   └── audit.py           # verbatim outbound payload log
│   └── ui/
│       ├── index.html         # Aegis chat app shell
│       ├── aegis.js           # WebGL2 setup, uniforms, dev panel (see Aegis UI spec)
│       ├── aegis.frag         # the emblem: ray-marched black hole shader
│       └── chat.js            # chat client for /api/chat + /api/events (SSE)
├── scripts/
│   ├── install_launchd.sh
│   ├── sandbox.sb             # sandbox-exec profile for code.py
│   └── egress_lockdown.md     # OS-level firewall rule instructions
└── tests/
```

---

## State machine (`state.py`)

Three states. Transitions are matched by **plain-string phrase matching on the transcript, before the LLM ever sees the text**. Deactivation must work even if Ollama is down or the model is mid-generation (cancel in-flight generation on transition).

```
DORMANT ──"athena, initiate" | "athena, it's go time"──▶ ACTIVE
ACTIVE  ──"athena, let's get serious" | "athena, let's get cracking"──▶ SERIOUS
SERIOUS ──"good session athena"──▶ ACTIVE
ACTIVE | SERIOUS ──"that's enough for today athena"──▶ DORMANT
```

Rules:

- Phrase matching is case-insensitive, punctuation-stripped, and tolerant of leading/trailing words in the same utterance.
- Wake phrases are configurable in `athena.toml` but the defaults above must always work.
- In `DORMANT`, only the wake-word engine runs. **No transcription occurs and no audio is stored.** Raw audio buffers are discarded immediately after the wake-word check.
- In `ACTIVE`, each utterance is transcribed and routed: task → tool call, question → answer (spoken + logged). Conversation context is kept for the session.
- In `SERIOUS`, the brain switches to the serious system prompt, retrieves memory before every reply, and allows longer multi-turn reasoning. SERIOUS transcripts are always written to memory.
- An `ACTIVE` session auto-returns to `DORMANT` after a configurable idle timeout (default 120 s) with a brief spoken confirmation. `last_session_end` is written to `settings` on every transition to DORMANT.
- State is owned by the daemon and broadcast over `/api/events` (SSE) so the Aegis emblem reacts live.

### Name-addressing convention

In ACTIVE and SERIOUS, an utterance counts as *directed at Athena* only if it **starts or ends with "Athena"**. Everything else in the room is overheard, not commanded — transcribed for session context but never acted on.

- **Follow-up window:** for **8 seconds** after Athena finishes asking a question or completing a reply, the next utterance is treated as directed without requiring her name. The window closes on silence or on a new named address.
- The address token is stripped before routing.

### Modality handoff (voice ⇄ text)

State (what her brain is doing) and modality (which mouth and ears she's using) are orthogonal. Voice and the Aegis chat are one session with one context; these phrases switch the channel mid-thought without touching state or losing context:

- **"Athena, let's get talking"** — typed or spoken: opens the live voice loop and switches replies to speech.
- **"Athena, let's get handsy"** — spoken or typed: closes the live mic loop and continues the same session in text via Aegis (hands on keyboard).

Rules:

- Handoff phrases are matched by the same pre-LLM string rules as state transitions and must work even if the model is down.
- **Text-initiated sessions start mic-closed by default** — the microphone opens only on the talking phrase. (A quiet privacy win: chatting with Athena at 2 AM never means the room is being transcribed.)
- Modality changes are broadcast on `/api/events` so Aegis can indicate mic-open vs mic-closed.
- DORMANT is unaffected: entering/leaving DORMANT still requires the state phrases; modality applies within ACTIVE and SERIOUS.
- Reserved view phrase: "Athena, show me your mind" opens the brain view in Aegis (see The brain view).

### Voice reliability (non-negotiable plumbing)

- Custom-trained Porcupine (or openWakeWord) "Athena" keyword.
- **Silero VAD gate** in front of whisper: transcribe human speech, not fans and traffic.
- **Push-to-talk hotkey** (configurable, default ⌥Space) as a manual override that force-opens an ACTIVE listening window. Even JARVIS had manual overrides.
- **Acoustic test protocol (phase 2, mandatory):** a fixed script of 10 phrases spoken under a condition matrix — adjacent / across the room / music playing / morning voice. Record detection and false-positive rates; tune wake sensitivity against this scorecard once, properly, instead of forever by vibes. Keep the script and scores in `tests/acoustic_protocol.md`.

---

## Daemon API (localhost only)

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/chat` | POST | Text message in → assistant reply (used by Aegis UI). Body: `{message, mode_hint?}` |
| `/api/events` | GET (SSE) | Stream of `{state, valve, modality, speaking, amplitude}` events for the UI |
| `/api/state` | GET/POST | Read or set state (POST allows UI buttons to mirror voice phrases) |
| `/api/valve` | GET/POST | Read or set valve level 0–3 |
| `/api/status` | GET | Daemon health: uptime, loaded models, RAM footprint vs budget, last errors |
| `/api/audit` | GET | Paginated list of outbound payloads (verbatim) with timestamps and valve level |
| `/api/memory/facts` | GET | The distilled warm-tier facts with provenance — how the user audits what Athena believes about them |
| `/api/memory/map` | GET | The brain view data: topic clusters with named constellations, session stars, tiers, positions (recomputed nightly, cached) |
| `/api/memory/search` | GET | Debug/inspection of tiered memory retrieval |

Bind strictly to `127.0.0.1`. Random per-install bearer token (generated on first run, stored in settings) required on every request.

---

## Brain (`brain.py`)

Routing order per directed utterance:

1. **State-transition phrases** (`state.py`, string match, absolute priority).
2. **Fast path:** regex/keyword table for high-frequency commands ("pause", "play some music", "volume up", "what time is it") → direct tool dispatch, **< 100 ms to action**, no LLM round-trip.
3. **Constrained tool intent:** the local LLM emits **structured output against a strict JSON schema** (grammar-constrained generation via Ollama's format parameter). A malformed tool call must be impossible by construction, not caught after.
4. **Answer path:** plain reply; local vs cloud decided by `gateway/valve.py`.

Prompts: `ACTIVE` is concise, tool-forward, ≤ 2 spoken sentences unless asked. `SERIOUS` enables debate, willingness to disagree, and memory-grounded corrections ("On June 12 you said…"). TTS is always interruptible; a new utterance cancels speech.

## Tools (`tools/`)

Tiered app control. Every tool: zero network access, logged with arguments and results.

- **Tier 1 (six first-class skills + mail):** `music`, `calendar`, `files` (read-only), `apps`, `safari`, `system`, plus `mail`. Purpose-built, high-quality AppleScript/EventKit/mdfind integrations.
- **Tier 1.5 (guarded capabilities):** `code.py` and `draft.py` — see contracts below.
- **Tier 2 (fallback):** `fallback.py` drives arbitrary apps via System Events at lower fidelity, so unknown requests degrade instead of failing.
- TCC permission failures (Microphone, Automation, Calendar) produce friendly spoken explanations plus a deep link to the right System Settings pane.

### `mail.py` — email briefings (Tier 1)

Mail.app has already fetched the mail; Athena only reads its **local store** via AppleScript. Zero Gateway involvement, zero new network surface.

- **Away-briefing:** on wake after an absence, filter `date received > last_session_end` and brief: one headline count, then only items worth attention (the local brain triages; promotional/automated mail is counted, not narrated). Hard cap ~4 spoken sentences; "anything else?" expands on request. Skippable mid-speech; disableable in config.
- **Valve rule (absolute):** inbox content is a personal entity. Summarization is local-brain work, always; no valve level below 3's explicit per-payload consent makes mail cloud-eligible. Summarizing a day's email is compression, not brilliance — the 8B model suffices.

### `code.py` — sandboxed execution (Tier 1.5, the padded room)

The only write-capable, side-effect-capable skill. Built last, kept paranoid. Three walls:

1. **Filesystem wall:** all execution confined to `~/Athena/workbench/`, enforced at the OS level via `sandbox-exec` with the profile in `scripts/sandbox.sb` (deny-default; allow read/write only inside the workbench + read of the interpreter runtime). Not a convention — a kernel-enforced boundary.
2. **Resource wall:** hard wall-clock timeout (default 30 s) and memory cap; runaway scripts are killed, then explained.
3. **Network wall (free):** the egress firewall permits outbound traffic only for the Gateway process. Any spawned subprocess is by definition not the Gateway, so code that tries to phone home hits the kernel. No extra policy needed.

Consent must be informed: before running, Athena states **what the code touches** (files read/written, expected effect) and requires verbal confirmation. On failure, she explains the error and proposes the correction. Valve rule: code content is never cloud-eligible without Level 3 per-payload consent.

### `draft.py` — writing (Tier 1.5)

Creation-only: writes new files into the workbench, **never overwrites an existing file** (test asserts it), never sends anything anywhere. Drafts are handed to the user, not acted on.

---

## Memory (`memory/`) — three tiers, never deletes

**Design principle: Athena never deletes; she lets distance do the softening.** Quantization *is* the forgetting — old memories blur into cheap, low-resolution gists unless she deliberately concentrates on them. Nothing is ever erased.

SQLite at `~/Library/Application Support/Athena/athena.db`, directory `chmod 700`.
Tables (minimum): `messages`, `embeddings`, `facts`, `fact_provenance` (join table), `settings`, `audit`.

### Tiers

1. **Hot** — last N days (default 14). Full-precision embeddings, full transcripts, exact cosine retrieval. What SERIOUS quotes verbatim.
2. **Warm** — distilled facts from consolidation ("Saro prefers Porcupine over openWakeWord for latency"). Full-precision embeddings over short fact strings; dated, versioned, provenance-linked.
3. **Cold** — raw transcripts older than the hot window whose embeddings are **Product-Quantized** (~30× compression). Raw text stays on disk untouched; only vectors compress. Searched via asymmetric distance computation; candidates re-ranked at full precision on demand.

Retrieval flow: query → exact search over hot + warm → if signals suggest deeper detail, coarse PQ scan of cold → fetch + re-rank the survivors → assemble context.

### Consolidation — nightly launchd job ("Athena dreams")

- Local LLM reads hot transcripts aging out, distills fact-memories, demotes raw transcripts to cold (vectors PQ-encoded).
- **Conservative-writer rule:** distill only what is clearly stated or strongly implied — facts, preferences, decisions, outcomes. Inferred personality judgments: never.
- ACTIVE sessions contribute facts/outcomes only; SERIOUS sessions persist full transcripts and feed consolidation.
- PQ codebooks trained on the install's own vectors (plain k-means, no FAISS dependency); retrained when the corpus doubles.

### Provenance posture — chill, not nonchalant

Always (non-negotiable): every fact carries provenance (foreign keys to source messages, written at consolidation); facts are dated and versioned; a contradicting fact **supersedes** rather than overwrites — belief history is kept; on challenge ("that's not what I said"), Athena pulls the source, checks, and corrects the fact aloud if unsupported.

Never (explicitly out of scope): confidence scores or job citations in normal speech; retrieval-time re-verification; user confirmation gates on consolidation writes (auditing happens via `/api/memory/facts` in Aegis).

Behavioral summary: **trust by default, verify on challenge.** "Athena, forget the last conversation" deletes that session's rows and embeddings — the one explicit exception to never-delete, because it is the user's command.

---

## Gateway and the valve (`gateway/`)

The only module allowed to import networking libraries. Enforced by a CI test that greps the rest of the package for forbidden imports (`requests`, `httpx`, `urllib`, `socket`, `aiohttp`) and fails if found outside `gateway/`.

Valve levels (persisted, changeable by voice, UI, or `/api/valve`):

- **Level 0 — Sealed.** No outbound traffic at all. Verified, not promised (see acceptance).
- **Level 1 — Questions only (default).** Cloud-eligible only if the classifier judges the request general-knowledge with zero local context. Anything referencing files, calendar, mail, code, people the user knows, memory contents, or prior local results stays local.
- **Level 2 — Redacted context.** Three-layer pipeline in `redact.py`:
  1. **Deterministic scrub** (no AI): regex + NER + the user's contacts list remove emails, phone numbers, file paths, addresses, and known names. Pattern-matchers never get lazy.
  2. **LLM abstraction:** the local model rewrites the request as an anonymous, generalized question.
  3. **Blind verification:** the local model is shown *only the abstraction* and asked one question — "does this contain anything identifying?" Any yes, or any hesitation, cancels the transmission and answers locally.
  Both original and abstraction are written to the audit log so the user can grade the redactor's homework.
- **Level 3 — Open (per-request consent).** Full context may go out, but each transmission requires explicit confirmation of the exact payload, read back or displayed.

Hard rules: **fail closed** on every uncertainty and every network error (with a spoken note the local model answered); **audit everything** verbatim *before* sending; API key from macOS Keychain, loaded by `gateway.py` only; recommended kernel backing via PF/Little Snitch scoped to the daemon process (`scripts/egress_lockdown.md`) — which also gives `code.py` its network wall for free.

---

## Aegis UI spec (`ui/`)

The companion app is a single dark page served by the daemon: the Aegis emblem centered, wordmark split as **ATH ⟨emblem⟩ ENA**, chat below.

### Ground truth

`design/reference.png` is the user-provided reference image (an edge-on, Gargantua-style black hole: blazing white-gold core, disk cooling to deep ember-red tapered tips, thick cream lensed halo above and a bright lensed arc below the shadow, pale photon ring, dense multi-colored starfield with soft nebulae). **It is the acceptance standard.** The finished emblem must hold up in a direct side-by-side comparison with this image. When in visual doubt, open the reference — never invent a look. The user is the final acceptance test; no emblem milestone is "done" until they approve it side-by-side on screen.

### Implementation: WebGL2 ray-marched shader (`aegis.js` + `aegis.frag`)

The emblem is a full-screen-quad fragment shader, not 2D canvas drawing. Any canvas-2D sketches from the design phase are storyboards for composition only — do not port them; flat shape-layering cannot reach the reference look. The cinematic quality comes from actual light transport:

- **Lensing:** Schwarzschild geodesic bending per ray (numeric integration, 64–128 steps, or the Beloborodov approximation). The upper/lower lensed disk images and the photon ring must *emerge from the lensing math*, never be painted as arcs.
- **Disk:** thin equatorial disk, `r_in ≈ 2.2 r_s`, `r_out ≈ 5.5 r_s`; camera inclination ≈ 85° (near edge-on), roll ≈ −12° so the blade cuts diagonally as in the reference. Procedural noise in disk density for plasma streaks, advected with Keplerian `ω ∝ r^-1.5` so the disk visibly spins.
- **Shading:** radial temperature palette sampled from the reference image's actual pixels — approximately `#FFF6E0 → #FFD37A → #FF8C2E → #E0451C → #7A1E0A` core-to-tips — plus Doppler/relativistic beaming (approaching side brighter and whiter).
- **Post:** HDR accumulation → bright-pass → two-pass Gaussian bloom → ACES tonemap. The bloom is what makes it cinematic; treat it as required, not polish.
- **Starfield:** ≈240 stars in four color families (neutral, blue-white, warm, pink). Chromatic scintillation per star: two superimposed sine flickers (≈0.7–2.5 Hz slow wander + ≈2–6 Hz shimmer) and a slow hue drift between a cool-shifted and warm-shifted variant of the star's own color; soft bloom on the brightest; a few faint pink/blue/violet nebula blobs. No cross or plus-sign glints of any kind.
- **Engraving:** Athena in left-facing profile, coin style — crested Corinthian helm with plume hatching, brow/nose/lips/chin, cheek guard, hair curl — as a crisp SVG overlay composited over the shadow (not drawn in the shader), two-pass ember stroke, ~7 s luminance pulse. Optional Gorgoneion (Medusa) cross-fade at valve Level 0, built last.
- **Wordmark:** `ATH` / `ENA` flanking, weight 500, letter-spacing 0.28em, `#F3E7D8`.
- **Fallbacks:** `prefers-reduced-motion` → one static high-quality frame; no WebGL2 → the canvas-2D storyboard as an explicitly degraded fallback.
- **Study material:** James, von Tunzelmann, Franklin & Thorne (2015), *Gravitational Lensing by Spinning Black Holes in Astrophysics, and in the Movie Interstellar* (Class. Quantum Grav. 32) for the math; public Shadertoy black-hole shaders may be studied for technique, but write original code.

### Tuning workflow (mandatory)

- Dev panel behind `?dev=1`: live sliders for inclination, roll, `r_in`/`r_out`, temperature-curve bias, Doppler strength, bloom threshold/strength, exposure, and spin speed, so the gap between render and reference is closed by turning knobs with the user, not by recompiling guesses.
- Emblem build order (inside phase 6), each step ends with a side-by-side against `design/reference.png` and explicit user approval before continuing: (a) static lensed frame; (b) spin, plasma shimmer, star scintillation; (c) engraving + wordmark; (d) state/valve reactivity.
- Performance target: 60 fps at Retina on Apple Silicon; degrade ray-march steps before resolution.

### State-reactive behavior (driven by `/api/events`)

- `DORMANT`: disk slow and dim, deep-red palette, engraving barely visible.
- `ACTIVE`: disk brightens and speeds up ~1.6×, engraving at full glow.
- `SERIOUS`: disk tightens (`r_in` −10%) and shifts white-hot; halo intensifies.
- Speaking: photon ring pulses with the TTS amplitude value from the event stream.
- Valve tint on the ambient halo and engraving, eased over ~1 s:

| Level | Ambient halo | Engraving | Intensity |
|---|---|---|---|
| 0 Sealed | `rgb(112,20,10)` | `rgb(195,75,55)` | 0.38 (dim, watchful) |
| 1 Questions only | `rgb(205,78,32)` | `rgb(255,178,118)` | 0.85 |
| 2 Redacted | `rgb(236,128,58)` | `rgb(255,205,150)` | 1.0 |
| 3 Open | `rgb(255,178,84)` | `rgb(255,228,178)` | 1.15 (warm gold) |

One glance at the emblem shows both mode and privacy posture. All state transitions ease over ~1.5 s, never snapped. Aegis also renders an `/api/status` panel (RAM vs budget, models loaded) and the `/api/memory/facts` audit view.

---

## macOS integration

- **launchd:** `scripts/install_launchd.sh` writes the LaunchAgent plist (`RunAtLoad`, `KeepAlive`) and loads it; a second plist schedules the nightly consolidation job. Logs to `~/Library/Logs/Athena/`.
- **Permissions (TCC):** Microphone, Automation for Music/Finder/Mail/Safari, Calendar. Handle denials gracefully with a spoken/UI explanation and a deep link to the relevant System Settings pane.
- **No sandboxing tricks for Athena herself:** do not request Full Disk Access unless `files.py` proves to need it (mdfind generally does not). `sandbox-exec` applies to *executed code*, not to the daemon.

---

## Build order

Work phase by phase. Each phase must run and pass its acceptance check before starting the next.

1. **Skeleton + text brain.** Daemon, config, state machine, `/api/chat` against Ollama, `/api/status`, minimal Aegis page with working chat. ✔ Accept: text conversation with mode switching via typed phrases; state events visible; measured RAM matches the budget table (correct the table if not).
2. **Voice loop.** Wake word → VAD → transcribe → name-addressing filter → route → spoken reply; 8 s follow-up window; idle timeout; interruptible TTS; push-to-talk hotkey. ✔ Accept: full hands-free session from "Athena, initiate" to "That's enough for today Athena"; **acoustic test protocol executed and scores recorded in `tests/acoustic_protocol.md`**; undirected room speech provably ignored; typed "Athena, let's get talking" opens the mic mid-session with context intact, spoken "Athena, let's get handsy" closes it and the conversation continues seamlessly in text; a text-initiated session provably keeps the mic closed until the talking phrase.
3. **Brain + fast path + tools tier 1 & 1.5.** Constrained tool-call output; fast-path commands; music/calendar/files/apps/safari/system/mail skills; away-briefing; `code.py` + `draft.py` with guardrails. ✔ Accept: fast-path commands < 100 ms to action; malformed tool call impossible by construction; TCC failures produce friendly speech; away-briefing fires after simulated absence and summarizes only post-timestamp mail; `code.py` refuses to run without verbal confirmation, is denied outside the workbench by `sandbox.sb`, and kills runaway scripts at timeout; `draft.py` cannot overwrite an existing file (test asserts it).
   **→ Daily-driver gate: after phase 3, stop building for two weeks and live with her.** Hot-tier-only Athena as a daily driver decides what warm/cold consolidation should prioritize. Usage schedules phase 4, not enthusiasm.
4. **Memory.** Hot tier first; then warm facts + nightly consolidation + provenance; then cold PQ tier; "forget" command; `/api/memory/facts`. ✔ Accept: Athena correctly references a fact from a previous session with provenance intact; a superseded fact keeps its history; forget removes a session end-to-end.
5. **Gateway + valve.** Levels 0–3, classifier, three-layer redactor, audit log + `/api/audit`, Keychain loading, forbidden-import test. ✔ Accept: Level 1 general question uses the cloud and appears verbatim in the audit log; a question mentioning a local file stays local; **PQ recall check** (cold-tier query surfaces the correct transcript after re-rank); **Level 0 produces zero outbound packets, verified with `nettop`**; redaction pipeline's original/abstraction pairs visible in audit.
6. **Aegis emblem + service install.** WebGL shader emblem via the tuning workflow (static frame → motion → engraving → reactivity, user side-by-side approval against `design/reference.png` at each step); Gorgoneion at Level 0; status + facts panels; launchd install. ✔ Accept: user confirms side-by-side comparability to the reference; emblem reflects live state and valve changes; 60 fps on Apple Silicon; daemon survives reboot.

---

## Horizon (v2 scope — documented so v1 never blocks it, NOT to be built now)

- **Initiative engine:** Athena speaking unprompted beyond the away-briefing (calendar nudges, anomaly alerts). Needs a theory of when silence is correct; the daemon already sees calendar, state, and memory, so this is a future consumer of existing infrastructure.
- **Action valve:** the sibling of the data valve, governing *autonomy* instead of *data* — Level 0 "propose only" → Level 3 "act freely within scope." Prerequisite for any multi-step autonomous workflow. Until it exists, the standing rule holds: **Athena acts once per confirmed request; anything with external consequence (send, publish, delete, pay) is out of scope.** Aegis may eventually tint for the action valve as it does for the data valve.
- **Business/creation workflows:** decompose into registry tools following the existing pattern (capability = tool + routing path + permission posture). No architectural change anticipated; growth is additive.

---

## The brain view (v1.1 — build after phase 4, does not block v1)

A second Aegis view: instead of scrolling a chat log, the user looks at Athena's mind. The emblem stays at center; the sky around it becomes her memory.

- **Stars = sessions.** Every past conversation is one star. Hover → title and date; click → that session's transcript opens in the chat pane.
- **Constellations = topics.** Session embeddings (mean of message embeddings) are clustered (k-means or HDBSCAN); the local LLM names each cluster in 2–3 words. Thin constellation lines join a cluster's stars.
- **Distance = tier. Brightness = precision.** Hot-tier sessions orbit close to the emblem and burn bright; warm facts occupy the middle ring; cold, Product-Quantized sessions drift to the outer dark as faint, fuzzy stars. This is "distance does the softening" made visible — nothing is gone, old memories are just far and soft. Clicking a cold star triggers the full-precision re-rank and the detail snaps into focus: retrieval as a telescope.
- **The sky rearranges when she dreams.** Cluster assignments, names, and positions are recomputed by the nightly consolidation job and served cached via `/api/memory/map`. New sessions appear near the emblem; aging ones drift outward.
- **Layout:** angle = cluster sector around the emblem; radius = tier ring (three faint tier rings drawn as orientation); jittered clumping within a cluster so constellations read as constellations, not grids.
- **Access:** a view toggle in Aegis, plus the voice phrase "Athena, show me your mind" (string-matched like all phrases).
- **Render:** same scene as the emblem (WebGL layer or 2D overlay); a few hundred sessions is trivial, and cold stars are deliberately low-detail so the view scales to years.

✔ Accept: hover reveals session title/date; click opens the correct transcript; the nightly job visibly re-clusters after new sessions; a cold-star click performs the full-precision re-rank; view toggles by button and by phrase.

---

## Security invariants (never violate)

1. No networking imports outside `gateway/` — enforced by test.
2. Daemon binds `127.0.0.1` only, with bearer token auth.
3. In DORMANT, audio is never transcribed or persisted.
4. Valve fails closed in every ambiguous or error path.
5. Outbound payloads are logged verbatim before sending.
6. API keys live in the Keychain only — never in files, never in the repo, never in logs.
7. Deactivation phrases are honored by string matching, independent of any model's availability or opinion.
8. Memory DB directory is `chmod 700`; no telemetry, analytics, or crash reporting of any kind.
9. Executed code is confined to the workbench by `sandbox-exec`, resource-capped, and — being a spawned process, never the Gateway — has no network. Mail and code content are never cloud-eligible below Level 3 per-payload consent.

---

## Conventions

- Python: type hints everywhere, `ruff` for lint/format, small modules, no global mutable state outside the daemon's app state.
- Frontend: no build step, no framework; vanilla JS + WebGL2 for the emblem, plain DOM for chat. All emblem colors are intentional hardcoded hex sampled from `design/reference.png` (it is night-sky art, not themed UI). Never mark emblem work complete without the user's side-by-side approval.
- Tests: pytest; every phase adds tests for its acceptance criteria; the forbidden-import egress test is mandatory from phase 5 on.
- Voice UX: replies in ACTIVE are short; never read file paths aloud character by character; confirm destructive-feeling actions verbally.
- RAM discipline: any new resident component must be justified against the 16 GB budget table in this file.
