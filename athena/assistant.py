"""Athena — the orchestrator tying voice, brain and skills together.

Run modes:
  * run_voice(): wake word -> command -> a short conversation window for
    follow-ups (no need to repeat the wake word) -> back to sleep.
  * run_text():  keyboard loop for testing without a mic or on a server.
"""

import re

from .config import Config
from .brain import build_brain
from .skills import build_skills
from .skills.smalltalk import EXIT_WORDS
from .voice.speaker import Speaker


class Athena:
    def __init__(self, text_mode: bool = False, config: Config | None = None):
        self.config = config or Config()
        self.text_mode = text_mode
        self.running = True

        self.speaker = Speaker(self.config.voice_name, self.config.speech_rate)
        self.brain = build_brain(self.config, build_skills())
        self._listener = None  # created lazily, only in voice mode

    @property
    def listener(self):
        if self._listener is None:
            from .voice.listener import Listener
            self._listener = Listener(
                wake_word=self.config.wake_word,
                energy_threshold=self.config.energy_threshold,
                pause_threshold=self.config.pause_threshold,
            )
        return self._listener

    # ------------------------------------------------------------------ core
    def speak(self, text: str) -> None:
        self.speaker.say(text)

    def handle(self, text: str) -> None:
        """Route one command and speak the reply. Exit words are handled here so
        they work identically under either brain."""
        if self._is_exit(text):
            self.running = False
            self.speak(f"Goodbye, {self.config.owner_name}. Call my name whenever you need me.")
            return
        self.speak(self.brain.respond(text, self))

    @staticmethod
    def _is_exit(text: str) -> bool:
        lowered = (text or "").lower().strip()
        return any(re.search(rf"\b{re.escape(w)}\b", lowered) for w in EXIT_WORDS)

    # ------------------------------------------------------------ run: text
    def run_text(self) -> None:
        self.speak(f"{self.config.assistant_name} online. Type a command, or 'exit' to quit.")
        while self.running:
            try:
                text = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if text:
                self.handle(text)

    # ----------------------------------------------------------- run: voice
    def run_voice(self) -> None:
        wake = self.config.wake_word.capitalize()
        self.speak(f"{self.config.assistant_name} online. Say '{wake}' to wake me.")
        while self.running:
            try:
                trailing = self.listener.wait_for_wake_word()
                command = trailing or self._ask()
                # Conversation window: keep taking follow-ups until the user
                # goes quiet, then drop back to waiting for the wake word.
                while self.running and command:
                    self.handle(command)
                    if not self.running:
                        break
                    command = self.listener.listen_command(
                        timeout=self.config.follow_up_timeout
                    )
            except KeyboardInterrupt:
                self.speak("Shutting down. Goodbye.")
                break

    def _ask(self) -> str:
        self.speak("Yes?")
        return self.listener.listen_command()
