"""Athena — the orchestrator that ties voice, brain and skills together.

Two run modes:
  * run_voice(): wake-word loop using the microphone (the real assistant).
  * run_text():  keyboard loop, handy for testing without a mic or on a server.
"""

from .config import Config
from .brain.router import Brain
from .skills import build_skills
from .voice.speaker import Speaker


class Athena:
    def __init__(self, text_mode: bool = False, config: Config | None = None):
        self.config = config or Config()
        self.text_mode = text_mode
        self.running = True

        self.speaker = Speaker(self.config.voice_name, self.config.speech_rate)
        self.brain = Brain(build_skills(), llm=self._build_llm())
        self._listener = None  # created lazily, only in voice mode

    # ------------------------------------------------------------------ setup
    def _build_llm(self):
        """Attach the Claude brain if we have a key; otherwise stay rule-based."""
        if not self.config.llm_available:
            print("[athena] No ANTHROPIC_API_KEY — running with built-in skills only.")
            return None
        try:
            from .brain.llm import LLM
            return LLM(self.config.model)
        except Exception as exc:
            print(f"[athena] Could not start Claude brain: {exc}")
            return None

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
        """Route one command and speak the reply."""
        reply = self.brain.respond(text, self)
        self.speak(reply)

    # ------------------------------------------------------------ run: text
    def run_text(self) -> None:
        self.speak(f"{self.config.assistant_name} online. Type a command, or 'exit' to quit.")
        while self.running:
            try:
                text = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not text:
                continue
            self.handle(text)

    # ----------------------------------------------------------- run: voice
    def run_voice(self) -> None:
        wake = self.config.wake_word.capitalize()
        self.speak(
            f"{self.config.assistant_name} online. Say '{wake}' followed by a command."
        )
        while self.running:
            try:
                # Anything said right after the wake word counts as the command.
                trailing = self.listener.wait_for_wake_word()
                command = trailing or self._prompt_for_command()
                if command:
                    self.handle(command)
            except KeyboardInterrupt:
                self.speak("Shutting down. Goodbye.")
                break

    def _prompt_for_command(self) -> str:
        self.speak("Yes?")
        return self.listener.listen_command()
