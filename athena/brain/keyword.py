"""The offline keyword brain — deterministic routing with no network needed.

Walks skills in priority order; the first one whose `parse()` claims the command
runs it. If a skill parses but then declines (`run()` returns None), routing
continues to the next skill.
"""


class KeywordBrain:
    def __init__(self, skills):
        self.skills = skills

    def respond(self, text: str, athena) -> str:
        text = (text or "").strip()
        if not text:
            return "I didn't catch that. Could you say it again?"

        for skill in self.skills:
            try:
                params = skill.parse(text)
                if params is None:
                    continue
                reply = skill.run(athena, **params)
                if reply is not None:
                    return reply
            except Exception as exc:  # one bad skill shouldn't crash Athena
                print(f"[keyword] skill '{skill.name}' error: {exc}")

        return (
            "I don't have a built-in skill for that, and my Claude brain is "
            "offline. Set ANTHROPIC_API_KEY to answer open-ended questions."
        )
