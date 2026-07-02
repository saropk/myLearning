"""Music: play a song, and control playback of the macOS Music app.

"play <song>" plays the first YouTube result (via pywhatkit if installed,
otherwise opens a YouTube search). Transport controls use AppleScript.
"""

import subprocess
import webbrowser
from urllib.parse import quote_plus

from .base import Skill

PLAY_PHRASES = ("play", "put on", "start playing")
CONTROL_SCRIPT = {
    "pause": 'tell application "Music" to pause',
    "resume": 'tell application "Music" to play',
    "next": 'tell application "Music" to next track',
    "previous": 'tell application "Music" to previous track',
    "stop": 'tell application "Music" to stop',
}
CONTROL_REPLY = {
    "pause": "Paused.", "resume": "Resuming.", "next": "Skipping ahead.",
    "previous": "Going back.", "stop": "Stopped.",
}


class MusicSkill(Skill):
    name = "control_music"
    triggers = PLAY_PHRASES + ("pause", "resume", "next track", "skip",
                               "previous", "stop music", "song")

    expose = True
    description = "Play a song, or control playback (pause, resume, next, previous, stop)."
    parameters = {
        "action": {
            "type": "string",
            "enum": ["play", "pause", "resume", "next", "previous", "stop"],
        },
        "query": {"type": "string", "description": "Song/artist to play (for 'play')."},
    }
    required = ("action",)

    def run(self, athena, action: str = "play", query: str | None = None) -> str:
        if action == "play":
            return self._play((query or "").strip())
        script = CONTROL_SCRIPT.get(action)
        if not script:
            return "I'm not sure how to control that."
        self._osascript(script)
        return CONTROL_REPLY[action]

    def _play(self, song: str) -> str:
        if not song:
            return "What would you like me to play?"
        try:
            import pywhatkit
            pywhatkit.playonyt(song)
            return f"Playing {song}."
        except Exception:
            webbrowser.open(f"https://www.youtube.com/results?search_query={quote_plus(song)}")
            return f"Here are results for {song} on YouTube."

    def parse(self, text: str) -> dict | None:
        lowered = text.lower().strip()
        if "pause" in lowered:
            return {"action": "pause"}
        if "resume" in lowered or "unpause" in lowered:
            return {"action": "resume"}
        if "next" in lowered or "skip" in lowered:
            return {"action": "next"}
        if "previous" in lowered or "go back" in lowered:
            return {"action": "previous"}
        if "stop music" in lowered:
            return {"action": "stop"}
        if any(lowered.startswith(p) for p in PLAY_PHRASES):
            song = self.strip_phrases(lowered, PLAY_PHRASES)
            song = song.replace("on youtube", "").replace("some music", "").strip()
            return {"action": "play", "query": song}
        return None

    @staticmethod
    def _osascript(script: str) -> None:
        try:
            subprocess.run(["osascript", "-e", script], check=False)
        except FileNotFoundError:
            print("[music] osascript not found — playback control is macOS-only.")
