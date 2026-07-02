"""Base class shared by every skill.

A skill answers two questions:
  * can_handle(text): "Is this command mine?"
  * handle(text, athena): "Do it, and return what Athena should say."

handle() may return None to decline after the fact (e.g. a lookup skill that
finds nothing), which lets the router fall through to the next skill or Claude.
"""


class Skill:
    name: str = "skill"
    # Words/phrases that mark a command as belonging to this skill.
    triggers: tuple[str, ...] = ()

    def can_handle(self, text: str) -> bool:
        text = text.lower()
        return any(trigger in text for trigger in self.triggers)

    def handle(self, text: str, athena) -> str | None:
        raise NotImplementedError

    @staticmethod
    def strip_phrases(text: str, phrases) -> str:
        """Remove leading command words to isolate the real argument.

        e.g. strip_phrases("play bohemian rhapsody", ["play"]) -> "bohemian rhapsody"
        """
        cleaned = text.lower().strip()
        for phrase in sorted(phrases, key=len, reverse=True):
            if cleaned.startswith(phrase):
                cleaned = cleaned[len(phrase):].strip()
                break
        return cleaned
