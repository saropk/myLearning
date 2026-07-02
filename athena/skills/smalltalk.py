"""Greetings, identity, jokes and goodbye.

The goodbye branch flips athena.running to False so the main loop exits cleanly.
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

EXIT_WORDS = ("goodbye", "bye", "exit", "quit", "shut down", "shutdown", "stop listening", "power off")
GREETINGS = ("hello", "hi ", "hey", "good morning", "good afternoon", "good evening", "greetings")


class SmallTalkSkill(Skill):
    name = "smalltalk"
    triggers = EXIT_WORDS + GREETINGS + (
        "how are you", "who are you", "your name", "what can you do",
        "thank you", "thanks", "tell me a joke", "joke",
    )

    def can_handle(self, text: str) -> bool:
        text = text.lower().strip()
        if text in ("hi", "hey", "hello"):
            return True
        return super().can_handle(text)

    def handle(self, text: str, athena) -> str | None:
        text = text.lower().strip()
        cfg = athena.config

        if any(word in text for word in EXIT_WORDS):
            athena.running = False
            return f"Goodbye, {cfg.owner_name}. Call my name whenever you need me."

        if any(g in f" {text} " for g in GREETINGS) or text in ("hi", "hey", "hello"):
            return f"{self._time_greeting()}, {cfg.owner_name}. How can I help?"

        if "how are you" in text:
            return "Sharp and ready. What's the strategy today?"

        if "who are you" in text or "your name" in text:
            return (
                f"I'm {cfg.assistant_name}, your assistant — named for the Greek "
                "goddess of wisdom, war and strategy."
            )

        if "what can you do" in text:
            return (
                "I can tell the time, open apps and websites, play music, look "
                "things up, and answer open-ended questions. Just ask."
            )

        if "thank" in text:
            return "Anytime."

        if "joke" in text:
            return random.choice(JOKES)

        return None

    @staticmethod
    def _time_greeting() -> str:
        hour = datetime.now().hour
        if hour < 12:
            return "Good morning"
        if hour < 18:
            return "Good afternoon"
        return "Good evening"
