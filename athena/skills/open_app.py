"""Launch macOS applications with `open -a`."""

import subprocess

from .base import Skill

OPEN_PHRASES = ("open", "launch", "start")
# Spoken name -> actual macOS application name.
APPS = {
    "safari": "Safari", "chrome": "Google Chrome", "google chrome": "Google Chrome",
    "finder": "Finder", "terminal": "Terminal", "notes": "Notes",
    "calendar": "Calendar", "mail": "Mail", "messages": "Messages",
    "music": "Music", "spotify": "Spotify", "calculator": "Calculator",
    "system settings": "System Settings", "system preferences": "System Settings",
    "vs code": "Visual Studio Code", "visual studio code": "Visual Studio Code",
    "photos": "Photos", "preview": "Preview", "reminders": "Reminders",
    "maps": "Maps", "facetime": "FaceTime", "app store": "App Store",
}


class OpenAppSkill(Skill):
    name = "open_app"
    triggers = OPEN_PHRASES

    expose = True
    description = "Open a macOS application by name (Safari, Notes, Spotify, ...)."
    parameters = {"app": {"type": "string", "description": "Application name."}}
    required = ("app",)

    def run(self, athena, app: str = "") -> str | None:
        app = app.strip()
        if not app:
            return None
        # Accept either a friendly spoken name or a real app name.
        target = APPS.get(app.lower(), app if app in APPS.values() else None)
        if target is None:
            for spoken, real in APPS.items():
                if spoken in app.lower():
                    target = real
                    break
        if target is None:
            return None  # unknown app — let the web skill try instead
        self._run(["open", "-a", target])
        return f"Opening {target}."

    def parse(self, text: str) -> dict | None:
        target = self.strip_phrases(text.lower(), OPEN_PHRASES)
        for spoken in APPS:
            if spoken in target:
                return {"app": spoken}
        return None

    @staticmethod
    def _run(args) -> None:
        try:
            subprocess.run(args, check=False)
        except FileNotFoundError:
            print(f"[open_app] '{args[0]}' not found — app launching is macOS-only.")
