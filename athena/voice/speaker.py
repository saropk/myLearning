"""Text-to-speech: Athena's voice.

Uses pyttsx3, which runs fully offline. On macOS it drives the built-in
NSSpeechSynthesizer, so voices like "Samantha" or "Alex" are available with no
setup. If pyttsx3 isn't installed, Athena still "speaks" by printing to the
screen so the rest of the program keeps working.
"""

try:
    import pyttsx3
except ImportError:  # pragma: no cover - optional at runtime
    pyttsx3 = None


class Speaker:
    def __init__(self, voice_name: str | None = None, rate: int = 180):
        self.engine = None
        if pyttsx3 is None:
            print("[speaker] pyttsx3 not installed — falling back to text output.")
            return
        try:
            self.engine = pyttsx3.init()
            self.engine.setProperty("rate", rate)
            if voice_name:
                self._select_voice(voice_name)
        except Exception as exc:  # engine can fail if no audio backend exists
            print(f"[speaker] Could not start the speech engine: {exc}")
            self.engine = None

    def _select_voice(self, voice_name: str) -> None:
        wanted = voice_name.lower()
        for voice in self.engine.getProperty("voices"):
            if wanted in voice.name.lower() or wanted in voice.id.lower():
                self.engine.setProperty("voice", voice.id)
                return

    def say(self, text: str) -> None:
        """Speak the text aloud (and always echo it to the console)."""
        if not text:
            return
        print(f"Athena: {text}")
        if self.engine is None:
            return
        try:
            self.engine.say(text)
            self.engine.runAndWait()
        except Exception as exc:  # pragma: no cover - hardware/driver hiccups
            print(f"[speaker] Speech error: {exc}")
