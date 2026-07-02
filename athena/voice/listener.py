"""Speech-to-text: Athena's ears.

Uses the SpeechRecognition library with Google's free web recogniser (accurate,
needs internet). Listening happens in two stages:

  1. wait_for_wake_word() keeps transcribing short clips until it hears "athena".
  2. listen_command() then captures the actual instruction.

Requires a working microphone and PyAudio (see the README for macOS setup).
"""

try:
    import speech_recognition as sr
except ImportError:  # pragma: no cover - optional at runtime
    sr = None


class Listener:
    def __init__(
        self,
        wake_word: str = "athena",
        energy_threshold: int = 300,
        pause_threshold: float = 0.8,
    ):
        if sr is None:
            raise RuntimeError(
                "SpeechRecognition/PyAudio not installed. Install them with "
                "`pip install SpeechRecognition PyAudio` (see README), or run "
                "Athena in keyboard mode with `python -m athena --text`."
            )
        self._sr = sr
        self.wake_word = wake_word.lower()
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = energy_threshold
        self.recognizer.pause_threshold = pause_threshold
        self.mic = sr.Microphone()
        # Learn the room's background noise once so short clips transcribe cleanly.
        with self.mic as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)

    def _transcribe(self, timeout=None, phrase_time_limit=None) -> str:
        """Record one utterance and return its lowercase transcript ("" on failure)."""
        with self.mic as source:
            audio = self.recognizer.listen(
                source, timeout=timeout, phrase_time_limit=phrase_time_limit
            )
        try:
            return self.recognizer.recognize_google(audio).lower()
        except self._sr.UnknownValueError:
            return ""  # heard sound but couldn't make out words
        except self._sr.RequestError as exc:
            print(f"[listener] Speech service unavailable: {exc}")
            return ""

    def wait_for_wake_word(self) -> str:
        """Block until the wake word is heard.

        Returns anything spoken right after it (e.g. "athena what time is it"
        returns "what time is it"), or "" if only the wake word was said.
        """
        while True:
            try:
                text = self._transcribe(phrase_time_limit=4)
            except self._sr.WaitTimeoutError:
                continue
            if self.wake_word in text:
                return text.split(self.wake_word, 1)[1].strip()

    def listen_command(self, timeout: int = 6, phrase_time_limit: int = 10) -> str:
        """Capture a single command after the wake word has fired."""
        try:
            return self._transcribe(timeout=timeout, phrase_time_limit=phrase_time_limit)
        except self._sr.WaitTimeoutError:
            return ""
