"""Quick factual lookups via Wikipedia.

Handles "who is ...", "what is ...", "tell me about ...". If the `wikipedia`
package isn't installed, or nothing is found, the skill declines (returns None)
so the router falls through to Claude.
"""

from .base import Skill

LOOKUP_PHRASES = (
    "who is", "who was", "what is", "what are", "what was",
    "tell me about", "who's", "what's",
)

try:
    import wikipedia
except ImportError:  # pragma: no cover - optional at runtime
    wikipedia = None


class WikipediaSkill(Skill):
    name = "wikipedia"
    triggers = LOOKUP_PHRASES

    def can_handle(self, text: str) -> bool:
        if wikipedia is None:
            return False  # let Claude handle it instead
        return super().can_handle(text)

    def handle(self, text: str, athena) -> str | None:
        topic = self.strip_phrases(text.lower(), LOOKUP_PHRASES).rstrip("?").strip()
        if not topic:
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
            return None  # not found / offline — defer to Claude
