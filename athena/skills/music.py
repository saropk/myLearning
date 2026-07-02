"""Music: play a song and control playback.

"play <song>"  -> plays the first YouTube result (via pywhatkit if installed,
                  otherwise opens a YouTube search page).
"pause" / "resume" / "next" / "previous" / "stop music"
               -> control the macOS Music app via AppleScript.
"""

import subprocess
import webbrowser
from urllib.parse import quote_plus

from .base import Skill

PLAY_PHRASES = ("play", "put on", "start playing")
CONTROL = {
    "pause": 'tell application "Music" to pause',
    "resume": 'tell application "Music" to play',
    "unpause": 'tell application "Music" to play',
    "next": 'tell application "Music" to next track',
    "skip": 'tell application "Music" to next track',
    "previous": 'tell application "Music" to previous track',
    "stop music": 'tell application "Music" to stop',
}


class MusicSkill(Skill):
    name = "music"
    triggers = PLAY_PHRASES + tuple(CONTROL) + ("song", "music")

    def handle(self, text: str, athena) -> str | None:
        lowered = text.lower().strip()

        # Playback controls first (so "next" isn't mistaken for a song title).
        for keyword, script in CONTROL.items():
            if keyword in lowered:
                self._osascript(script)
                return {
                    "pause": "Paused.",
                    "resume": "Resuming.",
                    "unpause": "Resuming.",
                    "next": "Skipping ahead.",
                    "skip": "Skipping ahead.",
                    "previous": "Going back.",
                    "stop music": "Stopped.",
                }[keyword]

        # "play <something>"
        if any(lowered.startswith(p) for p in PLAY_PHRASES):
            song = self.strip_phrases(lowered, PLAY_PHRASES)
            song = song.replace("on youtube", "").replace("some music", "").strip()
            if not song:
                return "What would you like me to play?"
            return self._play(song)

        return None

    def _play(self, song: str) -> str:
        try:
            import pywhatkit  # optional; plays the first YouTube hit directly
            pywhatkit.playonyt(song)
            return f"Playing {song}."
        except Exception:
            # No pywhatkit (or it failed) — open a YouTube search instead.
            webbrowser.open(
                f"https://www.youtube.com/results?search_query={quote_plus(song)}"
            )
            return f"Here are results for {song} on YouTube."

    @staticmethod
    def _osascript(script: str) -> None:
        try:
            subprocess.run(["osascript", "-e", script], check=False)
        except FileNotFoundError:
            print("[music] osascript not found — playback control is macOS-only.")
