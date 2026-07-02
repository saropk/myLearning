"""Greetings, identity, jokes, thanks — the offline social layer.

Hidden from Claude (expose=False): when the Claude brain is active it handles
chit-chat natively. This skill exists for the offline keyword brain. Exit words
are exported for the assistant, which handles shutdown centrally.
"""

import random
from datetime import datetime

from .base import Skill

JOKES = [
    "Why did the strategist bring a ladder to battle? To reach new heights of tactics.",
    "I would tell you a UDP joke, but you might not get it.",
    "Why do programmers prefer dark mode? Because light attracts bugs.",
    "I asked the owl for wisdom. It just said 'who' — not very strategic.",
    "There are 10 kinds of people: those who understand binary and those who don't.",
]

EXIT_WORDS = (
    "goodbye", "bye", "exit", "quit", "shut down", "shutdown",
    "stop listening", "power off", "go to sleep",
)
GREETINGS = ("hello", "hi", "hey", "good morning", "good afternoon",
             "good evening", "greetings", "yo ")


class SmallTalkSkill(Skill):
    name = "smalltalk"
    triggers = GREETINGS + (
        "how are you", "who are you", "your name", "what can you do",
        "thank you", "thanks", "joke",
    )

    def can_handle(self, text: str) -> bool:
        text = text.lower().strip()
        if text in ("hi", "hey", "hello", "yo"):
            return True
        return super().can_handle(text)

    def run(self, athena, **params) -> str | None:
        # The keyword brain passes the raw text through parse(); recover it here.
        text = params.get("_text", "").lower().strip()
        cfg = athena.config

        if "how are you" in text:
            return "Sharp and ready. What's the strategy today?"
        if "who are you" in text or "your name" in text:
            return (
                f"I'm {cfg.assistant_name}, your assistant — named for the Greek "
                "goddess of wisdom, war and strategy."
            )
        if "what can you do" in text:
            return (
                "I can tell time, check the weather and news, set timers, do math, "
                "open apps and sites, play music, remember things, and answer "
                "questions. Just ask."
            )
        if "thank" in text:
            return "Anytime."
        if "joke" in text:
            return random.choice(JOKES)
        if self._is_greeting(text):
            return f"{self._time_greeting()}, {cfg.owner_name}. How can I help?"
        return None

    def parse(self, text: str) -> dict | None:
        if self.can_handle(text):
            return {"_text": text}
        return None

    def _is_greeting(self, text: str) -> bool:
        return text in ("hi", "hey", "hello", "yo") or any(
            g in f" {text} " for g in GREETINGS
        )

    @staticmethod
    def _time_greeting() -> str:
        hour = datetime.now().hour
        if hour < 12:
            return "Good morning"
        if hour < 18:
            return "Good afternoon"
        return "Good evening"
