# Athena 🦉 — a voice-activated assistant

Athena (Greek goddess of wisdom, war and strategy) is a hands-free assistant.
Say her name, give a command, and she either handles it instantly with a
built-in skill or thinks it through with Claude.

- **Wake word + voice commands** — "Athena, what time is it?"
- **Hybrid brain** — fast rule-based skills, with Claude for open-ended questions
- **Mixed voice engine** — cloud speech-to-text (accurate) + offline speaking (private)
- **Built for macOS** — opens apps, controls volume and Music via AppleScript

---

## What she can do today

| Say… | Athena… |
|------|---------|
| "Athena, what time is it?" / "what's the date?" | tells the time / date |
| "open Safari" / "launch Spotify" | opens a macOS app |
| "open YouTube" / "go to github" | opens a website |
| "search for the weather in Paris" | runs a web search |
| "play Bohemian Rhapsody" | plays the first YouTube result |
| "pause" / "next" / "stop music" | controls the Music app |
| "volume up" / "set volume to 40" / "mute" | adjusts system volume |
| "who is Ada Lovelace?" | reads a quick Wikipedia summary |
| "tell me a joke" / "how are you?" | small talk |
| _anything else_ | asks Claude and answers conversationally |
| "goodbye" | shuts down |

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

# 3. Give Athena a brain (optional but recommended)
cp .env.example .env          # then paste your Anthropic API key into .env
export ANTHROPIC_API_KEY="sk-ant-..."
```

The first run will prompt macOS for **Microphone** permission (and, for app/volume
control, **Automation** permission for your terminal) — allow both.

---

## Running

From the directory **above** `athena/` (so the package imports correctly):

```bash
# Voice mode — the real deal (needs a mic)
python -m athena

# Keyboard mode — type commands, no mic needed. Great for testing.
python -m athena --text
```

In voice mode, say **"Athena"**, wait for "Yes?", then speak your command — or
say it all at once: _"Athena, open YouTube."_

---

## How it fits together

```
  microphone ─▶ voice/listener.py ─▶ brain/router.py ─┬─▶ skills/*  (fast, free)
   (Google STT)                                        └─▶ brain/llm.py  (Claude)
                                                              │
  speaker  ◀── voice/speaker.py ◀───────── reply ◀────────────┘
   (pyttsx3, offline)
```

- **`brain/router.py`** tries each skill in order; the first match wins.
- If no skill matches, the command goes to **`brain/llm.py`** (Claude `claude-opus-4-8`).
- Every setting lives in **`config.py`** and is overridable via environment variables.

---

## Extending Athena

Adding a skill is three steps:

1. Create `skills/my_skill.py` with a class that subclasses `Skill`
   (set `triggers`, implement `handle`).
2. Register it in `skills/__init__.py` → `build_skills()`.
3. Order matters — put more specific skills before general ones.

```python
from .base import Skill

class WeatherSkill(Skill):
    name = "weather"
    triggers = ("weather", "forecast", "temperature")

    def handle(self, text, athena):
        return "It's sunny."   # return None to let Claude handle it instead
```

---

## Notes & limits

- **macOS-focused.** App launching, volume and Music control use AppleScript /
  `open`. On Linux/Windows those commands no-op, but voice, web, search,
  Wikipedia and the Claude brain still work.
- **Speech-to-text needs internet** (Google recogniser). Speaking is fully offline.
- `pywhatkit` and `wikipedia` are optional — without them, "play" opens a YouTube
  search and factual lookups fall through to Claude.
