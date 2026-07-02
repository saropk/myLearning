"""System volume control for macOS via AppleScript."""

import re
import subprocess

from .base import Skill


class VolumeSkill(Skill):
    name = "set_volume"
    triggers = ("volume", "mute", "unmute", "louder", "quieter", "turn it up",
                "turn it down")

    expose = True
    description = "Adjust system volume: raise, lower, set to a level, mute or unmute."
    parameters = {
        "action": {"type": "string", "enum": ["up", "down", "set", "mute", "unmute"]},
        "level": {"type": "integer", "description": "Target volume 0–100 (for 'set')."},
    }
    required = ("action",)

    def run(self, athena, action: str = "up", level: int | None = None) -> str:
        if action == "mute":
            self._osascript("set volume with output muted")
            return "Muted."
        if action == "unmute":
            self._osascript("set volume without output muted")
            return "Unmuted."
        if action == "set" and level is not None:
            level = max(0, min(100, int(level)))
            self._osascript(f"set volume output volume {level}")
            return f"Volume set to {level} percent."

        current = self._current_volume()
        new = min(100, current + 15) if action == "up" else max(0, current - 15)
        self._osascript(f"set volume output volume {new}")
        return f"Volume now at {new} percent."

    def parse(self, text: str) -> dict | None:
        lowered = text.lower()
        if "unmute" in lowered:
            return {"action": "unmute"}
        if "mute" in lowered:
            return {"action": "mute"}
        match = re.search(r"(\d{1,3})", lowered)
        if "volume" in lowered and match:
            return {"action": "set", "level": int(match.group(1))}
        if any(w in lowered for w in ("up", "louder", "increase", "turn it up")):
            return {"action": "up"}
        if any(w in lowered for w in ("down", "quieter", "lower", "decrease", "turn it down")):
            return {"action": "down"}
        if "volume" in lowered:
            return {"action": "up"}
        return None

    @staticmethod
    def _current_volume() -> int:
        try:
            out = subprocess.run(
                ["osascript", "-e", "output volume of (get volume settings)"],
                capture_output=True, text=True, check=False,
            )
            return int(out.stdout.strip() or 50)
        except (ValueError, FileNotFoundError):
            return 50

    @staticmethod
    def _osascript(script: str) -> None:
        try:
            subprocess.run(["osascript", "-e", script], check=False)
        except FileNotFoundError:
            print("[volume] osascript not found — volume control is macOS-only.")
