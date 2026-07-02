"""System control for macOS: open apps and adjust the volume.

Apps are launched with `open -a`, volume is set with AppleScript. These are the
macOS-specific bits — on another OS these commands simply won't do anything.
"""

import re
import subprocess

from .base import Skill

OPEN_PHRASES = ("open", "launch", "start")
# Spoken name -> actual macOS application name.
APPS = {
    "safari": "Safari",
    "chrome": "Google Chrome",
    "google chrome": "Google Chrome",
    "finder": "Finder",
    "terminal": "Terminal",
    "notes": "Notes",
    "calendar": "Calendar",
    "mail": "Mail",
    "messages": "Messages",
    "music": "Music",
    "spotify": "Spotify",
    "calculator": "Calculator",
    "system settings": "System Settings",
    "system preferences": "System Settings",
    "vs code": "Visual Studio Code",
    "visual studio code": "Visual Studio Code",
    "photos": "Photos",
    "preview": "Preview",
    "reminders": "Reminders",
}


class SystemSkill(Skill):
    name = "system"
    triggers = ("volume", "mute", "unmute") + OPEN_PHRASES

    def handle(self, text: str, athena) -> str | None:
        lowered = text.lower().strip()

        if "volume" in lowered or "mute" in lowered:
            return self._handle_volume(lowered)

        # "open <app>"
        target = self.strip_phrases(lowered, OPEN_PHRASES)
        for spoken, app in APPS.items():
            if spoken in target:
                self._run(["open", "-a", app])
                return f"Opening {app}."

        # Not a known app — let another skill (e.g. web) try instead.
        return None

    def _handle_volume(self, text: str) -> str:
        if "mute" in text and "unmute" not in text:
            self._osascript("set volume with output muted")
            return "Muted."
        if "unmute" in text:
            self._osascript("set volume without output muted")
            return "Unmuted."

        match = re.search(r"(\d{1,3})", text)
        if match:
            level = max(0, min(100, int(match.group(1))))
            self._osascript(f"set volume output volume {level}")
            return f"Volume set to {level} percent."

        current = self._current_volume()
        if "up" in text or "increase" in text or "louder" in text:
            level = min(100, current + 15)
        elif "down" in text or "decrease" in text or "lower" in text or "quieter" in text:
            level = max(0, current - 15)
        else:
            return f"The volume is at {current} percent."
        self._osascript(f"set volume output volume {level}")
        return f"Volume now at {level} percent."

    def _current_volume(self) -> int:
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
        SystemSkill._run(["osascript", "-e", script])

    @staticmethod
    def _run(args) -> None:
        try:
            subprocess.run(args, check=False)
        except FileNotFoundError:
            print(f"[system] '{args[0]}' not found — this feature is macOS-only.")
