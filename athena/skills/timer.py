"""Countdown timers. When the time is up, Athena speaks the reminder.

Uses a background threading.Timer so it doesn't block the main loop. Works in
both voice and text modes (in text mode the reminder is printed).
"""

import re
import threading

from .base import Skill

UNIT_SECONDS = {"second": 1, "sec": 1, "minute": 60, "min": 60, "hour": 3600}


class TimerSkill(Skill):
    name = "set_timer"
    triggers = ("timer", "remind me", "reminder", "alarm", "wake me")

    expose = True
    description = "Set a countdown timer; Athena announces it when the time is up."
    parameters = {
        "seconds": {"type": "integer", "description": "Duration in seconds."},
        "label": {"type": "string", "description": "Optional reminder text."},
    }
    required = ("seconds",)

    def run(self, athena, seconds: int = 0, label: str | None = None) -> str:
        seconds = int(seconds or 0)
        if seconds <= 0:
            return "How long should I set the timer for?"

        message = f"Time's up{f' — {label}' if label else ''}."
        timer = threading.Timer(seconds, lambda: athena.speak(message))
        timer.daemon = True  # don't keep the process alive just for a pending timer
        timer.start()
        return f"Okay, timer set for {self._spoken_duration(seconds)}" + (
            f" to {label}." if label else "."
        )

    def parse(self, text: str) -> dict | None:
        if not self.can_handle(text):
            return None
        total = 0
        for value, unit in re.findall(r"(\d+)\s*(hours?|hrs?|minutes?|mins?|seconds?|secs?)", text.lower()):
            key = unit.rstrip("s")
            key = {"hr": "hour", "hrs": "hour", "min": "minute", "mins": "minute",
                   "sec": "second", "secs": "second"}.get(key, key)
            total += int(value) * UNIT_SECONDS.get(key, 0)
        if total == 0:
            return None
        match = re.search(r"\bto\s+(.+?)(?:\s+in\b|\s+for\b|$)", text.lower())
        label = match.group(1).strip(" .?") if match else None
        return {"seconds": total, "label": label}

    @staticmethod
    def _spoken_duration(seconds: int) -> str:
        if seconds % 3600 == 0:
            n = seconds // 3600
            return f"{n} hour{'s' if n != 1 else ''}"
        if seconds % 60 == 0:
            n = seconds // 60
            return f"{n} minute{'s' if n != 1 else ''}"
        return f"{seconds} seconds"
