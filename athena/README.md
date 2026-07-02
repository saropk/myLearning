# Athena 🦉 — a voice-activated assistant

Athena (Greek goddess of wisdom, war and strategy) is a hands-free assistant.
Say her name, give a command, and she either handles it instantly with a
built-in skill or reasons about it — and acts — using Claude.

- **Wake word + conversation mode** — "Athena, what's the weather?" then keep
  talking; follow-ups don't need the wake word again.
- **Two brains, chosen automatically:**
  - **Claude tool-use brain** (when `ANTHROPIC_API_KEY` is set) — understands
    natural language and can *chain actions*: _"I'm cold, turn the music down and
    tell me the forecast"_ becomes two real tool calls plus a spoken summary.
  - **Offline keyword brain** (no key needed) — fast, deterministic, private.
- **Mixed voice engine** — cloud speech-to-text (accurate) + offline speaking
  (private, no data leaves your Mac when talking).
- **Live data, no extra API keys** — weather (Open-Meteo) and news (Google News).

---

## What she can do

| Say… | Athena… |
|------|---------|
| "what time is it?" / "what's the date?" | tells the time / date / day |
| "what's the weather in Tokyo?" | live current conditions |
| "give me the news" / "news about space" | reads the top headlines |
| "set a timer for 10 minutes to check the oven" | counts down and reminds you |
| "remember that my locker code is 4417" | saves it permanently |
| "what do you remember?" | recalls saved facts |
| "what is 15 times 12?" | does the math |
| "play Bohemian Rhapsody" / "pause" / "next" | plays / controls music |
| "volume up" / "set volume to 40" / "mute" | adjusts system volume |
| "open Safari" / "launch Spotify" | opens a macOS app |
| "open YouTube" / "search for flights to Rome" | opens a site / web search |
| "who is Ada Lovelace?" | answers (via Claude, or Wikipedia offline) |
| "flip a coin" / "roll a dice" | random fun |
| "tell me a joke" / "how are you?" | small talk |
| _anything else_ | Claude answers conversationally |
| "goodbye" | shuts down |

With the Claude brain active, you don't need the exact phrasing above — say it
however feels natural and Claude routes it to the right skill.

---

## Setup (macOS)

```bash
# 1. PortAudio is needed by PyAudio (the microphone library)
brew install portaudio

# 2. Create a virtual environment and install dependencies
cd athena
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Give Athena her Claude brain (optional but recommended)
cp .env.example .env          # paste your Anthropic API key into .env
export ANTHROPIC_API_KEY="sk-ant-..."
```

The first run prompts macOS for **Microphone** permission (and **Automation**
permission for app/volume/Music control) — allow both.

---

## Running

From the directory **above** `athena/`:

```bash
python -m athena          # voice mode (needs a mic)
python -m athena --text   # keyboard mode — great for testing, no mic needed
```

In voice mode: say **"Athena"**, wait for "Yes?", then speak — or say it all at
once, _"Athena, what's the weather in Paris?"_. After she answers she keeps
listening briefly, so you can just say _"and the news?"_ without waking her again.

---

## How it fits together

```
  microphone ─▶ voice/listener.py ─▶ brain ─┬─ KeywordBrain ─▶ skills/*  (offline)
   (Google STT)                             │
                                            └─ LLMBrain ─▶ Claude ⇄ skills as tools
  speaker  ◀── voice/speaker.py ◀── reply ◀─┘                (claude-opus-4-8)
   (pyttsx3, offline)
```

- **`brain/__init__.py`** picks the brain: Claude if a key is present (with the
  keyword brain as an automatic fallback on API errors), otherwise keyword-only.
- **`brain/llm.py`** runs a tool-use loop — each skill's `tool_spec()` is a tool
  Claude can call; results are fed back for one natural spoken reply.
- **`brain/keyword.py`** matches skills by their `parse()` in priority order.
- Every skill lives in `skills/` and implements one `run()` used by both paths.
- Settings live in `config.py`, all overridable via environment variables.
- Persistent memory is a JSON file at `~/.athena/memory.json`.

---

## Adding a skill

Each skill implements a single `run()`, plus a `parse()` for the offline path.
Set `expose = True` to let Claude call it as a tool.

```python
from .base import Skill

class CoffeeSkill(Skill):
    name = "make_coffee"
    triggers = ("coffee", "espresso")

    expose = True
    description = "Start the coffee machine."
    parameters = {"size": {"type": "string", "enum": ["small", "large"]}}

    def run(self, athena, size="small"):
        return f"Brewing a {size} coffee."      # return None to defer

    def parse(self, text):                        # offline keyword extraction
        return {"size": "large" if "large" in text else "small"} \
            if self.can_handle(text) else None
```

Then register it in `skills/__init__.py` → `build_skills()` (order matters for
the keyword brain — more specific skills first).

---

## Notes & limits

- **macOS-focused for system actions.** App launching, volume and Music control
  use AppleScript / `open`. On Linux/Windows those no-op, but voice, weather,
  news, timers, math, memory, web/search and the Claude brain still work.
- **Speech-to-text needs internet** (Google recogniser); speaking is offline.
- The **wake word is simple keyword-spotting** — it listens continuously and
  matches "athena" in the transcript. Good for personal use; a trained hotword
  engine (e.g. Porcupine) would be the next upgrade for offline, false-trigger-
  resistant detection.
- `pywhatkit` and `wikipedia` are optional. Without them, "play" opens a YouTube
  search and offline factual lookups defer to Claude.
