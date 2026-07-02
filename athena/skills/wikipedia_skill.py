"""Quick factual lookups via Wikipedia — offline keyword brain only.

Hidden from Claude (it answers general-knowledge questions itself). If the
`wikipedia` package isn't installed, this skill simply declines.
"""

from .base import Skill

LOOKUP_PHRASES = ("who is", "who was", "what is", "what are", "what was",
                  "tell me about", "who's", "what's")

try:
    import wikipedia
except ImportError:  # pragma: no cover - optional at runtime
    wikipedia = None


class WikipediaSkill(Skill):
    name = "wikipedia"
    triggers = LOOKUP_PHRASES

    def run(self, athena, topic: str = "") -> str | None:
        if wikipedia is None or not topic.strip():
            return None
        try:
            return wikipedia.summary(topic, sentences=2, auto_suggest=True)
        except wikipedia.DisambiguationError as exc:
            option = exc.options[0] if exc.options else topic
            try:
                return wikipedia.summary(option, sentences=2)
            except Exception:
                return None
        except Exception:
            return None

    def parse(self, text: str) -> dict | None:
        if wikipedia is None or not self.can_handle(text):
            return None
        topic = self.strip_phrases(text.lower(), LOOKUP_PHRASES).rstrip("?").strip()
        return {"topic": topic} if topic else None
